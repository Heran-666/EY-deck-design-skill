#!/usr/bin/env python3
"""Candidate lifecycle and integrity rules for page-level SVG review."""

from __future__ import annotations

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from workflow_content import content_section
from workflow_io import now, read_json, sha256, text_sha256, write_json
from workflow_paths import ProjectPaths
from workflow_spec import is_substantive_page_type

PPT_MASTER_SCRIPTS = Path(__file__).resolve().parents[1] / "ppt-master" / "scripts"
if str(PPT_MASTER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PPT_MASTER_SCRIPTS))
from ey_svg_resources import resource_errors  # noqa: E402


INITIAL_VERSIONS = ("A",)
LEGACY_SUBSTANTIVE_VERSIONS = ("A", "B")
VERSION_RE = re.compile(r"(?:A|B|R[1-9]\d*)")
FORBIDDEN_TAGS = {"foreignObject", "script", "style"}
PAGE_CONTEXT_SCHEMA = "ey-deck.page-authoring-context.v6"
REQUEST_SCHEMAS = {
    "ppt-master.page-svg-request.v2",
    "ppt-master.page-svg-request.v4",
}


def initial_versions_for_page_type(page_type: str) -> tuple[str, ...]:
    """Return the single initial SVG version."""
    return INITIAL_VERSIONS


def legacy_initial_versions_for_page_type(page_type: str) -> tuple[str, ...]:
    """Recover a legacy cycle created before adaptive candidate planning."""
    return LEGACY_SUBSTANTIVE_VERSIONS if is_substantive_page_type(page_type) else INITIAL_VERSIONS


def require_version(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid SVG version: {version}")
    return version


def svg_errors(path: Path) -> list[str]:
    if not path.is_file():
        return [f"SVG candidate not found: {path}"]
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"invalid SVG XML: {exc}"]
    errors: list[str] = []
    if root.tag.rsplit("}", 1)[-1] != "svg":
        errors.append("candidate root must be <svg>")
    view_box = " ".join(root.attrib.get("viewBox", "").replace(",", " ").split())
    if view_box != "0 0 1280 720":
        errors.append('candidate viewBox must be exactly "0 0 1280 720"')
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in FORBIDDEN_TAGS:
            errors.append(f"candidate contains forbidden <{tag}>")
        href = element.attrib.get("href") or element.attrib.get("{http://www.w3.org/1999/xlink}href")
        if href and re.match(r"(?i)^(?:https?:)?//", href):
            errors.append(f"candidate contains external URL: {href}")
    errors.extend(resource_errors(root, path.read_bytes()))
    return list(dict.fromkeys(errors))


def candidate_valid(paths: ProjectPaths, slide_id: str, version: str) -> bool:
    require_version(version)
    packet = paths.packet(slide_id, version)
    artifact = paths.candidate(slide_id, version)
    receipt_path = paths.candidate_receipt(slide_id, version)
    if not packet.is_file() or not artifact.is_file() or not receipt_path.is_file():
        return False
    try:
        receipt = read_json(receipt_path)
        request = read_json(packet)
    except ValueError:
        return False
    if request.get("schema") == "ppt-master.page-svg-request.v4":
        descriptor = request.get("authoring_context")
        if not isinstance(descriptor, dict):
            return False
        context_path = paths.page_context(slide_id)
        if (
            descriptor.get("path") != str(context_path.resolve())
            or not context_path.is_file()
            or descriptor.get("sha256") != sha256(context_path)
        ):
            return False
        try:
            context = read_json(context_path)
        except ValueError:
            return False
        approved_content_sha256 = context.get("approved_content_sha256")
        context_valid = (
            context.get("schema") == PAGE_CONTEXT_SCHEMA
            and context.get("caller") == "ey-deck-design"
            and context.get("slide_id") == slide_id
        )
    else:
        approved_content_sha256 = request.get("approved_content_sha256")
        context_valid = request.get("schema") == "ppt-master.page-svg-request.v2"
    return (
        receipt.get("schema") in {"ey-deck.svg-candidate.v1", "ey-deck.svg-candidate.v2"}
        and receipt.get("slide_id") == slide_id
        and receipt.get("version") == version
        and receipt.get("packet_sha256") == sha256(packet)
        and receipt.get("artifact_sha256") == sha256(artifact)
        and request.get("schema") in REQUEST_SCHEMAS
        and request.get("caller") == "ey-deck-design"
        and request.get("slide_id") == slide_id
        and request.get("version") == version
        and request.get("artifact_path") == str(artifact.resolve())
        and context_valid
        and approved_content_sha256
        == text_sha256(content_section(paths.content.read_text(encoding="utf-8"), slide_id).rstrip())
        and not svg_errors(artifact)
    )


