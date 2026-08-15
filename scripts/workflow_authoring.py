#!/usr/bin/env python3
"""Hash-bound Stage 1 candidate packets, receipts, and comparison evidence."""

from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

from framework_lib import PageEntry, h2_section, line_fields, page_entries
from svg_boundary import candidate_errors, svg_canvas
from workflow_content import content_section
from workflow_copy_contract import visible_copy_contract, visible_copy_errors
from workflow_io import atomic_write, now, read_json, sha256, text_sha256, write_json
from workflow_paths import (
    authoring_packet_paths,
    page_author_result_path,
    receipt_path,
    revision_active_path,
    selected_working_path,
    working_paths,
)
from workflow_preview_evidence import presentation_preview_errors
from workflow_spec import STAGE1_ACCEPTANCE_SCHEMA
from workflow_templates import page_template_binding, template_candidate_errors


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
    binding = payload.get("template_binding")
    if not isinstance(binding, dict):
        return None
    prototype = Path(str(binding.get("prototype_path", "")))
    if (
        not prototype.is_file()
        or binding.get("prototype_sha256") != sha256(prototype)
    ):
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
    framework_matches = bool(
        packet and packet.get("framework_page_sha256") == text_sha256(page.text)
    )
    return bool(
        packet
        and framework_matches
        and packet.get("template_binding")
        == page_template_binding(page.fields.get("Page type", ""))
    )


