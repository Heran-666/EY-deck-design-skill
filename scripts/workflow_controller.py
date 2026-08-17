#!/usr/bin/env python3
"""Application controller for EY content approval and page-SVG decisions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from framework_lib import PageEntry, h2_section, line_fields, page_entries, replace_field
from validate_deck_blueprint import validate_collection
from validate_framework import validate as validate_framework
from workflow_content import content_section, promote_provisional_content, provisional_content_errors
from workflow_io import atomic_write, command_line, now, read_json, sha256, text_sha256, write_json
from workflow_paths import ProjectPaths
from workflow_ppt_master import (
    SERVICE_CLI,
    candidate_plan_for_page,
    embedding_errors,
    write_packet,
    write_page_context,
)
from workflow_pptx import (
    SERVICE_CONTRACT as PPTX_SERVICE_CONTRACT,
    export_from_request,
    export_valid,
    request_valid as pptx_request_valid,
    write_request as write_pptx_request,
)
from workflow_spec import (
    READABLE_WORKFLOW_VERSIONS,
    TERMINAL_PAGE_STATES,
    WORKFLOW_VERSION,
    normalize_page_type,
)
from workflow_svg import (
    candidate_valid,
    confirm_candidate,
    confirmation_valid,
    discard_cycle,
    latest_revision,
    next_revision,
    presentation_valid,
    presented_versions,
    record_candidate,
    record_presentation,
    require_version,
)


SVG_RUNTIME_ENV = "EY_DECK_SVG_PYTHON"


def update_page(text: str, slide_id: str, updates: dict[str, str]) -> str:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    updated = page.text
    for field, value in updates.items():
        updated = replace_field(updated, field, value)
    return text.replace(page.text, updated, 1)


def update_page_title(text: str, slide_id: str, title: str) -> str:
    replacement = f"### {slide_id}｜{title}"
    return re.sub(
        rf"^### {re.escape(slide_id)}｜.*$",
        lambda _match: replacement,
        text,
        count=1,
        flags=re.MULTILINE,
    )


def active_page(text: str) -> PageEntry | None:
    return next(
        (page for page in page_entries(text) if page.fields.get("Status") not in TERMINAL_PAGE_STATES),
        None,
    )


def page_by_id(text: str, slide_id: str) -> PageEntry:
    page = next((item for item in page_entries(text) if item.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"page not found: {slide_id}")
    return page


def review_valid(paths: ProjectPaths, page: PageEntry) -> bool:
    if not paths.content_review.is_file() or not paths.provisional.is_file():
        return False
    try:
        receipt = read_json(paths.content_review)
    except ValueError:
        return False
    scope_hash = text_sha256(
        json.dumps(
            review_context(paths.framework.read_text(encoding="utf-8"), page),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return (
        receipt.get("slide_id") == page.slide_id
        and (
            receipt.get("review_scope_sha256") == scope_hash
            or receipt.get("framework_sha256") == sha256(paths.framework)
        )
        and receipt.get("provisional_sha256") == sha256(paths.provisional)
    )


def content_validation_errors(paths: ProjectPaths, text: str) -> list[str]:
    pages = [
        page
        for page in page_entries(text)
        if page.fields.get("Status") not in {"Deferred template", "Protected placeholder"}
    ]
    if not paths.content.is_file():
        if not pages:
            return []
        return [f"content not found: {paths.content}"]
    return validate_collection(
        paths.content,
        [page.slide_id for page in pages],
        require_complete=True,
        expected_page_types={page.slide_id: page.fields.get("Page type", "") for page in pages},
    )


def review_context(text: str, page: PageEntry) -> dict[str, object]:
    pages = page_entries(text)
    index = next(i for i, item in enumerate(pages) if item.slide_id == page.slide_id)
    return {
        "project_context": line_fields(h2_section(text, "Project context")),
        "active_page": {"slide_id": page.slide_id, "title": page.title, **page.fields},
        "previous_page": None if index == 0 else {"slide_id": pages[index - 1].slide_id, "title": pages[index - 1].title},
        "next_page": None if index + 1 == len(pages) else {"slide_id": pages[index + 1].slide_id, "title": pages[index + 1].title},
    }


def _svg_runtime_python() -> str:
    configured = os.environ.get(SVG_RUNTIME_ENV, "").strip()
    if not configured:
        raise ValueError(
            "Load workspace dependencies and set command-scoped "
            f"{SVG_RUNTIME_ENV} to the returned Python executable."
        )
    path = Path(configured).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError(
            f"{SVG_RUNTIME_ENV} must be the absolute bundled Python executable"
        )
    probe = subprocess.run(
        [str(path), "-c", "from PIL import Image"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode:
        raise ValueError(
            "SVG validation runtime is unavailable. Load workspace dependencies "
            f"and set {SVG_RUNTIME_ENV} to its Python executable."
        )
    return str(path.resolve())


def service_request_payload(paths: ProjectPaths, controller: Path, slide_id: str, version: str) -> dict[str, object]:
    request = paths.packet(slide_id, version)
    python = _svg_runtime_python()
    record = command_line(
        controller, "record-svg", paths.root,
        "--page", slide_id, "--version", version,
    )
    return {
        "version": version,
        "request_path": str(request),
        "validate_request": shlex.join([python, str(SERVICE_CLI), "validate-request", str(request)]),
        "record": shlex.join(["env", f"{SVG_RUNTIME_ENV}={python}", *shlex.split(record)]),
    }


def planned_initial_versions(paths: ProjectPaths, page: PageEntry) -> tuple[str, ...]:
    """Resolve the current hash-bound single-SVG plan."""
    framework_text = paths.framework.read_text(encoding="utf-8")
    plan = candidate_plan_for_page(paths, framework_text, page)
    versions = plan.get("versions")
    if versions != ["A"]:
        raise ValueError(f"invalid candidate plan for {page.slide_id}")
    return tuple(versions)


def svg_cycle_started(paths: ProjectPaths, page: PageEntry) -> bool:
    versions = planned_initial_versions(paths, page)
    packets = [paths.packet(page.slide_id, version) for version in versions]
    if any(not packet.is_file() for packet in packets):
        return False
    context_path = paths.page_context(page.slide_id)
    if not context_path.is_file():
        try:
            legacy_requests = [read_json(packet) for packet in packets]
        except ValueError:
            return False
        return all(
            request.get("schema") == "ppt-master.page-svg-request.v2"
            and request.get("caller") == "ey-deck-design"
            and request.get("slide_id") == page.slide_id
            and request.get("version") == version
            for request, version in zip(legacy_requests, versions)
        )
    try:
        context = read_json(context_path)
        requests = [read_json(packet) for packet in packets]
    except ValueError:
        return False
    current_section_hash = text_sha256(
        content_section(paths.content.read_text(encoding="utf-8"), page.slide_id).rstrip()
    )
    if (
        context.get("schema") != "ey-deck.page-authoring-context.v1"
        or context.get("caller") != "ey-deck-design"
        or context.get("slide_id") != page.slide_id
        or context.get("approved_content_sha256") != current_section_hash
        or context.get("candidate_plan")
        != candidate_plan_for_page(paths, paths.framework.read_text(encoding="utf-8"), page)
    ):
        return False
    context_hash = sha256(context_path)
    return all(
        request.get("schema") == "ppt-master.page-svg-request.v3"
        and request.get("caller") == "ey-deck-design"
        and request.get("slide_id") == page.slide_id
        and request.get("version") == version
        and request.get("authoring_context")
        == {"path": str(context_path.resolve()), "sha256": context_hash}
        for request, version in zip(requests, versions)
    )


def decision_directive(
    paths: ProjectPaths,
    slide_id: str,
    versions: list[str],
    controller: Path,
    *,
    revision: bool,
) -> dict[str, object]:
    feedback = paths.revision_request(slide_id)
    return {
        "action": "COLLECT_SVG_REVISION_DECISION" if revision else "COLLECT_SVG_DECISION",
        "slide_id": slide_id,
        "displayed_versions": versions,
        "decision_rules": "Confirm the displayed SVG, or write one concrete optimization request for that SVG.",
        "revision_feedback_file": str(feedback),
        "commands": {
            "confirm": command_line(controller, "confirm-svg", paths.root, "--page", slide_id, "--version", "<DISPLAYED_VERSION>"),
            "revise": command_line(
                controller, "request-svg-revision", paths.root,
                "--page", slide_id, "--base", "<DISPLAYED_VERSION>",
                "--feedback-file", str(feedback),
            ),
        },
    }


def svg_directive(paths: ProjectPaths, page: PageEntry, controller: Path) -> dict[str, object]:
    latest = latest_revision(paths, page.slide_id)
    if latest:
        if not candidate_valid(paths, page.slide_id, latest):
            return {
                "action": "RUN_EMBEDDED_PPT_MASTER_SVG",
                "slide_id": page.slide_id,
                "requests": [service_request_payload(paths, controller, page.slide_id, latest)],
            }
        versions = [latest]
        if not presentation_valid(paths, page.slide_id, versions):
            return {
                "action": "PRESENT_SVG_REVISION",
                "slide_id": page.slide_id,
                "versions": versions,
                "artifacts": [str(paths.candidate(page.slide_id, item)) for item in versions],
                "commands": {
                    "present": command_line(
                        controller, "present-svg", paths.root,
                        "--page", page.slide_id, "--versions", ",".join(versions),
                    )
                },
            }
        return decision_directive(paths, page.slide_id, versions, controller, revision=True)

    initial_versions = planned_initial_versions(paths, page)
    missing = [item for item in initial_versions if not candidate_valid(paths, page.slide_id, item)]
    if missing:
        return {
            "action": "RUN_EMBEDDED_PPT_MASTER_SVG",
            "slide_id": page.slide_id,
            "requests": [service_request_payload(paths, controller, page.slide_id, item) for item in missing],
        }
    versions = list(initial_versions)
    if not presentation_valid(paths, page.slide_id, versions):
        return {
            "action": "PRESENT_SVG_OPTION",
            "slide_id": page.slide_id,
            "versions": versions,
            "artifacts": [str(paths.candidate(page.slide_id, item)) for item in versions],
            "commands": {
                "present": command_line(
                    controller, "present-svg", paths.root,
                    "--page", page.slide_id, "--versions", ",".join(versions),
                )
            },
        }
    return decision_directive(paths, page.slide_id, versions, controller, revision=False)


def directive_payload(project_dir: Path, text: str, controller: Path) -> dict[str, object]:
    paths = ProjectPaths(project_dir)
    for page in page_entries(text):
        if page.fields.get("Status") == "SVG confirmed" and not confirmation_valid(paths, page.slide_id):
            return {
                "action": "REPAIR_STALE_SVG_CONFIRMATION",
                "slide_id": page.slide_id,
                "commands": {"reopen": command_line(controller, "reopen-svg", project_dir, "--page", page.slide_id)},
            }
        if page.fields.get("Status") not in TERMINAL_PAGE_STATES:
            break
    page = active_page(text)
    if page is None:
        paths = ProjectPaths(project_dir)
        filename = line_fields(h2_section(text, "Current position"))["Output filename"]
        if export_valid(paths, text):
            return {
                "action": "PPTX_STAGE_COMPLETE",
                "pptx": str(paths.pptx_output(filename).resolve()),
                "postflight_report": str(paths.pptx_postflight_report(filename).resolve()),
                "text_frame_audit": str(paths.pptx_text_audit.resolve()),
            }
        if pptx_request_valid(paths, text):
            return {
                "action": "RUN_EMBEDDED_PPT_MASTER_PPTX",
                "request_path": str(paths.pptx_request.resolve()),
                "service_contract": str(PPTX_SERVICE_CONTRACT.resolve()),
                "requested_artifact": str(paths.pptx_output(filename).resolve()),
                "conversion_contract": {
                    "object_model": "editable-native-drawingml",
                    "text_flow": "preserve",
                    "text_frame_rule": "one logical SVG <text> carrier becomes one PowerPoint text box",
                },
                "required_environment": {
                    "EY_DECK_PPTX_PYTHON": "Absolute Python executable returned by load_workspace_dependencies",
                },
                "commands": {
                    "run": command_line(controller, "export-pptx", project_dir),
                },
            }
        return {
            "action": "PREPARE_PPTX_EXPORT",
            "ordered_slides": [
                {
                    "slide_id": item.slide_id,
                    "page_type": item.fields.get("Page type", ""),
                    "source_kind": (
                        "confirmed-svg"
                        if item.fields.get("Status") == "SVG confirmed"
                        else "deferred-template"
                    ),
                }
                for item in page_entries(text)
                if item.fields.get("Status") != "Protected placeholder"
            ],
            "commands": {
                "run": command_line(controller, "prepare-pptx-export", project_dir),
            },
        }
    status = page.fields.get("Status")
    if status in {"Not started", "Content reviewing"}:
        if review_valid(paths, page):
            return {
                "action": "COLLECT_CONTENT_DECISION",
                "slide_id": page.slide_id,
                "review_path": str(paths.provisional),
                "commands": {
                    "approve": command_line(controller, "approve-content", project_dir),
                    "revise": "Replace working/provisional-content.md, then run present-review again.",
                },
            }
        return {
            "action": "PRESENT_PAGE_REVIEW",
            "slide_id": page.slide_id,
            "provisional_content": {"path": str(paths.provisional), "expected_pages": [page.slide_id]},
            "review_context": review_context(text, page),
            "commands": {"present": command_line(controller, "present-review", project_dir)},
        }
    if status == "Content locked":
        if svg_cycle_started(paths, page):
            return svg_directive(paths, page, controller)
        plan = candidate_plan_for_page(paths, text, page)
        initial_versions = tuple(plan["versions"])
        return {
            "action": "PREPARE_SVG_CANDIDATES",
            "slide_id": page.slide_id,
            "versions": list(initial_versions),
            "candidate_plan": plan,
            "required_environment": {
                SVG_RUNTIME_ENV: "Absolute Python executable returned by load_workspace_dependencies",
            },
            "commands": {"run": command_line(controller, "prepare-svg-candidates", project_dir, "--page", page.slide_id)},
        }
    if status == "Awaiting SVG decision":
        return svg_directive(paths, page, controller)
    raise ValueError(f"unsupported active state for {page.slide_id}: {status}")


def load_context(project_dir: Path) -> tuple[Path, str]:
    paths = ProjectPaths(project_dir)
    errors = validate_framework(paths.framework, project_dir)
    if errors:
        raise ValueError("; ".join(errors))
    return paths.framework, paths.framework.read_text(encoding="utf-8")


def print_next(project_dir: Path, text: str, controller: Path) -> None:
    print(json.dumps(directive_payload(project_dir, text, controller), ensure_ascii=False, indent=2))


def handle_present_review(project_dir: Path, text: str, controller: Path) -> int:
    page = active_page(text)
    if page is None or page.fields.get("Status") not in {"Not started", "Content reviewing"}:
        raise ValueError("no page is waiting for content review")
    paths = ProjectPaths(project_dir)
    errors = provisional_content_errors(paths.provisional, [page])
    if errors:
        raise ValueError(" | ".join(errors))
    write_json(
        paths.content_review,
        {
            "slide_id": page.slide_id,
            "review_scope_sha256": text_sha256(
                json.dumps(review_context(text, page), ensure_ascii=False, sort_keys=True)
            ),
            "provisional_sha256": sha256(paths.provisional),
            "presented_at": now(),
        },
    )
    print(paths.provisional.read_text(encoding="utf-8"))
    print("\nContent review is ready. Explicit approval is required.")
    print(command_line(controller, "approve-content", project_dir))
    return 0


def handle_approve_content(project_dir: Path, framework: Path, text: str, controller: Path) -> int:
    page = active_page(text)
    paths = ProjectPaths(project_dir)
    if (
        page is None
        or page.fields.get("Status") not in {"Not started", "Content reviewing"}
        or not review_valid(paths, page)
    ):
        raise ValueError("no current presented content review to approve")
    provisional = paths.provisional.read_text(encoding="utf-8")
    existing = paths.content.read_text(encoding="utf-8") if paths.content.is_file() else ""
    atomic_write(paths.content, promote_provisional_content(text, existing, provisional))
    section = content_section(provisional, page.slide_id)
    title_match = re.search(r"^- Title:\s*(.+)$", section, re.MULTILINE)
    if not title_match:
        raise ValueError(f"{page.slide_id} has no Title field")
    text = update_page(text, page.slide_id, {"Status": "Content locked", "Open items": "None"})
    text = update_page_title(text, page.slide_id, title_match.group(1).strip())
    atomic_write(framework, text)
    paths.provisional.unlink(missing_ok=True)
    print_next(project_dir, text, controller)
    return 0


def handle_prepare_candidates(project_dir: Path, text: str, page_id: str, controller: Path) -> int:
    page = page_by_id(text, page_id)
    current = active_page(text)
    if current is None or current.slide_id != page.slide_id or page.fields.get("Status") != "Content locked":
        raise ValueError(f"{page_id} is not the active content-locked page")
    errors = embedding_errors()
    if errors:
        raise ValueError(" | ".join(errors))
    _svg_runtime_python()
    paths = ProjectPaths(project_dir)
    discard_cycle(paths, page_id)
    paths.svg_dir(page_id).mkdir(parents=True, exist_ok=True)
    write_page_context(paths, text, page)
    for version in planned_initial_versions(paths, page):
        write_packet(paths, page, version)
    print_next(project_dir, text, controller)
    return 0


def handle_record_svg(project_dir: Path, text: str, page_id: str, version: str, controller: Path) -> int:
    version = require_version(version)
    page = page_by_id(text, page_id)
    current = active_page(text)
    if (
        current is None
        or current.slide_id != page.slide_id
        or page.fields.get("Status") not in {"Content locked", "Awaiting SVG decision"}
        or not svg_cycle_started(ProjectPaths(project_dir), page)
    ):
        raise ValueError(f"{page_id} is not the active page awaiting an SVG decision")
    paths = ProjectPaths(project_dir)
    latest = latest_revision(paths, page_id)
    expected = [latest] if latest else list(planned_initial_versions(paths, page))
    if version not in expected:
        raise ValueError(f"record-svg must use a current requested version: {','.join(expected)}")
    packet = paths.packet(page_id, version)
    python = _svg_runtime_python()
    completed = subprocess.run(
        [python, str(SERVICE_CLI), "complete", str(packet)],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"PPT Master complete returned invalid JSON: {completed.stdout.strip()}") from exc
    if not isinstance(result, dict):
        raise ValueError("PPT Master complete result must be a JSON object")
    if (
        completed.returncode != 0
        or result.get("status") != "COMPLETE"
        or result.get("slide_id") != page_id
        or result.get("version") != version
    ):
        reason = result.get("reason") or completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"PPT Master complete did not accept {page_id} {version}: {reason}")
    record_candidate(paths, page_id, version)
    print_next(project_dir, text, controller)
    return 0


def handle_present_svg(project_dir: Path, text: str, page_id: str, versions_text: str, controller: Path) -> int:
    page = page_by_id(text, page_id)
    if (
        page.fields.get("Status") not in {"Content locked", "Awaiting SVG decision"}
        or not svg_cycle_started(ProjectPaths(project_dir), page)
    ):
        raise ValueError(f"{page_id} is not awaiting an SVG decision")
    versions = [require_version(item.strip()) for item in versions_text.split(",") if item.strip()]
    if len(versions) != 1:
        raise ValueError("present-svg requires exactly one version")
    paths = ProjectPaths(project_dir)
    latest = latest_revision(paths, page_id)
    if latest:
        expected = [latest]
    else:
        expected = list(planned_initial_versions(paths, page))
    if versions != expected:
        raise ValueError(f"present-svg must use the current version: {','.join(expected)}")
    paths.revision_request(page_id).parent.mkdir(parents=True, exist_ok=True)
    record_presentation(paths, page_id, versions)
    for version in versions:
        artifact = paths.candidate(page_id, version).resolve()
        print(f"### {page_id}｜{version}\n\n![{page_id} {version}]({artifact})\n")
    print("The SVG is displayed at review scale. Collect an explicit confirmation or optimization request.")
    print(json.dumps(decision_directive(paths, page_id, versions, controller, revision=versions[-1].startswith("R")), ensure_ascii=False, indent=2))
    return 0


def handle_request_revision(project_dir: Path, text: str, page_id: str, base: str, feedback_file: Path, controller: Path) -> int:
    page = page_by_id(text, page_id)
    paths = ProjectPaths(project_dir)
    if (
        page.fields.get("Status") not in {"Content locked", "Awaiting SVG decision"}
        or not svg_cycle_started(paths, page)
        or base not in presented_versions(paths, page_id)
    ):
        raise ValueError("revision base must be one of the currently displayed candidates")
    feedback_file = feedback_file.expanduser().resolve()
    expected_feedback_file = paths.revision_request(page_id).resolve()
    if feedback_file != expected_feedback_file:
        raise ValueError(f"revision feedback must use the emitted file: {expected_feedback_file}")
    if not feedback_file.is_file():
        raise ValueError(f"revision feedback file not found: {feedback_file}")
    feedback = feedback_file.read_text(encoding="utf-8").strip()
    if not feedback:
        raise ValueError("revision feedback must be non-empty")
    version = next_revision(paths, page_id)
    write_packet(paths, page, version, base_version=base, feedback=feedback)
    feedback_file.unlink()
    paths.presentation_receipt(page_id).unlink(missing_ok=True)
    print_next(project_dir, text, controller)
    return 0


def handle_confirm_svg(project_dir: Path, framework: Path, text: str, page_id: str, version: str, controller: Path) -> int:
    page = page_by_id(text, page_id)
    if (
        page.fields.get("Status") not in {"Content locked", "Awaiting SVG decision"}
        or not svg_cycle_started(ProjectPaths(project_dir), page)
    ):
        raise ValueError(f"{page_id} is not awaiting an SVG decision")
    paths = ProjectPaths(project_dir)
    target = confirm_candidate(paths, page_id, require_version(version))
    text = update_page(text, page_id, {"Status": "SVG confirmed"})
    atomic_write(framework, text)
    print(f"Confirmed {page_id} {version}: {target}")
    print_next(project_dir, text, controller)
    return 0


def handle_prepare_pptx(project_dir: Path, text: str, controller: Path) -> int:
    paths = ProjectPaths(project_dir)
    request = write_pptx_request(paths, text)
    print(f"Prepared PPTX export request: {request}")
    print_next(project_dir, text, controller)
    return 0


def handle_export_pptx(project_dir: Path, text: str, controller: Path) -> int:
    output = export_from_request(ProjectPaths(project_dir), text)
    print(f"Exported editable PPTX: {output}")
    print_next(project_dir, text, controller)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    commands = (
        "bootstrap", "upgrade-workflow", "next", "audit", "present-review", "approve-content",
        "prepare-svg-candidates", "record-svg", "present-svg", "request-svg-revision",
        "confirm-svg", "prepare-pptx-export", "export-pptx",
        "reopen-content", "reopen-svg", "set-output-filename",
    )
    for name in commands:
        command = sub.add_parser(name)
        command.add_argument("--project-dir", type=Path, required=True)
        if name == "next":
            command.add_argument("--format", choices=("text", "json"), default="text")
        if name in {"prepare-svg-candidates", "record-svg", "present-svg", "request-svg-revision", "confirm-svg", "reopen-content", "reopen-svg"}:
            command.add_argument("--page", required=True)
        if name in {"record-svg", "confirm-svg"}:
            command.add_argument("--version", required=True)
        if name == "present-svg":
            command.add_argument("--versions", required=True)
        if name == "request-svg-revision":
            command.add_argument("--base", required=True)
            command.add_argument("--feedback-file", type=Path, required=True)
        if name == "set-output-filename":
            command.add_argument("--filename", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_dir = args.project_dir.expanduser().resolve()
    controller = Path(__file__).resolve()
    try:
        if args.command == "upgrade-workflow":
            framework = ProjectPaths(project_dir).framework
            if not framework.is_file():
                raise ValueError(f"framework not found: {framework}")
            text = framework.read_text(encoding="utf-8")
            current = h2_section(text, "Current position")
            version = line_fields(current).get("Workflow version", "")
            if version not in READABLE_WORKFLOW_VERSIONS:
                raise ValueError(
                    "unsupported workflow version for migration: "
                    f"{version or 'missing'}"
                )
            preflight_errors = validate_framework(framework, project_dir)
            allowed_version_error = f"Workflow version must be {WORKFLOW_VERSION}"
            blocking_errors = [
                error for error in preflight_errors
                if not (version != WORKFLOW_VERSION and error == allowed_version_error)
            ]
            if blocking_errors:
                raise ValueError(" | ".join(blocking_errors))
            if version != WORKFLOW_VERSION:
                text = text.replace(
                    current,
                    replace_field(current, "Workflow version", WORKFLOW_VERSION),
                    1,
                )
                atomic_write(framework, text)
            print(f"Workflow upgraded to {WORKFLOW_VERSION}.")
            print_next(project_dir, text, controller)
            return 0
        framework, text = load_context(project_dir)
        if args.command in {"bootstrap", "next"}:
            if args.command == "bootstrap":
                ProjectPaths(project_dir).working.mkdir(parents=True, exist_ok=True)
            payload = directive_payload(project_dir, text, controller)
            if args.command == "next" and args.format == "text":
                print(f"NEXT ACTION: {payload['action']}")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "audit":
            paths = ProjectPaths(project_dir)
            errors = content_validation_errors(paths, text)
            for page in page_entries(text):
                if page.fields.get("Status") == "SVG confirmed" and not confirmation_valid(paths, page.slide_id):
                    errors.append(f"{page.slide_id} has a stale SVG confirmation")
            if active_page(text) is None and not export_valid(paths, text):
                errors.append("editable PPTX export is missing or stale")
            if errors:
                raise ValueError(" | ".join(errors))
            print("EY content, SVG, and editable PPTX workflow audit passed.")
            return 0
        if args.command == "present-review":
            return handle_present_review(project_dir, text, controller)
        if args.command == "approve-content":
            return handle_approve_content(project_dir, framework, text, controller)
        if args.command == "prepare-svg-candidates":
            return handle_prepare_candidates(project_dir, text, args.page, controller)
        if args.command == "record-svg":
            return handle_record_svg(project_dir, text, args.page, args.version, controller)
        if args.command == "present-svg":
            return handle_present_svg(project_dir, text, args.page, args.versions, controller)
        if args.command == "request-svg-revision":
            return handle_request_revision(project_dir, text, args.page, args.base, args.feedback_file, controller)
        if args.command == "confirm-svg":
            return handle_confirm_svg(project_dir, framework, text, args.page, args.version, controller)
        if args.command == "prepare-pptx-export":
            return handle_prepare_pptx(project_dir, text, controller)
        if args.command == "export-pptx":
            return handle_export_pptx(project_dir, text, controller)
        if args.command in {"reopen-content", "reopen-svg"}:
            page = page_by_id(text, args.page)
            if page.fields.get("Status") == "Protected placeholder":
                raise ValueError(f"page cannot be reopened: {args.page}")
            if (
                page.fields.get("Status") == "Deferred template"
                and normalize_page_type(page.fields.get("Page type", ""))
                in {"ending", "closing", "closing page"}
            ):
                raise ValueError(f"{args.page} is the fixed Ending and cannot be modified")
            if (
                args.command == "reopen-svg"
                and page.fields.get("Status") == "Deferred template"
            ):
                raise ValueError(
                    f"{args.page} has no SVG cycle; use reopen-content to activate custom design"
                )
            discard_cycle(ProjectPaths(project_dir), args.page)
            target = "Not started" if args.command == "reopen-content" else "Content locked"
            text = update_page(text, args.page, {"Status": target})
            atomic_write(framework, text)
            print_next(project_dir, text, controller)
            return 0
        if args.command == "set-output-filename":
            if not args.filename.lower().endswith(".pptx") or Path(args.filename).name != args.filename:
                raise ValueError("filename must be one plain .pptx filename")
            current = h2_section(text, "Current position")
            atomic_write(framework, text.replace(current, replace_field(current, "Output filename", args.filename), 1))
            print(f"Output filename updated: {args.filename}")
            return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
