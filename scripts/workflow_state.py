#!/usr/bin/env python3
"""Pure workflow state derivation and framework page updates."""

from __future__ import annotations

import re

from framework_lib import PageEntry, page_entries, replace_field
from workflow_spec import TERMINAL_STATES


def update_page(text: str, slide_id: str, updates: dict[str, str]) -> str:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    updated = page.text
    for field, value in updates.items():
        updated = replace_field(updated, field, value)
    return text.replace(page.text, updated, 1)


def update_page_title(text: str, slide_id: str, title: str) -> str:
    return re.sub(
        rf"^### {re.escape(slide_id)}｜.*$",
        f"### {slide_id}｜{title}",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def page_type(page: PageEntry) -> str:
    return page.fields.get("Page type", "").strip().lower()


def is_structural(page: PageEntry) -> bool:
    return page_type(page) in {"cover", "section divider"}


def is_agenda(page: PageEntry) -> bool:
    return page_type(page) == "agenda"


def is_body(page: PageEntry) -> bool:
    return not is_structural(page) and not is_agenda(page)


def unresolved(pages: list[PageEntry]) -> list[PageEntry]:
    return [page for page in pages if page.fields.get("Status") not in TERMINAL_STATES]


def derived_phase(text: str) -> str:
    pages = page_entries(text)
    if unresolved([page for page in pages if is_body(page)]):
        return "Stage 1 — Body page loop"
    if unresolved([page for page in pages if is_structural(page)]):
        return "Stage 1 — Structural page review"
    if unresolved([page for page in pages if is_agenda(page)]):
        return "Stage 1 — Agenda review"
    return "Stage 2 — EY confirmed SVG export"


def phase_pages(pages: list[PageEntry], phase: str) -> list[PageEntry]:
    if phase == "Stage 1 — Body page loop":
        return [page for page in pages if is_body(page)]
    if phase == "Stage 1 — Structural page review":
        return [page for page in pages if is_structural(page)]
    if phase == "Stage 1 — Agenda review":
        return [page for page in pages if is_agenda(page)]
    return []


def current_group(text: str) -> list[PageEntry]:
    pages = page_entries(text)
    phase = derived_phase(text)
    remaining = unresolved(phase_pages(pages, phase))
    if not remaining:
        return []
    first = remaining[0]
    if phase == "Stage 1 — Structural page review":
        return remaining
    if phase == "Stage 1 — Agenda review":
        return [first]
    if first.fields.get("Review mode") == "Batch":
        chapter = first.fields.get("Chapter")
        return [
            page
            for page in remaining
            if page.fields.get("Review mode") == "Batch" and page.fields.get("Chapter") == chapter
        ]
    return [first]
