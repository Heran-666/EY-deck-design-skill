#!/usr/bin/env python3
"""Workflow mutations, recovery transitions, and terminal receipt recording."""

from __future__ import annotations

import re
from pathlib import Path

from framework_lib import page_entries
from preview_renderer import preview_paths, preview_runtime_errors, preview_runtime_path
from svg_boundary import candidate_errors, protected_candidate_errors, svg_canvas
from validate_terminal_result import validate_terminal_result
from workflow_authoring import (
    active_page_author_block,
    active_revision,
    author_version_for_action,
    authoring_packet_paths,
    current_authoring_packet,
    page_author_completion_valid,
    parse_terminal_json,
    revision_presentation_path,
)
from workflow_content import content_section
from workflow_copy_contract import visible_copy_errors
from workflow_directives import directive
from workflow_doctor import export_runtime_binding, run_doctor
from workflow_handoff import current_export, current_handoff_result, recorded_export
from workflow_io import atomic_write, now, read_json, sha256, text_sha256, write_json
from workflow_paths import (
    archive_items,
    handoff_result_path,
    page_author_result_path,
    receipt_path,
    selected_working_path,
)
from workflow_runtime import stage2_runtime_path, validate_stage2_runtime
from workflow_spec import (
    LEGACY_MANAGED_END,
    LEGACY_MANAGED_START,
    MANAGED_END,
    MANAGED_START,
    STAGE1_ACCEPTANCE_SCHEMA,
    WORKFLOW_VERSION,
)
from workflow_state import current_group, update_page
from workflow_templates import template_candidate_errors


