"""Legacy workflow migration, loaded only by the controller's migrate command."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from framework_lib import h2_section, line_fields, page_entries, replace_field
from workflow_io import atomic_write, now, sha256, text_sha256, write_json
from workflow_paths import (
    archive_items,
    page_author_result_path,
    receipt_path,
    selected_working_path,
)
from workflow_spec import (
    FRAMEWORK_VERSION,
    WORKFLOW_VERSION,
)


LEGACY_WORKFLOW_RULE_FIELDS = {
    "Review order",
    "Page review",
    "SVG gate",
    "PPTX gate",
    "Locked-content rule",
}


def migrate_visual_direction_schema(content: str) -> str:
    content = re.sub(
        r"\A# Proposal Build Specification\b",
        "# Presentation Build Specification",
        content,
        count=1,
    )
    if content and "## Deck build profile（Build-only）" not in content:
        first_slide = re.search(r"^## S\d{2}｜", content, re.MULTILINE)
        if first_slide:
            language_match = re.search(
                r"^- Language:\s*(Chinese|English)\s*$",
                content[: first_slide.start()],
                re.MULTILINE | re.IGNORECASE,
            )
            language = (
                language_match.group(1).title()
                if language_match
                else ("Chinese" if re.search(r"[\u3400-\u9fff]", content[first_slide.start():]) else "English")
            )
            content = (
                "# Presentation Build Specification\n\n"
                "## Deck build profile（Build-only）\n"
                f"- Language: {language}\n\n"
                + content[first_slide.start():]
            )
    pattern = re.compile(
        r"^### Design Brief（Build-only）\s*$\n(.*?)(?=^### |^## S\d{2}｜|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    def replacement(match: re.Match[str]) -> str:
        fields = line_fields(match.group(1))
        page_type = fields.get("Page type", "Standard content")
        legacy_relationship = fields.get("Relationship to express", "")
        relationship = (
            legacy_relationship
            if re.search(
                r"comparison|contrast|progression|hierarchy|cause|effect|convergence|parallel|"
                r"support|sequence|对比|比较|递进|层级|因果|汇聚|并列|支撑|顺序",
                legacy_relationship,
                re.IGNORECASE,
            )
            else "Approved semantic relationship among the on-slide content"
        )
        return (
            "### Visual Direction（Build-only）\n"
            f"- Page type: {page_type}\n"
            "- Visual focus: The page's approved core conclusion\n"
            "- Information hierarchy: Core conclusion first; supporting approved content follows in semantic order\n"
            f"- Relationship to preserve: {relationship}\n"
            "- Fixed constraints: Approved copy, data, sources, emphasis, and semantic relationships\n"
            "- Avoid: Do not weaken the core conclusion, omit approved content, or distort the stated relationship\n\n"
        )

    migrated = pattern.sub(replacement, content)
    return re.sub(
        r"^### Wireframe（Build-only）\s*$\n+```text\s*\n.*?\n```\s*\n?",
        "",
        migrated,
        flags=re.MULTILINE | re.DOTALL,
    )


def default_output_filename(text: str) -> str:
    context = line_fields(h2_section(text, "Project context"))
    name = context.get("Deliverable name") or context.get("Proposal name") or "final-deck"
    safe = re.sub(r"[\x00/\\]+", "-", name).strip(" .-") or "final-deck"
    return safe[:120] + ".pptx"


def migrate_legacy_project_schema(text: str) -> str:
    context = h2_section(text, "Project context")
    values = line_fields(context)
    legacy = text.startswith("# Proposal Framework\n") or any(
        field in values
        for field in ("Proposal name", "Client", "Proposal type", "Client decision", "Proposal thesis")
    )
    if not legacy:
        return text
    core_need = values.get("Core need", "Missing")
    proposal_type = values.get("Proposal type", "").strip()
    if proposal_type and proposal_type.lower() != "none" and proposal_type not in core_need:
        suffix = f"; Legacy proposal type: {proposal_type}"
        if len(core_need) + len(suffix) > 700:
            raise ValueError("legacy Proposal type cannot fit in Core need; shorten Core need first")
        core_need += suffix
    migrated_context = """## Project context

