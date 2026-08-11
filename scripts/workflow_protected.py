#!/usr/bin/env python3
"""Materialize and verify protected-page canonical SVGs."""

from __future__ import annotations

import html
import shutil
import unicodedata
from pathlib import Path

from framework_lib import PageEntry, page_entries
from svg_boundary import protected_candidate_errors
from workflow_io import atomic_write, now, read_json, sha256, text_sha256, write_json
from workflow_paths import receipt_path


def protected_canonical_evidence_valid(project_dir: Path, page: PageEntry) -> bool:
    canonical = project_dir / "svg_output" / f"{page.slide_id}.svg"
    receipt_file = receipt_path(project_dir, page.slide_id, "protected")
    if protected_candidate_errors(canonical) or not receipt_file.is_file():
        return False
    try:
        receipt = read_json(receipt_file)
        return (
            receipt.get("slide_id") == page.slide_id
            and receipt.get("canonical_sha256") == sha256(canonical)
            and receipt.get("content_scope_sha256")
            == text_sha256(page.fields.get("Content scope", ""))
        )
    except (OSError, ValueError):
        return False


def protected_artifact_valid(project_dir: Path, page: PageEntry) -> bool:
    if not protected_canonical_evidence_valid(project_dir, page):
        return False
    source = project_dir / "protected_input" / f"{page.slide_id}.svg"
    try:
        receipt = read_json(receipt_path(project_dir, page.slide_id, "protected"))
        source_kind = receipt.get("source_kind")
        return (
            source_kind == "user-supplied-svg"
            and source.is_file()
            and receipt.get("source_sha256") == sha256(source)
        ) or (
            source_kind == "deterministic-placeholder"
            and not source.exists()
            and receipt.get("source_sha256") == "Not applicable"
        )
    except (OSError, ValueError):
        return False


def _display_width(char: str) -> float:
    return 1.0 if unicodedata.east_asian_width(char) in {"W", "F"} else 0.5


def _wrap_display_text(value: str, max_width: float = 64.0) -> list[str]:
    """Wrap without dropping any approved instruction text."""
    normalized = " ".join(value.split())
    if not normalized:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    width = 0.0
    for char in normalized:
        char_width = _display_width(char)
        if current and width + char_width > max_width:
            lines.append("".join(current))
            current = []
            width = 0.0
        current.append(char)
        width += char_width
    if current:
        lines.append("".join(current))
    return lines


def protected_placeholder_svg(page: PageEntry) -> str:
    instruction = page.fields.get("Content scope", "").strip()
    chunks = _wrap_display_text(instruction)
    font_size = 13.3333 if len(chunks) <= 8 else 10.6667
    line_height = font_size + 8
    lines = []
    for index, chunk in enumerate(chunks):
        dy = "0" if index == 0 else str(line_height)
        lines.append(f'<tspan x="112" dy="{dy}">{html.escape(chunk)}</tspan>')
    body = "".join(lines)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="content">
  <desc>{html.escape(instruction)}</desc>
  <rect id="background" x="0" y="0" width="1280" height="720" fill="#000000" data-pptx-role="background"/>
  <g id="protected-placeholder" data-pptx-bounds="80 72 1120 560">
    <text x="112" y="128" fill="#FFE600" font-family="Microsoft YaHei, Calibri, Arial, sans-serif" font-size="16" font-weight="700">PROTECTED INSERTION PLACEHOLDER</text>
    <text x="112" y="198" fill="#FFFFFF" font-family="Microsoft YaHei, Calibri, Arial, sans-serif" font-size="32" font-weight="700">{html.escape(page.title)}</text>
    <text x="112" y="286" fill="#D9D9D9" font-family="Microsoft YaHei, Calibri, Arial, sans-serif" font-size="{font_size}">{body}</text>
  </g>
</svg>
'''


def materialize_protected_pages(text: str, project_dir: Path) -> list[str]:
    materialized: list[str] = []
    for page in page_entries(text):
        if (
            page.fields.get("Status") != "Protected placeholder"
            or protected_artifact_valid(project_dir, page)
        ):
            continue
        source = project_dir / "protected_input" / f"{page.slide_id}.svg"
        canonical = project_dir / "svg_output" / f"{page.slide_id}.svg"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, canonical)
            source_kind = "user-supplied-svg"
            source_hash = sha256(source)
        else:
            instruction = page.fields.get("Content scope", "")
            if "[占位：" not in instruction or "AI不得生成、改写或补充" not in instruction:
                raise ValueError(
                    f"{page.slide_id} protected placeholder needs an exact [占位：...] instruction "
                    "that prohibits AI generation, rewriting, or supplementation"
                )
            atomic_write(canonical, protected_placeholder_svg(page))
            source_kind = "deterministic-placeholder"
            source_hash = "Not applicable"
        problems = protected_candidate_errors(canonical)
        if problems:
            canonical.unlink(missing_ok=True)
            raise ValueError("; ".join(problems))
        write_json(receipt_path(project_dir, page.slide_id, "protected"), {
            "slide_id": page.slide_id,
            "source_kind": source_kind,
            "source_sha256": source_hash,
            "content_scope_sha256": text_sha256(page.fields.get("Content scope", "")),
            "canonical_sha256": sha256(canonical),
            "created_at": now(),
        })
        materialized.append(page.slide_id)
    return materialized
