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


XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


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
