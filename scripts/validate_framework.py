#!/usr/bin/env python3
"""Validate the human-readable EY presentation framework and canonical SVG set."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from framework_lib import duplicate_line_fields, h2_section, line_fields, page_entries
from workflow_export import validate_output_filename
from workflow_spec import (
    FRAMEWORK_VERSION,
    PAGE_AUTHORING_MODES,
    PAGE_STATES,
    READABLE_WORKFLOW_VERSIONS,
    REQUESTED_AUTHORING_MODES,
    LONG_DECK_CONTENT_THRESHOLD,
    WORKFLOW_VERSION,
    initial_authoring_mode,
)


CURRENT_FIELDS = (
    "Framework version",
    "Workflow version",
    "Storyline version",
    "Output filename",
)
GENERAL_CONTEXT_FIELDS = (
    "Deliverable name",
    "Audience",
    "Deliverable type",
    "Requested authoring mode",
    "Audience outcome",
    "Core need",
    "Storyline thesis",
    "Scope boundaries",
    "Protected content",
)
PAGE_FIELDS = (
    "Chapter",
    "Page type",
    "Narrative role",
    "Content scope",
    "Next connection",
    "Review mode",
    "Authoring mode",
    "Status",
    "Confirmed decisions",
    "Open items",
    "Confirmed version",
)
LENGTH_LIMITS = {
    "Narrative role": 500,
    "Content scope": 700,
    "Next connection": 500,
    "Confirmed decisions": 500,
    "Open items": 500,
}
DESIGN_RULE_FIELDS = ("Canvas", "Project-specific rules")
GENERAL_CONTEXT_LIMITS = {
    "Deliverable name": 200,
    "Audience": 200,
    "Deliverable type": 100,
    "Requested authoring mode": 20,
    "Audience outcome": 700,
    "Core need": 700,
    "Storyline thesis": 700,
    "Scope boundaries": 700,
    "Protected content": 700,
}


def required_fields(section: str, fields: tuple[str, ...], label: str) -> list[str]:
    values = line_fields(section)
    errors = [f"{label} is missing {field}" for field in fields if not values.get(field, "").strip()]
    errors.extend(f"{label} has duplicate field: {field}" for field in duplicate_line_fields(section))
    return errors


def validate(framework: Path, project_dir: Path | None) -> list[str]:
    text = framework.read_text(encoding="utf-8")
    errors: list[str] = []
    if not text.startswith("# Presentation Framework\n"):
        errors.append(
            "framework.md must begin with # Presentation Framework; run migrate for a legacy schema"
        )
    if re.search(r"^- Page Key:", text, re.MULTILINE):
        errors.append("framework.md must use only the single Slide ID; Page Key is prohibited")

    allowed_h2 = ["Current position", "Project context", "Design hard rules", "Confirmed Storyline"]
    actual_h2 = [heading.strip() for heading in re.findall(r"^## (.+)$", text, re.MULTILINE)]
    if actual_h2 != allowed_h2:
        errors.append(
            "framework.md must contain exactly these H2 sections in order: "
            + ", ".join(allowed_h2)
        )

    current = h2_section(text, "Current position")
    context = h2_section(text, "Project context")
    rules = h2_section(text, "Design hard rules")
    storyline = h2_section(text, "Confirmed Storyline")
    for name, section in (
        ("Current position", current),
        ("Project context", context),
        ("Design hard rules", rules),
        ("Confirmed Storyline", storyline),
    ):
        if not section:
            errors.append(f"framework.md is missing ## {name}")
    if errors:
        return errors

    errors.extend(required_fields(current, CURRENT_FIELDS, "Current position"))
    current_values = line_fields(current)
    unexpected_current = set(current_values) - set(CURRENT_FIELDS)
    if unexpected_current:
        errors.append(
            "Current position has unsupported fields: " + ", ".join(sorted(unexpected_current))
        )
    context_values = line_fields(context)
    errors.extend(required_fields(context, GENERAL_CONTEXT_FIELDS, "Project context"))
    unexpected_context = set(context_values) - set(GENERAL_CONTEXT_FIELDS)
    if unexpected_context:
        errors.append(
            "Project context has unsupported fields: " + ", ".join(sorted(unexpected_context))
        )
    deliverable_type = context_values.get("Deliverable type", "").strip()
    if deliverable_type and not re.fullmatch(
        r"(?:Proposal|Sharing deck|Training|Interpretation|Other:\s*\S(?:.*\S)?)",
        deliverable_type,
    ):
        errors.append(
            "Deliverable type must be Proposal, Sharing deck, Training, Interpretation, "
            "or Other: <specific form>"
        )
    requested_authoring_mode = context_values.get("Requested authoring mode", "").strip()
    if requested_authoring_mode not in REQUESTED_AUTHORING_MODES:
        errors.append("Requested authoring mode must be Simplified or Standard")
    errors.extend(required_fields(rules, DESIGN_RULE_FIELDS, "Design hard rules"))
    for field, limit in GENERAL_CONTEXT_LIMITS.items():
        if len(context_values.get(field, "")) > limit:
            errors.append(f"Project context {field} exceeds {limit} characters")
    rule_values = line_fields(rules)
    unexpected_rules = set(rule_values) - set(DESIGN_RULE_FIELDS)
    if unexpected_rules:
        errors.append("Design hard rules has unsupported fields: " + ", ".join(sorted(unexpected_rules)))
    if len(rule_values.get("Project-specific rules", "")) > 1200:
        errors.append("Design hard rules Project-specific rules exceeds 1200 characters")
    if not (
        re.search(r"\bppt169\b", rule_values.get("Canvas", ""), re.IGNORECASE)
        and re.search(r"1280\s*[×x]\s*720", rule_values.get("Canvas", ""), re.IGNORECASE)
        and re.search(r"33\.86\d*\s*cm.*19\.05\s*cm", rule_values.get("Canvas", ""), re.IGNORECASE)
    ):
        errors.append(
            "Design hard rules Canvas must specify ppt169 1280 × 720 and approximately "
            "33.867 cm × 19.05 cm"
        )
    if current_values.get("Framework version") != FRAMEWORK_VERSION:
        errors.append(
            f"Framework version must be {FRAMEWORK_VERSION}: "
            f"{current_values.get('Framework version')}"
        )
    if current_values.get("Workflow version") not in READABLE_WORKFLOW_VERSIONS:
        errors.append(
            f"Workflow version must be one of {sorted(READABLE_WORKFLOW_VERSIONS)}: "
            f"{current_values.get('Workflow version')}"
        )
    if not re.fullmatch(r"\d+(?:\.\d+)?", current_values.get("Storyline version", "")):
        errors.append("Storyline version must be a numeric version such as 1.0")
    try:
        validate_output_filename(current_values.get("Output filename", ""))
    except ValueError as exc:
        errors.append(str(exc))

    pages = page_entries(text)
    if not pages:
        errors.append("Confirmed Storyline has no pages")
        return errors
    ids = [page.slide_id for page in pages]
    expected = [f"S{index:02d}" for index in range(1, len(pages) + 1)]
    if ids != expected:
        errors.append("Storyline Slide IDs must be unique and sequential from S01")
    canonical_ids: set[str] = set()
    cover_ids: list[str] = []
    agenda_ids: list[str] = []
    divider_ids: list[str] = []
    substantive_ids: list[str] = []
    for page in pages:
        errors.extend(required_fields(page.text, PAGE_FIELDS, page.slide_id))
        if len(page.text) > 2600:
            errors.append(f"{page.slide_id} entry exceeds 2600 characters")
        state = page.fields.get("Status", "")
        normalized_type = page.fields.get("Page type", "").strip().lower()
        if normalized_type == "cover":
            cover_ids.append(page.slide_id)
        elif normalized_type == "agenda":
            agenda_ids.append(page.slide_id)
        elif normalized_type == "section divider":
            divider_ids.append(page.slide_id)
        elif normalized_type != "protected placeholder":
            substantive_ids.append(page.slide_id)
        if state not in PAGE_STATES:
            errors.append(f"{page.slide_id} has unsupported Status: {state}")
        for field, limit in LENGTH_LIMITS.items():
            if len(page.fields.get(field, "")) > limit:
                errors.append(f"{page.slide_id} {field} exceeds {limit} characters")
        authoring_mode = page.fields.get("Authoring mode", "")
        if authoring_mode not in PAGE_AUTHORING_MODES:
            errors.append(
                f"{page.slide_id} Authoring mode must be Simplified, Standard, or Not applicable"
            )
        elif normalized_type in {"cover", "agenda", "section divider"}:
            expected_mode = initial_authoring_mode(
                requested_authoring_mode,
                page.fields.get("Page type", ""),
            )
            if authoring_mode != expected_mode:
                errors.append(
                    f"{page.slide_id} {page.fields.get('Page type')} requires Authoring mode "
                    f"{expected_mode} for requested mode {requested_authoring_mode}"
                )
        confirmed = page.fields.get("Confirmed version", "")
        confirmed_pattern = (
            r"(?:A|R[1-9]\d*)" if authoring_mode == "Simplified" else r"(?:A|B|R[1-9]\d*)"
        )
        if state == "SVG confirmed" and not re.fullmatch(confirmed_pattern, confirmed):
            allowed = "A or Rn" if authoring_mode == "Simplified" else "A, B, or Rn"
            errors.append(f"{page.slide_id} {state} requires Confirmed version {allowed}")
        if state not in {"SVG confirmed", "Protected placeholder"} and confirmed != "Pending":
            errors.append(f"{page.slide_id} {state} must keep Confirmed version Pending")
        if state == "Protected placeholder" and confirmed != "Not applicable":
            errors.append(
                f"{page.slide_id} Protected placeholder requires Confirmed version: Not applicable"
            )
        if state in {"Content locked", "Awaiting SVG decision", "SVG confirmed"} and page.fields.get(
            "Open items", ""
        ).strip().lower() != "none":
            errors.append(f"{page.slide_id} {state} requires Open items: None")
        if state == "Protected placeholder" and normalized_type != "protected placeholder":
            errors.append(
                f"{page.slide_id} Protected placeholder state requires Page type: Protected placeholder"
            )
        if normalized_type == "protected placeholder" and state != "Protected placeholder":
            errors.append(
                f"{page.slide_id} Page type Protected placeholder requires Protected placeholder state"
            )
        if state == "Protected placeholder" and authoring_mode != "Not applicable":
            errors.append(
                f"{page.slide_id} Protected placeholder requires Authoring mode: Not applicable"
            )
        if state != "Protected placeholder" and authoring_mode == "Not applicable":
            errors.append(
                f"{page.slide_id} normal page requires Authoring mode Simplified or Standard"
            )
        if state == "SVG confirmed":
            canonical_ids.add(page.slide_id)
        if state == "Protected placeholder":
            canonical_ids.add(page.slide_id)
            instruction = page.fields.get("Content scope", "")
            if "[占位：" not in instruction or "AI不得生成、改写或补充" not in instruction:
                errors.append(
                    f"{page.slide_id} Protected placeholder Content scope needs an exact insertion "
                    "instruction that prohibits AI generation, rewriting, or supplementation"
                )
        if page.fields.get("Review mode") not in {"Page-by-page", "Batch"}:
            errors.append(f"{page.slide_id} Review mode must be Page-by-page or Batch")

    current_workflow = current_values.get("Workflow version")
    if current_workflow == WORKFLOW_VERSION and not cover_ids:
        errors.append("Every workflow 3.9 Storyline requires one opening Cover at S01")
    if len(cover_ids) > 1:
        errors.append("Confirmed Storyline may contain only one Cover: " + ", ".join(cover_ids))
    if cover_ids and cover_ids[0] != "S01":
        errors.append("The single opening Cover must be S01")
    if len(agenda_ids) > 1:
        errors.append("Confirmed Storyline may contain only one Agenda: " + ", ".join(agenda_ids))
    if agenda_ids and agenda_ids[0] != "S02":
        errors.append("Agenda must immediately follow the opening Cover at S02")
    if (
        current_workflow == WORKFLOW_VERSION
        and cover_ids
        and len(substantive_ids) >= LONG_DECK_CONTENT_THRESHOLD
    ):
        if not agenda_ids:
            errors.append(
                f"A deck with {LONG_DECK_CONTENT_THRESHOLD} or more substantive pages requires an Agenda"
            )
        if not divider_ids:
            errors.append(
                f"A deck with {LONG_DECK_CONTENT_THRESHOLD} or more substantive pages requires at least one Section divider"
            )

    if project_dir:
        svg_dir = project_dir / "svg_output"
        actual: set[str] = set()
        if svg_dir.exists():
            for item in svg_dir.iterdir():
                if item.name == ".DS_Store":
                    continue
                if not item.is_file() or not re.fullmatch(r"S\d{2}\.svg", item.name):
                    errors.append(f"svg_output contains a non-canonical artifact: {item.name}")
                else:
                    actual.add(item.stem)
        if actual != canonical_ids:
            if canonical_ids - actual:
                missing = canonical_ids - actual
                non_protected_missing = {
                    slide_id
                    for slide_id in missing
                    if next(p for p in pages if p.slide_id == slide_id).fields.get("Status")
                    != "Protected placeholder"
                }
                if non_protected_missing:
                    errors.append(
                        "svg_output is missing confirmed SVGs: "
                        + ", ".join(sorted(non_protected_missing))
                    )
            if actual - canonical_ids:
                errors.append("svg_output has unconfirmed SVGs: " + ", ".join(sorted(actual - canonical_ids)))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_framework", nargs="?", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--framework", dest="framework_option", type=Path)
    parser.add_argument("--project-dir", type=Path)
    args = parser.parse_args()
    framework = args.framework_option or args.legacy_framework
    if framework is None and args.project_dir:
        framework = args.project_dir / "framework.md"
    framework = framework or Path("framework.md")
    if not framework.is_file():
        print(f"ERROR: framework not found: {framework}")
        return 2
    errors = validate(framework, args.project_dir)
    if errors:
        print(f"Framework validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Presentation framework validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
