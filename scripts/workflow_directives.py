#!/usr/bin/env python3
"""Single next-action authority and machine-readable directive construction."""

from __future__ import annotations

import json
from pathlib import Path

from framework_lib import PageEntry, page_entries
from preview_renderer import preview_paths
from preview_renderer import preview_receipt_errors
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
from workflow_io import command_line, sha256, text_sha256
from workflow_paths import (
    design_context_path,
    design_decision_path,
    selected_working_path,
    visual_qa_path,
)
from workflow_design import (
    DESIGN_MODULE_VERSION,
    DESIGN_OWNER,
    current_design_context,
    current_design_decision,
    design_page_fingerprint,
    design_workflow_enabled,
    visual_qa_pass_valid,
    visual_qa_receipt,
)
from workflow_protected import protected_artifact_valid
from workflow_spec import (
    B_OPTION_KERNEL,
    EY_PAGE_AUTHORING_INSTRUCTION,
    PREPARE_AUTHORING_ACTIONS,
    TERMINAL_STATES,
    WORKFLOW_VERSION,
)
from workflow_state import current_group, derived_phase


def _candidate_action(
    project_dir: Path,
    page: PageEntry,
    version: str,
    *,
    revision: bool = False,
) -> str | None:
    if current_design_decision(project_dir, page, version) is None:
        return (
            "PLAN_PAGE_DESIGN"
            if current_design_context(project_dir, page, version)
            else "PREPARE_PAGE_DESIGN"
        )
    if not page_author_completion_valid(project_dir, page.slide_id, version):
        if authoring_packet_valid(project_dir, page):
            return "GENERATE_SVG_REVISION" if revision else f"GENERATE_SVG_{version}"
        return "PREPARE_SVG_REVISION" if revision else f"PREPARE_SVG_{version}"
    qa = visual_qa_receipt(project_dir, page, version)
    if qa and qa.get("status") == "BLOCKED":
        return "REPAIR_VISUAL_QA"
    if not visual_qa_pass_valid(project_dir, page, version):
        if preview_receipt_errors(project_dir, page.slide_id, version):
            return "PREPARE_VISUAL_QA"
        return "REVIEW_VISUAL_QA"
    return None


def _v4_action_for_group(project_dir: Path, group: list[PageEntry]) -> tuple[str, list[PageEntry]]:
    page = group[0]
    if active_page_author_block(project_dir, page.slide_id):
        return "RESOLVE_PAGE_AUTHOR_BLOCK", [page]
    if page.fields.get("Status") in {"Not started", "Content reviewing"}:
        return "PRESENT_PAGE_REVIEW", [page]
    if page.fields.get("Status") == "Content locked":
        action = _candidate_action(project_dir, page, "A")
        if action:
            return action, [page]
        if page.fields.get("Authoring mode") == "Standard":
            action = _candidate_action(project_dir, page, "B")
            if action:
                return action, [page]
            errors, _ = validate_ab(project_dir, page.slide_id)
            if errors:
                return "RESOLVE_AB_CONFLICT", [page]
            return "PRESENT_AB_OPTIONS", [page]
        errors, _ = validate_single(project_dir, page.slide_id)
        if errors:
            return "GENERATE_SVG_A", [page]
        return "PRESENT_SINGLE_OPTION", [page]
    if page.fields.get("Status") == "Awaiting SVG decision":
        request = active_revision(project_dir, page.slide_id)
        if request is None:
            return "COLLECT_SVG_DECISION", [page]
        version = str(request.get("revision_id", ""))
        action = _candidate_action(project_dir, page, version, revision=True)
        if action:
            return action, [page]
        if validate_revision(project_dir, page.slide_id, request):
            return "GENERATE_SVG_REVISION", [page]
        if not revision_presentation_valid(project_dir, page.slide_id, request):
            return "PRESENT_SVG_REVISION", [page]
        return "COLLECT_REVISION_CONFIRMATION", [page]
    raise ValueError("active workflow 4.0 page has no actionable state")


