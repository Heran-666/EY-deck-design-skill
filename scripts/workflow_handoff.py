#!/usr/bin/env python3
"""Confirmed-export read model and handoff artifact identity checks."""

from __future__ import annotations

from pathlib import Path

from framework_lib import h2_section, line_fields, page_entries
from workflow_export import inspect_export_workspace
from workflow_io import read_json, sha256
from workflow_paths import handoff_result_path


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
