#!/usr/bin/env python3
"""Validate the lean build specification produced by EY Deck Design."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from framework_lib import duplicate_line_fields, line_fields, page_entries
from workflow_agenda import agenda_schema_errors
from workflow_spec import is_substantive_page_type


SLIDE_RE = re.compile(r"^## (S\d{2})(?:｜[^\n]*)?$", re.MULTILINE)
BLOCK_HEADING_RE = re.compile(
    r"^(#{4,6}) (S\d{2}-B\d+(?:\.\d+)*)｜(.+)$", re.MULTILINE
)
FIELD_RE = re.compile(r"^- (Title|Subtitle|Core insight):\s*(.+)$", re.MULTILINE)
PROFILE_FIELDS = (
    "Language",
)
PROHIBITED_PAGE_FIELDS = (
    "Chapter",
    "Narrative role",
    "Previous connection",
    "Next connection",
    "Status",
    "Confirmed decisions",
    "Open items",
    "Content section",
    "SVG candidates",
    "Confirmed version",
    "Final SVG",
    "Review status",
    "Authoring mode",
    "Content logic",
    "RFP relevance",
    "Primary/supporting hierarchy",
    "Density",
    "Deferred",
    "Block roles",
    "Relationships",
    "Block role",
    "Display form",
    "Visual cue",
    "Relationship",
    "Primary visual",
    "Visual hierarchy",
    "ID-to-visual mapping",
    "Relationship to express",
    "Background discipline",
    "Fixed",
    "Flexible",
)
BUILD_SPEC_HEADING_RE = r"# Presentation Build Specification"
ALLOWED_EMPHASIS_STYLES = {"关键重点", "次级重点", "对比重点", "普通加粗"}
PAGE_LOGIC_FIELDS = (
    "Page objective",
    "Audience move",
    "Reasoning pattern",
    "Argument chain",
    "Relationship constraints",
    "Argument priority",
)


def named_h2_section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*$", text, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^## ", text[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start():end]


def named_h3_section(text: str, heading: str) -> str:
    match = re.search(rf"^### {re.escape(heading)}.*$", text, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^### ", text[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start():end]


def slide_sections(text: str) -> dict[str, str]:
    matches = list(SLIDE_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.start():end]
    return sections


def validate_header(content: str) -> list[str]:
    errors: list[str] = []
    profile = named_h2_section(content, "Deck build profile（Build-only）")
    if not re.match(rf"\A{BUILD_SPEC_HEADING_RE}\s+\n## Deck build profile（Build-only）", content):
        errors.append("content.md must begin with the compact Deck build profile")
    if not profile:
        errors.append("content.md has no Deck build profile")
    else:
        fields = line_fields(profile)
        errors.extend(
            f"Deck build profile has duplicate field: {field}"
            for field in duplicate_line_fields(profile)
        )
        for field in PROFILE_FIELDS:
            if not fields.get(field, "").strip():
                errors.append(f"Deck build profile is missing {field}")
        unexpected = set(fields) - set(PROFILE_FIELDS)
        if unexpected:
            errors.append("Deck build profile has unsupported fields: " + ", ".join(sorted(unexpected)))
        if fields.get("Language") not in {"Chinese", "English"}:
            errors.append("Deck build profile Language must be Chinese or English")

    for legacy in (
        "Build instructions（Build-only）",
        "Deck context（Build-only）",
        "Deck design system（Build-only）",
    ):
        if named_h2_section(content, legacy):
            errors.append(f"content.md must not duplicate global policy in {legacy}")
    first_slide = re.search(r"^## S\d{2}(?:｜[^\n]*)?$", content, re.MULTILINE)
    prefix = content[: first_slide.start()] if first_slide else content
    unexpected_h2 = [
        heading
        for heading in re.findall(r"^## (.+)$", prefix, re.MULTILINE)
        if heading.strip() != "Deck build profile（Build-only）"
    ]
    if unexpected_h2:
        errors.append(
            "content.md has unsupported global sections: " + ", ".join(unexpected_h2)
        )

    for deprecated_heading in (
        "Proposal information",
        "Storyline summary",
        "Overall principles",
        "Complete source register",
    ):
        if re.search(rf"^##? {re.escape(deprecated_heading)}", content, re.MULTILINE):
            errors.append(f"content.md must not contain deprecated section: {deprecated_heading}")
    return errors


def validate_block_hierarchy(slide_id: str, section: str, page_type: str) -> list[str]:
    errors: list[str] = []
    matches = list(BLOCK_HEADING_RE.finditer(section))
    block_ids = [match.group(2) for match in matches]

    for block_id in block_ids:
        if not block_id.startswith(slide_id + "-B"):
            errors.append(f"{slide_id} contains a block with the wrong prefix: {block_id}")

    for index, match in enumerate(matches):
        block_id = match.group(2)
        hierarchy_depth = block_id.count(".") + 1
        expected_heading_level = hierarchy_depth + 3
        if hierarchy_depth > 3:
            errors.append(f"{slide_id} block hierarchy exceeds three levels: {block_id}")
        if len(match.group(1)) != expected_heading_level:
            errors.append(
                f"{slide_id} block {block_id} must use heading level {expected_heading_level}"
            )
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        body = section[match.end():end]
        children = [other for other in block_ids if other.startswith(block_id + ".")]
        if children and not re.search(r"^- Child logic（Build-only）:\s*\S+", body, re.MULTILINE):
            errors.append(f"{slide_id} parent is missing Child logic: {block_id}")
        if children and re.search(r"^- Detail:\s*\S+", body, re.MULTILINE):
            errors.append(f"{slide_id} parent must not repeat Detail: {block_id}")

        table_purpose = re.search(r"^- Table purpose（Build-only）:\s*\S+", body, re.MULTILINE)
        chart_purpose = re.search(r"^- Chart purpose（Build-only）:\s*\S+", body, re.MULTILINE)
        markdown_table = re.search(
            r"^\|[^\n]+\|\s*\n\|(?:\s*:?-{3,}:?\s*\|)+\s*\n\|[^\n]+\|",
            body,
            re.MULTILINE,
        )
        if table_purpose and not markdown_table:
            errors.append(f"{slide_id} table block has no complete Markdown table: {block_id}")
        if chart_purpose:
            if not markdown_table:
                errors.append(f"{slide_id} chart block has no complete data table: {block_id}")
            if not re.search(r"^- Unit:\s*\S+", body, re.MULTILINE):
                errors.append(f"{slide_id} chart block is missing Unit: {block_id}")

        immediate: list[int] = []
        prefix = block_id + "."
        for other in block_ids:
            if other.startswith(prefix):
                suffix = other[len(prefix):]
                if suffix.isdigit():
                    immediate.append(int(suffix))
        if len(immediate) == 1:
            errors.append(f"{slide_id} parent {block_id} has only one child")
        if immediate and sorted(immediate) != list(range(1, len(immediate) + 1)):
            errors.append(f"{slide_id} children under {block_id} must be sequential from .1")
    return errors


def validate_page_logic(slide_id: str, section: str, page_type: str) -> list[str]:
    errors: list[str] = []
    logic = named_h3_section(section, "Page logic（Build-only）")
    substantive = is_substantive_page_type(page_type)
    if not substantive:
        if logic:
            errors.append(f"{slide_id} structural page must not contain Page logic")
        return errors
    if not logic:
        return [f"{slide_id} substantive page is missing Page logic（Build-only）"]

    fields = line_fields(logic)
    errors.extend(
        f"{slide_id} Page logic has duplicate field: {field}"
        for field in duplicate_line_fields(logic)
    )
    for field in PAGE_LOGIC_FIELDS:
        if not fields.get(field, "").strip():
            errors.append(f"{slide_id} Page logic is missing {field}")
    unexpected = set(fields) - set(PAGE_LOGIC_FIELDS)
    if unexpected:
        errors.append(
            f"{slide_id} Page logic has unsupported fields: "
            + ", ".join(sorted(unexpected))
        )

    top_level_ids = [
        block_id
        for _level, block_id, _title in BLOCK_HEADING_RE.findall(section)
        if "." not in block_id
    ]
    chain = fields.get("Argument chain", "")
    missing_ids = [block_id for block_id in top_level_ids if block_id not in chain]
    if missing_ids:
        errors.append(
            f"{slide_id} Argument chain must name every top-level block: "
            + ", ".join(missing_ids)
        )
    referenced_ids = set(re.findall(rf"\b{re.escape(slide_id)}-B\d+(?:\.\d+)*\b", logic))
    actual_ids = {
        block_id for _level, block_id, _title in BLOCK_HEADING_RE.findall(section)
    }
    unknown_ids = sorted(referenced_ids - actual_ids)
    if unknown_ids:
        errors.append(
            f"{slide_id} Page logic references unknown blocks: "
            + ", ".join(unknown_ids)
        )
    return errors


def validate_slide(
    slide_id: str,
    section: str,
    page_type: str = "",
) -> tuple[list[str], str]:
    errors: list[str] = []
    visible_matches = FIELD_RE.findall(section)
    visible_fields = dict(visible_matches)
    for field, count in Counter(field for field, _value in visible_matches).items():
        if count > 1:
            errors.append(f"{slide_id} has duplicate on-slide field: {field}")
    title = visible_fields.get("Title")
    is_placeholder = "AI不得生成、改写或补充本页内容或设计" in section
    if not re.search(r"^### On-slide content\s*$", section, re.MULTILINE):
        errors.append(f"{slide_id} has no On-slide content section")
    if not title and not is_placeholder:
        errors.append(f"{slide_id} has no preferred Title field")

    if re.search(r"^### Content structure", section, re.MULTILINE):
        errors.append(f"{slide_id} must not contain the deprecated Content structure section")
    if re.search(
        r"^### (?:Production Brief|Design Brief（Build-only）|Visual Direction（Build-only）|Wireframe（Build-only）)",
        section,
        re.MULTILINE,
    ):
        errors.append(f"{slide_id} must not contain design directions")
    if re.search(r"^### Internal notes", section, re.MULTILINE):
        errors.append(f"{slide_id} must not contain Internal notes")
    allowed_h3 = {
        "Page logic（Build-only）",
        "On-slide content",
        "Sources",
    }
    unexpected_h3 = [
        heading.strip()
        for heading in re.findall(r"^### (.+)$", section, re.MULTILINE)
        if heading.strip() not in allowed_h3
    ]
    if unexpected_h3:
        errors.append(
            f"{slide_id} has unsupported page sections: " + ", ".join(unexpected_h3)
        )
    for prohibited in PROHIBITED_PAGE_FIELDS:
        if re.search(rf"^- {re.escape(prohibited)}:", section, re.MULTILINE):
            errors.append(f"{slide_id} must not contain review-oriented field: {prohibited}")

    errors.extend(agenda_schema_errors(section, slide_id, page_type))
    errors.extend(validate_page_logic(slide_id, section, page_type))

    if "[占位：" in section and not is_placeholder:
        errors.append(f"{slide_id} protected placeholder must prohibit replacement content and design")

    errors.extend(validate_block_hierarchy(slide_id, section, page_type))
    sources = named_h3_section(section, "Sources")
    if not sources:
        errors.append(f"{slide_id} has no Sources section")
    else:
        source_fields = line_fields(sources)
        errors.extend(
            f"{slide_id} Sources has duplicate field: {field}"
            for field in duplicate_line_fields(sources)
        )
        for field in ("On-slide source", "Source details"):
            if not source_fields.get(field, "").strip():
                errors.append(f"{slide_id} Sources is missing {field}")
        unexpected_sources = set(source_fields) - {"On-slide source", "Source details"}
        if unexpected_sources:
            errors.append(
                f"{slide_id} Sources has unsupported fields: "
                + ", ".join(sorted(unexpected_sources))
            )

    return errors, page_type


def _emphasis_errors(content: str) -> list[str]:
    errors: list[str] = []
    matches = list(BLOCK_HEADING_RE.finditer(content))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[match.end():end]
        emphasis_matches = list(re.finditer(r"^- Emphasis:\s*$", body, re.MULTILINE))
        if not emphasis_matches:
            continue
        if len(emphasis_matches) > 1:
            errors.append(f"{match.group(2)} has duplicate Emphasis fields")
        emphasis_match = emphasis_matches[0]
        visible_text = [match.group(3).strip()]
        visible_text.extend(
            value.strip()
            for value in re.findall(
                r"^- (?:Detail|Table note|Unit|Period|Chart note):\s*(.+)$",
                body,
                re.MULTILINE,
            )
        )
        for line in body.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            visible_text.extend(cell for cell in cells if cell)
        tail = body[emphasis_match.end():]
        boundary = re.search(r"^(?:- [^\s].*|#{3,6} .*)$", tail, re.MULTILINE)
        emphasis_section = tail[:boundary.start()] if boundary else tail
        lines = [line for line in emphasis_section.splitlines() if line.strip()]
        if not lines:
            errors.append(f"{match.group(2)} Emphasis must contain at least one annotation")
            continue
        annotations: list[tuple[str, str]] = []
        for line in lines:
            annotation = re.fullmatch(r'\s{2,}- “([^”\n]+)”｜([^\n]+)', line)
            if not annotation:
                errors.append(
                    f"{match.group(2)} has malformed Emphasis annotation: {line.strip()!r}"
                )
                continue
            annotations.append((annotation.group(1), annotation.group(2)))
        phrases = [phrase for phrase, _style in annotations]
        duplicates = sorted(phrase for phrase, count in Counter(phrases).items() if count > 1)
        if duplicates:
            errors.append(
                f"{match.group(2)} has duplicate Emphasis targets: " + ", ".join(duplicates)
            )
        for phrase, style in annotations:
            if not any(phrase in value for value in visible_text):
                errors.append(
                    f"{match.group(2)} Emphasis phrase must quote an exact substring from "
                    f"visible text in the same block: {phrase!r}"
                )
            if style.strip() not in ALLOWED_EMPHASIS_STYLES:
                errors.append(
                    f"{match.group(2)} uses unsupported Emphasis style: {style.strip()}"
                )
    return errors


def validate_collection(
    content_path: Path,
    expected_pages: list[str],
    *,
    require_complete: bool = False,
    expected_page_types: dict[str, str] | None = None,
) -> list[str]:
    """Validate all current sections against framework order without rejecting partial progress."""
    content = content_path.read_text(encoding="utf-8")
    errors = validate_header(content)
    slides = SLIDE_RE.findall(content)
    duplicates = sorted(slide_id for slide_id, count in Counter(slides).items() if count > 1)
    if duplicates:
        errors.append("content.md has duplicate Slide IDs: " + ", ".join(duplicates))
    unknown = sorted(set(slides) - set(expected_pages))
    if unknown:
        errors.append("content.md has pages absent from framework: " + ", ".join(unknown))
    expected_current = [slide_id for slide_id in expected_pages if slide_id in set(slides)]
    if slides != expected_current:
        errors.append("content.md pages must follow framework order without duplicates")
    if require_complete and slides != expected_pages:
        missing = [slide_id for slide_id in expected_pages if slide_id not in set(slides)]
        errors.append("content.md is missing required pages: " + ", ".join(missing))

    cover_ids: list[str] = []
    for slide_id, section in slide_sections(content).items():
        page_type = (expected_page_types or {}).get(slide_id, "")
        slide_errors, page_type = validate_slide(slide_id, section, page_type)
        errors.extend(slide_errors)
        if page_type.strip().lower() == "cover":
            cover_ids.append(slide_id)
    if len(cover_ids) > 1:
        errors.append("Only one page may use Page type: Cover: " + ", ".join(cover_ids))
    errors.extend(_emphasis_errors(content))
    return errors


def validate(
    content_path: Path,
    only_page: str | None = None,
    *,
    expected_page_type: str = "",
) -> list[str]:
    content = content_path.read_text(encoding="utf-8")
    errors = validate_header(content)

    slides = SLIDE_RE.findall(content)
    if not slides:
        errors.append("No presentation pages found in content.md")
    duplicates = sorted(slide_id for slide_id, count in Counter(slides).items() if count > 1)
    if duplicates:
        errors.append("content.md has duplicate Slide IDs: " + ", ".join(duplicates))
    expected = [f"S{index:02d}" for index in range(1, len(slides) + 1)]
    if only_page is None and slides != expected:
        errors.append("Slide IDs must be sequential from S01")

    cover_ids: list[str] = []
    for slide_id, section in slide_sections(content).items():
        if only_page is not None and slide_id != only_page:
            continue
        slide_errors, page_type = validate_slide(
            slide_id,
            section,
            expected_page_type if only_page == slide_id else "",
        )
        errors.extend(slide_errors)
        if page_type.strip().lower() == "cover":
            cover_ids.append(slide_id)
    if len(cover_ids) > 1:
        errors.append("Only one page may use Page type: Cover: " + ", ".join(cover_ids))

    if only_page is not None and only_page not in slide_sections(content):
        errors.append(f"Requested page is missing from content.md: {only_page}")

    errors.extend(_emphasis_errors(content))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_content", nargs="?", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--content", dest="content_option", type=Path)
    parser.add_argument("--framework", type=Path)
    parser.add_argument(
        "--page",
        action="append",
        default=[],
        help="validate one or more incremental pages without requiring a complete S01..Sn deck",
    )
    args = parser.parse_args()

    content_path = args.content_option or args.legacy_content or Path("content.md")
    if not content_path.is_file():
        print(f"ERROR: file not found: {content_path}")
        return 2
    try:
        if args.framework:
            if not args.framework.is_file():
                print(f"ERROR: framework not found: {args.framework}")
                return 2
            framework_text = args.framework.read_text(encoding="utf-8")
            framework_pages = page_entries(framework_text)
            expected = [page.slide_id for page in framework_pages]
            expected_types = {
                page.slide_id: page.fields.get("Page type", "")
                for page in framework_pages
            }
            errors = validate_collection(
                content_path,
                expected,
                require_complete=False,
                expected_page_types=expected_types,
            )
            present = set(SLIDE_RE.findall(content_path.read_text(encoding="utf-8")))
            for slide_id in args.page:
                if slide_id not in present:
                    errors.append(f"Requested page is missing from content.md: {slide_id}")
        elif args.page:
            errors = []
            for slide_id in args.page:
                for error in validate(content_path, slide_id):
                    if error not in errors:
                        errors.append(error)
        else:
            errors = validate(content_path)
    except UnicodeDecodeError as exc:
        print(f"Build-spec validation failed: invalid UTF-8 ({exc})")
        return 1

    if errors:
        print(f"Presentation build-spec validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Lean presentation build specification validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
