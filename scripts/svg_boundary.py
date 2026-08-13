#!/usr/bin/env python3
"""Minimum self-contained SVG boundary shared by all workflow routes."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree


EXPORT_RUNTIME = Path(__file__).resolve().parent / "pptx_export_runtime"
sys.path.insert(0, str(EXPORT_RUNTIME))

from ey_typography_policy import TypographyPolicyError, audit_svg_typography
from svg_to_pptx.drawingml.text_properties import resolve_project_font_sizes
from svg_to_pptx.drawingml.utils import font_px_to_hpt


XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
ALLOWED_DENSITY_JUSTIFICATIONS = frozenset({"dense-table", "compact-matrix"})
NON_BODY_COPY_ID_TOKENS = frozenset({
    "title", "subtitle", "heading", "label", "number", "source", "footer",
    "footnote", "note", "citation", "disclaimer", "caption", "eyebrow", "tag",
})


def svg_error(path: Path) -> str | None:
    if not path.is_file():
        return f"missing SVG: {path}"
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError) as exc:
        return f"invalid SVG {path}: {exc}"
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return f"invalid SVG root element: {path}"
    if not (root.get("viewBox") or (root.get("width") and root.get("height"))):
        return f"SVG has no viewBox or dimensions: {path}"
    return None


def svg_self_contained_errors(path: Path) -> list[str]:
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return [f"cannot verify SVG self-containment: {path}"]

    errors: list[str] = []
    for element in root.iter():
        element_id = element.get("id") or element.tag.rsplit("}", 1)[-1]
        if element.get("data-icon"):
            errors.append(f"SVG is not self-contained: {element_id} uses data-icon")
        for attribute in ("href", XLINK_HREF):
            value = (element.get(attribute) or "").strip()
            if value and not value.startswith(("#", "data:")):
                errors.append(
                    f"SVG is not self-contained: {element_id} has external {attribute}={value}"
                )
        css_sources = [
            value for name, value in element.attrib.items() if name not in {"href", XLINK_HREF}
        ]
        if element.tag.rsplit("}", 1)[-1].lower() == "style":
            css_sources.append(element.text or "")
        for css_source in css_sources:
            for _, target in CSS_URL_PATTERN.findall(css_source):
                value = target.strip()
                if value and not value.startswith(("#", "data:")):
                    errors.append(
                        f"SVG is not self-contained: {element_id} has external CSS url({value})"
                    )
    return errors


def candidate_errors(path: Path) -> list[str]:
    errors = protected_candidate_errors(path)
    if errors:
        return errors
    root = ElementTree.parse(path).getroot()
    has_stylesheet = any(
        element.tag.rsplit("}", 1)[-1].lower() == "style"
        for element in root.iter()
    )
    if has_stylesheet:
        errors.append(f"authored SVG must inline CSS and remove <style>: {path}")
    else:
        try:
            audit_svg_typography(path)
        except TypographyPolicyError as exc:
            errors.append(str(exc))
        errors.extend(content_fit_errors(path))
    return errors


def _rendered_line_count(text: ElementTree.Element) -> int:
    tspans = [
        child
        for child in text
        if child.tag.rsplit("}", 1)[-1].lower() == "tspan"
        and "".join(child.itertext()).strip()
    ]
    if not tspans:
        return 1
    explicit_lines = [
        child for child in tspans if child.get("x") is not None or child.get("dy") is not None
    ]
    return max(1, len(explicit_lines))


def content_fit_errors(path: Path) -> list[str]:
    """Reject visibly under-filled 8pt body blocks on content-layout pages."""
    try:
        root = ElementTree.parse(path).getroot()
        font_sizes = resolve_project_font_sizes(root)
    except (ElementTree.ParseError, OSError, ValueError):
        return []
    if (root.get("data-pptx-layout") or "").strip().lower() != "content":
        return []

    parent = {child: owner for owner in root.iter() for child in owner}
    errors: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "text":
            continue
        if not "".join(element.itertext()).strip():
            continue

        chain: list[ElementTree.Element] = []
        cursor: ElementTree.Element | None = element
        while cursor is not None:
            chain.append(cursor)
            cursor = parent.get(cursor)
        if any(item.get("data-pptx-layer") for item in chain):
            continue
        if any(item.get("data-copy-scope") == "template-fixed" for item in chain):
            continue

        copy_id = next(
            (item.get("data-copy-id") for item in chain if item.get("data-copy-id")),
            element.get("id") or "unbound-text",
        )
        normalized_id = str(copy_id).casefold()
        if any(token in normalized_id for token in NON_BODY_COPY_ID_TOKENS):
            continue
        try:
            size_hpt = font_px_to_hpt(font_sizes[id(element)])
        except (KeyError, ValueError):
            continue
        if size_hpt != 800:
            continue

        justification = next(
            (
                (item.get("data-density-justification") or "").strip().lower()
                for item in chain
                if item.get("data-density-justification")
            ),
            "",
        )
        if justification:
            if justification not in ALLOWED_DENSITY_JUSTIFICATIONS:
                errors.append(
                    f"content-fit policy has unsupported density justification "
                    f"{justification!r} on {copy_id}"
                )
            continue

        line_count = _rendered_line_count(element)
        if line_count <= 4:
            errors.append(
                f"content-fit policy: {copy_id} uses 8pt body copy in only "
                f"{line_count} rendered line(s); use 10pt, right-size/recompose the "
                "container, or add a genuine semantic element. Dense tables and compact "
                "matrices require an explicit data-density-justification."
            )
    return errors


def protected_candidate_errors(path: Path) -> list[str]:
    """Validate protected input without rewriting its internal CSS representation."""
    problem = svg_error(path)
    if problem:
        return [problem]
    errors = svg_self_contained_errors(path)
    root = ElementTree.parse(path).getroot()
    viewbox = re.sub(r"[\s,]+", " ", (root.get("viewBox") or "").strip())
    if viewbox != "0 0 1280 720":
        errors.append(f"SVG must use viewBox 0 0 1280 720: {path}")
    return errors


def svg_canvas(path: Path) -> tuple[float, float, float, float]:
    """Return canonical viewBox geometry; width/height spelling does not affect scale."""
    root = ElementTree.parse(path).getroot()
    parts = [item for item in re.split(r"[\s,]+", (root.get("viewBox") or "").strip()) if item]
    if len(parts) != 4:
        raise ValueError(f"SVG has no four-number viewBox: {path}")
    values = tuple(float(item) for item in parts)
    if values[2] <= 0 or values[3] <= 0:
        raise ValueError(f"SVG viewBox must have positive dimensions: {path}")
    return values
