#!/usr/bin/env python3
"""Confirmed-export read model and handoff artifact identity checks."""

from __future__ import annotations

from pathlib import Path

from framework_lib import h2_section, line_fields, page_entries
from workflow_export import EXPORT_SCHEMA, canonical_records, export_fingerprint, inspect_export_workspace
from workflow_io import read_json, sha256
from workflow_paths import export_preparation_path, handoff_result_path


def output_filename(text: str) -> str:
    return line_fields(h2_section(text, "Current position")).get("Output filename", "")


def current_export(text: str, project_dir: Path) -> dict:
    prepared, errors = inspect_export_workspace(
        project_dir,
        [page.slide_id for page in page_entries(text)],
        output_filename(text),
    )
    if errors or prepared is None:
        raise ValueError("; ".join(errors) or "export workspace could not be prepared")
    return prepared


def recorded_export(text: str, project_dir: Path) -> dict:
    """Read the last prepared manifest without reproving a now-broken runtime."""
    receipt = read_json(export_preparation_path(project_dir))
    manifest_path = Path(str(receipt.get("manifest_path", ""))).expanduser().resolve()
    if not manifest_path.is_file() or receipt.get("manifest_sha256") != sha256(manifest_path):
        raise ValueError("recorded export manifest is missing or stale")
    manifest = read_json(manifest_path)
    slide_ids = [page.slide_id for page in page_entries(text)]
    fingerprint = export_fingerprint(
        canonical_records(project_dir, slide_ids),
        output_filename(text),
    )
    if (
        manifest.get("schema_version") != EXPORT_SCHEMA
        or manifest.get("svg_set_fingerprint") != fingerprint
        or receipt.get("svg_set_fingerprint") != fingerprint
        or receipt.get("output_path") != manifest.get("required_output_path")
    ):
        raise ValueError("recorded export no longer matches the confirmed SVG set")
    ordered = manifest.get("ordered_slides")
    expected_ids = slide_ids + ["EY-END"]
    if not isinstance(ordered, list) or [item.get("slide_id") for item in ordered] != expected_ids:
        raise ValueError("recorded export slide order is stale")
    return receipt


def current_handoff_result(text: str, project_dir: Path) -> dict | None:
    path = handoff_result_path(project_dir)
    if not path.is_file():
        return None
    try:
        result = read_json(path)
    except ValueError:
        return None
    try:
        export = current_export(text, project_dir)
    except (OSError, ValueError):
        try:
            export = recorded_export(text, project_dir)
        except (OSError, ValueError):
            return None
    if (
        result.get("svg_set_fingerprint") != export["svg_set_fingerprint"]
        or result.get("export_manifest") != export["manifest_path"]
        or result.get("export_manifest_sha256") != export["manifest_sha256"]
        or result.get("required_output_path") != export["output_path"]
    ):
        return None
    if result.get("status") == "COMPLETE":
        artifact = Path(str(result.get("artifact_path", ""))).expanduser()
        if artifact.resolve() != Path(export["output_path"]).resolve() or not artifact.is_file():
            return None
        if result.get("artifact_sha256") != sha256(artifact):
            return None
    return result
