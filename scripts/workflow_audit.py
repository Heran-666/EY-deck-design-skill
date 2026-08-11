#!/usr/bin/env python3
"""Cross-artifact workflow audit and event-target validation."""

from __future__ import annotations

import re
from pathlib import Path

from framework_lib import PageEntry, page_entries
from svg_boundary import candidate_errors, svg_error
from validate_deck_blueprint import validate_collection as validate_blueprint_collection
from validate_framework import validate as validate_framework
from workflow_authoring import (
    active_revision,
    page_author_completion_valid,
    revision_request_hash,
    validate_ab,
)
from workflow_content import content_identity_errors, content_section
from workflow_directives import directive
from workflow_io import read_json, sha256, text_sha256
from workflow_paths import receipt_path, revision_active_path, selected_working_path
from workflow_preview_evidence import ab_presentation_valid
from workflow_protected import protected_canonical_evidence_valid
from workflow_spec import (
    ACTION_EVENT,
    PAGE_PREFLIGHT_GATE_SCHEMA,
    PAGE_STATES,
    TERMINAL_STATES,
)


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
