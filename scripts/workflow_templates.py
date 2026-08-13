#!/usr/bin/env python3
"""Bundled EY structured-template profile selection and hash contracts."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from workflow_io import sha256, text_sha256


PROFILE_SCHEMA = "ey-deck.template-profile.v1"
BINDING_SCHEMA = "ey-deck.page-template-binding.v1"
STRUCTURED_EXPORT_SCHEMA = "ey-deck.structured-template-export.v1"
PROFILE_DIR = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "templates"
    / "ey-gradient-dark-v1"
)
PROFILE_MANIFEST = PROFILE_DIR / "manifest.json"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalized_node(element: ET.Element) -> object:
    return {
        "tag": _local_name(element.tag),
        "attributes": dict(sorted(element.attrib.items())),
        "text": (element.text or "").strip(),
        "children": [_normalized_node(child) for child in element],
    }


def _prototype_contract(path: Path) -> dict[str, object]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"invalid bundled template prototype {path}: {exc}") from exc
    root_identity = {
        key: root.get(key)
        for key in (
            "width",
            "height",
            "viewBox",
            "data-pptx-master",
            "data-pptx-master-name",
            "data-pptx-layout",
            "data-pptx-layout-name",
            "data-pptx-show-master-shapes",
            "data-pptx-show-inherited-shapes",
        )
    }
    fixed: list[dict[str, object]] = []
    placeholders: list[dict[str, object]] = []
    for child in root:
        layer = child.get("data-pptx-layer")
        placeholder = child.get("data-pptx-placeholder")
        if layer:
            fixed.append({
                "id": child.get("id"),
                "tag": _local_name(child.tag),
                "layer": layer,
                "editable": child.get("data-pptx-editable"),
                "node_sha256": text_sha256(
                    json.dumps(_normalized_node(child), ensure_ascii=False, sort_keys=True)
                ),
            })
        elif placeholder:
            carrier = next(
                (
                    candidate
                    for candidate in child
                    if (candidate.get("data-pptx-carrier") or "").strip().lower()
                    == "true"
                ),
                None,
            )
            placeholders.append({
                "id": child.get("id"),
                "tag": _local_name(child.tag),
                "placeholder": placeholder,
                "binding": child.get("data-pptx-binding") or "carrier",
                "idx": child.get("data-pptx-idx"),
                "bounds": child.get("data-pptx-bounds"),
                "carrier_tag": _local_name(carrier.tag) if carrier is not None else None,
            })
    payload: dict[str, object] = {
        "root": root_identity,
        "resources_sha256": text_sha256(
            json.dumps(
                [
                    _normalized_node(child)
                    for child in root
                    if _local_name(child.tag) in {"defs", "style"}
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
        "fixed": fixed,
        "placeholders": placeholders,
    }
    payload["contract_sha256"] = text_sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    return payload


def load_template_profile() -> dict:
    try:
        profile = json.loads(PROFILE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load bundled EY template profile: {exc}") from exc
    if profile.get("schema_version") != PROFILE_SCHEMA:
        raise ValueError("bundled EY template profile has the wrong schema version")
    if profile.get("native_structure_mode") != "structured":
        raise ValueError("bundled EY template profile is not structured")
    layouts = profile.get("layouts")
    masters = profile.get("masters")
    if not isinstance(layouts, dict) or not layouts:
        raise ValueError("bundled EY template profile has no layouts")
    if not isinstance(masters, dict) or not masters:
        raise ValueError("bundled EY template profile has no masters")
    source_assets = profile.get("source_assets", {})
    if not isinstance(source_assets, dict):
        raise ValueError("bundled EY template source-assets contract is invalid")
    for relative, expected_sha256 in source_assets.items():
        asset = PROFILE_DIR / str(relative)
        if not asset.is_file() or sha256(asset) != expected_sha256:
            raise ValueError(f"bundled EY template source asset is missing or stale: {asset}")
    materialized: dict[str, dict] = {}
    for layout_key, raw in layouts.items():
        if not isinstance(raw, dict):
            raise ValueError(f"bundled EY layout {layout_key} is invalid")
        prototype = PROFILE_DIR / str(raw.get("prototype", ""))
        master_key = str(raw.get("master", ""))
        if not prototype.is_file():
            raise ValueError(f"bundled EY layout prototype is missing: {prototype}")
        if master_key not in masters:
            raise ValueError(f"bundled EY layout {layout_key} has an unknown master")
        materialized[layout_key] = {
            **raw,
            "prototype_path": str(prototype.resolve()),
            "prototype_sha256": sha256(prototype),
            "structure_contract": _prototype_contract(prototype),
        }
    profile["layouts"] = materialized
    profile["manifest_path"] = str(PROFILE_MANIFEST.resolve())
    profile["manifest_sha256"] = sha256(PROFILE_MANIFEST)
    immutable = {
        "profile_id": profile.get("profile_id"),
        "manifest_sha256": profile["manifest_sha256"],
        "layouts": {
            key: {
                "prototype_sha256": value["prototype_sha256"],
                "contract_sha256": value["structure_contract"]["contract_sha256"],
            }
            for key, value in sorted(materialized.items())
        },
    }
    profile["profile_fingerprint"] = text_sha256(
        json.dumps(immutable, ensure_ascii=False, sort_keys=True)
    )
    return profile


def layout_key_for_page_type(page_type: str) -> str | None:
    normalized = page_type.strip().lower()
    if normalized == "protected placeholder":
        return None
    if normalized == "cover":
        return "cover"
    if normalized == "agenda":
        return "agenda"
    if normalized == "section divider":
        return "divider"
    if normalized == "ending":
        return "ending"
    return "content"


def page_template_binding(page_type: str) -> dict | None:
    layout_key = layout_key_for_page_type(page_type)
    if layout_key is None:
        return None
    profile = load_template_profile()
    layout = profile["layouts"][layout_key]
    contract = layout["structure_contract"]
    return {
        "schema_version": BINDING_SCHEMA,
        "profile_id": profile["profile_id"],
        "profile_fingerprint": profile["profile_fingerprint"],
        "manifest_path": profile["manifest_path"],
        "manifest_sha256": profile["manifest_sha256"],
        "layout_key": layout_key,
        "layout_name": layout["name"],
        "master_key": layout["master"],
        "master_name": profile["masters"][layout["master"]],
        "prototype_path": layout["prototype_path"],
        "prototype_sha256": layout["prototype_sha256"],
        "structure_contract_sha256": contract["contract_sha256"],
        "placeholder_contract": contract["placeholders"],
    }


def template_candidate_errors(path: Path, binding: dict | None) -> list[str]:
    if binding is None:
        return []
    errors: list[str] = []
    if binding.get("schema_version") != BINDING_SCHEMA:
        return ["page template binding has the wrong schema version"]
    prototype = Path(str(binding.get("prototype_path", "")))
    if not prototype.is_file() or binding.get("prototype_sha256") != sha256(prototype):
        return ["page template prototype is missing or stale"]
    expected = _prototype_contract(prototype)
    if binding.get("structure_contract_sha256") != expected.get("contract_sha256"):
        errors.append("page template structure contract is stale")
    if not path.is_file():
        return errors + [f"SVG does not exist: {path}"]
    try:
        actual = _prototype_contract(path)
    except ValueError as exc:
        return errors + [str(exc)]
    if actual.get("root") != expected.get("root"):
        errors.append("SVG root Master/Layout identity differs from its bound template")
    if actual.get("fixed") != expected.get("fixed"):
        errors.append("SVG fixed Master/Layout atoms differ from its bound template")
    if actual.get("resources_sha256") != expected.get("resources_sha256"):
        errors.append("SVG fixed template definitions differ from its bound template")
    if actual.get("placeholders") != expected.get("placeholders"):
        errors.append("SVG placeholder ids/types/bounds differ from its bound template")
    return errors