def page_visible_copy_contract(project_dir: Path, slide_id: str) -> dict:
    content_path = project_dir / "content.md"
    if not content_path.is_file():
        raise ValueError(f"approved content is missing for {slide_id}")
    section = content_section(content_path.read_text(encoding="utf-8"), slide_id)
    framework_path = project_dir / "framework.md"
    if not framework_path.is_file():
        raise ValueError(f"framework is missing for {slide_id}")
    page = next(
        (
            item
            for item in page_entries(framework_path.read_text(encoding="utf-8"))
            if item.slide_id == slide_id
        ),
        None,
    )
    if page is None:
        raise ValueError(f"framework page is missing for {slide_id}")
    return visible_copy_contract(
        section,
        slide_id,
        expected_page_type=page.fields.get("Page type", ""),
    )


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
        and result.get("route") == "embedded-ppt-master-stage1"
        and result.get("slide_id") == slide_id
        and result.get("version") == version
        and packet is not None
        and result.get("authoring_mode") == packet.get("authoring_mode")
        and result.get("artifact_path") == str(artifact.resolve())
        and result.get("artifact_sha256") == artifact_sha256
        and result.get("visible_copy_contract_sha256")
        == packet.get("visible_copy_contract_sha256")
        and result.get("template_structure_contract_sha256")
        == packet.get("template_structure_contract_sha256")
        and packet_matches
    )
    if not base_valid:
        return False

    acceptance = result.get("acceptance_gate")
    if isinstance(acceptance, dict):
        return bool(
            acceptance.get("schema") == STAGE1_ACCEPTANCE_SCHEMA
            and acceptance.get("status") == "PASS"
            and acceptance.get("artifact_sha256") == artifact_sha256
            and acceptance.get("visible_copy_contract_sha256")
            == packet.get("visible_copy_contract_sha256")
            and acceptance.get("template_structure_contract_sha256")
            == packet.get("template_structure_contract_sha256")
        )

    # Backward-compatible fallback for receipts created before reusable
    # Stage 1 acceptance evidence existed. New receipts take the hash-only path.
    return (
        not candidate_errors(artifact)
        and not visible_copy_errors(artifact, packet["visible_copy_contract"])
        and not template_candidate_errors(artifact, packet.get("template_binding"))
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
        required = ("stage", "reason", "resume_from")
        if (
            result.get("status") == "BLOCKED"
            and result.get("active") is True
            and result.get("route") == "embedded-ppt-master-stage1"
            and result.get("repair_scope") in {"design", "content", "environment"}
            and all(
                isinstance(result.get(key), str) and result.get(key).strip()
                for key in required
            )
            and result.get("slide_ids") == [slide_id]
        ):
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
            errors.append(f"{slide_id} {version} has no valid hash-bound Stage 1 acceptance receipt")
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


def validate_single(project_dir: Path, slide_id: str) -> tuple[list[str], dict | None]:
    errors: list[str] = []
    a_path, _b_path = working_paths(project_dir, slide_id)
    try:
        contract = page_visible_copy_contract(project_dir, slide_id)
    except (OSError, ValueError) as exc:
        contract = None
        errors.append(str(exc))
    if not page_author_completion_valid(project_dir, slide_id, "A"):
        before = len(errors)
        errors.extend(candidate_errors(a_path))
        if contract is not None and a_path.is_file():
            errors.extend(visible_copy_errors(a_path, contract))
        if len(errors) == before:
            errors.append(f"{slide_id} A has no valid hash-bound Stage 1 acceptance receipt")
    if errors:
        return errors, None
    return errors, {"slide_id": slide_id, "a_sha256": sha256(a_path)}


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
            errors.append(f"{slide_id} {version} has no valid hash-bound Stage 1 acceptance receipt")
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
        for field in (
            "Chapter",
            "Page type",
            "Authoring mode",
            "Narrative role",
            "Next connection",
        ):
            print(f"- {field}: {page.fields.get(field, 'Missing')}")
        adjacent = pages[max(0, index - 1): min(len(pages), index + 2)]
        print("- Adjacent titles: " + " | ".join(f"{item.slide_id} {item.title}" for item in adjacent))
        section = content_section(content, page.slide_id)
        print("\n" + (section.rstrip() if section else f"[Missing approved content for {page.slide_id}]") + "\n")


def ensure_authoring_packet(text: str, project_dir: Path, page: PageEntry) -> dict:
    """Materialize one stable mode-independent page packet outside conversation context."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_build_context(text, project_dir, [page])
    contract = page_visible_copy_contract(project_dir, page.slide_id)
    template_binding = page_template_binding(page.fields.get("Page type", ""))
    if template_binding is None:
        raise ValueError(f"{page.slide_id} has no authorable template binding")
    contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
    template_json = json.dumps(template_binding, ensure_ascii=False, indent=2)
    packet_text = (
        f"# Locked Embedded PPT Master Stage 1 Packet｜{page.slide_id}\n\n"
        "Use this exact packet for every requested candidate. Embedded PPT Master owns design, SVG production, "
        "rendered visual QA, and internal repair. Version-specific output paths and revision notes are controller "
        "directives, not page-content memory. Every page-authored visible SVG text run must be bound "
        "to exactly one approved item below with `data-copy-id`; inherited text marked "
        "`data-copy-scope=\"template-fixed\"` belongs to the template and must remain exact. "
        "Build-only text must never be visible. Text may be split into nested tspans inside one bound element or group. "
        "Start from the exact structured-template prototype below. Preserve its root Master/Layout "
        "identity, every fixed Master/Layout atom byte-for-byte, and every placeholder "
        "id/type/index/bounds. Replace only placeholder content; the content-region proxy may "
        "contain the page-specific composition. For an Agenda, start from the dedicated agenda "
        "prototype and replace only its title and agenda-region placeholder content.\n\n"
        + buffer.getvalue().strip()
        + "\n\n## Bound structured template\n\n```json\n"
        + template_json
        + "\n```\n"
        + "\n\n## Machine-enforced visible copy\n\n```json\n"
        + contract_json
        + "\n```\n"
    )
    packet_path, receipt_path_value = authoring_packet_paths(project_dir, page.slide_id)
    atomic_write(packet_path, packet_text)
    payload = {
        "slide_id": page.slide_id,
        "authoring_mode": page.fields.get("Authoring mode"),
        "packet_path": str(packet_path.resolve()),
        "packet_sha256": sha256(packet_path),
        "framework_page_sha256": text_sha256(page.text),
        "visible_copy_contract": contract,
        "visible_copy_contract_sha256": contract["contract_sha256"],
        "template_binding": template_binding,
        "template_structure_contract_sha256": template_binding["structure_contract_sha256"],
        "created_at": now(),
    }
    write_json(receipt_path_value, payload)
    return payload


def author_version_for_action(action: str, project_dir: Path, page: PageEntry) -> str:
    if action == "RUN_PPT_MASTER_A":
        return "A"
    if action == "RUN_PPT_MASTER_B":
        return "B"
    if action == "RUN_PPT_MASTER_REVISION":
        request = active_revision(project_dir, page.slide_id) or {}
        return str(request.get("revision_id", ""))
    raise ValueError(f"{action} is not a page-authoring action")
