#!/usr/bin/env python3
"""Deterministic, evidence-backed controller for long EY deck projects."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import shutil
import tempfile
from pathlib import Path

from framework_lib import PageEntry, h2_section, line_fields, page_entries, replace_field
from validate_framework import validate as validate_framework
from validate_deck_blueprint import (
    validate as validate_blueprint,
    validate_collection as validate_blueprint_collection,
)
from preview_renderer import (
    PreviewError,
    preview_runtime_errors,
    preview_runtime_path,
    preview_paths,
    ensure_preview_pair,
)
from workflow_spec import (
    ACTION_EVENT,
    PAGE_PREFLIGHT_GATE_SCHEMA,
    PAGE_STATES,
    TERMINAL_STATES,
    WORKFLOW_VERSION,
)
from workflow_io import atomic_write, command_line, now, read_json, sha256, text_sha256, write_json
from workflow_paths import (
    archive_items,
    authoring_packet_paths,
    handoff_result_path,
    page_author_result_path,
    receipt_path,
    revision_active_path,
    selected_working_path,
    working_paths,
)
from svg_boundary import candidate_errors, protected_candidate_errors, svg_canvas, svg_error
from workflow_export import (
    inspect_export_workspace,
    prepare_export_workspace,
    validate_output_filename,
)
from workflow_doctor import export_runtime_binding, preview_failure_issue, run_doctor
from workflow_runtime import stage2_runtime_path, validate_stage2_runtime
from validate_terminal_result import validate_terminal_result
from workflow_content import (
    content_identity_errors,
    content_section,
    promote_provisional_content,
    provisional_content_errors,
    review_receipt_path,
)
from workflow_copy_contract import visible_copy_contract, visible_copy_errors
from workflow_preview_evidence import (
    ab_presentation_valid,
    presentation_preview_errors,
    preview_presentation_evidence,
)
from workflow_protected import (
    materialize_protected_pages,
    protected_artifact_valid,
    protected_canonical_evidence_valid,
)


MANAGED_START = "<!-- EY-DECK-DESIGN-WORKFLOW:START -->"
MANAGED_END = "<!-- EY-DECK-DESIGN-WORKFLOW:END -->"
LEGACY_MANAGED_START = "<!-- EY-PROPOSAL-WORKFLOW:START -->"
LEGACY_MANAGED_END = "<!-- EY-PROPOSAL-WORKFLOW:END -->"
EY_PAGE_AUTHORING_INSTRUCTION = (
    "Use EY Deck Design's bundled Page SVG Authoring contract. Create one complete candidate from "
    "the exact hash-bound locked page packet at the supplied path. Own concept, composition, "
    "construction, fit, and normal SVG quality; bind every visible text run to the packet's exact "
    "data-copy-id, emit only inline SVG attributes/styles with no <style> or class dependency, and "
    "do not initialize a project or enter PPTX export."
)
B_OPTION_KERNEL = (
    "B option kernel: design B independently from the same locked content, semantic Visual Direction, "
    "and EY page-authoring rules; do not optimize, critique, repair, or incrementally polish A. "
    "Use independent design judgment to produce a genuinely distinct realization while preserving all "
    "approved copy, data, sources, emphasis, semantic relationships, and fixed constraints. Compare "
    "with A only after drafting to confirm at least one material design difference and the same canvas."
)
PREPARE_AUTHORING_ACTIONS = {
    "PREPARE_SVG_A": "GENERATE_SVG_A",
    "PREPARE_SVG_B": "GENERATE_SVG_B",
    "PREPARE_SVG_REVISION": "GENERATE_SVG_REVISION",
}


def update_page(text: str, slide_id: str, updates: dict[str, str]) -> str:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    updated = page.text
    for field, value in updates.items():
        updated = replace_field(updated, field, value)
    return text.replace(page.text, updated, 1)


def update_page_title(text: str, slide_id: str, title: str) -> str:
    return re.sub(
        rf"^### {re.escape(slide_id)}｜.*$",
        f"### {slide_id}｜{title}",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def page_type(page: PageEntry) -> str:
    return page.fields.get("Page type", "").strip().lower()


def is_structural(page: PageEntry) -> bool:
    return page_type(page) in {"cover", "section divider"}


def is_agenda(page: PageEntry) -> bool:
    return page_type(page) == "agenda"


def is_body(page: PageEntry) -> bool:
    return not is_structural(page) and not is_agenda(page)


def unresolved(pages: list[PageEntry]) -> list[PageEntry]:
    return [page for page in pages if page.fields.get("Status") not in TERMINAL_STATES]


def derived_phase(text: str) -> str:
    pages = page_entries(text)
    if unresolved([page for page in pages if is_body(page)]):
        return "Stage 1 — Body page loop"
    if unresolved([page for page in pages if is_structural(page)]):
        return "Stage 1 — Structural page review"
    if unresolved([page for page in pages if is_agenda(page)]):
        return "Stage 1 — Agenda review"
    return "Stage 2 — EY confirmed SVG export"


def phase_pages(pages: list[PageEntry], phase: str) -> list[PageEntry]:
    if phase == "Stage 1 — Body page loop":
        return [page for page in pages if is_body(page)]
    if phase == "Stage 1 — Structural page review":
        return [page for page in pages if is_structural(page)]
    if phase == "Stage 1 — Agenda review":
        return [page for page in pages if is_agenda(page)]
    return []


def current_group(text: str) -> list[PageEntry]:
    pages = page_entries(text)
    phase = derived_phase(text)
    remaining = unresolved(phase_pages(pages, phase))
    if not remaining:
        return []
    first = remaining[0]
    if phase == "Stage 1 — Structural page review":
        return remaining
    if phase == "Stage 1 — Agenda review":
        return [first]
    if first.fields.get("Review mode") == "Batch":
        chapter = first.fields.get("Chapter")
        return [
            page
            for page in remaining
            if page.fields.get("Review mode") == "Batch" and page.fields.get("Chapter") == chapter
        ]
    return [first]


def active_revision(project_dir: Path, slide_id: str) -> dict | None:
    path = revision_active_path(project_dir, slide_id)
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
    except ValueError:
        return None
    return payload if payload.get("active") is True else None


def next_revision_id(project_dir: Path, slide_id: str) -> str:
    base = project_dir / "svg_working" / slide_id
    used: list[int] = []
    if base.is_dir():
        for path in base.glob("R*.svg"):
            match = re.fullmatch(r"R([1-9]\d*)\.svg", path.name)
            if match:
                used.append(int(match.group(1)))
    receipts = project_dir / "working" / "receipts"
    if receipts.is_dir():
        for path in receipts.glob(f"{slide_id}-R*-request.json"):
            match = re.fullmatch(rf"{re.escape(slide_id)}-R([1-9]\d*)-request\.json", path.name)
            if match:
                used.append(int(match.group(1)))
    return f"R{max(used, default=0) + 1}"


def revision_request_hash(request: dict) -> str:
    immutable = {
        key: request.get(key)
        for key in ("slide_id", "revision_id", "base_version", "base_sha256", "note", "created_at")
    }
    return text_sha256(json.dumps(immutable, ensure_ascii=False, sort_keys=True))


def current_authoring_packet(project_dir: Path, slide_id: str) -> dict | None:
    packet, receipt = authoring_packet_paths(project_dir, slide_id)
    if not packet.is_file() or not receipt.is_file():
        return None
    try:
        payload = read_json(receipt)
    except ValueError:
        return None
    try:
        contract = page_visible_copy_contract(project_dir, slide_id)
    except (OSError, ValueError):
        return None
    if (
        payload.get("slide_id") != slide_id
        or payload.get("packet_path") != str(packet.resolve())
        or payload.get("packet_sha256") != sha256(packet)
        or payload.get("visible_copy_contract_sha256") != contract.get("contract_sha256")
        or payload.get("visible_copy_contract") != contract
    ):
        return None
    return payload


def authoring_packet_valid(project_dir: Path, page: PageEntry) -> bool:
    packet = current_authoring_packet(project_dir, page.slide_id)
    return bool(packet and packet.get("framework_page_sha256") == text_sha256(page.text))


def page_visible_copy_contract(project_dir: Path, slide_id: str) -> dict:
    content_path = project_dir / "content.md"
    if not content_path.is_file():
        raise ValueError(f"approved content is missing for {slide_id}")
    section = content_section(content_path.read_text(encoding="utf-8"), slide_id)
    return visible_copy_contract(section, slide_id)


def page_author_completion_valid(project_dir: Path, slide_id: str, version: str) -> bool:
    path = page_author_result_path(project_dir, slide_id, version)
    artifact = selected_working_path(project_dir, slide_id, version)
    if not path.is_file() or not artifact.is_file():
        return False
    try:
        result = read_json(path)
    except ValueError:
        return False
    packet = current_authoring_packet(project_dir, slide_id)
    packet_matches = bool(
        packet
        and result.get("packet_path") == packet.get("packet_path")
        and result.get("packet_sha256") == packet.get("packet_sha256")
    )
    artifact_sha256 = sha256(artifact)
    base_valid = (
        result.get("status") == "COMPLETE"
        and result.get("route") == "page-svg-authoring"
        and result.get("slide_id") == slide_id
        and result.get("version") == version
        and result.get("artifact_path") == str(artifact.resolve())
        and result.get("artifact_sha256") == artifact_sha256
        and packet is not None
        and result.get("visible_copy_contract_sha256")
        == packet.get("visible_copy_contract_sha256")
        and packet_matches
    )
    if not base_valid:
        return False

    preflight = result.get("preflight_gate")
    if isinstance(preflight, dict) and (
        preflight.get("schema") == PAGE_PREFLIGHT_GATE_SCHEMA
        and preflight.get("status") == "PASS"
        and preflight.get("artifact_sha256") == artifact_sha256
        and preflight.get("visible_copy_contract_sha256")
        == packet.get("visible_copy_contract_sha256")
    ):
        return True

    # Backward-compatible fallback for receipts created before reusable
    # page-preflight evidence existed. New receipts take the hash-only path.
    return (
        not candidate_errors(artifact)
        and not visible_copy_errors(artifact, packet["visible_copy_contract"])
    )


def active_page_author_block(project_dir: Path, slide_id: str) -> dict | None:
    receipts = project_dir / "working" / "receipts"
    if not receipts.is_dir():
        return None
    candidates: list[dict] = []
    for path in receipts.glob(f"{slide_id}-*-authoring.json"):
        try:
            result = read_json(path)
        except ValueError:
            continue
        if result.get("status") == "BLOCKED" and result.get("active") is True:
            candidates.append(result)
    if not candidates:
        return None
    return max(candidates, key=lambda item: str(item.get("recorded_at", "")))


def parse_terminal_json(raw: str) -> dict:
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"terminal result is not valid JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("terminal result must be one JSON object")
    return result


def validate_ab(project_dir: Path, slide_id: str) -> tuple[list[str], dict | None]:
    errors: list[str] = []
    a_path, b_path = working_paths(project_dir, slide_id)
    try:
        contract = page_visible_copy_contract(project_dir, slide_id)
    except (OSError, ValueError) as exc:
        contract = None
        errors.append(str(exc))
    for version, path in (("A", a_path), ("B", b_path)):
        if page_author_completion_valid(project_dir, slide_id, version):
            continue
        before = len(errors)
        errors.extend(candidate_errors(path))
        if contract is not None and path.is_file():
            errors.extend(visible_copy_errors(path, contract))
        if len(errors) == before:
            errors.append(f"{slide_id} {version} has no valid hash-bound preflight receipt")
    if errors:
        return errors, None
    a_hash, b_hash = sha256(a_path), sha256(b_path)
    if svg_canvas(a_path) != svg_canvas(b_path):
        errors.append(f"{slide_id} A.svg and B.svg must use the same canvas for equal-scale presentation")
    b_result_path = page_author_result_path(project_dir, slide_id, "B")
    try:
        b_result = read_json(b_result_path)
    except ValueError as exc:
        return [str(exc)], None
    terminal = b_result.get("terminal_result")
    differences = terminal.get("material_differences") if isinstance(terminal, dict) else None
    summary = {
        "slide_id": slide_id,
        "a_sha256": a_hash,
        "b_sha256": b_hash,
        "material_differences": differences if isinstance(differences, list) else [],
        "advisories": [],
    }
    advisories = summary["advisories"]
    if a_hash == b_hash:
        advisories.append(f"{slide_id} A.svg and B.svg are identical")
    if (
        not isinstance(differences, list)
        or not differences
        or any(not isinstance(item, str) or not item.strip() for item in differences)
    ):
        advisories.append(
            f"{slide_id} B result has missing or insufficient material_differences evidence"
        )
    return errors, summary


def validate_revision(project_dir: Path, slide_id: str, request: dict) -> list[str]:
    errors: list[str] = []
    revision_id = str(request.get("revision_id", ""))
    base_version = str(request.get("base_version", ""))
    if not re.fullmatch(r"R[1-9]\d*", revision_id):
        return [f"{slide_id} revision request has an invalid revision_id"]
    if request.get("slide_id") != slide_id:
        errors.append(f"{slide_id} revision request identifies the wrong page")
    if not str(request.get("note", "")).strip():
        errors.append(f"{slide_id} revision request has no targeted changes")
    if request.get("request_sha256") != revision_request_hash(request):
        errors.append(f"{slide_id} revision request changed after creation")
    try:
        base_path = selected_working_path(project_dir, slide_id, base_version)
        revision_path = selected_working_path(project_dir, slide_id, revision_id)
        contract = page_visible_copy_contract(project_dir, slide_id)
    except ValueError as exc:
        return [str(exc)]
    for version, path in ((base_version, base_path), (revision_id, revision_path)):
        if page_author_completion_valid(project_dir, slide_id, version):
            continue
        before = len(errors)
        errors.extend(candidate_errors(path))
        if path.is_file():
            errors.extend(visible_copy_errors(path, contract))
        if len(errors) == before:
            errors.append(f"{slide_id} {version} has no valid hash-bound preflight receipt")
    if errors:
        return errors
    if request.get("base_sha256") != sha256(base_path):
        errors.append(f"{slide_id} revision base changed after the request")
    if svg_canvas(base_path) != svg_canvas(revision_path):
        errors.append(f"{slide_id} {revision_id} must keep the base canvas for equal-scale review")
    return errors


def revision_advisories(project_dir: Path, slide_id: str, request: dict) -> list[str]:
    revision_id = str(request.get("revision_id", ""))
    base_version = str(request.get("base_version", ""))
    try:
        base_path = selected_working_path(project_dir, slide_id, base_version)
        revision_path = selected_working_path(project_dir, slide_id, revision_id)
    except ValueError:
        return []
    if base_path.is_file() and revision_path.is_file() and sha256(base_path) == sha256(revision_path):
        return [f"{slide_id} {revision_id} is identical to its base {base_version}"]
    return []


def revision_presentation_path(project_dir: Path, slide_id: str, revision_id: str) -> Path:
    return receipt_path(project_dir, slide_id, f"{revision_id}-presentation")


def revision_presentation_valid(project_dir: Path, slide_id: str, request: dict) -> bool:
    revision_id = str(request.get("revision_id", ""))
    path = revision_presentation_path(project_dir, slide_id, revision_id)
    if not path.is_file():
        return False
    try:
        receipt = read_json(path)
        base_path = selected_working_path(project_dir, slide_id, str(request.get("base_version", "")))
        revision_path = selected_working_path(project_dir, slide_id, revision_id)
    except (ValueError, OSError):
        return False
    hashes_match = (
        receipt.get("request_sha256") == request.get("request_sha256")
        and receipt.get("base_sha256") == sha256(base_path)
        and receipt.get("revision_sha256") == sha256(revision_path)
    )
    if not hashes_match:
        return False
    return not presentation_preview_errors(
        project_dir,
        slide_id,
        (str(request.get("base_version", "")), revision_id),
        receipt,
    )


def output_filename(text: str) -> str:
    return line_fields(h2_section(text, "Current position")).get("Output filename", "")


def current_export(text: str, project_dir: Path) -> dict:
    prepared, errors = inspect_export_workspace(
        project_dir,
        [page.slide_id for page in page_entries(text)],
        output_filename(text),
    )
    if errors or prepared is None:
        raise ValueError("; ".join(errors) or "export workspace could not be prepared")
    return prepared


def current_handoff_result(text: str, project_dir: Path) -> dict | None:
    path = handoff_result_path(project_dir)
    if not path.is_file():
        return None
    try:
        result = read_json(path)
    except ValueError:
        return None
    try:
        export = current_export(text, project_dir)
    except (OSError, ValueError):
        return None
    if (
        result.get("svg_set_fingerprint") != export["svg_set_fingerprint"]
        or result.get("export_manifest") != export["manifest_path"]
        or result.get("export_manifest_sha256") != export["manifest_sha256"]
        or result.get("required_output_path") != export["output_path"]
    ):
        return None
    if result.get("status") == "COMPLETE":
        artifact = Path(str(result.get("artifact_path", ""))).expanduser()
        if artifact.resolve() != Path(export["output_path"]).resolve() or not artifact.is_file():
            return None
        if result.get("artifact_sha256") != sha256(artifact):
            return None
    return result


def action_for_group(project_dir: Path, group: list[PageEntry]) -> tuple[str, list[PageEntry]]:
    for page in group:
        if active_page_author_block(project_dir, page.slide_id):
            return "RESOLVE_PAGE_AUTHOR_BLOCK", [page]
    reviewing = [
        page for page in group if page.fields.get("Status") in {"Not started", "Content reviewing"}
    ]
    if reviewing:
        return "PRESENT_PAGE_REVIEW", reviewing
    locked = [page for page in group if page.fields.get("Status") == "Content locked"]
    for page in locked:
        if not page_author_completion_valid(project_dir, page.slide_id, "A"):
            action = "GENERATE_SVG_A" if authoring_packet_valid(project_dir, page) else "PREPARE_SVG_A"
            return action, [page]
    for page in locked:
        if not page_author_completion_valid(project_dir, page.slide_id, "B"):
            action = "GENERATE_SVG_B" if authoring_packet_valid(project_dir, page) else "PREPARE_SVG_B"
            return action, [page]
    for page in locked:
        errors, _ = validate_ab(project_dir, page.slide_id)
        if errors:
            return "RESOLVE_AB_CONFLICT", [page]
    if locked:
        return "PRESENT_AB_OPTIONS", locked
    for page in group:
        if page.fields.get("Status") != "Awaiting SVG selection":
            continue
        request = active_revision(project_dir, page.slide_id)
        if request is None:
            continue
        revision_id = str(request.get("revision_id", ""))
        if active_page_author_block(project_dir, page.slide_id):
            return "RESOLVE_PAGE_AUTHOR_BLOCK", [page]
        if not page_author_completion_valid(project_dir, page.slide_id, revision_id):
            action = (
                "GENERATE_SVG_REVISION"
                if authoring_packet_valid(project_dir, page)
                else "PREPARE_SVG_REVISION"
            )
            return action, [page]
        if validate_revision(project_dir, page.slide_id, request):
            return "GENERATE_SVG_REVISION", [page]
        if not revision_presentation_valid(project_dir, page.slide_id, request):
            return "PRESENT_SVG_REVISION", [page]
        return "COLLECT_REVISION_CONFIRMATION", [page]
    awaiting = [page for page in group if page.fields.get("Status") == "Awaiting SVG selection"]
    if awaiting:
        return "COLLECT_SVG_SELECTION", awaiting
    raise ValueError("active page group has no actionable non-terminal state")


def directive(text: str, project_dir: Path) -> tuple[str, list[PageEntry]]:
    phase = derived_phase(text)
    pages = page_entries(text)
    all_terminal = bool(pages) and all(
        page.fields.get("Status") in TERMINAL_STATES for page in pages
    )
    result = current_handoff_result(text, project_dir) if all_terminal else None
    if result and result.get("status") == "BLOCKED":
        blocked_ids = set(result.get("slide_ids", []))
        return "RESOLVE_HANDOFF_BLOCK", [page for page in pages if page.slide_id in blocked_ids]
    missing_protected = [
        page
        for page in pages
        if page.fields.get("Status") == "Protected placeholder"
        and not protected_artifact_valid(project_dir, page)
    ]
    if missing_protected:
        return "MATERIALIZE_PROTECTED_PAGES", missing_protected
    if all_terminal:
        if result and result.get("status") == "COMPLETE":
            return "DELIVERY_COMPLETE", pages
        prepared, _errors = inspect_export_workspace(
            project_dir,
            [page.slide_id for page in pages],
            output_filename(text),
        )
        if prepared is None:
            return "PREPARE_CONFIRMED_EXPORT", pages
        return "RUN_CONFIRMED_EXPORT", pages
    if phase in {
        "Stage 1 — Body page loop",
        "Stage 1 — Structural page review",
        "Stage 1 — Agenda review",
    }:
        group = current_group(text)
        if not group:
            raise ValueError("derived phase has no active page group")
        return action_for_group(project_dir, group)
    return ("RUN_CONFIRMED_EXPORT", pages)


def print_project_brief(text: str) -> None:
    print(h2_section(text, "Project context").rstrip())
    print("\n" + h2_section(text, "Design hard rules").rstrip())


def review_context(text: str, selected: list[PageEntry]) -> dict:
    pages = page_entries(text)
    indexes = {page.slide_id: index for index, page in enumerate(pages)}
    targets: list[dict] = []
    for page in selected:
        index = indexes[page.slide_id]
        adjacent = pages[max(0, index - 1) : min(len(pages), index + 2)]
        targets.append({
            "slide_id": page.slide_id,
            "title": page.title,
            "fields": page.fields,
            "adjacent": [
                {
                    "slide_id": item.slide_id,
                    "title": item.title,
                    "narrative_role": item.fields.get("Narrative role", "Missing"),
                    "next_connection": item.fields.get("Next connection", "Missing"),
                    "status": item.fields.get("Status", "Missing"),
                }
                for item in adjacent
            ],
        })
    return {
        "project_context": line_fields(h2_section(text, "Project context")),
        "design_hard_rules": line_fields(h2_section(text, "Design hard rules")),
        "target_pages": targets,
    }


def print_build_context(text: str, project_dir: Path, selected: list[PageEntry]) -> None:
    print_project_brief(text)
    content_path = project_dir / "content.md"
    content = content_path.read_text(encoding="utf-8") if content_path.is_file() else ""
    profile = h2_section(content, "Deck build profile（Build-only）")
    if profile:
        print("\n" + profile.rstrip())
    else:
        print("\n[Missing Deck build profile]")
    pages = page_entries(text)
    indexes = {page.slide_id: index for index, page in enumerate(pages)}
    print("\n## Build context\n")
    for page in selected:
        index = indexes[page.slide_id]
        print(f"### {page.slide_id}｜{page.title}")
        for field in ("Chapter", "Page type", "Narrative role", "Next connection"):
            print(f"- {field}: {page.fields.get(field, 'Missing')}")
        adjacent = pages[max(0, index - 1): min(len(pages), index + 2)]
        print("- Adjacent titles: " + " | ".join(f"{item.slide_id} {item.title}" for item in adjacent))
        section = content_section(content, page.slide_id)
        print("\n" + (section.rstrip() if section else f"[Missing approved content for {page.slide_id}]") + "\n")


def ensure_authoring_packet(text: str, project_dir: Path, page: PageEntry) -> dict:
    """Materialize one stable A/B-shared page packet outside the conversation context."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_build_context(text, project_dir, [page])
    contract = page_visible_copy_contract(project_dir, page.slide_id)
    contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
    packet_text = (
        f"# Locked Page SVG Authoring Packet｜{page.slide_id}\n\n"
        "Use this exact packet for A and B. Version-specific output paths and revision notes are "
        "controller directives, not page-content memory. Every visible SVG text run must be bound "
        "to exactly one approved item below with `data-copy-id`; Build-only text must never be "
        "visible. Text may be split into nested tspans inside one bound element or group.\n\n"
        + buffer.getvalue().strip()
        + "\n\n## Machine-enforced visible copy\n\n```json\n"
        + contract_json
        + "\n```\n"
    )
    packet_path, receipt_path_value = authoring_packet_paths(project_dir, page.slide_id)
    atomic_write(packet_path, packet_text)
    payload = {
        "slide_id": page.slide_id,
        "packet_path": str(packet_path.resolve()),
        "packet_sha256": sha256(packet_path),
        "framework_page_sha256": text_sha256(page.text),
        "visible_copy_contract": contract,
        "visible_copy_contract_sha256": contract["contract_sha256"],
        "created_at": now(),
    }
    write_json(receipt_path_value, payload)
    return payload


