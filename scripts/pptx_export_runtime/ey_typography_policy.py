#!/usr/bin/env python3
"""Single-source EY typography scale for SVG authoring and PPTX export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_to_pptx.drawingml.text_properties import resolve_project_font_sizes
from svg_to_pptx.drawingml.utils import font_px_to_hpt


POLICY_SCHEMA = "ey-deck.typography-policy.v1"

# DrawingML stores font sizes in hundredths of a point.
ROLE_SIZES = (
    ("title", 2400, "32"),
    ("subtitle", 1800, "24"),
    ("body_heading_emphasis", 1400, "18.6667"),
    ("body_heading_compact", 1200, "16"),
    ("body_content_emphasis", 1000, "13.3333"),
    ("body_content_compact", 800, "10.6667"),
    ("other_information", 600, "8"),
)
ALLOWED_HPT = frozenset(size_hpt for _role, size_hpt, _svg_px in ROLE_SIZES)
BODY_MASTER_LEVELS_HPT = (1000, 1000, 800, 800, 800, 800, 800, 800, 800)
SPEC_LOCK_ROWS = (
    ("title", "32"),
    ("subtitle", "24"),
    ("body_heading_emphasis", "18.6667"),
    ("body_heading_compact", "16"),
    ("body", "13.3333"),
    ("body_content_compact", "10.6667"),
    ("other_information", "8"),
)
DEFINITION_CONTAINERS = frozenset({
    "clippath", "defs", "marker", "mask", "pattern", "symbol",
})


class TypographyPolicyError(ValueError):
    """Raised when visible text falls outside the EY typography scale."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _format_pt(size_hpt: int) -> str:
    return f"{size_hpt / 100:g}"


def typography_lock_rows() -> str:
    """Return the fixed spec-lock rows consumed by the PPTX theme builder."""
    return "\n".join(f"- {name}: {value}" for name, value in SPEC_LOCK_ROWS)


def policy_payload() -> dict[str, object]:
    return {
        "schema": POLICY_SCHEMA,
        "roles": [
            {"role": role, "pptx_pt": size_hpt / 100, "svg_px": svg_px}
            for role, size_hpt, svg_px in ROLE_SIZES
        ],
    }


def _visible_text_records(root: ET.Element) -> list[tuple[str, float]]:
    font_sizes = resolve_project_font_sizes(root)
    records: list[tuple[str, float]] = []

    def collect_text_object(element: ET.Element) -> None:
        def visit(node: ET.Element) -> None:
            if (node.text or "").strip():
                records.append(((node.text or "").strip(), font_sizes[id(node)]))
            for child in node:
                visit(child)
                if (child.tail or "").strip():
                    records.append(((child.tail or "").strip(), font_sizes[id(node)]))

        visit(element)

    def visit_visible(element: ET.Element) -> None:
        name = _local_name(element.tag)
        if name in DEFINITION_CONTAINERS:
            return
        if name == "text":
            collect_text_object(element)
            return
        for child in element:
            visit_visible(child)

    visit_visible(root)
    return records


def audit_svg_typography(path: Path) -> dict[str, object]:
    """Validate effective visible SVG sizes and return an auditable receipt."""
    try:
        root = ET.parse(path).getroot()
        records = _visible_text_records(root)
    except (OSError, ET.ParseError, ValueError) as exc:
        raise TypographyPolicyError(f"cannot resolve typography in {path}: {exc}") from exc

    observed: Counter[int] = Counter()
    violations: list[str] = []
    for text, size_px in records:
        try:
            size_hpt = font_px_to_hpt(size_px)
        except ValueError as exc:
            violations.append(f"{text[:36]!r}: {exc}")
            continue
        observed[size_hpt] += 1
        if size_hpt not in ALLOWED_HPT:
            violations.append(
                f"{text[:36]!r}: {size_px:g}px -> {_format_pt(size_hpt)}pt"
            )

    if violations:
        shown = "; ".join(violations[:6])
        more = len(violations) - 6
        suffix = f"; +{more} more" if more > 0 else ""
        allowed = "/".join(_format_pt(value) for value in sorted(ALLOWED_HPT, reverse=True))
        raise TypographyPolicyError(
            f"typography policy violation in {path.name}: {shown}{suffix}. "
            f"Allowed PPTX sizes are {allowed}pt; use the SVG px values in design-system.md."
        )

    return {
        **policy_payload(),
        "visible_text_fragment_count": sum(observed.values()),
        "observed_pptx_pt_counts": {
            _format_pt(size_hpt): count
            for size_hpt, count in sorted(observed.items(), reverse=True)
        },
    }
