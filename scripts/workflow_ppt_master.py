#!/usr/bin/env python3
"""Anti-corruption adapter for the vendored PPT Master SVG engine."""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from framework_lib import PageEntry, h2_section, line_fields, page_entries
from workflow_content import content_section
from workflow_io import atomic_write, read_json, sha256, text_sha256, write_json
from workflow_paths import ProjectPaths
from workflow_spec import normalize_page_type


SKILL_ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = SKILL_ROOT / "ppt-master"
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates" / "ey-gradient-dark-v1"
TEMPLATE_DESIGN_SPEC = TEMPLATE_ROOT / "templates" / "design_spec.md"
SERVICE_CONTRACT = PPT_MASTER_ROOT / "workflows" / "page-svg-service.md"
SERVICE_CLI = PPT_MASTER_ROOT / "scripts" / "page_svg_service.py"
PAGE_CONTEXT_SCHEMA = "ey-deck.page-authoring-context.v1"
REQUEST_SCHEMA = "ppt-master.page-svg-request.v3"
IMAGE_MIME_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def design_quality_contract() -> dict[str, object]:
    """Return the mandatory quality floor for every first-visible candidate."""
    return {
        "profile": "ey-executive-editorial-v3",
        "target": (
            "Executive-grade EY editorial design that is polished, restrained, "
            "distinctive, and ready for the user to evaluate without first asking for more design."
        ),
        "must_have": [
            "Anchor the page in one audience-facing visual idea tied to its core message.",
            "Create an intentional first, second, and third reading order through scale, position, contrast, and whitespace.",
            "Use semantic geometry, spatial relationships, or typography to explain content instead of merely containing it.",
            "Integrate EY identity through composition and controlled accent behavior, not decoration alone.",
            "Add coherent icon elements at semantically appropriate positions when they improve recognition, scanning, or visual rhythm; omit them when they have no clear communication job.",
            "Refine alignment, spacing, optical balance, edges, connectors, and emphasis at full-slide scale.",
            "Compose freely across the full 1280x720 slide. Placeholder bounds are native PowerPoint metadata only; do not treat y=650 or any other inset rectangle as a visual content limit.",
            "Author each logical PowerPoint text box as one SVG <text>; keep inline-formatting <tspan> runs non-positional with literal word spaces, and use same-x rows with first dy=0 then positive relative dy only as visual-wrap hints for continuous paragraph text; never use sibling <text> elements or authored hard breaks for one paragraph's visual lines, and create a semantic paragraph boundary only when the approved copy actually starts a new paragraph.",
        ],
        "visible_candidate_gate": [
            "information_design",
            "page_composition",
            "art_direction_refinement",
            "source_svg_full_slide_review",
            "source_repair_and_recheck",
        ],
    }


CANDIDATE_PLAN_POLICY = "single-svg-review-v1"

def candidate_plan(
    page: PageEntry,
    approved_content: str,
    project_context: dict[str, str],
) -> dict[str, object]:
    """Require one initial SVG for every authored page."""
    return {
        "policy": CANDIDATE_PLAN_POLICY,
        "versions": ["A"],
        "reason": "single-svg-review",
    }


def candidate_plan_for_page(
    paths: ProjectPaths,
    framework_text: str,
    page: PageEntry,
) -> dict[str, object]:
    section = content_section(paths.content.read_text(encoding="utf-8"), page.slide_id).rstrip()
    if not section:
        raise ValueError(f"approved content not found for {page.slide_id}")
    project_context = line_fields(h2_section(framework_text, "Project context"))
    return candidate_plan(page, section, project_context)


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


def materialize_template(prototype: Path, destination: Path) -> Path:
    """Write a request-local template whose image resources are embedded."""
    try:
        root = ET.parse(prototype).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"invalid EY template prototype: {prototype}: {exc}") from exc
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
    plan = candidate_plan(page, section.rstrip(), context)
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
    for item in pages[:page_index]:
        confirmed = paths.svg_output / f"{item.slide_id}.svg"
        if item.fields.get("Status") == "SVG confirmed" and confirmed.is_file():
            confirmed_pages.append({
                "slide_id": item.slide_id,
                "path": str(confirmed.resolve()),
                "sha256": sha256(confirmed),
            })
    return {
        "schema": PAGE_CONTEXT_SCHEMA,
        "caller": "ey-deck-design",
        "slide_id": page.slide_id,
        "canvas": "0 0 1280 720",
        "composition_space": {
            "mode": "full-slide",
            "canvas": "0 0 1280 720",
            "placeholder_bounds_role": "native-metadata-only",
            "global_content_cap": None,
            "check_fixed_atom_overlap": False,
        },
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
        "candidate_plan": plan,
        "design_quality": design_quality_contract(),
        "confirmed_pages": confirmed_pages,
        "approved_content": section.rstrip(),
        "approved_content_sha256": text_sha256(section.rstrip()),
        "approved_content_source": str(paths.content.resolve()),
        "approved_content_source_sha256": sha256(paths.content),
        "template": {
            "workspace": str(TEMPLATE_ROOT.resolve()),
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
    plan = context.get("candidate_plan")
    if not isinstance(plan, dict) or plan.get("versions") != ["A"]:
        raise ValueError(f"page authoring context has no valid candidate plan: {context_path}")
    if not base_version and version not in plan["versions"]:
        raise ValueError(f"candidate version {version} is not requested by the page candidate plan")
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
