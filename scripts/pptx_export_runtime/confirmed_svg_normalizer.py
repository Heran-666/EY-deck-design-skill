#!/usr/bin/env python3
"""Deterministically inline the supported CSS subset in confirmed SVG copies."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
COMPOUND_RE = re.compile(
    r"(?P<tag>\*|[A-Za-z_][A-Za-z0-9_-]*)?"
    r"(?P<qualifiers>(?:[.#][A-Za-z_][A-Za-z0-9_-]*)*)\Z"
)
QUALIFIER_RE = re.compile(r"([.#])([A-Za-z_][A-Za-z0-9_-]*)")


class NormalizationError(ValueError):
    """Raised when CSS cannot be inlined without guessing."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_declarations(raw: str, *, context: str) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for fragment in raw.split(";"):
        fragment = fragment.strip()
        if not fragment:
            continue
        if ":" not in fragment:
            raise NormalizationError(f"malformed CSS declaration in {context}: {fragment!r}")
        name, value = fragment.split(":", 1)
        name = name.strip().lower()
        value = value.strip()
        if not re.fullmatch(r"--?[A-Za-z][A-Za-z0-9_-]*|[A-Za-z][A-Za-z0-9_-]*", name):
            raise NormalizationError(f"unsupported CSS property name in {context}: {name!r}")
        if not value:
            raise NormalizationError(f"empty CSS value in {context}: {name}")
        if "!important" in value.lower() or "var(" in value.lower():
            raise NormalizationError(
                f"unsupported CSS cascade feature in {context}: {name}: {value}"
            )
        declarations[name] = value
    return declarations


def _parse_selector(selector: str) -> tuple[list[str], list[str]]:
    selector = " ".join(selector.strip().split())
    if not selector:
        raise NormalizationError("empty CSS selector")
    if any(token in selector for token in ("[", "]", ":", "+", "~")):
        raise NormalizationError(f"unsupported CSS selector: {selector!r}")
    tokens = re.findall(r"[^\s>]+|>", selector)
    compounds: list[str] = []
    relations: list[str] = []
    pending_relation = "descendant"
    for token in tokens:
        if token == ">":
            if not compounds or pending_relation == "child":
                raise NormalizationError(f"malformed CSS selector: {selector!r}")
            pending_relation = "child"
            continue
        if compounds:
            relations.append(pending_relation)
        compounds.append(token)
        pending_relation = "descendant"
    if not compounds or len(relations) != len(compounds) - 1:
        raise NormalizationError(f"malformed CSS selector: {selector!r}")
    for compound in compounds:
        if COMPOUND_RE.fullmatch(compound) is None:
            raise NormalizationError(f"unsupported CSS selector: {selector!r}")
    return compounds, relations


def _compound_matches(element: ET.Element, compound: str) -> bool:
    match = COMPOUND_RE.fullmatch(compound)
    if match is None:
        return False
    tag = match.group("tag")
    if tag and tag != "*" and _local_name(element.tag).casefold() != tag.casefold():
        return False
    classes = set((element.get("class") or "").split())
    element_id = element.get("id") or ""
    for kind, value in QUALIFIER_RE.findall(match.group("qualifiers")):
        if kind == "." and value not in classes:
            return False
        if kind == "#" and value != element_id:
            return False
    return True


def _selector_matches(
    element: ET.Element,
    compounds: list[str],
    relations: list[str],
    parents: dict[ET.Element, ET.Element],
) -> bool:
    if not _compound_matches(element, compounds[-1]):
        return False
    current = element
    for index in range(len(compounds) - 2, -1, -1):
        relation = relations[index]
        if relation == "child":
            current = parents.get(current)
            if current is None or not _compound_matches(current, compounds[index]):
                return False
            continue
        ancestor = parents.get(current)
        while ancestor is not None and not _compound_matches(ancestor, compounds[index]):
            ancestor = parents.get(ancestor)
        if ancestor is None:
            return False
        current = ancestor
    return True


def _specificity(compounds: list[str]) -> tuple[int, int, int]:
    ids = classes = tags = 0
    for compound in compounds:
        match = COMPOUND_RE.fullmatch(compound)
        if match is None:
            continue
        tag = match.group("tag")
        if tag and tag != "*":
            tags += 1
        for kind, _value in QUALIFIER_RE.findall(match.group("qualifiers")):
            ids += kind == "#"
            classes += kind == "."
    return ids, classes, tags