def record_handoff_result(text: str, project_dir: Path, raw: str) -> None:
    incoming = parse_terminal_json(raw)
    action, _pages = directive(text, project_dir)
    allow_recorded_environment_block = (
        action == "PREPARE_PPT_MASTER_EXPORT"
        and incoming.get("status") == "BLOCKED"
        and incoming.get("route") == "embedded-ppt-master-stage2"
        and incoming.get("repair_scope") == "environment"
    )
    if action != "RUN_PPT_MASTER_EXPORT" and not allow_recorded_environment_block:
        raise ValueError(f"handoff result blocked: current action is {action}")
    export = (
        current_export(text, project_dir)
        if action == "RUN_PPT_MASTER_EXPORT"
        else recorded_export(text, project_dir)
    )
    manifest = read_json(Path(export["manifest_path"]))
    result_errors = validate_terminal_result(manifest, incoming)
    if result_errors:
        raise ValueError("terminal-result validation failed: " + "; ".join(result_errors))
    status = str(incoming["status"])
    payload: dict[str, object] = {
        "status": status,
        "route": "embedded-ppt-master-stage2",
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
    if action not in {"RUN_PPT_MASTER_A", "RUN_PPT_MASTER_B", "RUN_PPT_MASTER_REVISION"} or len(selected) != 1:
        raise ValueError(f"PPT Master Stage 1 result blocked: current action is {action}")
    page = selected[0]
    version = author_version_for_action(action, project_dir, page)
    packet = current_authoring_packet(project_dir, page.slide_id)
    packet_page_matches = bool(
        packet and packet.get("framework_page_sha256") == text_sha256(page.text)
    )
    if not packet or not packet_page_matches:
        raise ValueError("run controller next to materialize the current hash-bound page packet first")
    result = parse_terminal_json(raw)
    if result.get("route") != "embedded-ppt-master-stage1":
        raise ValueError("PPT Master Stage 1 terminal result route must be embedded-ppt-master-stage1")
    status = result.get("status")
    if status not in {"COMPLETE", "BLOCKED"}:
        raise ValueError("PPT Master Stage 1 terminal result status must be COMPLETE or BLOCKED")
    allowed = (
        {"status", "route", "artifact_path", "material_differences"}
        if status == "COMPLETE"
        else {
            "status",
            "route",
            "stage",
            "reason",
            "repair_scope",
            "resume_from",
            "slide_ids",
        }
    )
    unexpected = sorted(set(result) - allowed)
    if unexpected:
        raise ValueError(
            "PPT Master Stage 1 terminal result has unsupported fields: "
            + ", ".join(unexpected)
        )
    payload: dict[str, object] = {
        "status": status,
        "route": "embedded-ppt-master-stage1",
        "terminal_result": result,
        "slide_id": page.slide_id,
        "authoring_mode": page.fields.get("Authoring mode"),
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
            raise ValueError(f"PPT Master Stage 1 artifact must be the requested path: {expected}")
        contract = packet.get("visible_copy_contract")
        problems = candidate_errors(artifact)
        problems.extend(template_candidate_errors(artifact, packet.get("template_binding")))
        if isinstance(contract, dict):
            problems.extend(visible_copy_errors(artifact, contract))
        else:
            problems.append("Stage 1 packet has no valid visible-copy contract")
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
        payload["template_structure_contract_sha256"] = packet[
            "template_structure_contract_sha256"
        ]
        payload["acceptance_gate"] = {
            "schema": STAGE1_ACCEPTANCE_SCHEMA,
            "status": "PASS",
            "artifact_sha256": artifact_sha256,
            "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
            "template_structure_contract_sha256": packet[
                "template_structure_contract_sha256"
            ],
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
        if result.get("repair_scope") not in {"design", "content", "environment"}:
            raise ValueError("PPT Master Stage 1 BLOCKED repair_scope must be design, content, or environment")
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
        raise ValueError(f"PPT Master Stage 1 resume blocked: current action is {action}")
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
    expected_scope = result.get("repair_scope")
    if scope != expected_scope or scope not in {"design", "content"} or not note:
        raise ValueError(f"PPT Master recovery requires --scope {expected_scope} and --note")
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
    updates = {"Status": target_state, "Confirmed version": "Pending"}
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


def repair_candidate(
    text: str,
    project_dir: Path,
    slide_id: str,
    version: str,
    note: str,
) -> str:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    if page.fields.get("Status") not in {"Content locked", "Awaiting SVG decision"}:
        raise ValueError(
            f"{slide_id} candidate repair requires Content locked or Awaiting SVG decision"
        )
    group = current_group(text)
    if slide_id not in {item.slide_id for item in group}:
        raise ValueError(f"{slide_id} is not in the active page group")
    revision = active_revision(project_dir, slide_id)
    allowed_versions = (
        {str(revision.get("revision_id"))}
        if revision
        else ({"A"} if page.fields.get("Authoring mode") == "Simplified" else {"A", "B"})
    )
    if version not in allowed_versions:
        allowed = ", ".join(sorted(allowed_versions))
        raise ValueError(f"candidate repair version must be {allowed} for this page mode")
    if not note.strip():
        raise ValueError("candidate repair requires a non-empty defect note")
    if not page_author_completion_valid(project_dir, slide_id, version):
        raise ValueError(f"{slide_id} {version} has no valid candidate to repair")

    preview_png, preview_receipt = preview_paths(project_dir, slide_id, version)
    archive_items(project_dir, f"{slide_id}-candidate-{version}", [
        selected_working_path(project_dir, slide_id, version),
        page_author_result_path(project_dir, slide_id, version),
        preview_png,
        preview_receipt,
        (
            revision_presentation_path(project_dir, slide_id, version)
            if revision
            else receipt_path(
                project_dir,
                slide_id,
                "single-presentation"
                if page.fields.get("Authoring mode") == "Simplified"
                else "ab-presentation",
            )
        ),
    ])
    text = update_page(
        text,
        slide_id,
        {
            "Status": "Awaiting SVG decision" if revision else "Content locked",
            "Confirmed version": "Pending",
        },
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
                "Confirmed version": "Pending",
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

Read `{skill_root / 'SKILL.md'}` once. On entry, re-entry, post-compaction, or uncertain state, run
`python3 "{controller}" next --project-dir . --format json`; follow only its action,
`command_when`, and the condition-matching command data. Treat emitted locked-content packets,
candidate paths, previews, manifests, and receipt hashes as the recovery authority. A successful controller command already returns the next directive. Never edit
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
            {"Status": target_state, "Confirmed version": "Pending"},
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
