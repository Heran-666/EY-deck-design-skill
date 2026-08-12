#!/usr/bin/env python3
"""Validate the lean build specification produced by EY Deck Design."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from framework_lib import duplicate_line_fields, line_fields, page_entries


SLIDE_RE = re.compile(r"^## (S\d{2})｜", re.MULTILINE)
BLOCK_HEADING_RE = re.compile(
    r"^(#{4,6}) (S\d{2}-B\d+(?:\.\d+)*)｜(.+)$", re.MULTILINE
)
FIELD_RE = re.compile(r"^- (Title|Subtitle|Core insight):\s*(.+)$", re.MULTILINE)
PROFILE_FIELDS = (
    "Language",
)
DESIGN_FIELDS = (
    "Page type",
    "Visual focus",
    "Information hierarchy",
    "Relationship to preserve",
    "Fixed constraints",
    "Avoid",
)
VISUAL_DIRECTION_FIELD_LIMIT = 400
HARD_DESIGN_PRESCRIPTION_RE = re.compile(
    r"(?:\b(?:wireframe|layout|mock[- ]?up)\b|"
    r"坐标|线框|版式|布局|x\s*=|y\s*=|\b\d+(?:\.\d+)?\s*(?:px|pt|cm|mm)\b)",
    re.IGNORECASE,
)
DESIGN_SOLUTION_TERM = (
    r"(?:\b(?:grid|card|panel|column|row|timeline|funnel|matrix|radial|"
    r"hub[- ]and[- ]spoke|split[- ]screen|staircase|dashboard)\b|"
    r"网格|卡片|面板|分栏|左右栏|上下栏|时间线|漏斗|矩阵|环形|放射|阶梯|仪表盘)"
)
PRESCRIPTIVE_DESIGN_RE = re.compile(
    rf"(?:(?:\b(?:use|adopt|arrange|place|render|present|build|draw|design)\b|"
    rf"采用|使用|安排|放置|呈现|设计|绘制|排成|分成).{{0,32}}{DESIGN_SOLUTION_TERM}|"
    rf"{DESIGN_SOLUTION_TERM}.{{0,24}}(?:\b(?:layout|arrangement|composition)\b|布局|排列|构图))",
    re.IGNORECASE,
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
    "Review mode",
    "Authoring mode",
    "Page objective",
    "Audience move",
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
NON_SUBSTANTIVE_TYPES = {"cover", "agenda", "section divider", "protected placeholder"}
BUILD_SPEC_HEADING_RE = r"# Presentation Build Specification"
ALLOWED_EMPHASIS_STYLES = {"关键重点", "次级重点", "对比重点", "普通加粗"}


def chinese_width(value: str) -> float:
    width = 0.0
    for char in value.strip():
        code = ord(char)
        is_wide = (
            0x2E80 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
            or 0xFF01 <= code <= 0xFF60
        )
        width += 1.0 if is_wide else 0.5
    return width


def prescribes_concrete_design(value: str) -> bool:
    """Reject construction instructions, not isolated analytical vocabulary."""
    return bool(
        HARD_DESIGN_PRESCRIPTION_RE.search(value)
        or PRESCRIPTIVE_DESIGN_RE.search(value)
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
    matches = list(re.finditer(r"^## (S\d{2})｜.*$", text, re.MULTILINE))
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
    first_slide = re.search(r"^## S\d{2}｜", content, re.MULTILINE)
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


def validate_slide(slide_id: str, section: str) -> tuple[list[str], str]:
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
        errors.append(f"{slide_id} has no exact audience-facing Title field")
    if title and chinese_width(title) > 36:
        errors.append(f"{slide_id} title exceeds 36 Chinese-width characters: {title}")

    if re.search(r"^### Content structure", section, re.MULTILINE):
        errors.append(f"{slide_id} must not contain the deprecated Content structure section")
    if re.search(r"^### (?:Production Brief|Design Brief（Build-only）)", section, re.MULTILINE):
        errors.append(f"{slide_id} must use semantic Visual Direction, not a production or design plan")
    if re.search(r"^### Wireframe（Build-only）", section, re.MULTILINE):
        errors.append(f"{slide_id} must not contain a wireframe or prescribed layout")
    if re.search(r"^### Internal notes", section, re.MULTILINE):
        errors.append(f"{slide_id} must not contain Internal notes")
    allowed_h3 = {
        "On-slide content",
        "Visual Direction（Build-only）",
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

    brief = named_h3_section(section, "Visual Direction（Build-only）")
    if not brief:
        errors.append(f"{slide_id} has no Visual Direction")
        brief_fields: dict[str, str] = {}
    else:
        brief_fields = line_fields(brief)
        errors.extend(
            f"{slide_id} Visual Direction has duplicate field: {field}"
            for field in duplicate_line_fields(brief)
        )
        for field in DESIGN_FIELDS:
            if not brief_fields.get(field, "").strip():
                errors.append(f"{slide_id} Visual Direction is missing {field}")
        unexpected = set(brief_fields) - set(DESIGN_FIELDS)
        if unexpected:
            errors.append(
                f"{slide_id} Visual Direction has unsupported fields: "
                + ", ".join(sorted(unexpected))
            )
        for field, value in brief_fields.items():
            if len(value) > VISUAL_DIRECTION_FIELD_LIMIT:
                errors.append(
                    f"{slide_id} Visual Direction {field} exceeds "
                    f"{VISUAL_DIRECTION_FIELD_LIMIT} characters"
                )
            if field != "Page type" and prescribes_concrete_design(value):
                errors.append(
                    f"{slide_id} Visual Direction {field} prescribes a concrete design solution"
                )

    page_type = brief_fields.get("Page type", "")
    normalized_type = page_type.strip().lower()
    if re.search(r"对比重点", section):
        relationship = brief_fields.get("Relationship to preserve", "")
        if not re.search(r"comparison|contrast|versus|\bvs\b|对比|比较|差异", relationship, re.IGNORECASE):
            errors.append(f"{slide_id} uses 对比重点 without an explicit comparison relationship")
    if normalized_type in {"agenda", "section divider"} and re.search(r"ImageGen", section, re.IGNORECASE):
        errors.append(f"{slide_id} {page_type} must not mention or use ImageGen")
    if normalized_type != "cover":
        for line in section.splitlines():
            if re.search(r"ImageGen", line, re.IGNORECASE) and re.search(
                r"background|背景", line, re.IGNORECASE
            ) and not re.search(
                r"do not|must not|never|no |不得|不要|禁止|不使用|不可", line, re.IGNORECASE
            ):
                errors.append(f"{slide_id} non-cover page must not request an ImageGen background")
                break
    elif re.search(r"ImageGen", section, re.IGNORECASE):
        if not re.search(r"background|背景", section, re.IGNORECASE):
            errors.append(f"{slide_id} Cover ImageGen use must be a background")
        if not re.search(r"text[- ]free|no embedded text|无文字|不含文字", section, re.IGNORECASE):
            errors.append(f"{slide_id} Cover ImageGen background must prohibit embedded text")

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
        detail_match = re.search(r"^- Detail:\s*(.+)$", body, re.MULTILINE)
        if not detail_match:
            continue
        detail = detail_match.group(1)
        tail = body[detail_match.end():]
        for phrase, style in re.findall(r'^\s+- “([^”]+)”｜([^\n]+)$', tail, re.MULTILINE):
            if phrase not in detail:
                errors.append(
                    f"{match.group(2)} Emphasis phrase must quote an exact substring from "
                    f"its - Detail: field: {phrase!r}"
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
        slide_errors, page_type = validate_slide(slide_id, section)
        errors.extend(slide_errors)
        if page_type.strip().lower() == "cover":
            cover_ids.append(slide_id)
    if len(cover_ids) > 1:
        errors.append("Only one page may use Page type: Cover: " + ", ".join(cover_ids))
    errors.extend(_emphasis_errors(content))
    return errors


def validate(content_path: Path, only_page: str | None = None) -> list[str]:
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
        slide_errors, page_type = validate_slide(slide_id, section)
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
            expected = [page.slide_id for page in page_entries(framework_text)]
            errors = validate_collection(content_path, expected, require_complete=False)
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