def normalize_confirmed_svg(path: Path) -> dict[str, object]:
    """Inline supported stylesheet rules in-place and return an audit receipt."""
    source_sha256 = _sha256(path)
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise NormalizationError(f"invalid SVG {path}: {exc}") from exc
    if _local_name(root.tag).casefold() != "svg":
        raise NormalizationError(f"not an SVG root: {path}")

    raw_viewbox = root.get("viewBox") or ""
    viewbox_parts = [item for item in re.split(r"[\s,]+", raw_viewbox.strip()) if item]
    if len(viewbox_parts) != 4:
        raise NormalizationError(f"SVG needs a four-number viewBox: {path}")
    try:
        viewbox = tuple(float(item) for item in viewbox_parts)
    except ValueError as exc:
        raise NormalizationError(f"SVG needs a numeric viewBox: {path}") from exc
    if not all(math.isfinite(item) for item in viewbox) or viewbox[2] <= 0 or viewbox[3] <= 0:
        raise NormalizationError(f"SVG needs a finite positive viewBox: {path}")
    canonical_viewbox = " ".join(format(item, ".12g") for item in viewbox)
    canvas_normalized = (
        raw_viewbox != canonical_viewbox
        or root.get("width") != format(viewbox[2], ".12g")
        or root.get("height") != format(viewbox[3], ".12g")
    )
    root.set("viewBox", canonical_viewbox)
    root.set("width", format(viewbox[2], ".12g"))
    root.set("height", format(viewbox[3], ".12g"))

    parents = {child: parent for parent in root.iter() for child in parent}
    style_elements = [element for element in root.iter() if _local_name(element.tag).casefold() == "style"]
    parsed_rules: list[tuple[list[str], list[str], tuple[int, int, int], int, dict[str, str]]] = []
    order = 0
    for style_index, style_element in enumerate(style_elements, start=1):
        css = CSS_COMMENT_RE.sub("", style_element.text or "").strip()
        if not css:
            continue
        consumed = "".join(match.group(0) for match in CSS_RULE_RE.finditer(css))
        if re.sub(r"\s+", "", consumed) != re.sub(r"\s+", "", css):
            raise NormalizationError(
                f"unsupported or malformed CSS syntax in <style> #{style_index}"
            )
        for rule_match in CSS_RULE_RE.finditer(css):
            raw_selector, raw_declarations = rule_match.groups()
            if raw_selector.lstrip().startswith("@"):
                raise NormalizationError(f"unsupported CSS at-rule: {raw_selector.strip()!r}")
            declarations = _parse_declarations(
                raw_declarations,
                context=f"<style> #{style_index}",
            )
            for selector in raw_selector.split(","):
                compounds, relations = _parse_selector(selector)
                parsed_rules.append(
                    (compounds, relations, _specificity(compounds), order, declarations)
                )
                order += 1

    applied_elements = 0
    applied_properties = 0
    for element in root.iter():
        if element in style_elements:
            continue
        selected: dict[str, tuple[tuple[int, int, int], int, str]] = {}
        for compounds, relations, specificity, rule_order, declarations in parsed_rules:
            if not _selector_matches(element, compounds, relations, parents):
                continue
            for name, value in declarations.items():
                candidate = (specificity, rule_order, value)
                current = selected.get(name)
                if current is None or candidate[:2] >= current[:2]:
                    selected[name] = candidate
        inline = _parse_declarations(
            element.get("style") or "",
            context=f"inline style on <{_local_name(element.tag)}>",
        )
        merged = {name: record[2] for name, record in selected.items()}
        merged.update(inline)
        if merged:
            serialized = ";".join(f"{name}:{value}" for name, value in merged.items())
            element.set("style", serialized)
        elif "style" in element.attrib:
            del element.attrib["style"]
        if selected:
            applied_elements += 1
            applied_properties += len(selected)
        element.attrib.pop("class", None)

    for style_element in style_elements:
        parent = parents.get(style_element)
        if parent is None:
            raise NormalizationError("cannot remove root <style> element safely")
        parent.remove(style_element)

    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    rendered = ET.tostring(root, encoding="unicode")
    if re.search(r"<style\b|\bclass\s*=", rendered, flags=re.IGNORECASE):
        raise NormalizationError("CSS normalization left a <style> or class dependency")
    path.write_text(rendered + "\n", encoding="utf-8")
    normalized_sha256 = _sha256(path)
    return {
        "schema": "ey-deck.confirmed-svg-normalization.v1",
        "source_sha256": source_sha256,
        "normalized_sha256": normalized_sha256,
        "style_elements_removed": len(style_elements),
        "elements_with_inlined_rules": applied_elements,
        "inlined_property_count": applied_properties,
        "canvas_normalized": canvas_normalized,
        "changed": source_sha256 != normalized_sha256,
    }
