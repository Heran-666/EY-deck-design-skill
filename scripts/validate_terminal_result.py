#!/usr/bin/env python3
"""Validate a confirmed-export terminal result against one EY export manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


REPAIR_SCOPES = {"source-svg", "user-decision", "environment"}


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_terminal_result(manifest: dict, result: dict) -> list[str]:
    errors: list[str] = []
    ordered = manifest.get("ordered_slides")
    if not isinstance(ordered, list) or not ordered:
        return ["export manifest has no ordered slides"]
    slide_ids = [item.get("slide_id") for item in ordered if isinstance(item, dict)]
    if len(slide_ids) != len(ordered) or any(not _nonempty_string(item) for item in slide_ids):
        return ["export manifest ordered slides have invalid Slide IDs"]

    if result.get("route") != "embedded-ppt-master-stage2":
        errors.append("route must be embedded-ppt-master-stage2")
    status = result.get("status")
    if status not in {"COMPLETE", "BLOCKED"}:
        errors.append("status must be COMPLETE or BLOCKED")
        return errors
    allowed = {"status", "route", "artifact_path"} if status == "COMPLETE" else {
        "status", "route", "stage", "reason", "repair_scope", "resume_from", "slide_ids"
    }
    unexpected = set(result) - allowed
    if unexpected:
        errors.append("terminal result has unsupported fields: " + ", ".join(sorted(unexpected)))

    if status == "COMPLETE":
        artifact_value = result.get("artifact_path")
        if not _nonempty_string(artifact_value):
            errors.append("COMPLETE requires artifact_path")
            return errors
        artifact = Path(str(artifact_value)).expanduser().resolve()
        expected = Path(str(manifest.get("required_output_path", ""))).expanduser().resolve()
        if artifact != expected:
            errors.append(f"COMPLETE artifact_path must equal the manifest output path: {expected}")
        if not artifact.is_file():
            errors.append(f"COMPLETE artifact does not exist: {artifact}")
            return errors
        try:
            with zipfile.ZipFile(artifact) as archive:
                corrupt = archive.testzip()
                slide_count = sum(
                    bool(re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
                    for name in archive.namelist()
                )
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"COMPLETE artifact is not a readable PPTX package: {exc}")
            return errors
        if corrupt is not None:
            errors.append(f"COMPLETE artifact has a corrupt ZIP member: {corrupt}")
        if slide_count != len(ordered):
            errors.append(
                "COMPLETE artifact slide count must match the manifest: "
                f"{slide_count} != {len(ordered)}"
            )
        return errors

    for key in ("stage", "reason", "repair_scope", "resume_from"):
        if not _nonempty_string(result.get(key)):
            errors.append(f"BLOCKED requires non-empty {key}")
    if result.get("repair_scope") not in REPAIR_SCOPES:
        errors.append("BLOCKED repair_scope must be source-svg, user-decision, or environment")
    blocked = result.get("slide_ids")
    if not isinstance(blocked, list) or not blocked:
        errors.append("BLOCKED requires non-empty slide_ids")
        return errors
    if any(not _nonempty_string(item) for item in blocked):
        errors.append("BLOCKED slide_ids must contain only non-empty strings")
        return errors
    if len(set(blocked)) != len(blocked):
        errors.append("BLOCKED slide_ids must be unique")
    unknown = [item for item in blocked if item not in slide_ids]
    if unknown:
        errors.append("BLOCKED references unknown Slide IDs: " + ", ".join(unknown))
    expected_order = [item for item in slide_ids if item in set(blocked)]
    if blocked != expected_order:
        errors.append("BLOCKED slide_ids must follow the original deck order")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--result-json")
    source.add_argument("--result-file", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        raw = args.result_json if args.result_json is not None else args.result_file.read_text(encoding="utf-8")
        result = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Terminal result validation failed: {exc}")
        return 2
    if not isinstance(manifest, dict) or not isinstance(result, dict):
        print("Terminal result validation failed: manifest and result must be JSON objects")
        return 2
    errors = validate_terminal_result(manifest, result)
    if errors:
        print(f"Terminal result validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