def author_version_for_action(action: str, project_dir: Path, page: PageEntry) -> str:
    if action == "GENERATE_SVG_A":
        return "A"
    if action == "GENERATE_SVG_B":
        return "B"
    if action == "GENERATE_SVG_REVISION":
        request = active_revision(project_dir, page.slide_id) or {}
        return str(request.get("revision_id", ""))
    raise ValueError(f"{action} is not a page-authoring action")


def directive_commands(
    text: str,
    action: str,
    selected: list[PageEntry],
    project_dir: Path,
    controller: Path,
) -> dict[str, str]:
    page_args = [item for page in selected for item in ("--page", page.slide_id)]
    target_page = selected[0].slide_id if len(selected) == 1 else "<ACTIVE_PAGE>"
    if action in PREPARE_AUTHORING_ACTIONS:
        return {
            "run": command_line(
                controller,
                "prepare-authoring",
                project_dir,
                "--page",
                target_page,
            )
        }
    if action == "PREPARE_CONFIRMED_EXPORT":
        return {"run": command_line(controller, "prepare-export", project_dir)}
    if action == "MATERIALIZE_PROTECTED_PAGES":
        return {"run": command_line(controller, "materialize-protected", project_dir)}
    if action == "PRESENT_PAGE_REVIEW":
        return {"run": command_line(controller, "present-review", project_dir)}
    if action in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"}:
        return {
            "record_result": command_line(
                controller,
                "page-author-result",
                project_dir,
                "--result-json",
                "<EXACT_TERMINAL_RESULT_JSON>",
            )
        }
    if action == "RESOLVE_AB_CONFLICT":
        return {
            "reopen_design": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "reopen",
                "--page",
                target_page,
                "--scope",
                "design",
                "--note",
                "<AB_CONFLICT_RESOLUTION>",
            )
        }
    if action == "PRESENT_AB_OPTIONS":
        return {"run": command_line(controller, "present-ab", project_dir)}
    if action == "COLLECT_SVG_SELECTION":
        selections = ",".join(f"{page.slide_id}=<A_OR_B>" for page in selected)
        return {
            "repair_before_user_display": command_line(
                controller,
                "repair-ab-candidate",
                project_dir,
                "--page",
                target_page,
                "--version",
                "<A_OR_B>",
                "--note",
                "<CANDIDATE_DEFECT>",
            ),
            "after_plain_selection": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "svg-selected",
                *page_args,
                "--selections",
                selections,
            ),
            "for_targeted_changes": command_line(
                controller,
                "request-revision",
                project_dir,
                "--page",
                target_page,
                "--base",
                "<A_OR_B>",
                "--note",
                "<TARGETED_CHANGES>",
            ),
        }
    if action == "PRESENT_SVG_REVISION":
        return {"run": command_line(controller, "present-revision", project_dir)}
    if action == "COLLECT_REVISION_CONFIRMATION":
        request = active_revision(project_dir, selected[0].slide_id) or {}
        revision_id = str(request.get("revision_id", "<Rn>"))
        return {
            "after_confirmation": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "svg-selected",
                "--page",
                selected[0].slide_id,
                "--selections",
                f"{selected[0].slide_id}={revision_id}",
            ),
            "for_targeted_changes": command_line(
                controller,
                "request-revision",
                project_dir,
                "--page",
                selected[0].slide_id,
                "--base",
                revision_id,
                "--note",
                "<TARGETED_CHANGES>",
            ),
        }
    if action == "RESOLVE_PAGE_AUTHOR_BLOCK":
        page = selected[0]
        result = active_page_author_block(project_dir, page.slide_id) or {}
        if result.get("repair_scope") == "environment":
            return {
                "after_environment_fix": command_line(
                    controller, "resume-page-author", project_dir, "--page", page.slide_id
                )
            }
        return {
            "after_decision": command_line(
                controller,
                "resume-page-author",
                project_dir,
                "--page",
                page.slide_id,
                "--scope",
                "<design_OR_content>",
                "--note",
                "<RESOLUTION>",
            )
        }
    if action == "RESOLVE_HANDOFF_BLOCK":
        result = current_handoff_result(text, project_dir) or {}
        if result.get("repair_scope") == "environment":
            return {"after_environment_fix": command_line(controller, "resume-handoff", project_dir)}
        return {
            "after_resolution": command_line(
                controller,
                "resume-handoff",
                project_dir,
                *page_args,
                "--note",
                "<RESOLUTION>",
            )
        }
    if action == "RUN_CONFIRMED_EXPORT":
        return {
            "record_result": command_line(
                controller,
                "handoff-result",
                project_dir,
                "--result-json",
                "<EXACT_TERMINAL_RESULT_JSON>",
            )
        }
    return {}


