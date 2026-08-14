#!/usr/bin/env python3
"""Persisted page design decisions, deck design memory, and independent visual QA."""

from __future__ import annotations

import json
from pathlib import Path

from framework_lib import PageEntry, h2_section, line_fields, page_entries
from preview_renderer import preview_paths, preview_receipt_errors
from workflow_content import content_section
from workflow_io import now, read_json, sha256, text_sha256, write_json
from workflow_paths import design_context_path, design_decision_path, visual_qa_path
from workflow_spec import (
    DESIGN_CONTEXT_SCHEMA,
    DESIGN_DECISION_SCHEMA,
    VISUAL_QA_SCHEMA,
    WORKFLOW_VERSION,
)


DESIGN_OWNER = "embedded-ppt-master-design"
DESIGN_MODULE_VERSION = "1.0"
DESIGN_LEAD_ROUTE = "ppt-master-design-lead"


DESIGN_POLICY_FILES = (
    "SKILL.md",
    "references/roles-and-stage-contracts.md",
    "references/ppt-master-design.md",
    "references/design-system.md",
    "references/composition-and-data-visual-language.md",
    "references/design-direction.md",
    "references/authoring-modes.md",
    "references/output-contract.md",
    "references/structured-template-profile.md",
    "references/page-svg-authoring.md",
    "references/visual-qa.md",
    "references/quality-gates.md",
)

DESIGN_PRINCIPLES = (
    "define one communication job, one primary claim, and one dominant page-scale visual mechanism",
    "choose reading mode and information model from the approved relationship, then use the simplest truthful editable form",
    "use hierarchy, asymmetry, scale, crop, rhythm, negative space, and one restrained EY gesture instead of UI-like card grids",
    "preserve approved copy, data, sources, semantic relationships, and structured-template atoms exactly",
    "judge each rendered candidate on its own; A/B difference is advisory and outside Visual QA",
)

DECISION_STRING_FIELDS = (
    "communication_job",
    "reading_mode",
    "primary_claim",
    "composition_family",
    "focal_mechanism",
    "information_model",
    "data_encoding",
    "typography_hierarchy",
    "ey_gesture",
    "density",
    "rationale",
)

QA_DIMENSIONS = (
    "composition_fidelity",
    "focal_hierarchy",
    "data_story",
    "brand_expression",
)

QA_ISSUE_CODE_DIMENSION = {
    "composition-fidelity": "composition_fidelity",
    "focal-hierarchy": "focal_hierarchy",
    "data-story": "data_story",
    "brand-expression": "brand_expression",
}

QA_ISSUE_TEXT = {
    "composition-fidelity": "Rendered candidate does not faithfully realize its persisted composition decision.",
    "focal-hierarchy": "Rendered candidate does not establish the committed first, second, and supporting read.",
    "data-story": "Rendered candidate does not communicate the approved data relationship truthfully and legibly.",
    "brand-expression": "Rendered candidate does not apply the committed EY gesture, typography, contrast, or negative space coherently.",
}


def design_page_fingerprint(page: PageEntry) -> str:
    stable = {
        "slide_id": page.slide_id,
        "title": page.title,
        "fields": {
            key: value
            for key, value in page.fields.items()
            if key not in {"Status", "Confirmed version"}
        },
    }
    return text_sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True))


def design_workflow_enabled(text: str) -> bool:
    current = line_fields(h2_section(text, "Current position"))
    return current.get("Workflow version") == WORKFLOW_VERSION


def design_policy_manifest() -> dict:
    skill_root = Path(__file__).resolve().parents[1]
    files: list[dict[str, str]] = []
    for relative in DESIGN_POLICY_FILES:
        path = skill_root / relative
        if not path.is_file():
            raise ValueError(f"design policy file is missing: {path}")
        files.append({
            "path": str(path.resolve()),
            "sha256": sha256(path),
        })
    manifest = {
        "workflow_version": WORKFLOW_VERSION,
        "design_owner": DESIGN_OWNER,
        "design_module_version": DESIGN_MODULE_VERSION,
        "files": files,
    }
    manifest["fingerprint"] = text_sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    )
    return manifest


