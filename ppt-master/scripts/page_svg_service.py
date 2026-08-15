#!/usr/bin/env python3
"""Validate the composable PPT Master page-SVG request/result boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REQUEST_SCHEMA = "ppt-master.page-svg-request.v2"
RESULT_SCHEMA = "ppt-master.page-svg-result.v1"
VERSION_RE = re.compile(r"(?:A|B|R[1-9]\d*)")
DESIGN_QUALITY_PROFILE = "ey-executive-editorial-v2"
ICON_QUALITY_RULE = (
    "Add coherent icon elements at semantically appropriate positions when they improve recognition, "
    "scanning, or visual rhythm; omit them when they have no clear communication job."
)
VISIBLE_CANDIDATE_GATE = [
    "information_design",
    "page_composition",
    "art_direction_refinement",
    "full_slide_render_review",
    "source_repair_and_recheck",
]
INDEPENDENT_VARIANT_ROLES = {
    "A": "clarity-led-editorial",
    "B": "concept-led-spatial",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def load_request(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid request JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def _bound_file(payload: dict, field: str, hash_field: str, label: str) -> list[str]:
    path = Path(str(payload.get(field, "")))
    if not path.is_absolute() or not path.is_file():
        return [f"{label} must be an existing absolute file: {path}"]
    if payload.get(hash_field) != digest(path):
        return [f"{label} SHA-256 mismatch: {path}"]
    return []


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_text_list(value: object, minimum: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(_nonempty_text(item) for item in value)
    )


def design_contract_errors(request: dict, mode: object, version: object) -> list[str]:
    errors: list[str] = []
    quality = request.get("design_quality")
    if not isinstance(quality, dict):
        errors.append("design_quality must be an object")
    else:
        if quality.get("profile") != DESIGN_QUALITY_PROFILE:
            errors.append(f"design_quality.profile must be {DESIGN_QUALITY_PROFILE}")
        if not _nonempty_text(quality.get("target")):
            errors.append("design_quality.target must be non-empty")
        if not _nonempty_text_list(quality.get("must_have"), 6):
            errors.append("design_quality.must_have must contain at least six non-empty rules")
        elif ICON_QUALITY_RULE not in quality["must_have"]:
            errors.append("design_quality.must_have must contain the required semantic icon rule")
        if not _nonempty_text_list(quality.get("avoid"), 5):
            errors.append("design_quality.avoid must contain at least five non-empty rules")
        if quality.get("visible_candidate_gate") != VISIBLE_CANDIDATE_GATE:
            errors.append("design_quality.visible_candidate_gate must contain the required ordered P0 passes")

    direction = request.get("variant_direction")
    if not isinstance(direction, dict):
        errors.append("variant_direction must be an object")
        return errors
    if not _nonempty_text(direction.get("intent")) or not _nonempty_text(direction.get("adaptation_rule")):
        errors.append("variant_direction intent and adaptation_rule must be non-empty")
    if mode == "independent" and isinstance(version, str):
        expected = INDEPENDENT_VARIANT_ROLES.get(version)
        if direction.get("role") != expected:
            errors.append(f"variant_direction.role for {version} must be {expected}")
        if "base_version" in direction:
            errors.append("independent variant_direction must not contain base_version")
    elif mode == "revision":
        base = request.get("base")
        base_version = base.get("version") if isinstance(base, dict) else None
        if direction.get("role") != "revision":
            errors.append("revision variant_direction.role must be revision")
        if direction.get("base_version") != base_version:
            errors.append("revision variant_direction.base_version must match base.version")
    return errors


def request_errors(request: dict) -> list[str]:
    errors: list[str] = []
    if request.get("schema") != REQUEST_SCHEMA:
        errors.append(f"schema must be {REQUEST_SCHEMA}")
    if request.get("caller") != "ey-deck-design":
        errors.append("caller must be ey-deck-design")
    slide_id = request.get("slide_id")
    if not isinstance(slide_id, str) or not re.fullmatch(r"S\d{2}", slide_id):
        errors.append("slide_id must match SNN")
    version = request.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        errors.append("version must be A, B, or Rn")
    if request.get("canvas") != "0 0 1280 720":
        errors.append("canvas must be 0 0 1280 720")
    artifact = Path(str(request.get("artifact_path", "")))
    if not artifact.is_absolute() or artifact.suffix.lower() != ".svg":
        errors.append("artifact_path must be an absolute .svg path")
    content = request.get("approved_content")
    if not isinstance(content, str) or not content.strip():
        errors.append("approved_content must be non-empty")
    elif request.get("approved_content_sha256") != hashlib.sha256(content.encode("utf-8")).hexdigest():
        errors.append("approved_content SHA-256 mismatch")
    errors.extend(_bound_file(request, "approved_content_source", "approved_content_source_sha256", "approved content source"))
    template = request.get("template")
    if not isinstance(template, dict):
        errors.append("template must be an object")
    else:
        errors.extend(_bound_file(template, "prototype", "prototype_sha256", "template prototype"))
    mode = request.get("mode")
    base = request.get("base")
    feedback = request.get("feedback")
    if mode == "independent":
        if version not in {"A", "B"} or base is not None or feedback is not None:
            errors.append("independent mode requires A/B with null base and feedback")
    elif mode == "revision":
        if not isinstance(version, str) or not version.startswith("R"):
            errors.append("revision mode requires an Rn version")
        if not isinstance(base, dict):
            errors.append("revision mode requires a base object")
        else:
            if not isinstance(base.get("version"), str) or not VERSION_RE.fullmatch(base["version"]):
                errors.append("revision base.version must be A, B, or Rn")
            errors.extend(_bound_file(base, "path", "sha256", "revision base"))
        if not isinstance(feedback, str) or not feedback.strip():
            errors.append("revision mode requires non-empty feedback")
    else:
        errors.append("mode must be independent or revision")
    errors.extend(design_contract_errors(request, mode, version))
    return errors


def artifact_errors(path: Path) -> list[str]:
    if not path.is_file():
        return [f"artifact not found: {path}"]
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"invalid SVG XML: {exc}"]
    errors: list[str] = []
    if root.tag.rsplit("}", 1)[-1] != "svg":
        errors.append("artifact root must be svg")
    if " ".join(root.attrib.get("viewBox", "").replace(",", " ").split()) != "0 0 1280 720":
        errors.append("artifact viewBox must be 0 0 1280 720")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"style", "script", "foreignObject"}:
            errors.append(f"artifact contains forbidden <{tag}>")
        href = element.attrib.get("href") or element.attrib.get("{http://www.w3.org/1999/xlink}href")
        if href and re.match(r"(?i)^(?:https?:)?//", href):
            errors.append(f"artifact contains remote URL: {href}")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate-request", "complete"))
    parser.add_argument("request", type=Path)
    args = parser.parse_args()
    try:
        request = load_request(args.request.resolve())
        errors = request_errors(request)
        if errors:
            raise ValueError(" | ".join(errors))
        if args.command == "validate-request":
            print(json.dumps({"status": "VALID", "schema": REQUEST_SCHEMA}, ensure_ascii=False))
            return 0
        artifact = Path(request["artifact_path"])
        errors = artifact_errors(artifact)
        if errors:
            raise ValueError(" | ".join(errors))
        print(
            json.dumps(
                {
                    "schema": RESULT_SCHEMA,
                    "status": "COMPLETE",
                    "slide_id": request["slide_id"],
                    "version": request["version"],
                    "artifact_path": str(artifact.resolve()),
                    "artifact_sha256": digest(artifact),
                    "request_sha256": digest(args.request.resolve()),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except ValueError as exc:
        print(json.dumps({"schema": RESULT_SCHEMA, "status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
