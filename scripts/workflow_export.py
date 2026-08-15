#!/usr/bin/env python3
"""Prepare and validate a filesystem-isolated Stage 2 export workspace."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from framework_lib import page_entries
from workflow_io import read_json, sha256, text_sha256, write_json
from workflow_paths import export_preparation_path, export_root
from workflow_runtime import stage2_runtime_path, validate_stage2_runtime
from workflow_templates import (
    STRUCTURED_EXPORT_SCHEMA,
    load_template_profile,
    page_template_binding,
    template_candidate_errors,
)


EXPORT_SCHEMA = "ey-deck.confirmed-svg-export.v4"
TERMINAL_SCHEMA = "ey-deck.confirmed-svg-terminal-result.v1"
TERMINAL_VALIDATOR = Path(__file__).resolve().parent / "validate_terminal_result.py"
EXPORT_RUNNER = Path(__file__).resolve().parent / "run_confirmed_export.py"
FIXED_ENDING_SLIDE_ID = "EY-END"


def validate_output_filename(value: str) -> str:
    filename = value.strip()
    if not filename or Path(filename).name != filename:
        raise ValueError("Output filename must be one plain filename, not a path")
    if Path(filename).suffix.lower() != ".pptx":
        raise ValueError("Output filename must end in .pptx")
    if filename in {".", ".."} or any(char in filename for char in "\0/\\"):
        raise ValueError("Output filename contains an unsafe path character")
    return filename


def export_fingerprint(records: list[dict[str, object]], output_filename: str) -> str:
    payload = {
        "schema_version": EXPORT_SCHEMA,
        "output_filename": validate_output_filename(output_filename),
        "slides": records,
    }
    return text_sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _project_slug(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return value[:48] or "deck"


def canonical_records(project_dir: Path, slide_ids: list[str]) -> list[dict[str, object]]:
    framework_path = project_dir / "framework.md"
    if not framework_path.is_file():
        raise ValueError("framework.md is missing")
    pages = {
        page.slide_id: page
        for page in page_entries(framework_path.read_text(encoding="utf-8"))
    }
    records: list[dict[str, object]] = []
    if FIXED_ENDING_SLIDE_ID in slide_ids:
        raise ValueError(f"{FIXED_ENDING_SLIDE_ID} is reserved for the bundled fixed ending")
    for slide_id in slide_ids:
        source = project_dir / "svg_output" / f"{slide_id}.svg"
        if not source.is_file():
            raise ValueError(f"canonical SVG is missing: {source}")
        page = pages.get(slide_id)
        if page is None:
            raise ValueError(f"framework page is missing: {slide_id}")
        page_type = page.fields.get("Page type", "")
        binding = page_template_binding(page_type)
        if binding is not None:
            problems = template_candidate_errors(source, binding)
            if problems:
                raise ValueError(f"{slide_id} template contract failed: " + "; ".join(problems))
        records.append({
            "slide_id": slide_id,
            "sha256": sha256(source),
            "page_type": page_type,
            "template_binding": binding,
            "asset_role": "storyline",
        })
    ending_binding = page_template_binding("Ending")
    if not isinstance(ending_binding, dict):
        raise ValueError("bundled fixed ending has no structured template binding")
    ending_source = Path(str(ending_binding["prototype_path"]))
    problems = template_candidate_errors(ending_source, ending_binding)
    if problems:
        raise ValueError("bundled fixed ending template contract failed: " + "; ".join(problems))
    records.append({
        "slide_id": FIXED_ENDING_SLIDE_ID,
        "sha256": sha256(ending_source),
        "page_type": "Ending",
        "template_binding": ending_binding,
        "asset_role": "fixed-ending",
    })
    return records


def record_source_path(project_dir: Path, record: dict[str, object]) -> Path:
    if record.get("asset_role") == "fixed-ending":
        binding = record.get("template_binding")
        if not isinstance(binding, dict):
            raise ValueError("bundled fixed ending has no template binding")
        source = Path(str(binding.get("prototype_path", ""))).expanduser().resolve()
    else:
        source = project_dir / "svg_output" / f"{record['slide_id']}.svg"
    if not source.is_file() or sha256(source) != record.get("sha256"):
        raise ValueError(f"record source is missing or stale: {record.get('slide_id')}")
    return source


def structured_template_plan(records: list[dict[str, object]]) -> dict | None:
    if any(record.get("template_binding") is None for record in records):
        return None
    profile = load_template_profile()
    pages = []
    for index, record in enumerate(records, start=1):
        binding = record["template_binding"]
        assert isinstance(binding, dict)
        pages.append({
            "page": f"P{index:02d}",
            "slide_id": record["slide_id"],
            "layout_key": binding["layout_key"],
            "prototype": Path(str(binding["prototype_path"])).name,
            "prototype_sha256": binding["prototype_sha256"],
        })
    return {
        "schema_version": STRUCTURED_EXPORT_SCHEMA,
        "profile_id": profile["profile_id"],
        "profile_fingerprint": profile["profile_fingerprint"],
        "profile_manifest_sha256": profile["manifest_sha256"],
        "template_adherence": profile["template_adherence"],
        "template_reuse_scope": profile["template_reuse_scope"],
        "masters": profile["masters"],
        "layouts": {
            key: {
                "name": value["name"],
                "master": value["master"],
                "prototype": Path(str(value["prototype_path"])).name,
                "prototype_sha256": value["prototype_sha256"],
                "structure_contract_sha256": value["structure_contract"]["contract_sha256"],
            }
            for key, value in sorted(profile["layouts"].items())
        },
        "pages": pages,
    }


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
    template_plan = structured_template_plan(records)
    fingerprint = export_fingerprint(records, filename)
    workspace = export_root(project_dir) / f"{_project_slug(project_dir.name)}-{fingerprint[:16]}"
    staged = [
        {
            "slide_id": record["slide_id"],
            "svg_path": str((workspace / "svg_input" / f"{record['slide_id']}.svg").resolve()),
            "sha256": record["sha256"],
            "asset_role": record["asset_role"],
            "template_layout_key": (
                record["template_binding"]["layout_key"]
                if isinstance(record.get("template_binding"), dict)
                else None
            ),
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
        "structured_template": template_plan,
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

    staged: list[dict[str, object]] = []
    for record in records:
        slide_id = record["slide_id"]
        source = record_source_path(project_dir, record)
        target = input_dir / f"{slide_id}.svg"
        if not target.is_file() or sha256(target) != record["sha256"]:
            shutil.copy2(source, target)
        staged.append({
            "slide_id": slide_id,
            "svg_path": str(target.resolve()),
            "sha256": record["sha256"],
            "asset_role": record["asset_role"],
            "template_layout_key": (
                record["template_binding"]["layout_key"]
                if isinstance(record.get("template_binding"), dict)
                else None
            ),
        })

    template_bundle: dict[str, object] | None = None
    template_plan = plan.get("structured_template")
    if isinstance(template_plan, dict):
        template_dir = workspace / "template_input"
        template_dir.mkdir(parents=True, exist_ok=True)
        profile = load_template_profile()
        staged_templates: list[dict[str, str]] = []
        for layout_key, layout in sorted(profile["layouts"].items()):
            source = Path(str(layout["prototype_path"]))
            target = template_dir / source.name
            if not target.is_file() or sha256(target) != layout["prototype_sha256"]:
                shutil.copy2(source, target)
            staged_templates.append({
                "layout_key": layout_key,
                "path": str(target.resolve()),
                "sha256": layout["prototype_sha256"],
            })
        structure_manifest = {
            **template_plan,
            "templates": staged_templates,
        }
        structure_manifest_path = template_dir / "structured-template.json"
        write_json(structure_manifest_path, structure_manifest)
        template_bundle = {
            "schema_version": STRUCTURED_EXPORT_SCHEMA,
            "structure_manifest_path": str(structure_manifest_path.resolve()),
            "structure_manifest_sha256": sha256(structure_manifest_path),
            "profile_fingerprint": template_plan["profile_fingerprint"],
        }

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
        "pptx_structure": "structured" if template_bundle else "flat",
        "template_bundle": template_bundle,
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
    prepared = prepared_payload(plan, sha256(manifest_path))
    write_json(export_preparation_path(project_dir), prepared)
    return prepared


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
    expected_mode = "structured" if isinstance(plan.get("structured_template"), dict) else "flat"
    if manifest.get("pptx_structure") != expected_mode:
        errors.append("export manifest PPTX structure mode is stale")
    template_bundle = manifest.get("template_bundle")
    if expected_mode == "structured":
        bundle = template_bundle if isinstance(template_bundle, dict) else {}
        structure_manifest = Path(str(bundle.get("structure_manifest_path", "")))
        if (
            bundle.get("schema_version") != STRUCTURED_EXPORT_SCHEMA
            or not structure_manifest.is_file()
            or bundle.get("structure_manifest_sha256") != sha256(structure_manifest)
            or bundle.get("profile_fingerprint")
            != plan["structured_template"]["profile_fingerprint"]
        ):
            errors.append("structured template bundle is missing or stale")
    elif template_bundle is not None:
        errors.append("flat export manifest must not bind a structured template bundle")
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
        errors.append("Embedded PPT Master Stage 2 runner binding is missing or stale")
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
