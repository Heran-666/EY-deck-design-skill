#!/usr/bin/env python3
"""Canonical project paths shared by controller, migration, and recovery code."""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def working_paths(project_dir: Path, slide_id: str) -> tuple[Path, Path]:
    base = project_dir / "svg_working" / slide_id
    return base / "A.svg", base / "B.svg"


def selected_working_path(project_dir: Path, slide_id: str, version: str) -> Path:
    if not re.fullmatch(r"(?:A|B|R[1-9]\d*)", version):
        raise ValueError(f"unsupported SVG version for {slide_id}: {version}")
    return project_dir / "svg_working" / slide_id / f"{version}.svg"


def receipt_path(project_dir: Path, slide_id: str, kind: str) -> Path:
    return project_dir / "working" / "receipts" / f"{slide_id}-{kind}.json"


def page_author_result_path(project_dir: Path, slide_id: str, version: str) -> Path:
    return receipt_path(project_dir, slide_id, f"{version}-authoring")


def authoring_packet_paths(project_dir: Path, slide_id: str) -> tuple[Path, Path]:
    root = project_dir / "working" / "packets"
    return root / f"{slide_id}-authoring.md", root / f"{slide_id}-authoring.json"


def revision_active_path(project_dir: Path, slide_id: str) -> Path:
    return receipt_path(project_dir, slide_id, "revision-active")


def handoff_result_path(project_dir: Path) -> Path:
    return project_dir / "working" / "receipts" / "confirmed-export-handoff.json"


def export_root(project_dir: Path) -> Path:
    override = os.environ.get("EY_EXPORT_ROOT")
    root = Path(override).expanduser() if override else project_dir.parent / "ey-deck-exports"
    resolved = root.resolve()
    try:
        resolved.relative_to(project_dir.resolve())
    except ValueError:
        return resolved
    raise ValueError("EY export root must be outside the EY project directory")


def archive_items(project_dir: Path, label: str, paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    root = project_dir / "working" / "archive" / label / stamp
    root.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.move(str(path), str(root / path.name))
