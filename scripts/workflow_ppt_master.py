#!/usr/bin/env python3
"""Anti-corruption adapter for the vendored PPT Master SVG engine."""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from framework_lib import PageEntry, h2_section, line_fields, page_entries
from workflow_content import content_section, page_logic
from workflow_io import atomic_write, read_json, sha256, text_sha256, write_json
from workflow_paths import ProjectPaths
from workflow_spec import normalize_page_type, page_rhythm, reading_mode


SKILL_ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = SKILL_ROOT / "ppt-master"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates" / "ey-gradient-dark-v1"
TEMPLATE_DESIGN_SPEC = TEMPLATE_ROOT / "templates" / "design_spec.md"
SERVICE_CONTRACT = PPT_MASTER_ROOT / "workflows" / "page-svg-service.md"
SERVICE_CLI = PPT_MASTER_ROOT / "scripts" / "page_svg_service.py"
PAGE_CONTEXT_SCHEMA = "ey-deck.page-authoring-context.v6"
REQUEST_SCHEMA = "ppt-master.page-svg-request.v4"
DESIGN_QUALITY_PROFILE = "ey-executive-editorial-v3"
IMAGE_MIME_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}

def embedding_errors() -> list[str]:
    required = (
        PPT_MASTER_ROOT / "INTERNAL.md",
        PPT_MASTER_ROOT / "scripts" / "attribution_guard.py",
        PPT_MASTER_ROOT / "references" / "strategist.md",
        PPT_MASTER_ROOT / "references" / "strategist-template.md",
        PPT_MASTER_ROOT / "references" / "executor-base.md",
        PPT_MASTER_ROOT / "references" / "executor-structured.md",
        SERVICE_CONTRACT,
        SERVICE_CLI,
        TEMPLATE_DESIGN_SPEC,
    )
    return [f"embedded PPT Master dependency not found: {path}" for path in required if not path.is_file()]


def template_name(page_type: str) -> str:
    normalized = normalize_page_type(page_type)
    if normalized == "cover":
        return "cover.svg"
    if normalized == "agenda":
        return "agenda.svg"
    if normalized in {"section divider", "divider"}:
        return "divider.svg"
    if normalized in {"ending", "closing", "closing page"}:
        return "ending.svg"
    return "content.svg"


def template_path(page: PageEntry) -> Path:
    path = TEMPLATE_ROOT / "templates" / template_name(page.fields.get("Page type", ""))
    if not path.is_file():
        raise ValueError(f"EY template prototype not found: {path}")
    return path


def deferred_template_text(
    framework_text: str,
    page: PageEntry,
) -> dict[str, str]:
    """Return exact text for editable deferred-template slots."""
    if normalize_page_type(page.fields.get("Page type", "")) != "cover":
        return {}
    context = line_fields(h2_section(framework_text, "Project context"))
    return {
        "cover-project-type": context.get("Deliverable type", "").strip(),
        "cover-title": page.title.strip(),
        "cover-subtitle": page.fields.get("Content scope", "").strip(),
    }


def _bind_template_text(root: ET.Element, bindings: dict[str, str]) -> None:
    elements_by_id = {
        element.attrib["id"]: element
        for element in root.iter()
        if element.attrib.get("id")
    }
    for element_id, value in bindings.items():
        if not value:
            raise ValueError(f"deferred template text is empty: {element_id}")
        container = elements_by_id.get(element_id)
        if container is None:
            raise ValueError(f"deferred template text slot not found: {element_id}")
        carrier = next(
            (
                element
                for element in container.iter()
                if element.tag.rsplit("}", 1)[-1] == "text"
            ),
            None,
        )
        if carrier is None:
            raise ValueError(f"deferred template text carrier not found: {element_id}")
        for child in list(carrier):
            carrier.remove(child)
        carrier.text = value


def materialize_template(
    prototype: Path,
    destination: Path,
    *,
    text_bindings: dict[str, str] | None = None,
) -> Path:
    """Write a request-local template whose image resources are embedded."""
    try:
        root = ET.parse(prototype).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"invalid EY template prototype: {prototype}: {exc}") from exc
    _bind_template_text(root, text_bindings or {})
    template_root = TEMPLATE_ROOT.resolve()
    href_keys = ("href", "{http://www.w3.org/1999/xlink}href")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "image":
            continue
        href_key = next((key for key in href_keys if element.attrib.get(key)), None)
        if href_key is None:
            continue
        href = element.attrib[href_key].strip()
        if href.lower().startswith("data:"):
            continue
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"EY template image must be local: {href}")
        resource = (prototype.parent / unquote(parsed.path)).resolve()
        try:
            resource.relative_to(template_root)
        except ValueError as exc:
            raise ValueError(f"EY template image escapes its workspace: {href}") from exc
        if not resource.is_file():
            raise ValueError(f"EY template image not found: {resource}")
        mime_type = IMAGE_MIME_TYPES.get(resource.suffix.lower())
        if mime_type is None:
            raise ValueError(f"unsupported EY template image type: {resource.suffix}")
        payload = base64.b64encode(resource.read_bytes()).decode("ascii")
        element.set(href_key, f"data:{mime_type};base64,{payload}")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    atomic_write(destination, ET.tostring(root, encoding="unicode") + "\n")
    return destination


