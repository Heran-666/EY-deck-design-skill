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
    return page_type(page) in {"cover", "agenda", "section divider"}


def is_agenda(page: PageEntry) -> bool:
    return page_type(page) == "agenda"


def is_body(page: PageEntry) -> bool:
    return not is_structural(page) and not is_agenda(page)


def unresolved(pages: list[PageEntry]) -> list[PageEntry]:
    return [page for page in pages if page.fields.get("Status") not in TERMINAL_STATES]


def derived_phase(text: str) -> str:
    pages = page_entries(text)
    if unresolved(pages):
        return "Stage 1 — Sequential page loop"
    return "Stage 2 — Embedded PPT Master export"


def phase_pages(pages: list[PageEntry], phase: str) -> list[PageEntry]:
    if phase == "Stage 1 — Sequential page loop":
        return pages
    return []


def current_group(text: str) -> list[PageEntry]:
    pages = page_entries(text)
    phase = derived_phase(text)
    remaining = unresolved(phase_pages(pages, phase))
    if not remaining:
        return []
    # Page order is the production authority; a later slide never overtakes or
    # batches with the first unfinished slide.
    return [remaining[0]]
