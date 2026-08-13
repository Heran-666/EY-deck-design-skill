#!/usr/bin/env python3
"""Normalize confirmed-SVG text frames on isolated Stage 2 copies.

The pass is deliberately narrow:

1. Detect authored ``<text>`` elements that the merge-mode converter would
   split into multiple native PowerPoint text boxes.
2. Repair only a missing parent baseline that is already unambiguously defined
   by the first absolute-y line ``<tspan>``.
3. Materialize mergeable paragraph topology without splitting unresolved
   blocks.
4. Prove exact text identity against the untouched confirmed source copy.
5. Re-run the same topology prediction and block unresolved pages.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from svg_finalize.flatten_tspan import (
    PARAGRAPH_MARK_ATTR,
    flatten_text_with_tspans,
    parse_first_number,
)


SVG_NS = "http://www.w3.org/2000/svg"
SCHEMA = "ey-deck.text-frame-topology-normalization.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def is_line_tspan(element: ET.Element) -> bool:
    if local_name(element.tag) != "tspan":
        return False
    if element.get("x") is not None or element.get("y") is not None:
        return True
    dy = parse_first_number(element.get("dy"))
    return dy is not None and abs(dy) > 1e-9


def element_xpath(root: ET.Element, target: ET.Element) -> str:
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    parts: list[str] = []
    current: ET.Element | None = target
    while current is not None:
        tag = local_name(current.tag)
        parent = parents.get(current)
        if parent is None:
            parts.append(tag)
            break
        siblings = [child for child in list(parent) if local_name(child.tag) == tag]
        parts.append(f"{tag}[{siblings.index(current) + 1}]")
        current = parent
    return "/" + "/".join(reversed(parts))


def predict_output_count(text_element: ET.Element) -> int:
    wrapper = ET.Element(f"{{{SVG_NS}}}g")
    wrapper.append(copy.deepcopy(text_element))
    isolated = ET.Element(f"{{{SVG_NS}}}svg")
    isolated.append(wrapper)
    flatten_text_with_tspans(
        ET.ElementTree(isolated),
        merge_paragraphs=True,
        split_unmergeable=True,
    )
    return sum(1 for element in wrapper.iter(f"{{{SVG_NS}}}text"))


def topology_violations(root: ET.Element) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for ordinal, text_element in enumerate(
        root.iter(f"{{{SVG_NS}}}text"), start=1
    ):
        if not any(is_line_tspan(child) for child in list(text_element)):
            continue
        output_count = predict_output_count(text_element)
        if output_count <= 1:
            continue
        copy_id = (text_element.get("data-copy-id") or "").strip() or None
        element_id = (text_element.get("id") or "").strip() or None
        violations.append({
            "copy_id": copy_id,
            "element_id": element_id,
            "text_ordinal": ordinal,
            "xpath": element_xpath(root, text_element),
            "predicted_text_boxes": output_count,
        })
    return violations


def text_snapshot(root: ET.Element) -> list[dict[str, object]]:
    """Return ordered exact text evidence without depending on SVG formatting."""
    records: list[dict[str, object]] = []
    for ordinal, element in enumerate(root.iter(f"{{{SVG_NS}}}text"), start=1):
        records.append({
            "ordinal": ordinal,
            "copy_id": (element.get("data-copy-id") or "").strip() or None,
            "element_id": (element.get("id") or "").strip() or None,
            "text": "".join(element.itertext()),
        })
    return records


def _safe_parent_baseline_repairs(root: ET.Element) -> list[dict[str, object]]:
    repairs: list[dict[str, object]] = []
    for text_element in root.iter(f"{{{SVG_NS}}}text"):
        if text_element.get("y") is not None or (text_element.text or "").strip():
            continue
        children = list(text_element)
        if len(children) < 2 or any(local_name(child.tag) != "tspan" for child in children):
            continue
        starters = [child for child in children if is_line_tspan(child)]
        if len(starters) < 2 or starters[0] is not children[0]:
            continue
        if any(child.get("y") is None for child in starters):
            continue
        if any(
            child.get("dy") is not None
            and abs(parse_first_number(child.get("dy")) or 0.0) > 1e-9
            for child in starters
        ):
            continue
        first_y = parse_first_number(starters[0].get("y"))
        if first_y is None:
            continue
        baselines = [parse_first_number(child.get("y")) for child in starters]
        if any(value is None for value in baselines):
            continue
        numeric_baselines = [float(value) for value in baselines if value is not None]
        if any(current <= previous for previous, current in zip(numeric_baselines, numeric_baselines[1:])):
            continue
        raw_first_y = str(starters[0].get("y"))
        text_element.set("y", raw_first_y)
        repairs.append({
            "copy_id": (text_element.get("data-copy-id") or "").strip() or None,
            "element_id": (text_element.get("id") or "").strip() or None,
            "xpath": element_xpath(root, text_element),
            "parent_y": raw_first_y,
            "reason": "parent baseline inherited from the unchanged first absolute-y line",
        })
    return repairs


def normalize_page(source: Path, destination: Path) -> dict[str, object]:
    source_root = ET.parse(source).getroot()
    tree = ET.parse(destination)
    root = tree.getroot()
    source_snapshot = text_snapshot(source_root)
    before_sha256 = sha256(destination)
    if (source_root.get("data-ey-fixed-ending") or "").strip().lower() == "true":
        exact_copy_passed = source.read_bytes() == destination.read_bytes()
        return {
            "source_path": str(source.resolve()),
            "source_sha256": sha256(source),
            "normalized_path": str(destination.resolve()),
            "input_normalized_sha256": before_sha256,
            "normalized_sha256": sha256(destination),
            "detected_before": [],
            "parent_baseline_repairs": [],
            "paragraph_blocks_normalized": 0,
            "exact_copy": {
                "status": "PASS" if exact_copy_passed else "FAIL",
                "source_text_frames": len(source_snapshot),
                "normalized_text_frames": len(text_snapshot(root)),
            },
            "detected_after": [],
            "fixed_asset_exception": "ending-source-topology-preserved",
            "status": "PASS" if exact_copy_passed else "BLOCKED",
        }
    # Detect against the untouched confirmed source before applying any
    # topology rewrite to the isolated working copy.
    before_violations = topology_violations(source_root)
    paragraph_marks_before = sum(
        element.get(PARAGRAPH_MARK_ATTR) is not None
        for element in root.iter(f"{{{SVG_NS}}}text")
    )
    baseline_repairs = _safe_parent_baseline_repairs(root)
    changed = flatten_text_with_tspans(
        tree,
        merge_paragraphs=True,
        split_unmergeable=False,
    )
    paragraph_marks_after = sum(
        element.get(PARAGRAPH_MARK_ATTR) is not None
        for element in root.iter(f"{{{SVG_NS}}}text")
    )
    if changed or baseline_repairs:
        ET.register_namespace("", SVG_NS)
        tree.write(destination, encoding="unicode", xml_declaration=False)
        with destination.open("a", encoding="utf-8") as handle:
            handle.write("\n")
    normalized_root = ET.parse(destination).getroot()
    normalized_snapshot = text_snapshot(normalized_root)
    exact_copy_passed = normalized_snapshot == source_snapshot
    after_violations = topology_violations(normalized_root)
    return {
        "source_path": str(source.resolve()),
        "source_sha256": sha256(source),
        "normalized_path": str(destination.resolve()),
        "input_normalized_sha256": before_sha256,
        "normalized_sha256": sha256(destination),
        "detected_before": before_violations,
        "parent_baseline_repairs": baseline_repairs,
        "paragraph_blocks_normalized": paragraph_marks_after - paragraph_marks_before,
        "exact_copy": {
            "status": "PASS" if exact_copy_passed else "FAIL",
            "source_text_frames": len(source_snapshot),
            "normalized_text_frames": len(normalized_snapshot),
        },
        "detected_after": after_violations,
        "status": (
            "PASS"
            if exact_copy_passed and not after_violations
            else "BLOCKED"
        ),
    }


def normalize_project(project_dir: Path) -> dict[str, object]:
    project_dir = project_dir.resolve()
    manifest_path = project_dir / "confirmed-svg-export.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = manifest.get("page_order")
    if not isinstance(pages, list) or not pages:
        raise ValueError("confirmed export manifest has no page order")
    results: list[dict[str, object]] = []
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("confirmed export manifest has an invalid page record")
        source = Path(str(page.get("source_path", ""))).resolve()
        destination = Path(str(page.get("normalized_path", ""))).resolve()
        for path in (source, destination):
            path.relative_to(project_dir)
            if not path.is_file():
                raise ValueError(f"confirmed export topology input is missing: {path}")
        result = normalize_page(source, destination)
        result.update({
            "page": page.get("page"),
            "source_slide_id": page.get("source_slide_id"),
        })
        page["normalized_sha256"] = result["normalized_sha256"]
        page["text_frame_topology"] = {
            "schema": SCHEMA,
            "status": result["status"],
            "normalized_sha256": result["normalized_sha256"],
        }
        results.append(result)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    blocked = [
        str(result.get("source_slide_id"))
        for result in results
        if result.get("status") != "PASS"
    ]
    payload = {
        "schema": SCHEMA,
        "status": "PASS" if not blocked else "BLOCKED",
        "project_dir": str(project_dir),
        "pages": results,
        "blocked_slide_ids": blocked,
    }
    receipt_path = project_dir / "validation" / "text_frame_topology.json"
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize and verify confirmed SVG text-frame topology."
    )
    parser.add_argument("--project-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = normalize_project(args.project_dir)
    except (ET.ParseError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Text-frame topology normalization failed: {exc}")
        return 1
    if result["status"] != "PASS":
        failed = ", ".join(result["blocked_slide_ids"])
        print(
            "Text-frame topology normalization blocked: "
            f"{failed}; see validation/text_frame_topology.json"
        )
        return 2
    print("Text-frame topology normalization and exact-copy verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
