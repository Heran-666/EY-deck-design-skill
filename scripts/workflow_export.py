#!/usr/bin/env python3
"""Prepare and validate a filesystem-isolated Stage 2 export workspace."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from workflow_io import read_json, sha256, text_sha256, write_json
from workflow_paths import export_root
from workflow_runtime import stage2_runtime_path, validate_stage2_runtime


EXPORT_SCHEMA = "ey-deck.confirmed-svg-export.v3"
TERMINAL_SCHEMA = "ey-deck.confirmed-svg-terminal-result.v1"
TERMINAL_VALIDATOR = Path(__file__).resolve().parent / "validate_terminal_result.py"
EXPORT_RUNNER = Path(__file__).resolve().parent / "run_confirmed_export.py"


def validate_output_filename(value: str) -> str:
    filename = value.strip()
    if not filename or Path(filename).name != filename:
        raise ValueError("Output filename must be one plain filename, not a path")
    if Path(filename).suffix.lower() != ".pptx":
        raise ValueError("Output filename must end in .pptx")
    if filename in {".", ".."} or any(char in filename for char in "\0/\\"):
        raise ValueError("Output filename contains an unsafe path character")
    return filename


def export_fingerprint(records: list[dict[str, str]], output_filename: str) -> str:
    payload = {
        "schema_version": EXPORT_SCHEMA,
        "output_filename": validate_output_filename(output_filename),
        "slides": records,
    }
    return text_sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _project_slug(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return value[:48] or "deck"


def canonical_records(project_dir: Path, slide_ids: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for slide_id in slide_ids:
        source = project_dir / "svg_output" / f"{slide_id}.svg"
        if not source.is_file():
            raise ValueError(f"canonical SVG is missing: {source}")
        records.append({"slide_id": slide_id, "sha256": sha256(source)})
    return records


def bound_stage2_runtime(project_dir: Path) -> dict:
    """Read the doctor-bound runtime without probing or mutating project state."""
    path = stage2_runtime_path(project_dir)
    if not path.is_file():
        raise ValueError("Stage 2 runtime is unbound; run bootstrap or doctor")
    runtime = read_json(path)
    errors = validate_stage2_runtime(runtime, reprobe=False)
    if errors:
        raise ValueError("; ".join(errors))
    return runtime


def export_plan(project_dir: Path, slide_ids: list[str], output_filename: str) -> dict:
    filename = validate_output_filename(output_filename)
    records = canonical_records(project_dir, slide_ids)
    runtime = bound_stage2_runtime(project_dir)
    fingerprint = export_fingerprint(records, filename)
    workspace = export_root(project_dir) / f"{_project_slug(project_dir.name)}-{fingerprint[:16]}"
    staged = [
        {
            "slide_id": record["slide_id"],
            "svg_path": str((workspace / "svg_input" / f"{record['slide_id']}.svg").resolve()),
            "sha256": record["sha256"],
        }
        for record in records
    ]
    return {
        "workspace": workspace,
        "manifest_path": workspace / "export-manifest.json",
        "output_path": workspace / "output" / filename,
        "validator_path": workspace / "validate-terminal-result.py",
        "runtime": runtime,
        "fingerprint": fingerprint,
        "filename": filename,
        "records": records,
        "staged": staged,
    }


def prepared_payload(plan: dict, manifest_sha256: str) -> dict:
    manifest_path = Path(plan["manifest_path"])
    runtime = plan["runtime"]
    return {
        "workspace": str(Path(plan["workspace"]).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": manifest_sha256,
        "svg_set_fingerprint": plan["fingerprint"],
        "output_path": str(Path(plan["output_path"]).resolve()),
        "runner_command": [
            runtime["bundled_python"],
            str(EXPORT_RUNNER.resolve()),
            "--manifest",
            str(manifest_path.resolve()),
            "--manifest-sha256",
            manifest_sha256,
        ],
    }


def prepare_export_workspace(
    project_dir: Path,
    slide_ids: list[str],
    output_filename: str,
) -> dict:
    plan = export_plan(project_dir, slide_ids, output_filename)
    filename = plan["filename"]
    records = plan["records"]
    runtime = plan["runtime"]
    fingerprint = plan["fingerprint"]
    workspace = Path(plan["workspace"])
    input_dir = workspace / "svg_input"
    output_dir = workspace / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    staged: list[dict[str, str]] = []
    for record in records:
        slide_id = record["slide_id"]
        source = project_dir / "svg_output" / f"{slide_id}.svg"
        target = input_dir / f"{slide_id}.svg"
        if not target.is_file() or sha256(target) != record["sha256"]:
            shutil.copy2(source, target)
        staged.append({
            "slide_id": slide_id,
            "svg_path": str(target.resolve()),
            "sha256": record["sha256"],
        })

    manifest_path = Path(plan["manifest_path"])
    output_path = Path(plan["output_path"])
    validator_path = Path(plan["validator_path"])
    if not validator_path.is_file() or sha256(validator_path) != sha256(TERMINAL_VALIDATOR):
        shutil.copy2(TERMINAL_VALIDATOR, validator_path)
    runner_sha256 = sha256(EXPORT_RUNNER)
    manifest = {
        "schema_version": EXPORT_SCHEMA,
        "svg_set_fingerprint": fingerprint,
        "ordered_slides": staged,
        "output_filename": filename,
        "required_output_path": str(output_path.resolve()),
        "runtime_bindings": runtime,
        "exporter_binding": {
            "schema_version": "ey-deck.confirmed-export-runner.v1",
            "runner_path": str(EXPORT_RUNNER.resolve()),
            "runner_sha256": runner_sha256,
        },
        "terminal_result_contract": {
            "schema_version": TERMINAL_SCHEMA,
            "validator_path": str(validator_path.resolve()),
            "validator_sha256": sha256(validator_path),
        },
    }
    write_json(manifest_path, manifest)
    return prepared_payload(plan, sha256(manifest_path))


def inspect_export_workspace(
    project_dir: Path,
    slide_ids: list[str],
    output_filename: str,
) -> tuple[dict | None, list[str]]:
    try:
        plan = export_plan(project_dir, slide_ids, output_filename)
    except (OSError, ValueError) as exc:
        return None, [str(exc)]
    errors: list[str] = []
    manifest_path = Path(plan["manifest_path"])
    if not manifest_path.is_file():
        return None, ["export workspace is not prepared"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"invalid export manifest: {exc}"]
    if manifest.get("schema_version") != EXPORT_SCHEMA:
        errors.append("export manifest has the wrong schema version")
    if manifest.get("svg_set_fingerprint") != plan["fingerprint"]:
        errors.append("export manifest fingerprint is stale")
    if manifest.get("ordered_slides") != plan["staged"]:
        errors.append("export manifest ordered slides are stale")
    if manifest.get("required_output_path") != str(Path(plan["output_path"]).resolve()):
        errors.append("export manifest output path is stale")
    runtime = manifest.get("runtime_bindings")
    if not isinstance(runtime, dict) or runtime.get("runtime_fingerprint") != plan["runtime"].get("runtime_fingerprint"):
        errors.append("export manifest runtime binding is missing or stale")
    exporter = manifest.get("exporter_binding")
    if (
        not isinstance(exporter, dict)
        or exporter.get("schema_version") != "ey-deck.confirmed-export-runner.v1"
        or exporter.get("runner_path") != str(EXPORT_RUNNER.resolve())
        or exporter.get("runner_sha256") != sha256(EXPORT_RUNNER)
    ):
        errors.append("EY confirmed-export runner binding is missing or stale")
    terminal = manifest.get("terminal_result_contract")
    terminal_fields = terminal if isinstance(terminal, dict) else {}
    validator = Path(str(terminal_fields.get("validator_path", "")))
    if (
        not isinstance(terminal, dict)
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or not validator.is_file()
        or terminal.get("validator_sha256") != sha256(validator)
    ):
        errors.append("export terminal-result validator is missing or stale")
    for item in manifest.get("ordered_slides", []):
        path = Path(str(item.get("svg_path", "")))
        if not path.is_file() or item.get("sha256") != sha256(path):
            errors.append(f"staged SVG is missing or stale: {item.get('slide_id', 'unknown')}")
    prepared = prepared_payload(plan, sha256(manifest_path))
    return (prepared if not errors else None), errors
