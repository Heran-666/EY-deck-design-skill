#!/usr/bin/env python3
"""Validate the compact EY presentation framework."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from framework_lib import duplicate_line_fields, h2_section, line_fields, page_entries
from workflow_spec import (
    FRAMEWORK_VERSION,
    PAGE_RHYTHMS,
    READING_MODES,
    READABLE_PAGE_STATES,
    WORKFLOW_VERSION,
    is_deferred_template_page_type,
    is_substantive_page_type,
    normalize_page_type,
)


CURRENT_FIELDS = (
    "Framework version",
    "Workflow version",
    "Storyline version",
    "Output filename",
)
CONTEXT_FIELDS = (
    "Deliverable name",
    "Audience",
    "Deliverable type",
    "Audience outcome",
    "Core need",
    "Storyline thesis",
    "Reading mode",
    "Scope boundaries",
    "Protected content",
)
PAGE_FIELDS = (
    "Chapter",
    "Page type",
    "Narrative role",
    "Page rhythm",
    "Content scope",
    "Next connection",
    "Status",
    "Confirmed decisions",
    "Open items",
)
LENGTH_LIMITS = {
    "Narrative role": 500,
    "Content scope": 700,
    "Next connection": 500,
    "Confirmed decisions": 500,
    "Open items": 500,
}
def _required(section: str, fields: tuple[str, ...], label: str) -> list[str]:
    values = line_fields(section)
    errors = [f"{label} is missing {field}" for field in fields if not values.get(field, "").strip()]
    errors.extend(f"{label} has duplicate field: {field}" for field in duplicate_line_fields(section))
    unexpected = set(values) - set(fields)
    if unexpected:
        errors.append(f"{label} has unsupported fields: " + ", ".join(sorted(unexpected)))
    return errors


def _valid_filename(value: str) -> bool:
    return bool(
        value
        and value.lower().endswith(".pptx")
        and Path(value).name == value
        and value not in {".", ".."}
    )


def validate(
    framework: Path,
    project_dir: Path | None = None,
    *,
    text: str | None = None,
) -> list[str]:
    if text is None:
        if not framework.is_file():
            return [f"framework not found: {framework}"]
        text = framework.read_text(encoding="utf-8")
    errors: list[str] = []
    if not text.startswith("# Presentation Framework\n"):
        errors.append("framework.md must begin with # Presentation Framework")

    expected_h2 = ["Current position", "Project context", "Confirmed Storyline"]
    actual_h2 = re.findall(r"^## (.+)$", text, re.MULTILINE)
    if actual_h2 != expected_h2:
        errors.append("framework.md must contain exactly these H2 sections in order: " + ", ".join(expected_h2))
        return errors

    current = h2_section(text, "Current position")
    context = h2_section(text, "Project context")
    storyline = h2_section(text, "Confirmed Storyline")
    errors.extend(_required(current, CURRENT_FIELDS, "Current position"))
    errors.extend(_required(context, CONTEXT_FIELDS, "Project context"))

    current_values = line_fields(current)
    if current_values.get("Framework version") != FRAMEWORK_VERSION:
        errors.append(f"Framework version must be {FRAMEWORK_VERSION}")
    if current_values.get("Workflow version") != WORKFLOW_VERSION:
        errors.append(f"Workflow version must be {WORKFLOW_VERSION}")
    if not re.fullmatch(r"\d+(?:\.\d+)?", current_values.get("Storyline version", "")):
        errors.append("Storyline version must be numeric, such as 1.0")
    if not _valid_filename(current_values.get("Output filename", "")):
        errors.append("Output filename must be one plain filename ending in .pptx")

    context_values = line_fields(context)
    configured_reading_mode = context_values.get("Reading mode")
    if configured_reading_mode and configured_reading_mode.strip().lower() not in READING_MODES:
        errors.append("Reading mode must be text, balanced, or presentation")
    deliverable_type = context_values.get("Deliverable type", "")
    if not re.fullmatch(r"(?:Proposal|Sharing deck|Training|Interpretation|Other:\s*\S(?:.*\S)?)", deliverable_type):
        errors.append("Deliverable type must be Proposal, Sharing deck, Training, Interpretation, or Other: <specific form>")

    pages = page_entries(text)
    if not pages:
        errors.append("Confirmed Storyline has no pages")
        return errors
    ids = [page.slide_id for page in pages]
    expected_ids = [f"S{index:02d}" for index in range(1, len(pages) + 1)]
    if ids != expected_ids:
        errors.append("Slide IDs must be sequential from S01")
    if pages[0].fields.get("Page type", "").strip().lower() != "cover":
        errors.append("S01 must be Cover")

    page_types = [normalize_page_type(page.fields.get("Page type", "")) for page in pages]
    cover_ids = [page.slide_id for page, page_type in zip(pages, page_types) if page_type == "cover"]
    if len(cover_ids) != 1:
        errors.append("Confirmed Storyline must contain exactly one Cover: " + (", ".join(cover_ids) or "None"))
    agenda_ids = [page.slide_id for page, page_type in zip(pages, page_types) if page_type == "agenda"]
    if len(agenda_ids) > 1:
        errors.append("Confirmed Storyline may contain at most one Agenda: " + ", ".join(agenda_ids))
    if agenda_ids and agenda_ids != ["S02"]:
        errors.append("Agenda must be S02 when present")
    substantive_count = sum(is_substantive_page_type(page_type) for page_type in page_types)
    divider_ids = [
        page.slide_id
        for page, page_type in zip(pages, page_types)
        if page_type in {"section divider", "divider"}
    ]
    if substantive_count >= 6:
        if agenda_ids != ["S02"]:
            errors.append("At six or more substantive pages, S02 must be Agenda")
        if not divider_ids:
            errors.append("At six or more substantive pages, at least one Section divider is required")

    for page in pages:
        errors.extend(_required(page.text, PAGE_FIELDS, page.slide_id))
        for field, limit in LENGTH_LIMITS.items():
            if len(page.fields.get(field, "")) > limit:
                errors.append(f"{page.slide_id} {field} exceeds {limit} characters")
        status = page.fields.get("Status", "")
        if status not in READABLE_PAGE_STATES:
            errors.append(f"{page.slide_id} has unsupported Status: {status}")
        page_type = page.fields.get("Page type", "").strip().lower()
        normalized_page_type = normalize_page_type(page_type)
        configured_page_rhythm = page.fields.get("Page rhythm", "")
        normalized_page_rhythm = configured_page_rhythm.strip().lower()
        if normalized_page_rhythm and normalized_page_rhythm not in PAGE_RHYTHMS:
            errors.append(f"{page.slide_id} Page rhythm must be anchor, dense, or breathing")
        elif is_substantive_page_type(page_type) and normalized_page_rhythm == "anchor":
            errors.append(f"{page.slide_id} substantive Page rhythm must be dense or breathing")
        elif not is_substantive_page_type(page_type) and normalized_page_rhythm not in {"", "anchor"}:
            errors.append(f"{page.slide_id} structural Page rhythm must be anchor")
        if (
            normalized_page_type in {"ending", "closing", "closing page"}
            and status not in {"Deferred template", "SVG confirmed"}
        ):
            errors.append(
                f"{page.slide_id} Ending must use Deferred template and remain unchanged"
            )
        if status == "Deferred template":
            if not is_deferred_template_page_type(page_type):
                errors.append(
                    f"{page.slide_id} Deferred template status requires Cover, Agenda, "
                    "Section divider, or Ending Page type"
                )
            if page.fields.get("Open items") != "None":
                errors.append(f"{page.slide_id} must clear Open items before deferring its template")
        elif status == "Protected placeholder":
            if page_type != "protected placeholder":
                errors.append(f"{page.slide_id} protected status requires Page type Protected placeholder")
            if not page.fields.get("Content scope", "").startswith("[占位："):
                errors.append(f"{page.slide_id} protected Content scope must begin with [占位：")
        elif page_type == "protected placeholder":
            errors.append(f"{page.slide_id} Page type Protected placeholder requires matching Status")
        if status in {"Content locked", "Awaiting SVG decision", "SVG confirmed"} and page.fields.get("Open items") != "None":
            errors.append(f"{page.slide_id} must clear Open items before content locks")

    for index, page in enumerate(pages):
        next_page = pages[index + 1] if index + 1 < len(pages) else None
        current_is_substantive = is_substantive_page_type(page.fields.get("Page type", ""))
        next_is_substantive = bool(
            next_page and is_substantive_page_type(next_page.fields.get("Page type", ""))
        )
        connection = page.fields.get("Next connection", "").strip()
        if current_is_substantive and next_is_substantive:
            if not connection or connection.lower() == "none":
                errors.append(
                    f"{page.slide_id} must name a substantive Next connection to {next_page.slide_id}"
                )
        elif connection.lower() != "none":
            errors.append(f"{page.slide_id} Next connection must be None outside adjacent content pages")

    if project_dir is not None and project_dir.resolve() != framework.parent.resolve():
        errors.append("framework.md must live directly in --project-dir")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("framework", type=Path)
    parser.add_argument("--project-dir", type=Path)
    args = parser.parse_args()
    errors = validate(args.framework, args.project_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("framework.md validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
