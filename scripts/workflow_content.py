#!/usr/bin/env python3
"""Content-section parsing, incremental validation, and exact promotion."""

from __future__ import annotations

import re
from pathlib import Path

from framework_lib import PageEntry, page_entries
from validate_deck_blueprint import validate as validate_blueprint


PAGE_LOGIC_FIELDS = {
    "Page objective": "page_objective",
    "Audience move": "audience_move",
    "Reasoning pattern": "reasoning_pattern",
    "Argument chain": "argument_chain",
    "Relationship constraints": "relationship_constraints",
    "Argument priority": "argument_priority",
}


def content_section(content: str, slide_id: str) -> str:
    match = re.search(
        rf"^## {re.escape(slide_id)}(?:｜[^\n]*)?$",
        content,
        re.MULTILINE,
    )
    if not match:
        return ""
    next_match = re.search(
        r"^## S\d{2}(?:｜[^\n]*)?$",
        content[match.end() :],
        re.MULTILINE,
    )
    end = match.end() + next_match.start() if next_match else len(content)
    return content[match.start() : end].rstrip() + "\n"


def page_logic(section: str) -> dict[str, str] | None:
    """Return the approved build-only page logic in service-friendly keys."""
    match = re.search(r"^### Page logic（Build-only）\s*$", section, re.MULTILINE)
    if not match:
        return None
    next_h3 = re.search(r"^### ", section[match.end() :], re.MULTILINE)
    end = match.end() + next_h3.start() if next_h3 else len(section)
    body = section[match.end() : end]
    values = {
        key.strip(): value.strip()
        for key, value in re.findall(r"^- ([^:\n]+):\s*(.*)$", body, re.MULTILINE)
    }
    return {
        output_key: values.get(source_key, "")
        for source_key, output_key in PAGE_LOGIC_FIELDS.items()
    }


def provisional_content_errors(path: Path, expected_pages: list[PageEntry]) -> list[str]:
    if not path.is_file():
        return [f"provisional content not found: {path}"]
    text = path.read_text(encoding="utf-8")
    actual_ids = re.findall(r"^## (S\d{2})(?:｜[^\n]*)?$", text, re.MULTILINE)
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
        for error in validate_blueprint(
            path,
            page.slide_id,
            expected_page_type=page.fields.get("Page type", ""),
        ):
            if error not in errors:
                errors.append(error)
    return errors


def content_header(content: str) -> str:
    first = re.search(r"^## S\d{2}(?:｜[^\n]*)?$", content, re.MULTILINE)
    return (content[: first.start()] if first else content).rstrip() + "\n\n"


def promote_provisional_content(
    framework_text: str,
    existing_content: str,
    provisional_content: str,
) -> str:
    sections = {
        slide_id: content_section(existing_content, slide_id)
        for slide_id in re.findall(r"^## (S\d{2})(?:｜[^\n]*)?$", existing_content, re.MULTILINE)
    }
    for slide_id in re.findall(r"^## (S\d{2})(?:｜[^\n]*)?$", provisional_content, re.MULTILINE):
        sections[slide_id] = content_section(provisional_content, slide_id)
    header = content_header(existing_content) if existing_content.strip() else content_header(provisional_content)
    ordered = [
        sections[page.slide_id].rstrip()
        for page in page_entries(framework_text)
        if page.slide_id in sections
    ]
    return header + "\n\n".join(ordered) + "\n"
