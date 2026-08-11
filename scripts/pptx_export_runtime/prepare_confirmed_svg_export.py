#!/usr/bin/env python3
"""Prepare an isolated EY export project from an ordered confirmed-SVG handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from confirmed_svg_normalizer import NormalizationError, normalize_confirmed_svg
from ey_typography_policy import (
    TypographyPolicyError,
    audit_svg_typography,
    policy_payload,
    typography_lock_rows,
)


XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
FONT_FAMILY_RE = re.compile(r"(?:^|;)\s*font-family\s*:\s*([^;]+)", re.IGNORECASE)
COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def allowed_reference(value: str) -> bool:
    normalized = value.strip()
    return not normalized or normalized.startswith("#") or normalized.startswith("data:")


def parse_viewbox(value: str, path: Path) -> str:
    parts = [item for item in re.split(r"[\s,]+", value.strip()) if item]
    if len(parts) != 4:
        raise ValueError(f"confirmed SVG needs a four-number viewBox: {path}")
    try:
        numbers = tuple(float(item) for item in parts)
    except ValueError as exc:
        raise ValueError(f"confirmed SVG needs a numeric viewBox: {path}") from exc
    if not all(math.isfinite(item) for item in numbers) or numbers[2] <= 0 or numbers[3] <= 0:
        raise ValueError(f"confirmed SVG needs a finite positive viewBox: {path}")
    return " ".join(format(item, ".12g") for item in numbers)


def inspect_svg(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"invalid SVG {path}: {exc}") from exc
    if local_name(root.tag) != "svg":
        raise ValueError(f"not an SVG root: {path}")
    viewbox = parse_viewbox(root.get("viewBox") or "", path)

    external: list[str] = []
    fonts: list[str] = []
    colors: list[str] = []
    for element in root.iter():
        if element.get("data-icon"):
            external.append(f"data-icon={element.get('data-icon')}")
        for attribute in ("href", XLINK_HREF):
            value = element.get(attribute)
            if value is not None and not allowed_reference(value):
                external.append(f"{local_name(element.tag)} {attribute}={value}")
        style = element.get("style") or ""
        css_sources = [
            value
            for name, value in element.attrib.items()
            if name not in {"href", XLINK_HREF}
        ]
        if local_name(element.tag).lower() == "style":
            css_sources.append(element.text or "")
        for css_source in css_sources:
            for _, value in URL_RE.findall(css_source):
                if not allowed_reference(value):
                    external.append(f"style url({value})")
        family = element.get("font-family")
        if family:
            fonts.append(family)
        fonts.extend(FONT_FAMILY_RE.findall(style))
        for value in element.attrib.values():
            colors.extend(COLOR_RE.findall(value))
        colors.extend(COLOR_RE.findall(style))
    if external:
        raise ValueError(
            f"confirmed SVG is not self-contained: {path}: " + "; ".join(external[:8])
        )
    return {
        "viewbox": viewbox,
        "width": root.get("width") or viewbox.split()[2],
        "height": root.get("height") or viewbox.split()[3],
        "fonts": fonts,
        "colors": colors,
    }


def first_font(records: list[dict]) -> str:
    for record in records:
        for raw in record["fonts"]:
            value = str(raw).split(",", 1)[0].strip().strip("'\"")
            if value:
                return value
    return "Arial"


def color_roles(records: list[dict]) -> tuple[str, str, str]:
    colors = [str(color).upper() for record in records for color in record["colors"]]
    background = "#000000" if "#000000" in colors else (colors[0] if colors else "#FFFFFF")
    text = "#FFFFFF" if "#FFFFFF" in colors else next(
        (color for color in colors if color != background), "#000000"
    )
    accent = next((color for color in colors if color not in {background, text}), text)
    return background, text, accent


def format_name(viewbox: str) -> str:
    _, _, width, height = (float(value) for value in viewbox.split())
    ratio = width / height
    if abs(ratio - 16 / 9) < 0.01:
        return "ppt169"
    if abs(ratio - 4 / 3) < 0.01:
        return "ppt43"
    return "custom"


def build_lock(records: list[dict], page_count: int) -> str:
    viewbox = records[0]["viewbox"]
    font = first_font(records)
    typography_rows = typography_lock_rows()
    background, text, accent = color_roles(records)
    rhythm = "\n".join(f"- P{index:02d}: confirmed SVG" for index in range(1, page_count + 1))
    return f"""<!-- ppt-master-schema: spec-lock/v1 -->