def _decision_summary(payload: dict) -> dict:
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    return {
        "slide_id": payload.get("slide_id"),
        "version": payload.get("version"),
        "reading_mode": decision.get("reading_mode"),
        "composition_family": decision.get("composition_family"),
        "focal_mechanism": decision.get("focal_mechanism"),
        "information_model": decision.get("information_model"),
        "data_encoding": decision.get("data_encoding"),
        "ey_gesture": decision.get("ey_gesture"),
        "density": decision.get("density"),
    }


def deck_design_memory(text: str, project_dir: Path, page: PageEntry, version: str) -> dict:
    pages = page_entries(text)
    index = next(i for i, item in enumerate(pages) if item.slide_id == page.slide_id)
    recent: list[dict] = []
    for prior in pages[:index]:
        confirmed = prior.fields.get("Confirmed version", "")
        if not confirmed or confirmed == "Pending":
            continue
        decision = current_design_decision(project_dir, prior, confirmed, require_context=False)
        if decision:
            recent.append(_decision_summary(decision))
    same_page: list[dict] = []
    if version != "A":
        for candidate in ("A", "B"):
            if candidate == version:
                continue
            decision = current_design_decision(project_dir, page, candidate, require_context=False)
            if decision:
                same_page.append(_decision_summary(decision))
    adjacent = []
    for item in pages[max(0, index - 1):min(len(pages), index + 2)]:
        adjacent.append({
            "slide_id": item.slide_id,
            "title": item.title,
            "narrative_role": item.fields.get("Narrative role", "Missing"),
            "status": item.fields.get("Status", "Missing"),
        })
    return {
        "recent_confirmed_designs": recent[-3:],
        "same_page_prior_candidates": same_page,
        "adjacent_pages": adjacent,
        "rhythm_note": (
            "Use this memory to maintain deck rhythm and avoid accidental repetition. It is design context, "
            "not a deterministic constraint; it must not turn A/B similarity into a blocking gate."
        ),
    }


def ensure_design_context(text: str, project_dir: Path, page: PageEntry, version: str) -> dict:
    content_path = project_dir / "content.md"
    if not content_path.is_file():
        raise ValueError(f"approved content is missing for {page.slide_id}")
    section = content_section(content_path.read_text(encoding="utf-8"), page.slide_id)
    if not section:
        raise ValueError(f"approved content section is missing for {page.slide_id}")
    policy = design_policy_manifest()
    payload = {
        "schema": DESIGN_CONTEXT_SCHEMA,
        "design_owner": DESIGN_OWNER,
        "design_module_version": DESIGN_MODULE_VERSION,
        "design_roles": {
            "lead": DESIGN_LEAD_ROUTE,
            "producer": "ppt-master-svg-producer",
            "review": "independent-visual-qa",
            "export_runtime": "ppt-master-export-runtime",
        },
        "slide_id": page.slide_id,
        "version": version,
        "framework_design_fingerprint": design_page_fingerprint(page),
        "approved_content": section,
        "approved_content_sha256": text_sha256(section),
        "page_fields": {
            key: page.fields.get(key, "Missing")
            for key in (
                "Chapter",
                "Page type",
                "Authoring mode",
                "Narrative role",
                "Next connection",
            )
        },
        "design_principles": list(DESIGN_PRINCIPLES),
        "design_policy_manifest": policy,
        "deck_design_memory": deck_design_memory(text, project_dir, page, version),
        "candidate_policy": (
            "Design this candidate on its own merits. Standard A/B distinction remains advisory and non-blocking."
        ),
        "created_at": now(),
    }
    path = design_context_path(project_dir, page.slide_id, version)
    write_json(path, payload)
    return payload


def current_design_context(project_dir: Path, page: PageEntry, version: str) -> dict | None:
    path = design_context_path(project_dir, page.slide_id, version)
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
        current_policy = design_policy_manifest()
        approved = content_section(
            (project_dir / "content.md").read_text(encoding="utf-8"),
            page.slide_id,
        )
    except (OSError, ValueError):
        return None
    if (
        payload.get("schema") != DESIGN_CONTEXT_SCHEMA
        or payload.get("design_owner") != DESIGN_OWNER
        or payload.get("design_module_version") != DESIGN_MODULE_VERSION
        or payload.get("design_roles") != {
            "lead": DESIGN_LEAD_ROUTE,
            "producer": "ppt-master-svg-producer",
            "review": "independent-visual-qa",
            "export_runtime": "ppt-master-export-runtime",
        }
        or payload.get("slide_id") != page.slide_id
        or payload.get("version") != version
        or payload.get("framework_design_fingerprint") != design_page_fingerprint(page)
        or payload.get("approved_content_sha256") != text_sha256(approved)
        or payload.get("design_policy_manifest") != current_policy
        or payload.get("design_principles") != list(DESIGN_PRINCIPLES)
    ):
        return None
    return payload


