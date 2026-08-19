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

from svg_quality_checker import SVGQualityChecker
from svg_finalize.flatten_tspan import text_carrier_integrity_errors


REQUEST_SCHEMA = "ppt-master.page-svg-request.v3"
LEGACY_REQUEST_SCHEMA = "ppt-master.page-svg-request.v2"
PAGE_CONTEXT_SCHEMA = "ey-deck.page-authoring-context.v5"
RESULT_SCHEMA = "ppt-master.page-svg-result.v1"
VERSION_RE = re.compile(r"(?:A|B|R[1-9]\d*)")
DESIGN_QUALITY_PROFILE = "ey-executive-editorial-v3"
CANDIDATE_PLAN_POLICY = "single-svg-review-v1"
ICON_QUALITY_RULE = (
    "Add coherent icon elements at semantically appropriate positions when they improve recognition, "
    "scanning, or visual rhythm; omit them when they have no clear communication job."
)
VISIBLE_CANDIDATE_GATE = [
    "information_design",
    "page_composition",
    "art_direction_refinement",
    "source_svg_full_slide_review",
    "source_repair_and_recheck",
]
FULL_SLIDE_COMPOSITION = {
    "mode": "full-slide",
    "canvas": "0 0 1280 720",
    "placeholder_bounds_role": "native-metadata-only",
    "global_content_cap": None,
    "check_fixed_atom_overlap": False,
}
STRUCTURAL_PAGE_TYPES = {
    "cover",
    "agenda",
    "section divider",
    "divider",
    "ending",
    "closing",
    "closing page",
    "protected placeholder",
}
PAGE_LOGIC_KEYS = {
    "page_objective",
    "audience_move",
    "reasoning_pattern",
    "argument_chain",
    "relationship_constraints",
    "argument_priority",
}
READING_MODES = {"text", "balanced", "presentation"}
PAGE_RHYTHMS = {"anchor", "dense", "breathing"}
BLOCKING_TEXT_WARNING_MARKERS = (
    "paragraph-like line run(s) split across sibling <text> elements",
    "multi-line <text> with leading direct text that cannot be normalized into one PPT text frame",
)


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


def _normalized_page_type(request: dict) -> str:
    context = request.get("page_context")
    value = context.get("page_type", "") if isinstance(context, dict) else ""
    return " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())


def _authoring_context(request: dict) -> tuple[dict, list[str]]:
    if request.get("schema") == LEGACY_REQUEST_SCHEMA:
        return request, []
    descriptor = request.get("authoring_context")
    if not isinstance(descriptor, dict):
        return {}, ["authoring_context must be an object"]
    errors = _bound_file(
        descriptor,
        "path",
        "sha256",
        "page authoring context",
    )
    if errors:
        return {}, errors
    try:
        context = load_request(Path(str(descriptor["path"])))
    except ValueError as exc:
        return {}, [str(exc)]
    if context.get("schema") != PAGE_CONTEXT_SCHEMA:
        errors.append(f"page authoring context schema must be {PAGE_CONTEXT_SCHEMA}")
    if context.get("caller") != "ey-deck-design":
        errors.append("page authoring context caller must be ey-deck-design")
    if context.get("slide_id") != request.get("slide_id"):
        errors.append("page authoring context slide_id must match request slide_id")
    return context, errors


def design_contract_errors(request: dict) -> list[str]:
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
        if quality.get("visible_candidate_gate") != VISIBLE_CANDIDATE_GATE:
            errors.append("design_quality.visible_candidate_gate must contain the required ordered P0 passes")
    return errors


def page_logic_errors(request: dict) -> list[str]:
    logic = request.get("page_logic")
    if _normalized_page_type(request) in STRUCTURAL_PAGE_TYPES:
        return [] if logic is None else ["structural page must not contain page_logic"]
    if not isinstance(logic, dict):
        return ["substantive page requires page_logic"]
    errors: list[str] = []
    if set(logic) != PAGE_LOGIC_KEYS:
        errors.append("page_logic must contain exactly the required semantic fields")
    for key in PAGE_LOGIC_KEYS:
        if not _nonempty_text(logic.get(key)):
            errors.append(f"page_logic.{key} must be non-empty")
    return errors