def record_candidate(
    paths: ProjectPaths,
    slide_id: str,
    version: str,
    *,
    packet_sha256: str,
    artifact_sha256: str,
) -> None:
    """Persist the exact request and artifact accepted by PPT Master complete."""
    require_version(version)
    packet = paths.packet(slide_id, version)
    artifact = paths.candidate(slide_id, version)
    if not packet.is_file() or not artifact.is_file():
        raise ValueError("candidate request or artifact disappeared after validation")
    if sha256(packet) != packet_sha256 or sha256(artifact) != artifact_sha256:
        raise ValueError("candidate request or artifact changed after validation")
    write_json(
        paths.candidate_receipt(slide_id, version),
        {
            "schema": "ey-deck.svg-candidate.v2",
            "slide_id": slide_id,
            "version": version,
            "packet_sha256": packet_sha256,
            "artifact_path": str(artifact.resolve()),
            "artifact_sha256": artifact_sha256,
            "recorded_at": now(),
        },
    )


def revision_versions(paths: ProjectPaths, slide_id: str) -> list[str]:
    directory = paths.packet(slide_id, "R1").parent
    if not directory.is_dir():
        return []
    versions = [path.stem for path in directory.glob("R*.json") if VERSION_RE.fullmatch(path.stem)]
    return sorted(versions, key=lambda item: int(item[1:]))


def next_revision(paths: ProjectPaths, slide_id: str) -> str:
    versions = revision_versions(paths, slide_id)
    return f"R{int(versions[-1][1:]) + 1}" if versions else "R1"


def latest_revision(paths: ProjectPaths, slide_id: str) -> str | None:
    versions = revision_versions(paths, slide_id)
    return versions[-1] if versions else None


def confirm_candidate(paths: ProjectPaths, slide_id: str, version: str, *, decision: dict | None = None) -> Path:
    if not candidate_valid(paths, slide_id, version):
        raise ValueError(f"{version} is not a valid current SVG candidate")
    if paths.decision_receipt(slide_id).is_file():
        previous = read_json(paths.decision_receipt(slide_id))
        previous_version = require_version(str(previous.get("confirmed_version", "")))
        history = paths.decision_receipt(slide_id).parent / "decisions" / f"{previous_version}.json"
        if history.is_file() and read_json(history) != previous:
            raise ValueError("prior SVG confirmation history does not match the current receipt")
        if not history.is_file():
            write_json(history, previous)
    source = paths.candidate(slide_id, version)
    target = paths.svg_output / f"{slide_id}.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    write_json(
        paths.decision_receipt(slide_id),
        {
            "schema": "ey-deck.svg-decision.v2",
            "slide_id": slide_id,
            "confirmed_version": version,
            "artifact_sha256": sha256(source),
            "confirmed_path": str(target.resolve()),
            "confirmed_at": now(),
            "decision_policy": decision or {"mode": "manual"},
        },
    )
    return target


def confirmation_valid(paths: ProjectPaths, slide_id: str) -> bool:
    receipt_path = paths.decision_receipt(slide_id)
    target = paths.svg_output / f"{slide_id}.svg"
    if not receipt_path.is_file() or not target.is_file():
        return False
    try:
        receipt = read_json(receipt_path)
        version = str(receipt.get("confirmed_version", ""))
    except ValueError:
        return False
    source = paths.candidate(slide_id, version)
    expected_hash = receipt.get("artifact_sha256") or receipt.get("candidate_sha256")
    return (
        receipt.get("schema") in {"ey-deck.svg-decision.v1", "ey-deck.svg-decision.v2"}
        and candidate_valid(paths, slide_id, version)
        and expected_hash == sha256(source)
        and expected_hash == sha256(target)
    )


def discard_cycle(paths: ProjectPaths, slide_id: str) -> None:
    """Delete one page's candidates and receipts before a clean restart."""
    sources = [
        paths.svg_dir(slide_id),
        paths.packet(slide_id, "A").parent,
        paths.template_prototype(slide_id).parent,
        paths.candidate_receipt(slide_id, "A").parent,
        paths.svg_output / f"{slide_id}.svg",
    ]
    for source in sources:
        if source.is_dir():
            shutil.rmtree(source)
        elif source.exists():
            source.unlink()
