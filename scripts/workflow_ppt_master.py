#!/usr/bin/env python3
"""Anti-corruption adapter for the vendored PPT Master SVG engine."""

from __future__ import annotations

from pathlib import Path

from framework_lib import PageEntry, h2_section, line_fields, page_entries
from workflow_content import content_section
from workflow_io import sha256, text_sha256, write_json
from workflow_paths import ProjectPaths


SKILL_ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = SKILL_ROOT / "ppt-master"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates" / "ey-gradient-dark-v1"
SERVICE_CONTRACT = PPT_MASTER_ROOT / "workflows" / "page-svg-service.md"
SERVICE_CLI = PPT_MASTER_ROOT / "scripts" / "page_svg_service.py"


def embedding_errors() -> list[str]:
    required = (
        PPT_MASTER_ROOT / "INTERNAL.md",
        PPT_MASTER_ROOT / "scripts" / "attribution_guard.py",
        PPT_MASTER_ROOT / "references" / "executor-base.md",
        PPT_MASTER_ROOT / "references" / "executor-structured.md",
        SERVICE_CONTRACT,
        SERVICE_CLI,
        TEMPLATE_ROOT / "templates" / "design_spec.md",
    )
    return [f"embedded PPT Master dependency not found: {path}" for path in required if not path.is_file()]


def template_name(page_type: str) -> str:
    normalized = page_type.strip().lower()
    if normalized == "cover":
        return "cover.svg"
    if normalized == "agenda":
        return "agenda.svg"
    if normalized in {"section divider", "divider"}:
        return "divider.svg"
    return "content.svg"


def template_path(page: PageEntry) -> Path:
    path = TEMPLATE_ROOT / "templates" / template_name(page.fields.get("Page type", ""))
    if not path.is_file():
        raise ValueError(f"EY template prototype not found: {path}")
    return path


def request_payload(
    paths: ProjectPaths,
    framework_text: str,
    page: PageEntry,
    version: str,
    *,
    base_version: str | None = None,
    feedback: str | None = None,
) -> dict[str, object]:
    errors = embedding_errors()
    if errors:
        raise ValueError(" | ".join(errors))
    section = content_section(paths.content.read_text(encoding="utf-8"), page.slide_id)
    if not section:
        raise ValueError(f"approved content not found for {page.slide_id}")
    prototype = template_path(page)
    context = line_fields(h2_section(framework_text, "Project context"))
    pages = page_entries(framework_text)
    page_index = next(index for index, item in enumerate(pages) if item.slide_id == page.slide_id)
    adjacent_pages = {
        "previous": None if page_index == 0 else {
            "slide_id": pages[page_index - 1].slide_id,
            "title": pages[page_index - 1].title,
            "narrative_role": pages[page_index - 1].fields.get("Narrative role", ""),
        },
        "next": None if page_index + 1 == len(pages) else {
            "slide_id": pages[page_index + 1].slide_id,
            "title": pages[page_index + 1].title,
            "narrative_role": pages[page_index + 1].fields.get("Narrative role", ""),
        },
    }
    confirmed_pages = []
    for item in pages:
        confirmed = paths.svg_output / f"{item.slide_id}.svg"
        if item.fields.get("Status") == "SVG confirmed" and confirmed.is_file():
            confirmed_pages.append({
                "slide_id": item.slide_id,
                "path": str(confirmed.resolve()),
                "sha256": sha256(confirmed),
            })
    base_payload: dict[str, str] | None = None
    if base_version:
        base = paths.candidate(page.slide_id, base_version)
        if not base.is_file():
            raise ValueError(f"revision base not found: {base}")
        base_payload = {
            "version": base_version,
            "path": str(base.resolve()),
            "sha256": sha256(base),
        }
    return {
        "schema": "ppt-master.page-svg-request.v1",
        "caller": "ey-deck-design",
        "slide_id": page.slide_id,
        "version": version,
        "mode": "revision" if base_version else "independent",
        "artifact_path": str(paths.candidate(page.slide_id, version).resolve()),
        "canvas": "0 0 1280 720",
        "service_contract": str(SERVICE_CONTRACT.resolve()),
        "project_context": {
            "deliverable": context.get("Deliverable name", ""),
            "audience": context.get("Audience", ""),
            "audience_outcome": context.get("Audience outcome", ""),
            "storyline_thesis": context.get("Storyline thesis", ""),
        },
        "page_context": {
            "page_type": page.fields.get("Page type", ""),
            "narrative_role": page.fields.get("Narrative role", ""),
            "next_connection": page.fields.get("Next connection", ""),
            "adjacent_pages": adjacent_pages,
        },
        "confirmed_pages": confirmed_pages,
        "approved_content": section.rstrip(),
        "approved_content_sha256": text_sha256(section.rstrip()),
        "approved_content_source": str(paths.content.resolve()),
        "approved_content_source_sha256": sha256(paths.content),
        "template": {
            "workspace": str(TEMPLATE_ROOT.resolve()),
            "prototype": str(prototype.resolve()),
            "prototype_sha256": sha256(prototype),
        },
        "base": base_payload,
        "feedback": feedback if base_version else None,
    }


def write_packet(
    paths: ProjectPaths,
    framework_text: str,
    page: PageEntry,
    version: str,
    *,
    base_version: str | None = None,
    feedback: str | None = None,
) -> Path:
    packet = paths.packet(page.slide_id, version)
    write_json(
        packet,
        request_payload(
            paths,
            framework_text,
            page,
            version,
            base_version=base_version,
            feedback=feedback,
        ),
    )
    return packet