- Deliverable name: {name}
- Audience: {audience}
- Deliverable type: Proposal
- Audience outcome: {outcome}
- Core need: {core_need}
- Storyline thesis: {thesis}
- Scope boundaries: {scope}
- Protected content: {protected}
""".format(
        name=values.get("Deliverable name") or values.get("Proposal name", "Missing"),
        audience=values.get("Audience") or values.get("Client", "Missing"),
        outcome=values.get("Audience outcome") or values.get("Client decision", "Missing"),
        core_need=core_need,
        thesis=values.get("Storyline thesis") or values.get("Proposal thesis", "Missing"),
        scope=values.get("Scope boundaries", "None"),
        protected=values.get("Protected content", "None"),
    )
    text = re.sub(r"\A# Proposal Framework\n", "# Presentation Framework\n", text, count=1)
    return text.replace(context, migrated_context, 1)


def migrate_workflow(
    text: str,
    project_dir: Path,
    *,
    candidate_errors: Callable[[Path], list[str]],
    content_section: Callable[[str, str], str],
) -> str:
    original_text = text
    text = migrate_legacy_project_schema(text)
    current = h2_section(text, "Current position")
    original_position = line_fields(current)
    if (
        original_position.get("Workflow version") == WORKFLOW_VERSION
        and original_position.get("Framework version") == FRAMEWORK_VERSION
        and original_position.get("Output filename")
        and "Final PPTX owner" not in original_position
        and "Final PPTX requirement" not in original_position
        and "Last checkpoint" not in original_position
        and all("Previous connection" not in page.fields for page in page_entries(text))
        and text == original_text
    ):
        return text

    updated = current
    for field in ("Current phase", "Active page", "Next action"):
        updated = re.sub(rf"^- {re.escape(field)}:.*\n", "", updated, flags=re.MULTILINE)
    updated = replace_field(updated, "Framework version", FRAMEWORK_VERSION)
    updated = replace_field(updated, "Workflow version", WORKFLOW_VERSION)
    updated = re.sub(
        r"^- (?:Last checkpoint|PPTX status|Final PPTX|Final PPTX owner|Final PPTX requirement):.*\n?",
        "",
        updated,
        flags=re.MULTILINE,
    )
    if "- Output filename:" not in updated:
        updated = re.sub(
            r"(^- Storyline version:.*$)",
            rf"\1\n- Output filename: {default_output_filename(text)}",
            updated,
            count=1,
            flags=re.MULTILINE,
        )
    text = text.replace(current, updated, 1)

    rules = h2_section(text, "Design hard rules")
    cleaned = rules
    for field in LEGACY_WORKFLOW_RULE_FIELDS:
        cleaned = re.sub(rf"^- {re.escape(field)}:.*\n?", "", cleaned, flags=re.MULTILINE)
    rule_values = line_fields(cleaned)
    extras = [
        f"{field}: {value}"
        for field, value in rule_values.items()
        if field not in {"Canvas", "Project-specific rules"}
    ]
    if extras:
        existing = rule_values.get("Project-specific rules", "None")
        combined = "; ".join(([existing] if existing.lower() != "none" else []) + extras)
        cleaned = replace_field(cleaned, "Project-specific rules", combined)
        for field in rule_values:
            if field not in {"Canvas", "Project-specific rules"}:
                cleaned = re.sub(rf"^- {re.escape(field)}:.*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = replace_field(
        cleaned,
        "Canvas",
        "ppt169, SVG 1280 × 720; exported at approximately 33.867 cm × 19.05 cm.",
    )
    text = text.replace(rules, cleaned, 1)

    mapping = {
        "Not started": "Not started",
        "Content reviewing": "Content reviewing",
        "Reopened": "Content reviewing",
        "Content locked": "Content locked",
        "SVG A ready": "Content locked",
        "SVG A/B ready": "Content locked",
        "SVG choice pending": "Content locked",
        "Awaiting SVG selection": "Content locked",
        "SVG selected": "Content locked",
        "SVG QA passed": "SVG confirmed",
        "Protected placeholder": "Protected placeholder",
    }
    for page in page_entries(text):
        section = page.text
        for field in ("Content section", "SVG candidates", "Final SVG", "Previous connection"):
            section = re.sub(rf"^- {re.escape(field)}:.*\n", "", section, flags=re.MULTILINE)
        section = replace_field(section, "Status", mapping.get(page.fields.get("Status"), "Not started"))
        if page.fields.get("Status") in {"SVG choice pending", "Awaiting SVG selection", "SVG selected"}:
            section = replace_field(section, "Selected version", "Pending")
        if mapping.get(page.fields.get("Status")) == "Protected placeholder":
            section = replace_field(section, "Page type", "Protected placeholder")
            section = replace_field(section, "Selected version", "Not applicable")
        text = text.replace(page.text, section, 1)

    content_path = project_dir / "content.md"
    content = content_path.read_text(encoding="utf-8") if content_path.is_file() else ""
    migrated_content = migrate_visual_direction_schema(content)
    if migrated_content != content:
        atomic_write(content_path, migrated_content)
        content = migrated_content

    for original_page in page_entries(text):
        page = next(item for item in page_entries(text) if item.slide_id == original_page.slide_id)
        state = page.fields.get("Status")
        archive_items(
            project_dir,
            "workflow-3.7-obsolete",
            [project_dir / "svg_working" / page.slide_id / "ab-manifest.json"],
        )
        section = content_section(content, page.slide_id)
        content_receipt = receipt_path(project_dir, page.slide_id, "content")
        if state in {"Content locked", "SVG confirmed"} and section and not content_receipt.is_file():
            write_json(content_receipt, {
                "slide_id": page.slide_id,
                "content_sha256": text_sha256(section),
                "approval_note": f"Migrated to workflow {WORKFLOW_VERSION}",
                "created_at": now(),
            })
        slide_dir = project_dir / "svg_working" / page.slide_id
        if slide_dir.is_dir():
            for artifact in sorted(slide_dir.glob("*.svg")):
                version = artifact.stem
                if not re.fullmatch(r"(?:A|B|R[1-9]\d*)", version) or candidate_errors(artifact):
                    continue
                author_receipt = page_author_result_path(project_dir, page.slide_id, version)
                if author_receipt.is_file():
                    continue
                write_json(author_receipt, {
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "slide_id": page.slide_id,
                    "version": version,
                    "artifact_path": str(artifact.resolve()),
                    "artifact_sha256": sha256(artifact),
                    "recorded_at": now(),
                    "active": False,
                    "migration": True,
                })
        if state == "SVG confirmed":
            final_path = project_dir / "svg_output" / f"{page.slide_id}.svg"
            version = page.fields.get("Selected version", "")
            try:
                selected = selected_working_path(project_dir, page.slide_id, version)
            except ValueError:
                selected = None
            if not candidate_errors(final_path) and selected is not None:
                write_json(receipt_path(project_dir, page.slide_id, "svg-selection"), {
                    "slide_id": page.slide_id,
                    "selected_version": version,
                    "selected_sha256": sha256(selected) if selected.is_file() else sha256(final_path),
                    "canonical_sha256": sha256(final_path),
                    "accepted_at": now(),
                    "migration": True,
                })
            else:
                current_page = next(item for item in page_entries(text) if item.slide_id == page.slide_id)
                reset = replace_field(current_page.text, "Status", "Content locked")
                reset = replace_field(reset, "Selected version", "Pending")
                text = text.replace(current_page.text, reset, 1)

    archive_items(project_dir, "workflow-3.0-obsolete", [
        project_dir / "working" / "preflight",
        project_dir / "working" / "pptx-envelope.json",
        project_dir / "working" / "design_spec.md",
        project_dir / "working" / "spec_lock.md",
        project_dir / "working" / "current-review.md",
        project_dir / "working" / "body-checkpoint.md",
        project_dir / "working" / "continuity-scan.md",
        project_dir / "working" / "receipts" / "body-checkpoint.json",
        *list((project_dir / "working" / "receipts").glob("*-svg-qa.json")),
    ])
    if original_position.get("PPTX status") in {"Authorized", "Reconstructed", "QA passed", "Stale"}:
        archive_items(project_dir, "workflow-migration", [
            project_dir / "working" / "receipts" / "pptx-fidelity.json",
            project_dir / "working" / "receipts" / "final-qa.json",
        ])
    receipts = project_dir / "working" / "receipts"
    old_handoff = receipts / "ppt-master-handoff.json"
    new_handoff = receipts / "confirmed-export-handoff.json"
    if old_handoff.is_file() and not new_handoff.exists():
        old_handoff.rename(new_handoff)
    elif old_handoff.exists():
        archive_items(project_dir, "workflow-3.7-obsolete", [old_handoff])
    return text