def decision_fingerprint(decision: dict) -> str:
    return text_sha256(json.dumps(decision, ensure_ascii=False, sort_keys=True))


def record_design_decision(
    project_dir: Path,
    page: PageEntry,
    version: str,
    raw: str,
) -> dict:
    context = current_design_context(project_dir, page, version)
    if context is None:
        raise ValueError("design decision requires the current hash-bound design context")
    try:
        incoming = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"design decision is not valid JSON: {exc}") from exc
    if not isinstance(incoming, dict) or incoming.get("status") != "COMPLETE":
        raise ValueError("design decision must be one COMPLETE JSON object")
    if incoming.get("route") != DESIGN_LEAD_ROUTE:
        raise ValueError(f"design decision route must be {DESIGN_LEAD_ROUTE}")
    decision = incoming.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("design decision must contain a decision object")
    missing = [
        field for field in DECISION_STRING_FIELDS
        if not isinstance(decision.get(field), str) or not decision[field].strip()
    ]
    avoid = decision.get("avoid")
    if not isinstance(avoid, list) or any(not isinstance(item, str) or not item.strip() for item in avoid):
        missing.append("avoid")
    if missing:
        raise ValueError("design decision has missing or invalid fields: " + ", ".join(missing))
    context_path = design_context_path(project_dir, page.slide_id, version)
    payload = {
        "schema": DESIGN_DECISION_SCHEMA,
        "status": "COMPLETE",
        "route": DESIGN_LEAD_ROUTE,
        "design_owner": DESIGN_OWNER,
        "design_module_version": DESIGN_MODULE_VERSION,
        "slide_id": page.slide_id,
        "version": version,
        "context_path": str(context_path.resolve()),
        "context_sha256": sha256(context_path),
        "design_policy_fingerprint": context["design_policy_manifest"]["fingerprint"],
        "decision": decision,
        "decision_fingerprint": decision_fingerprint(decision),
        "recorded_at": now(),
    }
    write_json(design_decision_path(project_dir, page.slide_id, version), payload)
    return payload


def current_design_decision(
    project_dir: Path,
    page: PageEntry,
    version: str,
    *,
    require_context: bool = True,
) -> dict | None:
    path = design_decision_path(project_dir, page.slide_id, version)
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
    except ValueError:
        return None
    context_path = design_context_path(project_dir, page.slide_id, version)
    context_ok = (
        context_path.is_file()
        and payload.get("context_path") == str(context_path.resolve())
        and payload.get("context_sha256") == sha256(context_path)
    )
    decision = payload.get("decision")
    if (
        payload.get("schema") != DESIGN_DECISION_SCHEMA
        or payload.get("status") != "COMPLETE"
        or payload.get("route") != DESIGN_LEAD_ROUTE
        or payload.get("design_owner") != DESIGN_OWNER
        or payload.get("design_module_version") != DESIGN_MODULE_VERSION
        or payload.get("slide_id") != page.slide_id
        or payload.get("version") != version
        or not isinstance(decision, dict)
        or payload.get("decision_fingerprint") != decision_fingerprint(decision)
        or (require_context and not context_ok)
    ):
        return None
    return payload


def visual_qa_receipt(project_dir: Path, page: PageEntry, version: str) -> dict | None:
    path = visual_qa_path(project_dir, page.slide_id, version)
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
    except ValueError:
        return None
    svg_path = project_dir / "svg_working" / page.slide_id / f"{version}.svg"
    preview_png, preview_receipt = preview_paths(project_dir, page.slide_id, version)
    decision_path = design_decision_path(project_dir, page.slide_id, version)
    if (
        not svg_path.is_file()
        or not preview_png.is_file()
        or not preview_receipt.is_file()
        or not decision_path.is_file()
        or payload.get("schema") != VISUAL_QA_SCHEMA
        or payload.get("design_owner") != DESIGN_OWNER
        or payload.get("design_module_version") != DESIGN_MODULE_VERSION
        or payload.get("slide_id") != page.slide_id
        or payload.get("version") != version
        or payload.get("artifact_sha256") != sha256(svg_path)
        or payload.get("preview_png_sha256") != sha256(preview_png)
        or payload.get("preview_receipt_sha256") != sha256(preview_receipt)
        or payload.get("design_decision_sha256") != sha256(decision_path)
        or preview_receipt_errors(project_dir, page.slide_id, version)
    ):
        return None
    return payload


