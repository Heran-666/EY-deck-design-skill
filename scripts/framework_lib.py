#!/usr/bin/env python3
"""Shared parser utilities for EY presentation framework memory."""

from __future__ import annotations

import re
from dataclasses import dataclass


PAGE_RE = re.compile(r"^### (S\d{2})｜(.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"^- ([^:\n]+):\s*(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class PageEntry:
    slide_id: str
    title: str
    text: str
    fields: dict[str, str]


def h2_section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^## ", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start() : end].rstrip() + "\n"


def line_fields(section: str) -> dict[str, str]:
    return {key.strip(): value.strip() for key, value in FIELD_RE.findall(section)}


def duplicate_line_fields(section: str) -> list[str]:
    counts: dict[str, int] = {}
    for key, _value in FIELD_RE.findall(section):
        normalized = key.strip()
        counts[normalized] = counts.get(normalized, 0) + 1
    return sorted(key for key, count in counts.items() if count > 1)


def replace_field(section: str, field: str, value: str) -> str:
    pattern = rf"^- {re.escape(field)}:\s*.*$"
    matches = list(re.finditer(pattern, section, re.MULTILINE))
    if not matches:
        raise ValueError(f"missing field: {field}")
    if len(matches) > 1:
        raise ValueError(f"duplicate field: {field}")
    return re.sub(pattern, f"- {field}: {value}", section, count=1, flags=re.MULTILINE)


def page_entries(text: str) -> list[PageEntry]:
    storyline = h2_section(text, "Confirmed Storyline")
    matches = list(PAGE_RE.finditer(storyline))
    pages: list[PageEntry] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(storyline)
        page_text = storyline[match.start() : end].rstrip() + "\n"
        pages.append(
            PageEntry(
                slide_id=match.group(1),
                title=match.group(2).strip(),
                text=page_text,
                fields=line_fields(page_text),
            )
        )
    return pages


def replace_slide_ids(text: str, mapping: dict[str, str]) -> str:
    """Replace overlapping slide IDs safely through collision-proof placeholders."""
    placeholders = {old: f"__EY_SLIDE_{index:04d}__" for index, old in enumerate(mapping)}
    for old, placeholder in placeholders.items():
        text = re.sub(rf"\b{re.escape(old)}\b", placeholder, text)
    for old, placeholder in placeholders.items():
        text = text.replace(placeholder, mapping[old])
    return text
