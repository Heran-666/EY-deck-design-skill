#!/usr/bin/env python3
"""Run EY's bundled confirmed-SVG export fast path and emit one terminal JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


RUNTIME = Path(__file__).resolve().parent / "pptx_export_runtime"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_detail(result: subprocess.CompletedProcess[str]) -> str:
    raw = (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
    return " ".join(raw.split())[-1200:]


def run_step(python: str, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [python, str(RUNTIME / script), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def blocked(
    *,
    stage: str,
    reason: str,
    repair_scope: str,
    slide_ids: list[str],
    resume_from: str,
) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "route": "confirmed-svg-export",
        "stage": stage,
        "slide_ids": slide_ids,
        "reason": reason,
        "repair_scope": repair_scope,
        "resume_from": resume_from,
    }


def affected_slide_ids(project: Path, fallback: list[str]) -> list[str]:
    private_manifest = project / "confirmed-svg-export.json"
    report_path = project / "validation" / "svg_quality_report.json"
    try:
        private = json.loads(private_manifest.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    mapping = {
        item.get("page"): item.get("source_slide_id")
        for item in private.get("page_order", [])
        if isinstance(item, dict)
    }
    failed_pages = {
        Path(str(item.get("file", ""))).stem
        for item in report.get("files", [])
        if isinstance(item, dict) and item.get("errors")
    }
    affected = [
        item.get("source_slide_id")
        for item in private.get("page_order", [])
        if isinstance(item, dict) and item.get("page") in failed_pages
    ]
    return [str(item) for item in affected if item in fallback] or fallback


def quality_failure_is_environment(project: Path) -> bool:
    """Distinguish missing validators from source-SVG compatibility failures."""
    report_path = project / "validation" / "svg_quality_report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    blocking = report.get("categories", {}).get("blocking", {}).get("issues", [])
    messages = [
        str(item.get("message", ""))
        for item in blocking
        if isinstance(item, dict) and str(item.get("message", "")).strip()
    ]
    if not messages:
        return False
    environment_markers = (
        "Unable to import",
        "validator could not be imported",
        "validation is unavailable",
        "cannot verify this SVG",
    )
    return all(any(marker in message for marker in environment_markers) for message in messages)


def topology_blocked_slide_ids(project: Path, fallback: list[str]) -> list[str]:
    """Return source Slide IDs from the isolated topology receipt."""
    receipt = project / "validation" / "text_frame_topology.json"
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    blocked = payload.get("blocked_slide_ids")
    if not isinstance(blocked, list):
        return fallback
    selected = [str(item) for item in blocked if str(item) in fallback]
    return selected or fallback


def validate_terminal(
    python: str,
    manifest_path: Path,
    manifest: dict,
    result: dict[str, object],
) -> dict[str, object]:
    contract = manifest.get("terminal_result_contract", {})
    validator = Path(str(contract.get("validator_path", ""))).expanduser().resolve()
    if not validator.is_file() or contract.get("validator_sha256") != sha256(validator):
        return blocked(
            stage="terminal-validation",
            reason="The manifest-bound terminal validator is missing or stale.",
            repair_scope="environment",
            slide_ids=[str(item["slide_id"]) for item in manifest["ordered_slides"]],
            resume_from="Rebuild the EY export workspace and retry the deterministic export runner.",
        )
    validation = subprocess.run(
        [
            python,
            str(validator),
            "--manifest",
            str(manifest_path),
            "--result-json",
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if validation.returncode == 0:
        try:
            payload = json.loads(validation.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            pass
        else:
            if isinstance(payload, dict):
                return payload
    return blocked(
        stage="terminal-validation",
        reason="Terminal result validation failed: " + compact_detail(validation),
        repair_scope="environment",
        slide_ids=[str(item["slide_id"]) for item in manifest["ordered_slides"]],
        resume_from="Rebuild the EY export workspace and retry the deterministic export runner.",
    )


def execute(manifest_path: Path, expected_manifest_sha256: str) -> dict[str, object]:
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.is_file() or sha256(manifest_path) != expected_manifest_sha256:
        raise ValueError("export manifest is missing or does not match the handoff hash")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "ey-deck.confirmed-svg-export.v4":
        raise ValueError("export manifest has an unsupported schema version")
    ordered = manifest.get("ordered_slides")
    if not isinstance(ordered, list) or not ordered:
        raise ValueError("export manifest has no ordered slides")
    slide_ids = [str(item["slide_id"]) for item in ordered]
    fixed_ending_indexes = [
        index
        for index, item in enumerate(ordered, start=1)
        if item.get("asset_role") == "fixed-ending"
    ]
    if fixed_ending_indexes != [len(ordered)]:
        raise ValueError("export manifest must contain exactly one fixed ending as the last slide")
    workspace = manifest_path.parent.resolve()
    python = str(manifest.get("runtime_bindings", {}).get("bundled_python", ""))
    if not Path(python).is_file():
        return blocked(
            stage="export",
            reason="The hash-bound bundled Python is unavailable.",
            repair_scope="environment",
            slide_ids=slide_ids,
            resume_from="Repair the bound runtime and retry the deterministic export runner.",
        )
    svg_paths: list[str] = []
    for item in ordered:
        path = Path(str(item.get("svg_path", ""))).expanduser().resolve()
        try:
            path.relative_to(workspace)
        except ValueError as exc:
            raise ValueError(f"staged SVG escapes the export workspace: {path}") from exc
        if not path.is_file() or item.get("sha256") != sha256(path):
            raise ValueError(f"staged SVG is missing or stale: {item.get('slide_id')}")
        svg_paths.append(str(path))

    prepare_args: list[str] = []
    structure_mode = manifest.get("pptx_structure")
    if structure_mode == "structured":
        bundle = manifest.get("template_bundle")
        if not isinstance(bundle, dict):
            raise ValueError("structured export has no template bundle")
        structure_manifest = Path(
            str(bundle.get("structure_manifest_path", ""))
        ).expanduser().resolve()
        try:
            structure_manifest.relative_to(workspace)
        except ValueError as exc:
            raise ValueError("structured template manifest escapes the export workspace") from exc
        if (
            not structure_manifest.is_file()
            or bundle.get("structure_manifest_sha256") != sha256(structure_manifest)
        ):
            raise ValueError("structured template manifest is missing or stale")
        prepare_args = ["--structure-manifest", str(structure_manifest)]
    elif structure_mode != "flat":
        raise ValueError("export manifest has an unsupported PPTX structure mode")

    attempts = workspace / "attempts"
    attempts.mkdir(exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="confirmed-", dir=attempts)).resolve()
    prepared = run_step(
        python,
        "prepare_confirmed_svg_export.py",
        "--project-dir",
        str(project),
        *prepare_args,
        *svg_paths,
    )
    if prepared.returncode != 0:
        typography_failure = prepared.returncode == 3
        result = blocked(
            stage="typography" if typography_failure else "svg-normalization",
            reason=compact_detail(prepared),
            repair_scope="source-svg",
            slide_ids=slide_ids,
            resume_from=(
                "Replace or reopen the affected pages with typography-scale-compliant SVGs, then retry export."
                if typography_failure
                else "Replace or reopen the affected confirmed SVG pages, then retry export."
            ),
        )
        return validate_terminal(python, manifest_path, manifest, result)

    guard_args = (
        "--project-dir", str(project), "--expected-python", python
    )
    guard = run_step(python, "assert_confirmed_export_runtime.py", *guard_args)
    if guard.returncode != 0:
        result = blocked(
            stage="export",
            reason=compact_detail(guard),
            repair_scope="environment",
            slide_ids=slide_ids,
            resume_from="Repair the bound runtime and retry the deterministic export runner.",
        )
        return validate_terminal(python, manifest_path, manifest, result)

    topology = run_step(
        python,
        "normalize_text_frame_topology.py",
        "--project-dir",
        str(project),
    )
    if topology.returncode != 0:
        result = blocked(
            stage="text-frame-topology",
            reason=(
                "Isolated-copy text-frame normalization, exact-copy verification, "
                "or topology recheck failed: " + compact_detail(topology)
            ),
            repair_scope="source-svg",
            slide_ids=topology_blocked_slide_ids(project, slide_ids),
            resume_from=(
                "Inspect validation/text_frame_topology.json and replace only an "
                "unresolved confirmed SVG; safely normalized pages do not require "
                "new user selection."
            ),
        )
        return validate_terminal(python, manifest_path, manifest, result)

    quality = run_step(
        python, "svg_quality_checker.py", str(project), "--stage", "final", "--json"
    )
    if quality.returncode != 0:
        environment_failure = quality_failure_is_environment(project)
        affected = slide_ids if environment_failure else affected_slide_ids(project, slide_ids)
        result = blocked(
            stage="svg-gate",
            reason=(
                "Blocking SVG compatibility error(s); advisory findings never cause "
                "this status. " + compact_detail(quality)
            ),
            repair_scope="environment" if environment_failure else "source-svg",
            slide_ids=affected,
            resume_from=(
                "Repair the bound SVG validation runtime and retry export."
                if environment_failure
                else "Replace or reopen only the named confirmed SVG pages, then retry export."
            ),
        )
        return validate_terminal(python, manifest_path, manifest, result)

    finalized = run_step(python, "finalize_svg.py", str(project))
    if finalized.returncode != 0:
        result = blocked(
            stage="svg-finalize",
            reason=compact_detail(finalized),
            repair_scope="source-svg",
            slide_ids=slide_ids,
            resume_from="Replace or reopen the incompatible confirmed SVG pages, then retry export.",
        )
        return validate_terminal(python, manifest_path, manifest, result)

    output = Path(str(manifest["required_output_path"])).expanduser().resolve()
    try:
        output.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("required output path escapes the export workspace") from exc
    exported = run_step(
        python,
        "svg_to_pptx.py",
        str(project),
        "--output",
        str(output),
        "--merge-paragraphs",
        "--no-notes",
    )
    if exported.returncode != 0 or not output.is_file():
        result = blocked(
            stage="export",
            reason=compact_detail(exported),
            repair_scope="environment",
            slide_ids=slide_ids,
            resume_from="Repair the export environment and retry the deterministic export runner.",
        )
        return validate_terminal(python, manifest_path, manifest, result)

    typography = run_step(
        python,
        "assert_pptx_typography.py",
        "--pptx",
        str(output),
        "--exempt-slide-number",
        str(fixed_ending_indexes[0]),
    )
    if typography.returncode != 0:
        result = blocked(
            stage="pptx-typography",
            reason=compact_detail(typography),
            repair_scope="environment",
            slide_ids=slide_ids,
            resume_from="Repair the bundled converter and retry the deterministic export runner.",
        )
        return validate_terminal(python, manifest_path, manifest, result)

    final_guard = run_step(python, "assert_confirmed_export_runtime.py", *guard_args)
    if final_guard.returncode != 0:
        result = blocked(
            stage="export",
            reason=compact_detail(final_guard),
            repair_scope="environment",
            slide_ids=slide_ids,
            resume_from="Repair the bound runtime and retry the deterministic export runner.",
        )
        return validate_terminal(python, manifest_path, manifest, result)
    return validate_terminal(
        python,
        manifest_path,
        manifest,
        {
            "status": "COMPLETE",
            "route": "confirmed-svg-export",
            "artifact_path": str(output),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    try:
        result = execute(args.manifest, args.manifest_sha256)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "status": "BLOCKED",
            "route": "confirmed-svg-export",
            "stage": "handoff",
            "slide_ids": ["unknown"],
            "reason": str(exc),
            "repair_scope": "environment",
            "resume_from": "Rebuild the EY export workspace and retry.",
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("status") == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
