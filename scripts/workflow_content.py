#!/usr/bin/env python3
"""Content-section parsing, incremental validation, and exact promotion."""

from __future__ import annotations

import re
from pathlib import Path

from framework_lib import PageEntry, line_fields, page_entries
from validate_deck_blueprint import validate as validate_blueprint
from workflow_copy_contract import copy_contract_errors, visible_copy_contract


def content_section(content: str, slide_id: str) -> str:
    match = re.search(rf"^## {re.escape(slide_id)}｜.*$", content, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^## S\d{2}｜", content[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(content)
    return content[match.start() : end].rstrip() + "\n"


def content_identity_errors(page: PageEntry, section: str) -> list[str]:
    errors: list[str] = []
    heading = re.search(rf"^## {re.escape(page.slide_id)}｜(.+)$", section, re.MULTILINE)
    title = re.search(r"^- Title:\s*(.+)$", section, re.MULTILINE)
    if heading and title and heading.group(1).strip() != title.group(1).strip():
        errors.append(f"{page.slide_id} content heading must equal its exact Title field")
    brief = re.search(
        r"^### Visual Direction（Build-only）\s*$\n(.*?)(?=^### |\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    )
    brief_type = line_fields(brief.group(1)).get("Page type") if brief else None
    page_type = page.fields.get("Page type", "").strip().lower()
    if brief_type and brief_type.strip().lower() != page_type:
        errors.append(
            f"{page.slide_id} Visual Direction Page type {brief_type!r} does not match "
            f"framework Page type {page.fields.get('Page type')!r}"
        )
    return errors


def provisional_content_errors(path: Path, expected_pages: list[PageEntry]) -> list[str]:
    if not path.is_file():
        return [f"provisional content not found: {path}"]
    text = path.read_text(encoding="utf-8")
    actual_ids = re.findall(r"^## (S\d{2})｜", text, re.MULTILINE)
    expected_ids = [page.slide_id for page in expected_pages]
    errors: list[str] = []
    if actual_ids != expected_ids:
        errors.append(
            "provisional content must contain exactly the active pages in order; expected "
            + (",".join(expected_ids) or "None")
            + "; found "
            + (",".join(actual_ids) or "None")
            + "; replace the entire file instead of appending"
        )
    for page in expected_pages:
        section = content_section(text, page.slide_id)
        contract_errors: list[str] = []
        try:
            contract_errors = copy_contract_errors(
                visible_copy_contract(section, page.slide_id)
            )
        except ValueError as exc:
            contract_errors = [str(exc)]
        for error in (
            validate_blueprint(path, page.slide_id)
            + content_identity_errors(page, section)
            + contract_errors
        ):
            if error not in errors:
                errors.append(error)
    return errors


def review_receipt_path(project_dir: Path, pages: list[str]) -> Path:
    return project_dir / "working" / "receipts" / f"review-{'_'.join(pages)}.json"


def content_header(content: str) -> str:
    first = re.search(r"^## S\d{2}｜", content, re.MULTILINE)
    return (content[: first.start()] if first else content).rstrip() + "\n\n"


def promote_provisional_content(
    framework_text: str,
    existing_content: str,
    provisional_content: str,
) -> str:
    sections = {
        slide_id: content_section(existing_content, slide_id)
        for slide_id in re.findall(r"^## (S\d{2})｜", existing_content, re.MULTILINE)
    }
    for slide_id in re.findall(r"^## (S\d{2})｜", provisional_content, re.MULTILINE):
        sections[slide_id] = content_section(provisional_content, slide_id)
    header = content_header(existing_content) if existing_content.strip() else content_header(provisional_content)
    ordered = [
        sections[page.slide_id].rstrip()
        for page in page_entries(framework_text)
        if page.slide_id in sections
    ]
    return header + "\n\n".join(ordered) + "\n"
