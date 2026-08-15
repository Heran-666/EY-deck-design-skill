#!/usr/bin/env python3
"""Agenda-specific content schema shared by review and authoring gates."""

from __future__ import annotations

import re


_H3_SECTION = re.compile(r"^### (.+?)\s*$", re.MULTILINE)
_BLOCK_HEADING = re.compile(
    r"^(#{4,6})\s+(S\d{2}-B\d+(?:\.\d+)*)｜(.+?)\s*$", re.MULTILINE
)
_FIELD = re.compile(r"^- ([^:\n]+):\s*(.*?)\s*$", re.MULTILINE)


def _h3_body(section: str, name: str) -> str:
    match = re.search(rf"^### {re.escape(name)}\s*$", section, re.MULTILINE)
    if not match:
        return ""
    following = _H3_SECTION.search(section, match.end())
    end = following.start() if following else len(section)
    return section[match.end():end]


def agenda_items(section: str, slide_id: str) -> list[tuple[str, str]]:
    """Return validated Agenda item IDs and labels in approved order."""
    return [
        (match.group(2), match.group(3).strip())
        for match in _BLOCK_HEADING.finditer(section)
        if match.group(2).startswith(slide_id + "-B")
    ]


def agenda_schema_errors(section: str, slide_id: str, page_type: str = "") -> list[str]:
    """Require a lean Agenda: Title plus sequential label-only blocks."""
    if page_type.strip().lower() != "agenda":
        return []

    errors: list[str] = []
    on_slide = _h3_body(section, "On-slide content")
    field_names = [match.group(1).strip() for match in _FIELD.finditer(on_slide)]
    unsupported = sorted({name for name in field_names if name != "Title"})
    if unsupported:
        errors.append(
            f"{slide_id} Agenda On-slide content supports only Title; remove: "
            + ", ".join(unsupported)
        )

    matches = list(_BLOCK_HEADING.finditer(section))
    if not matches:
        errors.append(f"{slide_id} Agenda must contain at least one agenda-item block")
        return errors

    expected_ids = [f"{slide_id}-B{index}" for index in range(1, len(matches) + 1)]
    actual_ids = [match.group(2) for match in matches]
    if (
        actual_ids != expected_ids
        or any(match.group(1) != "####" for match in matches)
    ):
        errors.append(
            f"{slide_id} Agenda items must use top-level sequential blocks "
            f"{', '.join(expected_ids)} with #### headings"
        )

    for index, match in enumerate(matches):
        following_block = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        following_h3 = _H3_SECTION.search(section, match.end())
        end = min(
            following_block,
            following_h3.start() if following_h3 else len(section),
        )
        body_lines = [line.strip() for line in section[match.end():end].splitlines() if line.strip()]
        if not body_lines:
            continue
        if any(re.match(r"^- Detail:\s*\S+", line) for line in body_lines):
            errors.append(
                f"{slide_id} Agenda item {match.group(2)} must not contain "
                "supporting-detail (- Detail:)"
            )
        else:
            errors.append(
                f"{slide_id} Agenda item {match.group(2)} must contain only its heading label"
            )
    return errors
