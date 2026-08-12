#!/usr/bin/env python3
"""Hash-bind displayed single, A/B, and revision PNG previews to source SVGs."""

from __future__ import annotations

from pathlib import Path

from preview_renderer import preview_paths, preview_receipt_errors
from workflow_io import read_json, sha256
from workflow_paths import receipt_path, working_paths


def presentation_preview_errors(
    project_dir: Path,
    slide_id: str,
    versions: tuple[str, ...],
    presentation: dict,
) -> list[str]:
    errors: list[str] = []
    for version in versions:
        png, preview_receipt = preview_paths(project_dir, slide_id, version)
        version_errors = preview_receipt_errors(project_dir, slide_id, version)
        errors.extend(version_errors)
        if version_errors:
            continue
        prefix = version.lower()
        expected_receipt = str(preview_receipt.relative_to(project_dir))
        if presentation.get(f"{prefix}_preview_png_sha256") != sha256(png):
            errors.append(f"{slide_id} {version} shown PNG changed after presentation")
        if presentation.get(f"{prefix}_preview_receipt") != expected_receipt:
            errors.append(f"{slide_id} {version} presentation points to the wrong preview receipt")
        if presentation.get(f"{prefix}_preview_receipt_sha256") != sha256(preview_receipt):
            errors.append(f"{slide_id} {version} preview receipt changed after presentation")
        try:
            preview = read_json(preview_receipt)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if presentation.get(f"{prefix}_preview_renderer") != preview.get("renderer"):
            errors.append(f"{slide_id} {version} preview renderer identity changed")
    return errors


def preview_presentation_evidence(
    project_dir: Path,
    slide_id: str,
    versions: tuple[str, ...],
    records: dict[str, dict],
) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for version in versions:
        _current_png, receipt_file = preview_paths(project_dir, slide_id, version)
        png = project_dir / str(records[version]["preview_png"])
        prefix = version.lower()
        evidence[f"{prefix}_preview_png_sha256"] = sha256(png)
        evidence[f"{prefix}_preview_receipt"] = str(receipt_file.relative_to(project_dir))
        evidence[f"{prefix}_preview_receipt_sha256"] = sha256(receipt_file)
        evidence[f"{prefix}_preview_renderer"] = str(records[version]["renderer"])
    return evidence


def ab_presentation_valid(project_dir: Path, slide_id: str) -> bool:
    path = receipt_path(project_dir, slide_id, "ab-presentation")
    if not path.is_file():
        return False
    try:
        receipt = read_json(path)
    except ValueError:
        return False
    a_path, b_path = working_paths(project_dir, slide_id)
    hashes_match = (
        a_path.is_file()
        and b_path.is_file()
        and receipt.get("a_sha256") == sha256(a_path)
        and receipt.get("b_sha256") == sha256(b_path)
    )
    return hashes_match and not presentation_preview_errors(
        project_dir, slide_id, ("A", "B"), receipt
    )


def single_presentation_valid(project_dir: Path, slide_id: str) -> bool:
    path = receipt_path(project_dir, slide_id, "single-presentation")
    if not path.is_file():
        return False
    try:
        receipt = read_json(path)
    except ValueError:
        return False
    a_path, _b_path = working_paths(project_dir, slide_id)
    hashes_match = a_path.is_file() and receipt.get("a_sha256") == sha256(a_path)
    return hashes_match and not presentation_preview_errors(
        project_dir, slide_id, ("A",), receipt
    )