def directive_payload(text: str, project_dir: Path, controller: Path) -> dict:
    action, selected = directive(text, project_dir)
    commands = directive_commands(text, action, selected, project_dir, controller)
    payload: dict[str, object] = {
        "workflow_version": WORKFLOW_VERSION,
        "stage": derived_phase(text),
        "action": action,
        "pages": [page.slide_id for page in selected],
        "commands": commands,
    }
    if action in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"}:
        payload["command_when"] = "after Page SVG Authoring returns its exact terminal JSON"
    elif action == "RUN_CONFIRMED_EXPORT":
        payload["command_when"] = "run the hash-bound deterministic exporter now; then record its exact terminal JSON"
    elif action == "COLLECT_SVG_SELECTION":
        payload["command_when"] = (
            "before user display, repair any defective A/B slot with repair_before_user_display; "
            "otherwise show both A and B, then use a user-response command"
        )
    elif action == "COLLECT_REVISION_CONFIRMATION":
        payload["command_when"] = (
            "first send the complete request-bound Base/Revision comparison in one user message, "
            "with both previews side by side at equal scale; never show the revision alone. "
            "After explicit user confirmation use after_confirmation; for another targeted change "
            "use for_targeted_changes"
        )
    elif action == "PRESENT_PAGE_REVIEW":
        payload["command_when"] = "after writing the active provisional-content sections"
    elif commands:
        payload["command_when"] = "now"
    if action in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"}:
        page = selected[0]
        version = author_version_for_action(action, project_dir, page)
        packet = current_authoring_packet(project_dir, page.slide_id)
        if not packet or packet.get("framework_page_sha256") != text_sha256(page.text):
            raise ValueError("authoring packet is not prepared for the current page")
        payload.update({
            "route": "$ey-deck-design / Page SVG Authoring",
            "route_instruction": EY_PAGE_AUTHORING_INSTRUCTION,
            "version": version,
            "requested_artifact": str(
                selected_working_path(project_dir, page.slide_id, version).resolve()
            ),
            "packet_path": packet["packet_path"],
            "packet_sha256": packet["packet_sha256"],
            "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
        })
        if action == "GENERATE_SVG_B":
            payload["option_kernel"] = B_OPTION_KERNEL
        if action == "GENERATE_SVG_REVISION":
            request = active_revision(project_dir, page.slide_id) or {}
            payload["base_version"] = request.get("base_version")
            payload["targeted_changes"] = request.get("note")
    if action == "COLLECT_REVISION_CONFIRMATION":
        page = selected[0]
        request = active_revision(project_dir, page.slide_id) or {}
        base_version = str(request.get("base_version", ""))
        revision_id = str(request.get("revision_id", ""))
        base_preview, _base_receipt = preview_paths(
            project_dir, page.slide_id, base_version
        )
        revision_preview, _revision_receipt = preview_paths(
            project_dir, page.slide_id, revision_id
        )
        payload["user_display"] = {
            "required": True,
            "mode": "side-by-side-equal-scale",
            "send_in_one_message": True,
            "base_version": base_version,
            "revision_version": revision_id,
            "base_preview_png": str(base_preview.resolve()),
            "revision_preview_png": str(revision_preview.resolve()),
            "base_svg": str(
                selected_working_path(project_dir, page.slide_id, base_version).resolve()
            ),
            "revision_svg": str(
                selected_working_path(project_dir, page.slide_id, revision_id).resolve()
            ),
            "instruction": (
                "Show this exact Base/Revision pair together before asking for confirmation; "
                "never show the revision alone."
            ),
        }
    if action == "PRESENT_PAGE_REVIEW":
        payload["review_context"] = review_context(text, selected)
        payload["provisional_content"] = {
            "path": str((project_dir / "working" / "provisional-content.md").resolve()),
            "write_mode": "replace",
            "expected_pages": [page.slide_id for page in selected],
        }
    if action == "RUN_CONFIRMED_EXPORT":
        export = current_export(text, project_dir)
        payload.update({
            "executor": "EY bundled deterministic confirmed-export runner",
            "route": "$ey-deck-design / Confirmed SVG Export",
            "export_manifest": export["manifest_path"],
            "export_manifest_sha256": export["manifest_sha256"],
            "required_output_path": export["output_path"],
            "runner_command": export["runner_command"],
        })
    if action == "RESOLVE_PAGE_AUTHOR_BLOCK":
        result = active_page_author_block(project_dir, selected[0].slide_id) or {}
        payload["block"] = {
            key: result.get(key)
            for key in ("stage", "reason", "repair_scope", "resume_from")
        }
    if action == "RESOLVE_HANDOFF_BLOCK":
        result = current_handoff_result(text, project_dir) or {}
        payload["block"] = {
            key: result.get(key)
            for key in ("stage", "reason", "repair_scope", "resume_from")
        }
    if action == "DELIVERY_COMPLETE":
        result = current_handoff_result(text, project_dir) or {}
        payload["artifact_path"] = result.get("artifact_path")
    return payload


