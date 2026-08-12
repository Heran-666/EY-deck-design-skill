#!/usr/bin/env python3
"""Single next-action authority and machine-readable directive construction."""

from __future__ import annotations

import json
from pathlib import Path

from framework_lib import PageEntry, page_entries
from preview_renderer import preview_paths
from workflow_authoring import (
    active_page_author_block,
    active_revision,
    author_version_for_action,
    authoring_packet_valid,
    current_authoring_packet,
    page_author_completion_valid,
    review_context,
    revision_presentation_valid,
    validate_ab,
    validate_single,
    validate_revision,
)
from workflow_export import inspect_export_workspace
from workflow_handoff import current_export, current_handoff_result, output_filename
from workflow_io import command_line, text_sha256
from workflow_paths import selected_working_path
from workflow_protected import protected_artifact_valid
from workflow_spec import (
    B_OPTION_KERNEL,
    EY_PAGE_AUTHORING_INSTRUCTION,
    PREPARE_AUTHORING_ACTIONS,
    TERMINAL_STATES,
    WORKFLOW_VERSION,
)
from workflow_state import current_group, derived_phase


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
        if page.fields.get("Authoring mode") != "Standard":
            continue
        if not page_author_completion_valid(project_dir, page.slide_id, "B"):
            action = "GENERATE_SVG_B" if authoring_packet_valid(project_dir, page) else "PREPARE_SVG_B"
            return action, [page]
    for page in locked:
        if page.fields.get("Authoring mode") != "Standard":
            continue
        errors, _ = validate_ab(project_dir, page.slide_id)
        if errors:
            return "RESOLVE_AB_CONFLICT", [page]
    simplified = [page for page in locked if page.fields.get("Authoring mode") == "Simplified"]
    for page in simplified:
        errors, _ = validate_single(project_dir, page.slide_id)
        if errors:
            return "GENERATE_SVG_A", [page]
    if simplified:
        return "PRESENT_SINGLE_OPTION", simplified
    standard = [page for page in locked if page.fields.get("Authoring mode") == "Standard"]
    if standard:
        return "PRESENT_AB_OPTIONS", standard
    for page in group:
        if page.fields.get("Status") != "Awaiting SVG decision":
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
    awaiting = [page for page in group if page.fields.get("Status") == "Awaiting SVG decision"]
    if awaiting:
        return "COLLECT_SVG_DECISION", awaiting
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
    if action == "PRESENT_SINGLE_OPTION":
        return {"run": command_line(controller, "present-single", project_dir)}
    if action == "COLLECT_SVG_DECISION":
        modes = {page.fields.get("Authoring mode") for page in selected}
        selections = ",".join(
            f"{page.slide_id}="
            + ("A" if page.fields.get("Authoring mode") == "Simplified" else "<A_OR_B>")
            for page in selected
        )
        if len(modes) == 1:
            repair_commands = {
                "repair_before_user_display": command_line(
                    controller,
                    "repair-candidate",
                    project_dir,
                    "--page",
                    target_page,
                    "--version",
                    "A" if modes == {"Simplified"} else "<A_OR_B>",
                    "--note",
                    "<CANDIDATE_DEFECT>",
                )
            }
        else:
            repair_commands = {
                f"repair_before_user_display_{page.slide_id}": command_line(
                    controller,
                    "repair-candidate",
                    project_dir,
                    "--page",
                    page.slide_id,
                    "--version",
                    (
                        "A"
                        if page.fields.get("Authoring mode") == "Simplified"
                        else "<A_OR_B>"
                    ),
                    "--note",
                    "<CANDIDATE_DEFECT>",
                )
                for page in selected
            }
        return {
            **repair_commands,
            "after_confirmation_or_selection": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "svg-confirmed",
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
                "<DISPLAYED_BASE_VERSION>",
                "--note",
                "<TARGETED_CHANGES>",
            ),
        }
    if action == "PRESENT_SVG_REVISION":
        return {"run": command_line(controller, "present-revision", project_dir)}
    if action == "COLLECT_REVISION_CONFIRMATION":
        request = active_revision(project_dir, selected[0].slide_id) or {}
        base_version = str(request.get("base_version", "<Base>"))
        revision_id = str(request.get("revision_id", "<Rn>"))
        return {
            "after_keep_base": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "svg-confirmed",
                "--page",
                selected[0].slide_id,
                "--selections",
                f"{selected[0].slide_id}={base_version}",
            ),
            "after_confirmation": command_line(
                controller,
                "advance",
                project_dir,
                "--event",
                "svg-confirmed",
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
    elif action == "COLLECT_SVG_DECISION":
        modes = {page.fields.get("Authoring mode") for page in selected}
        if modes == {"Simplified"}:
            payload["command_when"] = (
                "after the user has seen every single A preview and explicitly confirms or "
                "requests changes for each page"
            )
        elif modes == {"Standard"}:
            payload["command_when"] = (
                "after the user has seen every A/B comparison and explicitly selects or "
                "requests changes for each page"
            )
        else:
            payload["command_when"] = (
                "after the user has seen every page in its mode-required display: a single A "
                "preview for each Simplified page and an A/B comparison for each Standard page; "
                "then explicitly confirm, select, or request changes for every page"
            )
        payload["decision_requirements"] = [
            {
                "slide_id": page.slide_id,
                "authoring_mode": page.fields.get("Authoring mode"),
                "required_display": (
                    "single-A-preview"
                    if page.fields.get("Authoring mode") == "Simplified"
                    else "A/B-comparison"
                ),
                "allowed_selections": (
                    ["A"]
                    if page.fields.get("Authoring mode") == "Simplified"
                    else ["A", "B"]
                ),
                "allowed_repair_versions": (
                    ["A"]
                    if page.fields.get("Authoring mode") == "Simplified"
                    else ["A", "B"]
                ),
            }
            for page in selected
        ]
    elif action == "COLLECT_REVISION_CONFIRMATION":
        payload["command_when"] = (
            "first send the complete request-bound Base/Revision comparison in one user message, "
            "with both previews side by side at equal scale; never show the revision alone. "
            "After an explicit user decision use after_keep_base to retain the displayed Base or "
            "after_confirmation to confirm the displayed Revision; for another targeted change use "
            "for_targeted_changes"
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
            "authoring_mode": page.fields.get("Authoring mode"),
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
            "allowed_selections": [base_version, revision_id],
            "base_preview_png": str(base_preview.resolve()),
            "revision_preview_png": str(revision_preview.resolve()),
            "base_svg": str(
                selected_working_path(project_dir, page.slide_id, base_version).resolve()
            ),
            "revision_svg": str(
                selected_working_path(project_dir, page.slide_id, revision_id).resolve()
            ),
            "instruction": (
                "Show this exact Base/Revision pair together before asking the user to retain the "
                "Base, confirm the Revision, or request another targeted change; never show the "
                "revision alone."
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