def action_for_group(
    project_dir: Path,
    group: list[PageEntry],
    text: str | None = None,
) -> tuple[str, list[PageEntry]]:
    if text is not None and design_workflow_enabled(text):
        return _v4_action_for_group(project_dir, group)
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
    if phase == "Stage 1 — Sequential page loop":
        group = current_group(text)
        if not group:
            raise ValueError("derived phase has no active page group")
        return action_for_group(project_dir, group, text)
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
    if action == "PREPARE_PAGE_DESIGN":
        return {
            "run": command_line(controller, "prepare-design", project_dir, "--page", target_page)
        }
    if action == "PLAN_PAGE_DESIGN":
        return {
            "record_result": command_line(
                controller,
                "record-design-decision",
                project_dir,
                "--result-json",
                "<EXACT_DESIGN_DECISION_JSON>",
            )
        }
    if action == "PREPARE_VISUAL_QA":
        return {
            "run": command_line(controller, "prepare-visual-qa", project_dir, "--page", target_page)
        }
    if action == "REVIEW_VISUAL_QA":
        return {
            "record_result": command_line(
                controller,
                "visual-qa-result",
                project_dir,
                "--result-json",
                "<EXACT_VISUAL_QA_JSON>",
            )
        }
    if action == "REPAIR_VISUAL_QA":
        return {
            "run": command_line(
                controller,
                "repair-visual-qa",
                project_dir,
                "--page",
                selected[0].slide_id,
            )
        }
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
    if action == "PLAN_PAGE_DESIGN":
        payload["command_when"] = "after the Embedded PPT Master Design Lead returns one exact persisted Design Decision JSON object"
    elif action == "REVIEW_VISUAL_QA":
        payload["command_when"] = "after independently inspecting this one rendered candidate at full-slide scale"
    elif action in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"}:
        payload["command_when"] = "after the Embedded PPT Master SVG Producer returns its exact terminal JSON"
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
            "with each equal-scale preview in its own standalone image block; never put local "
            "preview images in a Markdown table or show the revision alone. "
            "After an explicit user decision use after_keep_base to retain the displayed Base or "
            "after_confirmation to confirm the displayed Revision; for another targeted change use "
            "for_targeted_changes"
        )
    elif action == "PRESENT_PAGE_REVIEW":
        payload["command_when"] = "after writing the active provisional-content sections"
    elif commands:
        payload["command_when"] = "now"
    if action in {
        "PREPARE_PAGE_DESIGN",
        "PLAN_PAGE_DESIGN",
        "PREPARE_VISUAL_QA",
        "REVIEW_VISUAL_QA",
        "REPAIR_VISUAL_QA",
    }:
        page = selected[0]
        version = _active_candidate_version(project_dir, page)
        payload["version"] = version
    if action == "PLAN_PAGE_DESIGN":
        page = selected[0]
        version = str(payload["version"])
        context_path = design_context_path(project_dir, page.slide_id, version)
        decision_path = design_decision_path(project_dir, page.slide_id, version)
        context = current_design_context(project_dir, page, version)
        if context is None:
            raise ValueError("design context is not prepared for the current candidate")
        payload.update({
            "route": "$ey-deck-design / Embedded PPT Master Design Lead",
            "route_instruction": (
                "Lead the complete visual-design decision for this candidate. Define its communication job "
                "and reading mode; choose and commit the primary claim, composition family, focal mechanism, "
                "information-model/data encoding, typography hierarchy, EY gesture, density, rationale, and "
                "avoid list. Use the persisted Embedded PPT Master policy and deck design memory. Do not author "
                "SVG, change approved meaning, own workflow state, or turn A/B similarity into a gate."
            ),
            "design_context_path": str(context_path.resolve()),
            "design_context_sha256": sha256(context_path),
            "design_owner": DESIGN_OWNER,
            "design_module_version": DESIGN_MODULE_VERSION,
            "design_policy_fingerprint": context["design_policy_manifest"]["fingerprint"],
            "design_decision_path": str(decision_path.resolve()),
        })
    if action in {"PREPARE_VISUAL_QA", "REVIEW_VISUAL_QA", "REPAIR_VISUAL_QA"}:
        page = selected[0]
        version = str(payload["version"])
        artifact = selected_working_path(project_dir, page.slide_id, version)
        preview_png, preview_receipt = preview_paths(project_dir, page.slide_id, version)
        decision_path = design_decision_path(project_dir, page.slide_id, version)
        decision = current_design_decision(project_dir, page, version)
        payload.update({
            "route": "$ey-deck-design / Embedded PPT Master / Independent Visual QA",
            "route_instruction": (
                "Inspect this rendered candidate by itself against its persisted Design Decision. "
                "Return PASS or BLOCKED for composition_fidelity, focal_hierarchy, data_story, and "
                "brand_expression and matching single-candidate issue_codes. "
                "Set scope=single-candidate-only. Do not edit the SVG during judgment."
            ),
            "qa_scope": "single-candidate-only",
            "design_owner": DESIGN_OWNER,
            "design_module_version": DESIGN_MODULE_VERSION,
            "qa_exclusion": "Do not compare A/B and do not judge whether their compositions differ.",
            "artifact_path": str(artifact.resolve()),
            "artifact_sha256": sha256(artifact) if artifact.is_file() else None,
            "preview_png": str(preview_png.resolve()),
            "preview_png_sha256": sha256(preview_png) if preview_png.is_file() else None,
            "preview_receipt": str(preview_receipt.resolve()),
            "preview_receipt_sha256": sha256(preview_receipt) if preview_receipt.is_file() else None,
            "design_decision_path": str(decision_path.resolve()),
            "design_decision_sha256": sha256(decision_path) if decision_path.is_file() else None,
            "design_decision": (
                {
                    key: decision["decision"].get(key)
                    for key in (
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
                        "avoid",
                    )
                }
                if decision else None
            ),
            "design_policy_fingerprint": (
                decision.get("design_policy_fingerprint") if decision else None
            ),
            "visual_qa_receipt": str(visual_qa_path(project_dir, page.slide_id, version).resolve()),
        })
    if action in {"GENERATE_SVG_A", "GENERATE_SVG_B", "GENERATE_SVG_REVISION"}:
        page = selected[0]
        version = author_version_for_action(action, project_dir, page)
        packet = current_authoring_packet(project_dir, page.slide_id)
        packet_page_matches = bool(
            packet
            and (
                packet.get("framework_design_fingerprint") == design_page_fingerprint(page)
                if isinstance(packet.get("design_policy_manifest"), dict)
                else packet.get("framework_page_sha256") == text_sha256(page.text)
            )
        )
        if not packet or not packet_page_matches:
            raise ValueError("authoring packet is not prepared for the current page")
        template_binding = packet.get("template_binding")
        if not isinstance(template_binding, dict):
            raise ValueError("authoring packet has no structured template binding")
        payload.update({
            "route": "$ey-deck-design / Embedded PPT Master SVG Producer",
            "route_instruction": EY_PAGE_AUTHORING_INSTRUCTION,
            "authoring_mode": page.fields.get("Authoring mode"),
            "version": version,
            "requested_artifact": str(
                selected_working_path(project_dir, page.slide_id, version).resolve()
            ),
            "packet_path": packet["packet_path"],
            "packet_sha256": packet["packet_sha256"],
            "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
            "template_profile_id": template_binding["profile_id"],
            "template_layout": template_binding["layout_key"],
            "template_prototype": template_binding["prototype_path"],
            "template_prototype_sha256": template_binding["prototype_sha256"],
            "template_structure_contract_sha256": template_binding[
                "structure_contract_sha256"
            ],
        })
        if isinstance(packet.get("design_policy_manifest"), dict):
            decision_path = design_decision_path(project_dir, page.slide_id, version)
            decision = current_design_decision(project_dir, page, version)
            if decision is None or not decision_path.is_file():
                raise ValueError("current candidate has no persisted Design Decision")
            context_path = design_context_path(project_dir, page.slide_id, version)
            payload.update({
                "design_owner": DESIGN_OWNER,
                "design_module_version": DESIGN_MODULE_VERSION,
                "design_context_path": str(context_path.resolve()),
                "design_context_sha256": sha256(context_path),
                "design_decision_path": str(decision_path.resolve()),
                "design_decision_sha256": sha256(decision_path),
                "design_decision": decision["decision"],
                "design_policy_fingerprint": packet["design_policy_fingerprint"],
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
            "mode": "standalone-blocks-equal-scale",
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
                "Show this exact Base/Revision pair together using one standalone image block per "
                "preview before asking the user to retain the Base, confirm the Revision, or request "
                "another targeted change; never put local preview images in a Markdown table or show "
                "the revision alone."
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


def _active_candidate_version(project_dir: Path, page: PageEntry) -> str:
    request = active_revision(project_dir, page.slide_id)
    if page.fields.get("Status") == "Awaiting SVG decision" and request:
        return str(request.get("revision_id", ""))
    if not visual_qa_pass_valid(project_dir, page, "A"):
        return "A"
    if page.fields.get("Authoring mode") == "Standard" and not visual_qa_pass_valid(
        project_dir, page, "B"
    ):
        return "B"
    return "A"


def print_directive(text: str, project_dir: Path, controller: Path) -> None:
    payload = directive_payload(text, project_dir, controller)
    if payload["action"] in {"PREPARE_CONFIRMED_EXPORT", "RUN_CONFIRMED_EXPORT"}:
        print("STAGE_1_COMPLETE")
    print("NEXT_DIRECTIVE_JSON")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