def page_context_payload(
    paths: ProjectPaths,
    framework_text: str,
    page: PageEntry,
) -> dict[str, object]:
    errors = embedding_errors()
    if errors:
        raise ValueError(" | ".join(errors))
    section = content_section(paths.content.read_text(encoding="utf-8"), page.slide_id)
    if not section:
        raise ValueError(f"approved content not found for {page.slide_id}")
    source_prototype = template_path(page)
    prototype = materialize_template(
        source_prototype,
        paths.template_prototype(page.slide_id),
    )
    context = line_fields(h2_section(framework_text, "Project context"))
    resolved_reading_mode = reading_mode(context.get("Reading mode", ""))
    resolved_page_rhythm = page_rhythm(
        page.fields.get("Page rhythm", ""),
        page.fields.get("Page type", ""),
    )
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
    consistency_references = []
    current_type = normalize_page_type(page.fields.get("Page type", ""))
    for item in reversed(pages[:page_index]):
        confirmed = paths.svg_output / f"{item.slide_id}.svg"
        if item.fields.get("Status") != "SVG confirmed" or not confirmed.is_file():
            continue
        reference = {
            "slide_id": item.slide_id,
            "path": str(confirmed.resolve()),
            "sha256": sha256(confirmed),
        }
        if not consistency_references:
            consistency_references.append(reference)
            if normalize_page_type(item.fields.get("Page type", "")) == current_type:
                break
        elif normalize_page_type(item.fields.get("Page type", "")) == current_type:
            consistency_references.append(reference)
            break
    logic = page_logic(section)
    page_context = {
        "page_type": page.fields.get("Page type", ""),
        "next_connection": page.fields.get("Next connection", ""),
        "adjacent_pages": adjacent_pages,
    }
    if logic is None:
        page_context["purpose"] = page.fields.get("Narrative role", "")
    return {
        "schema": PAGE_CONTEXT_SCHEMA,
        "caller": "ey-deck-design",
        "slide_id": page.slide_id,
        "canvas": "0 0 1280 720",
        "composition_mode": "full-slide",
        "project_context": {
            "deliverable": context.get("Deliverable name", ""),
            "audience": context.get("Audience", ""),
        },
        "communication": {
            "consumption_mode": resolved_reading_mode,
            "objective": (
                f"{context.get('Core need', '')}; success means "
                f"{context.get('Audience outcome', '')}"
            ),
            "core_message": context.get("Storyline thesis", ""),
        },
        "page_context": page_context,
        "page_rhythm": resolved_page_rhythm,
        "page_logic": logic,
        "design_quality_profile": DESIGN_QUALITY_PROFILE,
        "consistency_references": consistency_references,
        "approved_content": section.rstrip(),
        "approved_content_sha256": text_sha256(section.rstrip()),
        "template": {
            "prototype": str(prototype.resolve()),
            "prototype_sha256": sha256(prototype),
            "design_spec": {
                "path": str(TEMPLATE_DESIGN_SPEC.resolve()),
                "sha256": sha256(TEMPLATE_DESIGN_SPEC),
            },
        },
    }


def write_page_context(
    paths: ProjectPaths,
    framework_text: str,
    page: PageEntry,
) -> Path:
    destination = paths.page_context(page.slide_id)
    write_json(destination, page_context_payload(paths, framework_text, page))
    return destination


def request_payload(
    paths: ProjectPaths,
    page: PageEntry,
    version: str,
    *,
    base_version: str | None = None,
    feedback: str | None = None,
) -> dict[str, object]:
    context_path = paths.page_context(page.slide_id)
    if not context_path.is_file():
        raise ValueError(f"page authoring context not found: {context_path}")
    context = read_json(context_path)
    if context.get("schema") != PAGE_CONTEXT_SCHEMA or context.get("slide_id") != page.slide_id:
        raise ValueError(f"invalid page authoring context: {context_path}")
    current_section = content_section(
        paths.content.read_text(encoding="utf-8"),
        page.slide_id,
    ).rstrip()
    if context.get("approved_content_sha256") != text_sha256(current_section):
        raise ValueError(f"stale page authoring context: {context_path}")
    project_context = context.get("project_context")
    if not isinstance(project_context, dict):
        raise ValueError(f"page authoring context has no project context: {context_path}")
    if not base_version and version != "A":
        raise ValueError("the initial candidate version must be A")
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
        "schema": REQUEST_SCHEMA,
        "caller": "ey-deck-design",
        "slide_id": page.slide_id,
        "version": version,
        "mode": "revision" if base_version else "independent",
        "artifact_path": str(paths.candidate(page.slide_id, version).resolve()),
        "authoring_context": {
            "path": str(context_path.resolve()),
            "sha256": sha256(context_path),
        },
        "base": base_payload,
        "feedback": feedback if base_version else None,
    }


def write_packet(
    paths: ProjectPaths,
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
            page,
            version,
            base_version=base_version,
            feedback=feedback,
        ),
    )
    return packet