def visual_qa_pass_valid(project_dir: Path, page: PageEntry, version: str) -> bool:
    payload = visual_qa_receipt(project_dir, page, version)
    return bool(payload and payload.get("status") == "PASS")


def record_visual_qa(project_dir: Path, page: PageEntry, version: str, raw: str) -> dict:
    try:
        incoming = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Visual QA result is not valid JSON: {exc}") from exc
    if not isinstance(incoming, dict) or incoming.get("route") != "independent-visual-qa":
        raise ValueError("Visual QA route must be independent-visual-qa")
    allowed_keys = {
        "status",
        "route",
        "scope",
        "issue_codes",
        *QA_DIMENSIONS,
    }
    unexpected = sorted(set(incoming) - allowed_keys)
    if unexpected:
        raise ValueError("Visual QA contains unsupported fields: " + ", ".join(unexpected))
    if incoming.get("scope") != "single-candidate-only":
        raise ValueError("Visual QA scope must be single-candidate-only")
    status = incoming.get("status")
    if status not in {"PASS", "BLOCKED"}:
        raise ValueError("Visual QA status must be PASS or BLOCKED")
    missing = [
        field for field in QA_DIMENSIONS
        if incoming.get(field) not in {"PASS", "BLOCKED"}
    ]
    issue_codes = incoming.get("issue_codes")
    if (
        not isinstance(issue_codes, list)
        or any(code not in QA_ISSUE_CODE_DIMENSION for code in issue_codes)
        or len(set(issue_codes)) != len(issue_codes)
    ):
        missing.append("issue_codes")
    if status == "PASS" and issue_codes:
        raise ValueError("PASS Visual QA must have an empty issue_codes list")
    if status == "PASS" and any(incoming[field] != "PASS" for field in QA_DIMENSIONS):
        raise ValueError("PASS Visual QA requires every review dimension to PASS")
    if status == "BLOCKED" and not issue_codes:
        raise ValueError("BLOCKED Visual QA must identify at least one single-candidate issue code")
    if status == "BLOCKED" and all(incoming[field] == "PASS" for field in QA_DIMENSIONS):
        raise ValueError("BLOCKED Visual QA requires at least one blocked review dimension")
    if missing:
        raise ValueError("Visual QA has missing or invalid fields: " + ", ".join(missing))
    if status == "BLOCKED":
        for code in issue_codes:
            dimension = QA_ISSUE_CODE_DIMENSION[code]
            if incoming[dimension] != "BLOCKED":
                raise ValueError(f"Visual QA issue code {code} requires {dimension}=BLOCKED")
    if current_design_decision(project_dir, page, version) is None:
        raise ValueError("Visual QA requires the current persisted Design Decision")
    if preview_receipt_errors(project_dir, page.slide_id, version):
        raise ValueError("Visual QA requires a current rendered preview")
    svg_path = project_dir / "svg_working" / page.slide_id / f"{version}.svg"
    preview_png, preview_receipt = preview_paths(project_dir, page.slide_id, version)
    decision_path = design_decision_path(project_dir, page.slide_id, version)
    payload = {
        "schema": VISUAL_QA_SCHEMA,
        "status": status,
        "route": "independent-visual-qa",
        "design_owner": DESIGN_OWNER,
        "design_module_version": DESIGN_MODULE_VERSION,
        "scope": "single-candidate-only",
        "slide_id": page.slide_id,
        "version": version,
        "artifact_sha256": sha256(svg_path),
        "preview_png": str(preview_png.resolve()),
        "preview_png_sha256": sha256(preview_png),
        "preview_receipt_sha256": sha256(preview_receipt),
        "design_decision_sha256": sha256(decision_path),
        **{field: incoming[field] for field in QA_DIMENSIONS},
        "issue_codes": issue_codes,
        "issues": [QA_ISSUE_TEXT[code] for code in issue_codes],
        "recorded_at": now(),
    }
    write_json(visual_qa_path(project_dir, page.slide_id, version), payload)
    return payload
