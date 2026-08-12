#!/usr/bin/env python3
"""Machine-enforced visible-copy contracts for authored page SVGs."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from xml.etree import ElementTree

from workflow_io import text_sha256


COPY_CONTRACT_SCHEMA = "ey-deck.visible-copy.v1"
COPY_ID_ATTRIBUTE = "data-copy-id"
XML_SPACE_ATTRIBUTE = "{http://www.w3.org/XML/1998/namespace}space"
_BLOCK_HEADING = re.compile(r"^#{4,5}\s+(S\d{2}-B[0-9.]+)｜(.+?)\s*$")
_SECTION_HEADING = re.compile(r"^###\s+(.+?)\s*$")
_FIELD = re.compile(r"^- ([^:\n]+):\s*(.*?)\s*$")


def normalize_visible_text(value: str) -> str:
    """Ignore wrapping whitespace without erasing English word boundaries."""
    normalized = unicodedata.normalize("NFC", value).replace("\u00A0", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return re.sub(
        r"(?<=[\u2E80-\u9FFF\uF900-\uFAFF\uFF01-\uFF60]) "
        r"(?=[\u2E80-\u9FFF\uF900-\uFAFF\uFF01-\uFF60])",
        "",
        normalized,
    )


def _is_formatting_whitespace(value: str | None, xml_space: str) -> bool:
    """Identify pretty-print whitespace that is not authored visible copy."""
    return bool(
        value
        and xml_space != "preserve"
        and not value.strip()
        and ("\n" in value or "\r" in value)
    )


def logical_svg_text(
    element: ElementTree.Element,
    inherited_xml_space: str = "default",
) -> str:
    """Extract authored SVG text without injecting XML indentation.

    A whitespace-only node containing a line break between adjacent elements is
    treated as source formatting under the default XML whitespace mode. A
    literal space-only node remains significant so English word boundaries are
    preserved. ``xml:space="preserve"`` disables the formatting exception.
    """
    xml_space = element.get(XML_SPACE_ATTRIBUTE, inherited_xml_space)
    if xml_space not in {"default", "preserve"}:
        xml_space = inherited_xml_space
    parts: list[str] = []
    if element.text and not _is_formatting_whitespace(element.text, xml_space):
        parts.append(element.text)
    for child in element:
        parts.append(logical_svg_text(child, xml_space))
        if child.tail and not _is_formatting_whitespace(child.tail, xml_space):
            parts.append(child.tail)
    return "".join(parts)


def _contract_hash(payload: dict) -> str:
    return text_sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _markdown_table_cells(line: str) -> list[str]:
    body = line.strip()[1:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(body):
        character = body[index]
        if character == "\\" and index + 1 < len(body):
            current.append(body[index + 1])
            index += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells


def visible_copy_contract(section: str, slide_id: str) -> dict:
    """Extract approved visible strings while excluding every Build-only field."""
    heading = re.search(rf"^## {re.escape(slide_id)}｜", section, re.MULTILINE)
    if not heading:
        raise ValueError(f"missing approved content section for {slide_id}")

    items: list[dict[str, object]] = []
    used_ids: set[str] = set()

    def add(copy_id: str, role: str, text: str, *, required: bool = True) -> None:
        value = text.strip()
        if not value or value == "None":
            return
        if copy_id in used_ids:
            raise ValueError(f"duplicate visible-copy id in {slide_id}: {copy_id}")
        used_ids.add(copy_id)
        items.append({"id": copy_id, "role": role, "text": value, "required": required})

    section_name = ""
    block_id = ""
    table_rows: dict[str, int] = {}
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        section_match = _SECTION_HEADING.match(line)
        if section_match:
            section_name = section_match.group(1).strip()
            block_id = ""
            continue
        block_match = _BLOCK_HEADING.match(line)
        if block_match:
            block_id = block_match.group(1)
            if not block_id.startswith(slide_id + "-"):
                raise ValueError(f"foreign content block in {slide_id}: {block_id}")
            add(f"{block_id}-heading", "block-heading", block_match.group(2))
            continue

        field_match = _FIELD.match(line)
        if field_match:
            name, value = field_match.group(1).strip(), field_match.group(2).strip()
            if section_name == "On-slide content" and name in {
                "Title",
                "Subtitle",
                "Core insight",
            }:
                add(
                    f"{slide_id}-{name.lower().replace(' ', '-')}",
                    name.lower().replace(" ", "-"),
                    value,
                )
            elif section_name == "Sources" and name == "On-slide source":
                add(f"{slide_id}-source", "on-slide-source", value)
            elif block_id and name in {"Detail", "Table note", "Chart note", "Unit", "Period"}:
                suffix = name.lower().replace(" ", "-")
                add(f"{block_id}-{suffix}", suffix, value)
            continue

        if block_id and line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            cells = _markdown_table_cells(line)
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            row = table_rows.get(block_id, 0)
            for column, cell in enumerate(cells):
                add(f"{block_id}-table-r{row}-c{column}", "table-cell", cell)
            table_rows[block_id] = row + 1

    add(f"{slide_id}-slide-id", "system-slide-id", slide_id, required=False)
    payload = {
        "schema_version": COPY_CONTRACT_SCHEMA,
        "slide_id": slide_id,
        "items": items,
    }
    payload["contract_sha256"] = _contract_hash(payload)
    return payload


def copy_contract_errors(contract: dict) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != COPY_CONTRACT_SCHEMA:
        errors.append("visible-copy contract has the wrong schema version")
    slide_id = contract.get("slide_id")
    if not isinstance(slide_id, str) or not re.fullmatch(r"S\d{2}", slide_id):
        errors.append("visible-copy contract has an invalid slide_id")
    items = contract.get("items")
    if not isinstance(items, list) or not items:
        errors.append("visible-copy contract has no items")
        return errors
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("visible-copy contract item is not an object")
            continue
        copy_id = item.get("id")
        if not isinstance(copy_id, str) or not copy_id:
            errors.append("visible-copy contract item has no id")
        elif copy_id in seen:
            errors.append(f"visible-copy contract repeats id {copy_id}")
        else:
            seen.add(copy_id)
        if not isinstance(item.get("text"), str) or not normalize_visible_text(str(item.get("text", ""))):
            errors.append(f"visible-copy contract item {copy_id!r} has no text")
        if not isinstance(item.get("required"), bool):
            errors.append(f"visible-copy contract item {copy_id!r} has invalid required flag")
    unsigned = {key: value for key, value in contract.items() if key != "contract_sha256"}
    if contract.get("contract_sha256") != _contract_hash(unsigned):
        errors.append("visible-copy contract hash is stale")
    return errors


def visible_copy_errors(path: Path, contract: dict) -> list[str]:
    """Reject missing, changed, duplicated, or unbound visible SVG text."""
    errors = copy_contract_errors(contract)
    if errors:
        return errors
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        return [f"cannot verify visible copy in {path}: {exc}"]

    expected = {
        str(item["id"]): item
        for item in contract["items"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    actual: dict[str, list[str]] = {}

    def visit(element: ElementTree.Element, inherited_id: str | None = None) -> None:
        own_id = element.get(COPY_ID_ATTRIBUTE)
        if own_id is not None:
            own_id = own_id.strip()
            if not own_id:
                errors.append(f"empty {COPY_ID_ATTRIBUTE} in {path}")
                own_id = None
            elif inherited_id:
                errors.append(
                    f"nested {COPY_ID_ATTRIBUTE} {own_id} inside {inherited_id} in {path}"
                )
        active_id = own_id or inherited_id
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag == "text" and not active_id:
            text = normalize_visible_text(logical_svg_text(element))
            if text:
                errors.append(f"unbound visible SVG text {text!r} in {path}")
        if own_id:
            if tag not in {"text", "g"}:
                errors.append(
                    f"{COPY_ID_ATTRIBUTE} {own_id} must bind a text element or text-only group"
                )
            if tag == "g":
                non_text = sorted({
                    descendant.tag.rsplit("}", 1)[-1].lower()
                    for descendant in element.iter()
                    if descendant is not element
                    and descendant.tag.rsplit("}", 1)[-1].lower()
                    not in {"g", "text", "tspan", "a"}
                })
                if non_text:
                    errors.append(
                        f"visible-copy group {own_id} contains non-text elements: "
                        + ", ".join(non_text)
                    )
            actual.setdefault(own_id, []).append(logical_svg_text(element))
        for child in element:
            visit(child, active_id)

    visit(root)
    for copy_id, values in actual.items():
        if copy_id not in expected:
            errors.append(f"unknown visible-copy id {copy_id} in {path}")
            continue
        if len(values) != 1:
            errors.append(f"visible-copy id {copy_id} appears {len(values)} times in {path}")
            continue
        observed = normalize_visible_text(values[0])
        approved = normalize_visible_text(str(expected[copy_id]["text"]))
        if observed != approved:
            errors.append(
                f"visible-copy id {copy_id} changed: expected {approved!r}, found {observed!r}"
            )
    for copy_id, item in expected.items():
        if item.get("required") is True and copy_id not in actual:
            errors.append(f"missing required visible-copy id {copy_id} in {path}")
    return errors