def print_directive(text: str, project_dir: Path, controller: Path) -> None:
    payload = directive_payload(text, project_dir, controller)
    if payload["action"] in {"PREPARE_CONFIRMED_EXPORT", "RUN_CONFIRMED_EXPORT"}:
        print("STAGE_1_COMPLETE")
    print("NEXT_DIRECTIVE_JSON")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def artifact_errors(text: str, project_dir: Path) -> list[str]:
    errors: list[str] = []
    content_path = project_dir / "content.md"
    content = content_path.read_text(encoding="utf-8") if content_path.is_file() else ""
    pages = page_entries(text)
    expected_content_ids = [
        page.slide_id for page in pages if page.fields.get("Status") != "Protected placeholder"
    ]
    if content_path.is_file():
        require_complete = bool(pages) and all(
            page.fields.get("Status") in TERMINAL_STATES for page in pages
        )
        errors.extend(
            validate_blueprint_collection(
                content_path,
                expected_content_ids,
                require_complete=require_complete,
            )
        )
    for page in pages:
        state = page.fields.get("Status")
        if state not in PAGE_STATES:
            continue
        if state in {"Content locked", "Awaiting SVG selection", "SVG confirmed"}:
            section = content_section(content, page.slide_id)
            receipt_file = receipt_path(project_dir, page.slide_id, "content")
            if not section:
                errors.append(f"{page.slide_id} locked state has no content.md section")
            elif not receipt_file.is_file():
                errors.append(f"{page.slide_id} has no content-lock receipt")
            else:
                errors.extend(content_identity_errors(page, section))
                title = re.search(r"^- Title:\s*(.+)$", section, re.MULTILINE)
                if title and page.title != title.group(1).strip():
                    errors.append(
                        f"{page.slide_id} framework title changed after content approval; reopen content"
                    )
                try:
                    receipt = read_json(receipt_file)
                    if receipt.get("content_sha256") != text_sha256(section):
                        errors.append(f"{page.slide_id} locked content changed after approval")
                except ValueError as exc:
                    errors.append(str(exc))
        if state == "Awaiting SVG selection":
            request = active_revision(project_dir, page.slide_id)
            if request is None:
                for version in ("A", "B"):
                    if not page_author_completion_valid(project_dir, page.slide_id, version):
                        errors.append(f"{page.slide_id} {version} has no valid COMPLETE authoring result")
                ab_errors, _ = validate_ab(project_dir, page.slide_id)
                errors.extend(ab_errors)
                if not ab_presentation_valid(project_dir, page.slide_id):
                    errors.append(f"{page.slide_id} has no valid A/B presentation evidence")
        active_path = revision_active_path(project_dir, page.slide_id)
        if active_path.is_file():
            try:
                request = read_json(active_path)
                if request.get("active") is True:
                    if state != "Awaiting SVG selection":
                        errors.append(f"{page.slide_id} active revision conflicts with page state {state}")
                    if request.get("slide_id") != page.slide_id:
                        errors.append(f"{page.slide_id} active revision identifies the wrong page")
                    if request.get("request_sha256") != revision_request_hash(request):
                        errors.append(f"{page.slide_id} active revision request changed after creation")
                    if not str(request.get("note", "")).strip():
                        errors.append(f"{page.slide_id} active revision has no targeted changes")
                    try:
                        base_path = selected_working_path(
                            project_dir, page.slide_id, str(request.get("base_version", ""))
                        )
                        if svg_error(base_path) or request.get("base_sha256") != sha256(base_path):
                            errors.append(f"{page.slide_id} active revision base is missing or changed")
                    except (ValueError, OSError):
                        errors.append(f"{page.slide_id} active revision has an invalid base")
            except ValueError as exc:
                errors.append(str(exc))
        selected_path: Path | None = None
        if state == "SVG confirmed":
            selected = page.fields.get("Selected version")
            if selected and not page_author_completion_valid(project_dir, page.slide_id, selected):
                errors.append(f"{page.slide_id} selected SVG has no valid COMPLETE authoring result")
            try:
                selected_path = selected_working_path(project_dir, page.slide_id, selected or "")
            except ValueError as exc:
                errors.append(str(exc))
            selection_path = receipt_path(project_dir, page.slide_id, "svg-selection")
            final_path = project_dir / "svg_output" / f"{page.slide_id}.svg"
            if not final_path.is_file():
                errors.append(f"{page.slide_id} canonical SVG is missing")
            elif not selection_path.is_file():
                errors.append(f"{page.slide_id} has no SVG selection receipt")
            else:
                try:
                    selection_receipt = read_json(selection_path)
                    if selection_receipt.get("slide_id") != page.slide_id:
                        errors.append(f"{page.slide_id} selection receipt identifies the wrong page")
                    if selection_receipt.get("selected_version") != selected:
                        errors.append(f"{page.slide_id} selection receipt has the wrong version")
                    if selection_receipt.get("canonical_sha256") != sha256(final_path):
                        errors.append(f"{page.slide_id} canonical SVG changed after selection")
                    presentation_value = selection_receipt.get("presentation_receipt")
                    if presentation_value:
                        presentation_path = Path(str(presentation_value))
                        if not presentation_path.is_absolute():
                            presentation_path = project_dir / presentation_path
                        if not presentation_path.is_file():
                            errors.append(f"{page.slide_id} selection presentation receipt is missing")
                        elif selection_receipt.get("presentation_receipt_sha256") != sha256(
                            presentation_path
                        ):
                            errors.append(f"{page.slide_id} selection presentation evidence changed")
                    if selected_path is not None and selected_path.is_file():
                        if selection_receipt.get("selected_sha256") != sha256(selected_path):
                            errors.append(f"{page.slide_id} selected working SVG changed after selection")
                    if selection_receipt.get("source_preflight_gate") != PAGE_PREFLIGHT_GATE_SCHEMA:
                        # Legacy canonical evidence predates reusable preflight
                        # receipts and therefore retains the former deep audit.
                        errors.extend(candidate_errors(final_path))
                except ValueError as exc:
                    errors.append(str(exc))
        if state == "Protected placeholder":
            canonical = project_dir / "svg_output" / f"{page.slide_id}.svg"
            if canonical.is_file() and not protected_canonical_evidence_valid(project_dir, page):
                errors.append(f"{page.slide_id} protected canonical SVG has missing or stale evidence")

    for forbidden_root in (project_dir / "working", project_dir / "svg_working", project_dir / "svg_output"):
        if forbidden_root.exists():
            for pptx in forbidden_root.rglob("*.pptx"):
                errors.append(f"page-level/intermediate PPTX is prohibited: {pptx}")
    canonical_dir = project_dir / "svg_output"
    if canonical_dir.is_dir():
        for png in canonical_dir.rglob("*.png"):
            errors.append(f"UI preview PNG is prohibited in svg_output: {png}")

    exports = project_dir / "exports"
    if exports.is_dir():
        for pptx in exports.rglob("*.pptx"):
            errors.append(
                f"EY Deck Design project must not contain a PPTX; final generation belongs to the isolated EY export workspace: {pptx}"
            )
    return errors


def audit(text: str, framework: Path, project_dir: Path) -> list[str]:
    errors = validate_framework(framework, project_dir)
    errors.extend(artifact_errors(text, project_dir))
    return errors


def assert_current_action(text: str, project_dir: Path, event: str, requested: list[str]) -> list[PageEntry]:
    action, selected = directive(text, project_dir)
    allowed = ACTION_EVENT.get(action)
    actual = [page.slide_id for page in selected]
    if event != allowed:
        raise ValueError(f"current action {action} allows {allowed or 'no advance event'}, not {event}")
    if requested != actual:
        raise ValueError(f"event must target exactly the active pages in order: {','.join(actual) or 'None'}")
    return selected


