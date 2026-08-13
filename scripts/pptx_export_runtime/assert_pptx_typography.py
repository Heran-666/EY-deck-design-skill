#!/usr/bin/env python3
"""Verify slide and master text sizes in one confirmed-export PPTX."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from ey_typography_policy import ALLOWED_HPT, POLICY_SCHEMA, policy_payload


DML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PML_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
SLIDE_RE = re.compile(r"ppt/slides/slide\d+\.xml\Z")
MASTER_RE = re.compile(r"ppt/slideMasters/slideMaster\d+\.xml\Z")


def _format_pt(size_hpt: int) -> str:
    return f"{size_hpt / 100:g}"


def _parse_size(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _slide_number(name: str) -> int:
    return int(name.rsplit("slide", 1)[1].split(".xml", 1)[0])


def audit_pptx(
    path: Path,
    *,
    exempt_slide_numbers: set[int] | None = None,
) -> dict[str, object]:
    exemptions = exempt_slide_numbers or set()
    observed: Counter[int] = Counter()
    violations: list[str] = []
    try:
        with zipfile.ZipFile(path) as package:
            slide_names = sorted(
                (name for name in package.namelist() if SLIDE_RE.fullmatch(name)),
                key=_slide_number,
            )
            if not slide_names:
                raise ValueError("PPTX package has no slide XML")
            for slide_name in slide_names:
                if _slide_number(slide_name) in exemptions:
                    continue
                root = ET.fromstring(package.read(slide_name))
                for run_tag in ("r", "fld"):
                    for run in root.iter(f"{{{DML_NS}}}{run_tag}"):
                        text = "".join(
                            item.text or "" for item in run.iter(f"{{{DML_NS}}}t")
                        ).strip()
                        if not text or not text.replace("\u200b", ""):
                            continue
                        props = run.find(f"{{{DML_NS}}}rPr")
                        size_hpt = _parse_size(props.get("sz") if props is not None else None)
                        if size_hpt is None:
                            violations.append(
                                f"{slide_name} {text[:36]!r}: missing explicit run font size"
                            )
                            continue
                        observed[size_hpt] += 1
                        if size_hpt not in ALLOWED_HPT:
                            violations.append(
                                f"{slide_name} {text[:36]!r}: {_format_pt(size_hpt)}pt"
                            )

            for master_name in sorted(
                name for name in package.namelist() if MASTER_RE.fullmatch(name)
            ):
                root = ET.fromstring(package.read(master_name))
                text_styles = root.find(f".//{{{PML_NS}}}txStyles")
                if text_styles is None:
                    continue
                for props in text_styles.iter(f"{{{DML_NS}}}defRPr"):
                    size_hpt = _parse_size(props.get("sz"))
                    if size_hpt is not None and size_hpt not in ALLOWED_HPT:
                        violations.append(
                            f"{master_name} txStyles: {_format_pt(size_hpt)}pt"
                        )
    except (OSError, ET.ParseError, zipfile.BadZipFile, ValueError) as exc:
        raise ValueError(f"cannot audit PPTX typography: {exc}") from exc

    if violations:
        shown = "; ".join(violations[:8])
        more = len(violations) - 8
        suffix = f"; +{more} more" if more > 0 else ""
        raise ValueError(f"PPTX typography audit failed: {shown}{suffix}")

    return {
        **policy_payload(),
        "status": "PASS",
        "pptx_path": str(path.resolve()),
        "observed_run_count": sum(observed.values()),
        "observed_pptx_pt_counts": {
            _format_pt(size_hpt): count
            for size_hpt, count in sorted(observed.items(), reverse=True)
        },
        "fixed_asset_exempt_slide_numbers": sorted(exemptions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", type=Path, required=True)
    parser.add_argument("--exempt-slide-number", type=int, action="append", default=[])
    args = parser.parse_args()
    try:
        result = audit_pptx(
            args.pptx.expanduser().resolve(),
            exempt_slide_numbers=set(args.exempt_slide_number),
        )
    except ValueError as exc:
        print(json.dumps({
            "schema": POLICY_SCHEMA,
            "status": "BLOCKED",
            "reason": str(exc),
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