# Execution Lock

## canvas
- viewBox: {viewbox}
- format: {format_name(viewbox)}

## communication
- audience: inherited from confirmed SVG handoff
- objective: export confirmed SVG pages without reinterpretation
- core_message: preserve confirmed SVG appearance and order
- consumption_mode: presentation

## mode
- mode: continuous

## visual_style
- visual_style: inherited from confirmed SVGs

## colors
- bg: {background}
- primary: {text}
- accent: {accent}
- text: {text}

## typography
- font_family: {font}
- title_family: {font}
- body_family: {font}
{typography_rows}

## icons
- library: none
- inventory: none

## page_rhythm
{rhythm}

## pptx_structure
- mode: flat

## forbidden
- storyline, content planning, page design, SVG authoring, web preview, staged confirmation
"""


def prepare(project_dir: Path, svg_paths: list[Path]) -> dict:
    project_dir = project_dir.resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        raise ValueError(f"fresh project directory is not empty: {project_dir}")
    sources = [path.resolve() for path in svg_paths]
    if not sources:
        raise ValueError("at least one confirmed SVG is required")
    for path in sources:
        if not path.is_file() or path.suffix.lower() != ".svg":
            raise ValueError(f"confirmed SVG does not exist: {path}")
    source_slide_ids = [path.stem for path in sources]
    if len(set(source_slide_ids)) != len(source_slide_ids):
        raise ValueError("confirmed SVG filenames must have unique stems for failure recovery")
    source_records = [inspect_svg(path) for path in sources]
    viewboxes = {record["viewbox"] for record in source_records}
    if len(viewboxes) != 1:
        raise ValueError("all confirmed SVGs must use the same viewBox")

    original_dir = project_dir / "source_original"
    svg_dir = project_dir / "svg_output"
    original_dir.mkdir(parents=True, exist_ok=False)
    svg_dir.mkdir(parents=True, exist_ok=False)
    (project_dir / "exports").mkdir()
    (project_dir / "validation").mkdir()
    pages: list[dict] = []
    normalized_records: list[dict] = []
    observed_pptx_pt_counts: Counter[str] = Counter()
    for index, (source, source_slide_id) in enumerate(zip(sources, source_slide_ids), start=1):
        page = f"P{index:02d}"
        original = original_dir / f"{page}.svg"
        destination = svg_dir / f"P{index:02d}.svg"
        shutil.copy2(source, original)
        shutil.copy2(source, destination)
        normalization = normalize_confirmed_svg(destination)
        record = inspect_svg(destination)
        typography = audit_svg_typography(destination)
        observed_pptx_pt_counts.update(typography["observed_pptx_pt_counts"])
        normalized_records.append(record)
        pages.append({
            "page": page,
            "source_slide_id": source_slide_id,
            "input_name": source.name,
            "source_path": str(original.resolve()),
            "source_sha256": sha256(original),
            "normalized_path": str(destination.resolve()),
            "normalized_sha256": sha256(destination),
            "normalization": normalization,
            "typography": typography,
        })
    (project_dir / "spec_lock.md").write_text(
        build_lock(normalized_records, len(pages)), encoding="utf-8"
    )
    observed_colors = Counter(
        str(color).upper()
        for record in normalized_records
        for color in record["colors"]
    )
    manifest = {
        "schema": "ey-deck.confirmed-svg-export-runtime.v1",
        "page_order": pages,
        "source_policy": "confirmed SVGs are the sole page source",
        "observed_visual_values": {
            "colors": dict(sorted(observed_colors.items())),
        },
        "typography_policy": {
            **policy_payload(),
            "observed_pptx_pt_counts": dict(
                sorted(
                    observed_pptx_pt_counts.items(),
                    key=lambda item: float(item[0]),
                    reverse=True,
                )
            ),
        },
    }
    (project_dir / "confirmed-svg-export.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a fresh EY export project from ordered confirmed SVG files."
    )
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("svg", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        manifest = prepare(args.project_dir, args.svg)
    except TypographyPolicyError as exc:
        print(f"Confirmed SVG typography blocked: {exc}")
        return 3
    except (NormalizationError, OSError, ValueError) as exc:
        print(f"Confirmed SVG export preparation blocked: {exc}")
        return 1
    print(f"Prepared isolated confirmed-SVG export project: {args.project_dir.resolve()}")
    print("Page order: " + ", ".join(page["page"] for page in manifest["page_order"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