def execution_anchor_errors(request: dict) -> list[str]:
    errors: list[str] = []
    communication = request.get("communication")
    if not isinstance(communication, dict):
        return ["communication must be an object"]
    mode = communication.get("consumption_mode")
    if mode not in READING_MODES:
        errors.append("communication.consumption_mode must be text, balanced, or presentation")
    if not _nonempty_text(communication.get("objective")):
        errors.append("communication.objective must be non-empty")
    if not _nonempty_text(communication.get("core_message")):
        errors.append("communication.core_message must be non-empty")
    rhythm = request.get("page_rhythm")
    if rhythm not in PAGE_RHYTHMS:
        errors.append("page_rhythm must be anchor, dense, or breathing")
    elif _normalized_page_type(request) in STRUCTURAL_PAGE_TYPES and rhythm != "anchor":
        errors.append("structural page_rhythm must be anchor")
    elif _normalized_page_type(request) not in STRUCTURAL_PAGE_TYPES and rhythm == "anchor":
        errors.append("substantive page_rhythm must be dense or breathing")
    return errors


def request_errors(request: dict) -> list[str]:
    errors: list[str] = []
    if request.get("schema") not in {REQUEST_SCHEMA, LEGACY_REQUEST_SCHEMA}:
        errors.append(f"schema must be {REQUEST_SCHEMA}")
    if request.get("caller") != "ey-deck-design":
        errors.append("caller must be ey-deck-design")
    slide_id = request.get("slide_id")
    if not isinstance(slide_id, str) or not re.fullmatch(r"S\d{2}", slide_id):
        errors.append("slide_id must match SNN")
    version = request.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        errors.append("version must be A, B, or Rn")
    context, context_errors = _authoring_context(request)
    errors.extend(context_errors)
    if context.get("canvas") != "0 0 1280 720":
        errors.append("canvas must be 0 0 1280 720")
    if context.get("composition_space") != FULL_SLIDE_COMPOSITION:
        errors.append(
            "composition_space must enable unrestricted full-slide composition; "
            "placeholder bounds are native metadata only and fixed-atom overlap is not a QA gate"
        )
    plan = context.get("candidate_plan")
    if request.get("schema") == LEGACY_REQUEST_SCHEMA:
        planned_versions = (
            ["A"] if _normalized_page_type(context) in STRUCTURAL_PAGE_TYPES else ["A", "B"]
        )
    elif not isinstance(plan, dict):
        errors.append("candidate_plan must be an object")
        planned_versions = None
    else:
        planned_versions = plan.get("versions")
        if plan.get("policy") != CANDIDATE_PLAN_POLICY:
            errors.append(f"candidate_plan.policy must be {CANDIDATE_PLAN_POLICY}")
        if planned_versions != ["A"]:
            errors.append("candidate_plan.versions must be ['A']")
        if not _nonempty_text(plan.get("reason")):
            errors.append("candidate_plan reason must be non-empty")
    artifact = Path(str(request.get("artifact_path", "")))
    if not artifact.is_absolute() or artifact.suffix.lower() != ".svg":
        errors.append("artifact_path must be an absolute .svg path")
    content = context.get("approved_content")
    if not isinstance(content, str) or not content.strip():
        errors.append("approved_content must be non-empty")
    elif context.get("approved_content_sha256") != hashlib.sha256(content.encode("utf-8")).hexdigest():
        errors.append("approved_content SHA-256 mismatch")
    errors.extend(_bound_file(context, "approved_content_source", "approved_content_source_sha256", "approved content source"))
    template = context.get("template")
    if not isinstance(template, dict):
        errors.append("template must be an object")
    else:
        errors.extend(_bound_file(template, "prototype", "prototype_sha256", "template prototype"))
        design_spec = template.get("design_spec")
        if not isinstance(design_spec, dict):
            errors.append("template.design_spec must be an object")
        else:
            errors.extend(_bound_file(design_spec, "path", "sha256", "template design spec"))
    mode = request.get("mode")
    base = request.get("base")
    feedback = request.get("feedback")
    if mode == "independent":
        if version != "A" or base is not None or feedback is not None:
            errors.append("independent mode requires planned A with null base and feedback")
        if isinstance(planned_versions, list) and version not in planned_versions:
            errors.append("independent version must be included in candidate_plan.versions")
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
    errors.extend(design_contract_errors(context))
    if request.get("schema") != LEGACY_REQUEST_SCHEMA:
        errors.extend(execution_anchor_errors(context))
        errors.extend(page_logic_errors(context))
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
    errors.extend(
        f"artifact violates PPTX text-frame integrity: {message}"
        for message in text_carrier_integrity_errors(root)
    )
    # Page requests are bound to structured Master/Layout prototypes. Validate
    # that contract directly; Quick Generate is reserved for the later flat
    # export projection and would misclassify required structure metadata.
    quality = SVGQualityChecker().check_file(str(path))
    errors.extend(
        f"artifact quality: {message}"
        for message in quality.get("errors", [])
    )
    for warning in quality.get("warnings", []):
        if any(marker in warning for marker in BLOCKING_TEXT_WARNING_MARKERS):
            errors.append(f"artifact violates PPTX text-frame integrity: {warning}")
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