def parse_selections(raw: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not raw:
        return result
    for item in raw.split(","):
        if "=" not in item:
            raise ValueError("selections must use S01=A,S02=B or S01=R1")
        slide_id, selection = (part.strip() for part in item.split("=", 1))
        if not re.fullmatch(r"(?:A|B|R[1-9]\d*)", selection):
            raise ValueError(f"unsupported selection: {item}")
        result[slide_id] = selection
    return result


def record_handoff_result(text: str, project_dir: Path, raw: str) -> None:
    action, _pages = directive(text, project_dir)
    if action != "RUN_CONFIRMED_EXPORT":
        raise ValueError(f"handoff result blocked: current action is {action}")
    incoming = parse_terminal_json(raw)
    export = current_export(text, project_dir)
    manifest = read_json(Path(export["manifest_path"]))
    preflight_errors = validate_terminal_result(manifest, incoming)
    if preflight_errors:
        raise ValueError("terminal-result preflight failed: " + "; ".join(preflight_errors))
    status = str(incoming["status"])
    payload: dict[str, object] = {
        "status": status,
        "route": "confirmed-svg-export",
        "terminal_result": incoming,
        "svg_set_fingerprint": export["svg_set_fingerprint"],
        "export_manifest": export["manifest_path"],
        "export_manifest_sha256": export["manifest_sha256"],
        "required_output_path": export["output_path"],
        "recorded_at": now(),
    }
    if status == "COMPLETE":
        artifact = Path(str(incoming["artifact_path"])).expanduser().resolve()
        payload["artifact_path"] = str(artifact)
        payload["artifact_sha256"] = sha256(artifact)
    else:
        payload.update({
            key: incoming[key]
            for key in ("stage", "reason", "repair_scope", "resume_from", "slide_ids")
        })
    write_json(handoff_result_path(project_dir), payload)


def record_page_author_result(text: str, project_dir: Path, raw: str) -> None:
    action, selected = directive(text, project_dir)
    if action not in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"} or len(selected) != 1:
        raise ValueError(f"page authoring result blocked: current action is {action}")
    page = selected[0]
    version = author_version_for_action(action, project_dir, page)
    packet = current_authoring_packet(project_dir, page.slide_id)
    if not packet or packet.get("framework_page_sha256") != text_sha256(page.text):
        raise ValueError("run controller next to materialize the current hash-bound page packet first")
    result = parse_terminal_json(raw)
    if result.get("route") != "page-svg-authoring":
        raise ValueError("page authoring terminal result route must be page-svg-authoring")
    status = result.get("status")
    if status not in {"COMPLETE", "BLOCKED"}:
        raise ValueError("page authoring terminal result status must be COMPLETE or BLOCKED")
    payload: dict[str, object] = {
        "status": status,
        "route": "page-svg-authoring",
        "terminal_result": result,
        "slide_id": page.slide_id,
        "version": version,
        "packet_path": packet["packet_path"],
        "packet_sha256": packet["packet_sha256"],
        "recorded_at": now(),
        "active": status == "BLOCKED",
    }
    if status == "COMPLETE":
        artifact = Path(str(result.get("artifact_path", ""))).expanduser().resolve()
        expected = selected_working_path(project_dir, page.slide_id, version).resolve()
        if artifact != expected:
            raise ValueError(f"page authoring artifact must be the requested path: {expected}")
        contract = packet.get("visible_copy_contract")
        problems = candidate_errors(artifact)
        if isinstance(contract, dict):
            problems.extend(visible_copy_errors(artifact, contract))
        else:
            problems.append("authoring packet has no valid visible-copy contract")
        if problems:
            raise ValueError("; ".join(problems))
        if version == "B":
            differences = result.get("material_differences")
            b_advisories: list[str] = []
            if not (
                isinstance(differences, list)
                and differences
                and all(isinstance(item, str) and item.strip() for item in differences)
            ):
                b_advisories.append(
                    f"{page.slide_id} B result has missing or insufficient material_differences evidence"
                )
            a_path = selected_working_path(project_dir, page.slide_id, "A")
            if not page_author_completion_valid(project_dir, page.slide_id, "A"):
                raise ValueError("B COMPLETE requires a valid A authoring result")
            if sha256(a_path) == sha256(artifact):
                b_advisories.append(f"{page.slide_id} A.svg and B.svg are identical")
            if svg_canvas(a_path) != svg_canvas(artifact):
                raise ValueError(f"{page.slide_id} A.svg and B.svg must use the same canvas")
            if b_advisories:
                payload["advisories"] = b_advisories
        payload["artifact_path"] = str(artifact)
        artifact_sha256 = sha256(artifact)
        payload["artifact_sha256"] = artifact_sha256
        payload["visible_copy_contract_sha256"] = packet["visible_copy_contract_sha256"]
        payload["preflight_gate"] = {
            "schema": PAGE_PREFLIGHT_GATE_SCHEMA,
            "status": "PASS",
            "artifact_sha256": artifact_sha256,
            "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
        }
    else:
        required = {key: result.get(key) for key in ("stage", "reason", "repair_scope", "resume_from")}
        slide_ids = result.get("slide_ids")
        missing = [
            key for key, value in required.items()
            if not isinstance(value, str) or not value.strip()
        ]
        if missing or slide_ids != [page.slide_id]:
            raise ValueError(
                "page BLOCKED requires non-empty string fields and this slide_id only"
            )
        if result.get("repair_scope") not in {"source-svg", "user-decision", "environment"}:
            raise ValueError("page BLOCKED repair_scope must be source-svg, user-decision, or environment")
        payload.update(required)
        payload["slide_ids"] = slide_ids
    write_json(page_author_result_path(project_dir, page.slide_id, version), payload)


def resume_page_author(
    text: str,
    project_dir: Path,
    slide_id: str,
    scope: str | None,
    note: str | None,
) -> str:
    action, selected = directive(text, project_dir)
    if action != "RESOLVE_PAGE_AUTHOR_BLOCK" or [page.slide_id for page in selected] != [slide_id]:
        raise ValueError(f"page authoring resume blocked: current action is {action}")
    result = active_page_author_block(project_dir, slide_id) or {}
    result_path = page_author_result_path(project_dir, slide_id, str(result.get("version", "")))
    if result.get("repair_scope") == "environment":
        if scope or note:
            raise ValueError("environment recovery accepts only --page")
        archive_items(project_dir, "page-author-retry", [
            result_path,
            selected_working_path(project_dir, slide_id, str(result.get("version", ""))),
        ])
        return text
    if scope not in {"design", "content"} or not note:
        raise ValueError("source/user recovery requires --scope design|content and --note")
    receipts_dir = project_dir / "working" / "receipts"
    page_receipts = list(receipts_dir.glob(f"{slide_id}-*.json"))
    if scope == "design":
        page_receipts = [path for path in page_receipts if path.name != f"{slide_id}-content.json"]
    archive_items(project_dir, "page-author-reopen", [
        project_dir / "svg_working" / slide_id,
        project_dir / "svg_output" / f"{slide_id}.svg",
        *authoring_packet_paths(project_dir, slide_id),
        *page_receipts,
    ])
    target_state = "Content locked" if scope == "design" else "Content reviewing"
    updates = {"Status": target_state, "Selected version": "Pending"}
    if scope == "content":
        updates["Open items"] = note
    text = update_page(text, slide_id, updates)
    write_json(receipt_path(project_dir, slide_id, "page-author-recovery"), {
        "slide_id": slide_id,
        "scope": scope,
        "note": note,
        "created_at": now(),
    })
    return text


def repair_ab_candidate(
    text: str,
    project_dir: Path,
    slide_id: str,
    version: str,
    note: str,
) -> str:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    if page.fields.get("Status") not in {"Content locked", "Awaiting SVG selection"}:
        raise ValueError(
            f"{slide_id} A/B candidate repair requires Content locked or Awaiting SVG selection"
        )
    group = current_group(text)
    if slide_id not in {item.slide_id for item in group}:
        raise ValueError(f"{slide_id} is not in the active page group")
    if version not in {"A", "B"}:
        raise ValueError("A/B candidate repair version must be A or B")
    if not note.strip():
        raise ValueError("A/B candidate repair requires a non-empty defect note")
    if active_revision(project_dir, slide_id):
        raise ValueError(f"{slide_id} already has an active user revision")
    if not page_author_completion_valid(project_dir, slide_id, version):
        raise ValueError(f"{slide_id} {version} has no valid candidate to repair")

    preview_png, preview_receipt = preview_paths(project_dir, slide_id, version)
    archive_items(project_dir, f"{slide_id}-candidate-{version}", [
        selected_working_path(project_dir, slide_id, version),
        page_author_result_path(project_dir, slide_id, version),
        preview_png,
        preview_receipt,
        *[
            receipt_path(project_dir, item.slide_id, "ab-presentation")
            for item in group
        ],
    ])
    for item in group:
        if item.slide_id == slide_id or item.fields.get("Status") == "Awaiting SVG selection":
            text = update_page(
                text,
                item.slide_id,
                {"Status": "Content locked", "Selected version": "Pending"},
            )
    write_json(receipt_path(project_dir, slide_id, f"{version}-candidate-repair"), {
        "slide_id": slide_id,
        "version": version,
        "note": note.strip(),
        "created_at": now(),
    })
    return text


def resume_handoff(text: str, project_dir: Path, pages: list[str], note: str | None) -> str:
    action, selected = directive(text, project_dir)
    if action != "RESOLVE_HANDOFF_BLOCK":
        raise ValueError(f"handoff resume blocked: current action is {action}")
    result = current_handoff_result(text, project_dir) or {}
    blocked = [page.slide_id for page in selected]
    scope = result.get("repair_scope")
    if scope == "environment":
        if pages:
            raise ValueError("environment recovery must not reopen pages; omit --page")
        archive_items(project_dir, "handoff-result", [handoff_result_path(project_dir)])
        return text
    if pages != blocked:
        raise ValueError("resume must target every blocked page in order: " + ",".join(blocked))
    if not note:
        raise ValueError("source/user recovery requires --note")
    for slide_id in pages:
        page = next(item for item in page_entries(text) if item.slide_id == slide_id)
        canonical = project_dir / "svg_output" / f"{slide_id}.svg"
        if page.fields.get("Status") == "Protected placeholder":
            source = project_dir / "protected_input" / f"{slide_id}.svg"
            problems = protected_candidate_errors(source)
            if problems:
                raise ValueError(f"{slide_id} requires a changed valid protected_input SVG: {'; '.join(problems)}")
            old = read_json(receipt_path(project_dir, slide_id, "protected"))
            if old.get("source_sha256") == sha256(source):
                raise ValueError(f"{slide_id} protected_input SVG has not changed")
            archive_items(project_dir, "handoff-reopen", [
                canonical,
                receipt_path(project_dir, slide_id, "protected"),
            ])
        else:
            page_receipts = [
                path for path in (project_dir / "working" / "receipts").glob(f"{slide_id}-*.json")
                if scope == "user-decision" or path.name != f"{slide_id}-content.json"
            ]
            archive_items(project_dir, "handoff-reopen", [
                project_dir / "svg_working" / slide_id,
                canonical,
                *authoring_packet_paths(project_dir, slide_id),
                *page_receipts,
            ])
            target_state = "Content reviewing" if scope == "user-decision" else "Content locked"
            updates = {
                "Status": target_state,
                "Selected version": "Pending",
                "Open items": note if target_state == "Content reviewing" else "None",
            }
            text = update_page(text, slide_id, updates)
            write_json(receipt_path(project_dir, slide_id, "handoff-recovery"), {
                "slide_id": slide_id,
                "repair_scope": scope,
                "note": note,
                "created_at": now(),
            })
    archive_items(project_dir, "handoff-result", [handoff_result_path(project_dir)])
    return text


def managed_agents_block(controller: Path, skill_root: Path) -> str:
    return f'''{MANAGED_START}
# EY Deck Design controlled workflow

Read `{skill_root / 'SKILL.md'}` once. On entry, re-entry, or uncertain state, run
`python3 "{controller}" next --project-dir . --format json`; follow only its action,
`command_when`, and the condition-matching command data. A successful controller command already returns the next directive. Never edit
workflow state manually or create a PPTX here. Record Page SVG and isolated Stage 2 terminal JSON
with the controller command before continuing.
{MANAGED_END}'''


def init_agents(project_dir: Path, controller: Path) -> None:
    path = project_dir / "AGENTS.md"
    block = managed_agents_block(controller, controller.parent.parent)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(
        rf"(?:{re.escape(MANAGED_START)}.*?{re.escape(MANAGED_END)}|"
        rf"{re.escape(LEGACY_MANAGED_START)}.*?{re.escape(LEGACY_MANAGED_END)})",
        re.DOTALL,
    )
    updated = pattern.sub(block, existing) if pattern.search(existing) else (existing.rstrip() + "\n\n" + block).lstrip()
    atomic_write(path, updated.rstrip() + "\n")


def reopen_pages(
    text: str,
    project_dir: Path,
    slide_ids: list[str],
    scope: str | None,
    note: str | None,
) -> str:
    """Allow explicit recovery even when stricter new audits reject legacy artifacts."""
    if not slide_ids or not note or scope not in {"content", "design"}:
        raise ValueError("reopen requires --page, --scope content|design, and --note")
    for slide_id in slide_ids:
        page = next((p for p in page_entries(text) if p.slide_id == slide_id), None)
        if not page or page.fields.get("Status") in {
            "Not started",
            "Content reviewing",
            "Protected placeholder",
        }:
            raise ValueError(f"{slide_id} cannot be reopened")
        receipts_dir = project_dir / "working" / "receipts"
        page_receipts = list(receipts_dir.glob(f"{slide_id}-*.json"))
        if scope == "design":
            page_receipts = [
                path for path in page_receipts if path.name != f"{slide_id}-content.json"
            ]
        else:
            for path in receipts_dir.glob("review-*.json"):
                if slide_id in path.stem.split("-")[-1].split("_"):
                    page_receipts.append(path)
        archive_items(project_dir, slide_id, [
            project_dir / "svg_working" / slide_id,
            project_dir / "svg_output" / f"{slide_id}.svg",
            *authoring_packet_paths(project_dir, slide_id),
            *page_receipts,
        ])
        target_state = "Content locked" if scope == "design" else "Content reviewing"
        text = update_page(
            text,
            slide_id,
            {"Status": target_state, "Selected version": "Pending"},
        )
    return text


def migrate_workflow(text: str, project_dir: Path) -> str:
    from workflow_migration import migrate_workflow as run_migration

    return run_migration(
        text,
        project_dir,
        candidate_errors=candidate_errors,
        content_section=content_section,
    )


def doctor_receipt_path(project_dir: Path) -> Path:
    return project_dir / "working" / "receipts" / "environment-doctor.json"


def doctor_receipt_valid(project_dir: Path) -> bool:
    path = doctor_receipt_path(project_dir)
    if not path.is_file():
        return False
    try:
        receipt = read_json(path)
    except ValueError:
        return False
    if receipt.get("workflow_version") != WORKFLOW_VERSION or receipt.get("status") != "PASS":
        return False
    checks = receipt.get("checks")
    if not isinstance(checks, dict):
        return False
    try:
        if checks.get("ey_export_runtime") != export_runtime_binding():
            return False
    except OSError:
        return False
    try:
        stage2 = read_json(stage2_runtime_path(project_dir))
        preview = read_json(preview_runtime_path(project_dir))
    except ValueError:
        return False
    stage2_receipt = checks.get("stage2_runtime_receipt")
    preview_receipt = checks.get("preview_runtime_receipt")
    if not isinstance(stage2_receipt, dict) or not isinstance(preview_receipt, dict):
        return False
    if stage2_receipt.get("sha256") != sha256(stage2_runtime_path(project_dir)):
        return False
    if preview_receipt.get("sha256") != sha256(preview_runtime_path(project_dir)):
        return False
    return not validate_stage2_runtime(stage2, reprobe=False) and not preview_runtime_errors(
        preview, verify_identity=False
    )


def run_and_record_doctor(
    project_dir: Path,
    bundled_python: str | None,
    bundle_version: str | None,
) -> tuple[list[dict[str, str]], list[str]]:
    doctor_receipt_path(project_dir).unlink(missing_ok=True)
    checks, errors, warnings = run_doctor(project_dir, bundled_python, bundle_version)
    if not errors:
        write_json(doctor_receipt_path(project_dir), {
            "status": "PASS",
            "workflow_version": WORKFLOW_VERSION,
            "checks": checks,
            "warnings": warnings,
            "created_at": now(),
        })
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "bootstrap", "doctor", "init", "next", "audit", "prepare-authoring", "prepare-export",
        "validate-review", "present-review", "present-ab", "repair-ab-candidate", "request-revision",
        "present-revision", "advance", "update-page", "set-output-filename", "migrate", "materialize-protected",
        "page-author-result", "resume-page-author", "handoff-result",
        "resume-handoff",
    ):
        command = sub.add_parser(name)
        command.add_argument(
            "legacy_framework", nargs="?", type=Path, help=argparse.SUPPRESS
        )
        command.add_argument("--framework", dest="framework_option", type=Path)
        command.add_argument("--project-dir", type=Path, required=True)
        if name in {"bootstrap", "doctor"}:
            command.add_argument("--bundled-python")
            command.add_argument("--bundle-version")
        if name == "next":
            command.add_argument("--format", choices=("text", "json"), default="text")
        if name == "advance":
            command.add_argument("--event", required=True)
            command.add_argument("--page", action="append", default=[])
            command.add_argument("--selections")
            command.add_argument("--note")
            command.add_argument("--scope", choices=("content", "design"))
        if name == "request-revision":
            command.add_argument("--page", required=True)
            command.add_argument("--base")
            command.add_argument("--note", required=True)
        if name == "repair-ab-candidate":
            command.add_argument("--page", required=True)
            command.add_argument("--version", choices=("A", "B"), required=True)
            command.add_argument("--note", required=True)
        if name == "update-page":
            command.add_argument("--page", required=True)
            command.add_argument("--confirmed-decisions")
            command.add_argument("--open-items")
            command.add_argument("--review-mode", choices=("Page-by-page", "Batch"))
            command.add_argument("--title")
        if name == "set-output-filename":
            command.add_argument("--filename", required=True)
        if name == "prepare-authoring":
            command.add_argument("--page", required=True)
        if name == "page-author-result":
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--result-json")
            source.add_argument("--result-file", type=Path)
        if name == "resume-page-author":
            command.add_argument("--page", required=True)
            command.add_argument("--scope", choices=("content", "design"))
            command.add_argument("--note")
        if name == "handoff-result":
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--result-json")
            source.add_argument("--result-file", type=Path)
        if name == "resume-handoff":
            command.add_argument("--page", action="append", default=[])
            command.add_argument("--note")
    args = parser.parse_args()
    project_dir = args.project_dir.resolve()
    framework_arg = args.framework_option or args.legacy_framework or Path("framework.md")
    framework = (framework_arg if framework_arg.is_absolute() else project_dir / framework_arg).resolve()
    try:
        framework.relative_to(project_dir)
    except ValueError:
        print("ERROR: framework.md must be inside the project directory")
        return 2
    if not framework.is_file():
        print(f"ERROR: framework not found: {framework}")
        return 2
    text = framework.read_text(encoding="utf-8")
    controller = Path(__file__).resolve()

    if args.command == "migrate":
        try:
            migrated = migrate_workflow(text, project_dir)
            atomic_write(framework, migrated)
            init_agents(project_dir, controller)
            print(f"Migrated framework to workflow {WORKFLOW_VERSION}.")
            return 0
        except (ValueError, OSError) as exc:
            print(f"Migration failed: {exc}")
            return 1

    if args.command == "advance" and args.event == "reopen":
        try:
            text = reopen_pages(text, project_dir, args.page, args.scope, args.note)
            atomic_write(framework, text)
        except (OSError, ValueError) as exc:
            print(f"Transition blocked: {exc}")
            return 1
        print("Workflow state updated.")
        print_directive(text, project_dir, controller)
        return 0

    errors = audit(text, framework, project_dir)
    if errors:
        print(f"Workflow blocked by {len(errors)} audit error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.command == "repair-ab-candidate":
        try:
            text = repair_ab_candidate(
                text, project_dir, args.page, args.version, args.note
            )
            atomic_write(framework, text)
        except (OSError, ValueError) as exc:
            print(f"A/B candidate repair blocked: {exc}")
            return 1
        print(f"Reopened {args.page} {args.version} for same-slot candidate repair.")
        print_directive(text, project_dir, controller)
        return 0
    if args.command in {"bootstrap", "doctor"}:
        doctor_errors, warnings = run_and_record_doctor(
            project_dir, args.bundled_python, args.bundle_version
        )
        for warning in warnings:
            print(f"WARNING: {warning}")
        if doctor_errors:
            print(f"Environment doctor failed with {len(doctor_errors)} error(s):")
            retry_arguments: list[str] = []
            if args.bundled_python:
                retry_arguments.extend(("--bundled-python", args.bundled_python))
            if args.bundle_version:
                retry_arguments.extend(("--bundle-version", args.bundle_version))
            retry_command = command_line(
                controller,
                args.command,
                project_dir,
                *retry_arguments,
            )
            for error in doctor_errors:
                payload: dict[str, object] = dict(error)
                if error.get("code") == "PREVIEW_BROWSER_SANDBOX_BLOCKED":
                    payload.update({
                        "retry_command": retry_command,
                        "approval_prefix": ["python3", str(controller)],
                    })
                print("- " + json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 1
        print("Environment doctor passed.")
        if args.command == "bootstrap":
            init_agents(project_dir, controller)
            print(f"Controlled workflow initialized: {project_dir / 'AGENTS.md'}")
            print_directive(text, project_dir, controller)
        return 0
    if args.command == "init":
        if not doctor_receipt_valid(project_dir):
            print("Initialization blocked: run controller doctor successfully first.")
            return 1
        init_agents(project_dir, controller)
        print(f"Controlled workflow initialized: {project_dir / 'AGENTS.md'}")
        print_directive(text, project_dir, controller)
        return 0
    if args.command == "audit":
        print("Workflow audit passed.")
        return 0
    if args.command == "next":
        if args.format == "json":
            print(json.dumps(directive_payload(text, project_dir, controller), ensure_ascii=False, indent=2))
        else:
            print_directive(text, project_dir, controller)
        return 0

    if args.command == "prepare-authoring":
        action, selected = directive(text, project_dir)
        if action not in PREPARE_AUTHORING_ACTIONS or [page.slide_id for page in selected] != [args.page]:
            print(f"Authoring preparation blocked: current action is {action}")
            return 1
        try:
            ensure_authoring_packet(text, project_dir, selected[0])
        except (OSError, ValueError) as exc:
            print(f"Authoring preparation failed: {exc}")
            return 1
        print(f"Authoring packet prepared for {args.page}.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "prepare-export":
        action, selected = directive(text, project_dir)
        if action != "PREPARE_CONFIRMED_EXPORT":
            print(f"Export preparation blocked: current action is {action}")
            return 1
        try:
            prepare_export_workspace(
                project_dir,
                [page.slide_id for page in selected],
                output_filename(text),
            )
        except (OSError, ValueError) as exc:
            print(f"Export preparation failed: {exc}")
            return 1
        print("Confirmed export workspace prepared.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "validate-review":
        action, selected = directive(text, project_dir)
        if action != "PRESENT_PAGE_REVIEW":
            print(f"Review validation blocked: current action is {action}")
            return 1
        review = project_dir / "working" / "provisional-content.md"
        problems = provisional_content_errors(review, selected)
        if problems:
            print(f"Provisional content validation failed with {len(problems)} error(s):")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("Provisional content validation passed for: " + ", ".join(page.slide_id for page in selected))
        return 0

    if args.command == "page-author-result":
        try:
            raw_result = (
                args.result_json
                if args.result_json is not None
                else args.result_file.read_text(encoding="utf-8")
            )
            record_page_author_result(text, project_dir, raw_result)
        except (OSError, ValueError) as exc:
            print(f"Page authoring result rejected: {exc}")
            return 1
        print("Page SVG Authoring terminal result recorded.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "resume-page-author":
        try:
            text = resume_page_author(text, project_dir, args.page, args.scope, args.note)
            atomic_write(framework, text)
        except (OSError, ValueError) as exc:
            print(f"Page authoring recovery blocked: {exc}")
            return 1
        print("Page authoring recovery state applied.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "handoff-result":
        try:
            raw_result = (
                args.result_json
                if args.result_json is not None
                else args.result_file.read_text(encoding="utf-8")
            )
            record_handoff_result(text, project_dir, raw_result)
        except (OSError, ValueError) as exc:
            print(f"Handoff result rejected: {exc}")
            return 1
        print("EY confirmed SVG export terminal result recorded.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "resume-handoff":
        try:
            text = resume_handoff(text, project_dir, args.page, args.note)
            atomic_write(framework, text)
        except (OSError, ValueError) as exc:
            print(f"Handoff recovery blocked: {exc}")
            return 1
        print("Handoff recovery state applied.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "materialize-protected":
        action, selected = directive(text, project_dir)
        if action != "MATERIALIZE_PROTECTED_PAGES":
            print(f"Protected-page materialization blocked: current action is {action}")
            return 1
        try:
            materialized = materialize_protected_pages(text, project_dir)
        except (OSError, ValueError) as exc:
            print(f"Protected-page materialization failed: {exc}")
            return 1
        print("Protected canonical pages materialized: " + ", ".join(materialized))
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "present-review":
        action, selected = directive(text, project_dir)
        if action != "PRESENT_PAGE_REVIEW":
            print(f"Presentation blocked: current action is {action}")
            return 1
        review = project_dir / "working" / "provisional-content.md"
        ids = [page.slide_id for page in selected]
        problems = provisional_content_errors(review, selected)
        if problems:
            print("Provisional content presentation blocked:")
            for problem in problems:
                print(f"- {problem}")
            return 1
        write_json(review_receipt_path(project_dir, ids), {
            "pages": ids,
            "provisional_sha256": sha256(review),
            "created_at": now(),
        })
        for page in selected:
            if page.fields.get("Status") == "Not started":
                text = update_page(text, page.slide_id, {"Status": "Content reviewing"})
        atomic_write(framework, text)
        print(review.read_text(encoding="utf-8").rstrip())
        print("\nAfter explicit approval, run:")
        page_args = [item for page in selected for item in ("--page", page.slide_id)]
        print(command_line(
            controller,
            "advance",
            project_dir,
            "--event",
            "content-approved",
            *page_args,
            "--note",
            "<EXPLICIT_APPROVAL_NOTE>",
        ))
        return 0

    if args.command == "present-ab":
        action, selected = directive(text, project_dir)
        if action != "PRESENT_AB_OPTIONS":
            print(f"A/B presentation blocked: current action is {action}")
            return 1
        packets: list[tuple[PageEntry, dict, Path, Path, dict[str, dict]]] = []
        for page in selected:
            problems, manifest = validate_ab(project_dir, page.slide_id)
            if problems:
                print("A/B presentation blocked: " + "; ".join(problems))
                return 1
            a_path, b_path = working_paths(project_dir, page.slide_id)
            try:
                previews = ensure_preview_pair(
                    project_dir,
                    page.slide_id,
                    ("A", "B"),
                    copy_contract=page_visible_copy_contract(project_dir, page.slide_id),
                    prevalidated_source_hashes={
                        "A": str((manifest or {}).get("a_sha256", "")),
                        "B": str((manifest or {}).get("b_sha256", "")),
                    },
                )
            except (OSError, PreviewError, ValueError) as exc:
                issue: dict[str, object] = preview_failure_issue(exc)
                issue.update({
                    "slide_id": page.slide_id,
                    "retry_command": command_line(controller, "present-ab", project_dir),
                })
                if issue.get("code") == "PREVIEW_BROWSER_SANDBOX_BLOCKED":
                    issue["approval_prefix"] = ["python3", str(controller)]
                print(
                    "A/B presentation blocked: "
                    + json.dumps(issue, ensure_ascii=False, sort_keys=True)
                )
                return 1
            packets.append((page, manifest or {}, a_path, b_path, previews))

        # No Markdown or state change is emitted until every selected page has
        # two valid, equal-scale previews. A late render failure therefore
        # cannot produce a partial comparison packet.
        for page, manifest, a_path, b_path, previews in packets:
            write_json(receipt_path(project_dir, page.slide_id, "ab-presentation"), {
                "slide_id": page.slide_id,
                "a_sha256": sha256(a_path),
                "b_sha256": sha256(b_path),
                "advisories": manifest.get("advisories", []),
                "evidence_scope": "rendered-comparison",
                **preview_presentation_evidence(
                    project_dir, page.slide_id, ("A", "B"), previews
                ),
                "created_at": now(),
            })
            text = update_page(text, page.slide_id, {"Status": "Awaiting SVG selection"})
        atomic_write(framework, text)

        for page, manifest, a_path, b_path, previews in packets:
            a_target = f"<{a_path}>"
            b_target = f"<{b_path}>"
            a_png = project_dir / str(previews["A"]["preview_png"])
            b_png = project_dir / str(previews["B"]["preview_png"])
            a_png_target = f"<{a_png}>"
            b_png_target = f"<{b_png}>"
            print(f"## {page.slide_id}｜A/B design choice\n")
            print("| A｜EY option A | B｜EY option B |")
            print("|---|---|")
            print(
                f"| ![{page.slide_id} A PNG preview]({a_png_target}) | "
                f"![{page.slide_id} B PNG preview]({b_png_target}) |\n"
            )
            print("Original SVG files:")
            print(f"- [A.svg]({a_target})")
            print(f"- [B.svg]({b_target})\n")
            print("Material differences:")
            differences = manifest.get("material_differences", [])
            if differences:
                for difference in differences:
                    print(f"- {difference}")
            else:
                print("- Not provided (non-blocking advisory)")
            advisories = manifest.get("advisories", [])
            if advisories:
                print("\nAdvisories:")
                for advisory in advisories:
                    print(f"- {advisory}")
            print(
                "\nBefore sending this comparison to the user, inspect both candidates. "
                "If either has a defect, run repair-ab-candidate for that same A/B slot and "
                "do not create Rn. Otherwise show both, then ask the user to choose A or B "
                "or request a targeted revision.\n"
            )
        return 0

    if args.command == "request-revision":
        page = next((p for p in page_entries(text) if p.slide_id == args.page), None)
        if not page or page.fields.get("Status") not in {
            "Awaiting SVG selection", "SVG confirmed",
        }:
            print(f"Revision request blocked: {args.page} is not in a selectable or confirmed SVG state")
            return 1
        if not args.note.strip():
            print("Revision request blocked: --note must record the targeted changes")
            return 1
        previous = active_revision(project_dir, args.page)
        base_version = args.base
        if not base_version and previous:
            base_version = str(previous.get("revision_id", ""))
        if not base_version and page.fields.get("Selected version") != "Pending":
            base_version = page.fields.get("Selected version")
        if not base_version or not re.fullmatch(r"(?:A|B|R[1-9]\d*)", base_version):
            print("Revision request blocked: provide a valid --base A, B, or Rn")
            return 1
        try:
            base_path = selected_working_path(project_dir, args.page, base_version)
        except ValueError as exc:
            print(f"Revision request blocked: {exc}")
            return 1
        problem = svg_error(base_path)
        if problem:
            print(f"Revision request blocked: {problem}")
            return 1
        if previous:
            previous["active"] = False
            previous["superseded_at"] = now()
            old_id = str(previous.get("revision_id", ""))
            if old_id:
                write_json(receipt_path(project_dir, args.page, f"{old_id}-request"), previous)
        revision_id = next_revision_id(project_dir, args.page)
        request = {
            "slide_id": args.page,
            "revision_id": revision_id,
            "base_version": base_version,
            "base_sha256": sha256(base_path),
            "note": args.note.strip(),
            "active": True,
            "created_at": now(),
        }
        request["request_sha256"] = revision_request_hash(request)
        receipts_dir = project_dir / "working" / "receipts"
        archive_items(project_dir, args.page, [
            *receipts_dir.glob(f"{args.page}-R*-presentation.json"),
        ])
        write_json(receipt_path(project_dir, args.page, f"{revision_id}-request"), request)
        write_json(revision_active_path(project_dir, args.page), request)
        if page.fields.get("Status") == "SVG confirmed":
            archive_items(project_dir, args.page, [
                project_dir / "svg_output" / f"{args.page}.svg",
                receipt_path(project_dir, args.page, "svg-selection"),
            ])
        text = update_page(text, args.page, {"Status": "Awaiting SVG selection", "Selected version": "Pending"})
        atomic_write(framework, text)
        print(f"Recorded targeted revision {revision_id} for {args.page} from base {base_version}.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "present-revision":
        action, selected = directive(text, project_dir)
        if action != "PRESENT_SVG_REVISION" or len(selected) != 1:
            print(f"Revision presentation blocked: current action is {action}")
            return 1
        page = selected[0]
        request = active_revision(project_dir, page.slide_id)
        if request is None:
            print("Revision presentation blocked: no active revision request")
            return 1
        problems = validate_revision(project_dir, page.slide_id, request)
        if problems:
            print("Revision presentation blocked: " + "; ".join(problems))
            return 1
        base_version = str(request["base_version"])
        revision_id = str(request["revision_id"])
        base_path = selected_working_path(project_dir, page.slide_id, base_version)
        revision_path = selected_working_path(project_dir, page.slide_id, revision_id)
        advisories = revision_advisories(project_dir, page.slide_id, request)
        try:
            previews = ensure_preview_pair(
                project_dir,
                page.slide_id,
                (base_version, revision_id),
                copy_contract=page_visible_copy_contract(project_dir, page.slide_id),
                prevalidated_source_hashes={
                    base_version: sha256(base_path),
                    revision_id: sha256(revision_path),
                },
            )
        except (OSError, PreviewError, ValueError) as exc:
            issue: dict[str, object] = preview_failure_issue(exc)
            issue.update({
                "slide_id": page.slide_id,
                "versions": [base_version, revision_id],
                "retry_command": command_line(controller, "present-revision", project_dir),
            })
            if issue.get("code") == "PREVIEW_BROWSER_SANDBOX_BLOCKED":
                issue["approval_prefix"] = ["python3", str(controller)]
            print(
                "Revision presentation blocked: "
                + json.dumps(issue, ensure_ascii=False, sort_keys=True)
            )
            return 1
        write_json(revision_presentation_path(project_dir, page.slide_id, revision_id), {
            "slide_id": page.slide_id,
            "request_sha256": request["request_sha256"],
            "base_sha256": sha256(base_path),
            "revision_sha256": sha256(revision_path),
            "advisories": advisories,
            **preview_presentation_evidence(
                project_dir, page.slide_id, (base_version, revision_id), previews
            ),
            "created_at": now(),
        })
        base_target = f"<{base_path}>"
        revision_target = f"<{revision_path}>"
        base_png = project_dir / str(previews[base_version]["preview_png"])
        revision_png = project_dir / str(previews[revision_id]["preview_png"])
        base_png_target = f"<{base_png}>"
        revision_png_target = f"<{revision_png}>"
        print(f"## {page.slide_id}｜Targeted revision review\n")
        print(f"Requested changes: {request.get('note')}\n")
        print(f"| {base_version}｜Base | {revision_id}｜Revision |")
        print("|---|---|")
        print(
            f"| ![{page.slide_id} {base_version} PNG preview]({base_png_target}) | "
            f"![{page.slide_id} {revision_id} PNG preview]({revision_png_target}) |\n"
        )
        print("Original SVG files:")
        print(f"- [{base_version}.svg]({base_target})")
        print(f"- [{revision_id}.svg]({revision_target})\n")
        if advisories:
            print("Advisories:")
            for advisory in advisories:
                print(f"- {advisory}")
            print()
        print(
            "Required user display: send both previews above together in the same message at "
            "equal scale; never show the revision alone."
        )
        print(f"Please explicitly confirm {revision_id}, or request another targeted revision.")
        return 0

    if args.command == "update-page":
        page = next((p for p in page_entries(text) if p.slide_id == args.page), None)
        if not page:
            print(f"Update blocked: page not found: {args.page}")
            return 1
        state = page.fields.get("Status")
        semantic_update = any(
            value is not None
            for value in (args.confirmed_decisions, args.open_items, args.title)
        )
        if semantic_update and state not in {"Not started", "Content reviewing"}:
            print("Update blocked: reopen content before changing title, decisions, or open items")
            return 1
        if args.review_mode is not None and state != "Not started":
            print("Update blocked: Review mode may change only before page review starts")
            return 1
        updates = {}
        if args.confirmed_decisions is not None:
            updates["Confirmed decisions"] = args.confirmed_decisions
        if args.open_items is not None:
            updates["Open items"] = args.open_items
        if args.review_mode is not None:
            updates["Review mode"] = args.review_mode
        if not updates and not args.title:
            print("Update blocked: no update supplied")
            return 1
        if updates:
            text = update_page(text, args.page, updates)
        if args.title:
            text = update_page_title(text, args.page, args.title)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=framework.parent, suffix=".md", delete=False
        ) as handle:
            handle.write(text)
            candidate_framework = Path(handle.name)
        post_errors = validate_framework(candidate_framework, project_dir)
        candidate_framework.unlink(missing_ok=True)
        if post_errors:
            print("Update produced an invalid framework: " + "; ".join(post_errors))
            return 1
        atomic_write(framework, text)
        print(f"Updated {args.page}.")
        print_directive(text, project_dir, controller)
        return 0

    if args.command == "set-output-filename":
        try:
            filename = validate_output_filename(args.filename)
            current = h2_section(text, "Current position")
            updated = replace_field(current, "Output filename", filename)
            candidate = text.replace(current, updated, 1)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=framework.parent, suffix=".md", delete=False
            ) as handle:
                handle.write(candidate)
                candidate_framework = Path(handle.name)
            problems = validate_framework(candidate_framework, project_dir)
            candidate_framework.unlink(missing_ok=True)
            if problems:
                raise ValueError("; ".join(problems))
            archive_items(project_dir, "output-filename", [handoff_result_path(project_dir)])
            atomic_write(framework, candidate)
        except (OSError, ValueError) as exc:
            print(f"Output filename update blocked: {exc}")
            return 1
        print(f"Output filename updated: {filename}")
        print_directive(candidate, project_dir, controller)
        return 0

    event = args.event
    review_to_clear: Path | None = None
    cleanup_warning: str | None = None
    try:
        current_action, _ = directive(text, project_dir)
        selected = assert_current_action(text, project_dir, event, args.page)
        ids = [page.slide_id for page in selected]
        if event == "content-approved":
            if not args.note:
                raise ValueError("content-approved requires --note recording the explicit user approval")
            review = project_dir / "working" / "provisional-content.md"
            receipt = review_receipt_path(project_dir, ids)
            if not receipt.is_file() or read_json(receipt).get("provisional_sha256") != sha256(review):
                raise ValueError("provisional content was not presented through present-review or changed afterward")
            content_path = project_dir / "content.md"
            provisional = review.read_text(encoding="utf-8")
            problems = provisional_content_errors(review, selected)
            if problems:
                raise ValueError("provisional build-spec validation failed: " + "; ".join(problems))
            existing = content_path.read_text(encoding="utf-8") if content_path.is_file() else ""
            content = promote_provisional_content(text, existing, provisional)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=project_dir, suffix=".md", delete=False
            ) as handle:
                handle.write(content)
                candidate_content = Path(handle.name)
            for slide_id, page in zip(ids, selected):
                problems = validate_blueprint(candidate_content, slide_id)
                section = content_section(content, slide_id)
                problems.extend(content_identity_errors(page, section))
                if problems:
                    candidate_content.unlink(missing_ok=True)
                    raise ValueError(f"{slide_id} build-spec validation failed: " + "; ".join(problems))
            candidate_content.unlink(missing_ok=True)
            atomic_write(content_path, content)
            for slide_id, page in zip(ids, selected):
                section = content_section(content, slide_id)
                write_json(receipt_path(project_dir, slide_id, "content"), {
                    "slide_id": slide_id,
                    "content_sha256": text_sha256(section),
                    "approval_note": args.note,
                    "created_at": now(),
                })
                text = update_page(text, slide_id, {"Status": "Content locked", "Open items": "None"})
                title_match = re.search(r"^- Title:\s*(.+)$", section, re.MULTILINE)
                if title_match:
                    text = update_page_title(text, slide_id, title_match.group(1).strip())
            review_to_clear = review
        elif event == "svg-selected":
            selections = parse_selections(args.selections)
            if set(selections) != set(ids):
                raise ValueError("explicit selections must cover exactly the active pages")
            for slide_id in ids:
                if current_action == "COLLECT_SVG_SELECTION" and selections[slide_id] not in {"A", "B"}:
                    raise ValueError(f"{slide_id} direct A/B selection must be A or B")
                presentation_file = receipt_path(project_dir, slide_id, "ab-presentation")
                if current_action == "COLLECT_SVG_SELECTION" and not ab_presentation_valid(
                    project_dir, slide_id
                ):
                    raise ValueError(f"{slide_id} A/B options were not presented or changed afterward")
                if current_action == "COLLECT_REVISION_CONFIRMATION":
                    request = active_revision(project_dir, slide_id)
                    if request is None or selections[slide_id] != request.get("revision_id"):
                        raise ValueError(f"{slide_id} must explicitly confirm the active revision")
                    if not revision_presentation_valid(project_dir, slide_id, request):
                        raise ValueError(f"{slide_id} revision was not presented or changed afterward")
                    request["active"] = False
                    request["confirmed_at"] = now()
                    revision_id = str(request["revision_id"])
                    write_json(receipt_path(project_dir, slide_id, f"{revision_id}-request"), request)
                    write_json(revision_active_path(project_dir, slide_id), request)
                    presentation_file = revision_presentation_path(
                        project_dir, slide_id, revision_id
                    )
                selected_path = selected_working_path(
                    project_dir, slide_id, selections[slide_id]
                )
                if not page_author_completion_valid(
                    project_dir, slide_id, selections[slide_id]
                ):
                    raise ValueError(
                        f"{slide_id} selected SVG has no valid hash-bound preflight receipt"
                    )
                if not presentation_file.is_file():
                    raise ValueError(f"{slide_id} has no presentation receipt")
                final_path = project_dir / "svg_output" / f"{slide_id}.svg"
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(selected_path, final_path)
                write_json(receipt_path(project_dir, slide_id, "svg-selection"), {
                    "slide_id": slide_id,
                    "selected_version": selections[slide_id],
                    "selected_sha256": sha256(selected_path),
                    "presentation_receipt": str(presentation_file.relative_to(project_dir)),
                    "presentation_receipt_sha256": sha256(presentation_file),
                    "canonical_sha256": sha256(final_path),
                    "source_preflight_gate": PAGE_PREFLIGHT_GATE_SCHEMA,
                    "accepted_at": now(),
                })
                text = update_page(text, slide_id, {
                    "Status": "SVG confirmed",
                    "Selected version": selections[slide_id],
                })
        else:
            raise ValueError(f"unsupported event: {event}")
        atomic_write(framework, text)
        if review_to_clear is not None:
            try:
                review_to_clear.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_warning = str(exc)
    except (ValueError, OSError) as exc:
        print(f"Transition blocked: {exc}")
        return 1
    print(f"Workflow advanced with event: {event}")
    if cleanup_warning:
        print(
            "WARNING: approved content was committed, but provisional-content cleanup failed: "
            + cleanup_warning
        )
    print_directive(text, project_dir, controller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
