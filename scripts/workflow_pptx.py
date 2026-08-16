#!/usr/bin/env python3
"""Anti-corruption adapter for confirmed EY SVGs -> editable PPTX export."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from framework_lib import h2_section, line_fields, page_entries
from workflow_io import now, read_json, sha256, write_json
from workflow_paths import ProjectPaths
from workflow_svg import confirmation_valid


SKILL_ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = SKILL_ROOT / "ppt-master"
SERVICE_CONTRACT = PPT_MASTER_ROOT / "workflows" / "svg-deck-pptx-service.md"
SVG_QUALITY_CHECKER = PPT_MASTER_ROOT / "scripts" / "svg_quality_checker.py"
PPTX_EXPORTER = PPT_MASTER_ROOT / "scripts" / "svg_to_pptx.py"
REQUEST_SCHEMA = "ppt-master.svg-deck-pptx-request.v1"
RECEIPT_SCHEMA = "ey-deck.pptx-export.v1"
TEXT_AUDIT_SCHEMA = "ey-deck.pptx-text-frame-audit.v1"
TEXT_FLOW = "preserve"
RUNTIME_PYTHON_ENV = "EY_DECK_PPTX_PYTHON"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
SVG_NS = "http://www.w3.org/2000/svg"
FLAT_PROJECTION_ATTRS = frozenset(
    {
        "data-pptx-binding",
        "data-pptx-carrier",
        "data-pptx-idx",
        "data-pptx-layer",
        "data-pptx-layout",
        "data-pptx-layout-name",
        "data-pptx-master",
        "data-pptx-master-name",
        "data-pptx-placeholder",
        "data-pptx-show-inherited-shapes",
        "data-pptx-show-master-shapes",
    }
)
BLOCKING_TEXT_WARNING_MARKERS = (
    "paragraph-like line run(s) split across sibling <text> elements",
    "multi-line <text> with leading direct text that cannot be normalized into one PPT text frame",
)


def _output_filename(text: str) -> str:
    return line_fields(h2_section(text, "Current position"))["Output filename"]


def _slide_roster(paths: ProjectPaths, text: str) -> list[dict[str, str]]:
    roster: list[dict[str, str]] = []
    for page in page_entries(text):
        status = page.fields.get("Status")
        if status == "Protected placeholder":
            continue
        if status != "SVG confirmed" or not confirmation_valid(paths, page.slide_id):
            raise ValueError(f"{page.slide_id} does not have a current confirmed SVG")
        svg_path = (paths.svg_output / f"{page.slide_id}.svg").resolve()
        roster.append(
            {
                "slide_id": page.slide_id,
                "path": str(svg_path),
                "sha256": sha256(svg_path),
            }
        )
    if not roster:
        raise ValueError("no confirmed authored SVGs are available for PPTX export")
    return roster


def request_payload(paths: ProjectPaths, text: str) -> dict[str, object]:
    filename = _output_filename(text)
    return {
        "schema": REQUEST_SCHEMA,
        "caller": "ey-deck-design",
        "project_dir": str(paths.root.resolve()),
        "framework_path": str(paths.framework.resolve()),
        "framework_sha256": sha256(paths.framework),
        "content_path": str(paths.content.resolve()),
        "content_sha256": sha256(paths.content),
        "slides": _slide_roster(paths, text),
        "output_path": str(paths.pptx_output(filename).resolve()),
        "quality_report_path": str(paths.svg_quality_report.resolve()),
        "postflight_report_path": str(paths.pptx_postflight_report(filename).resolve()),
        "conversion_trace_path": str(paths.pptx_conversion_trace(filename).resolve()),
        "text_frame_audit_path": str(paths.pptx_text_audit.resolve()),
        "conversion": {
            "object_model": "editable-native-drawingml",
            "text_flow": TEXT_FLOW,
            "speaker_notes": "disabled",
            "pptx_structure": "flat-quick-generate",
        },
        "quality_policy": {
            "require_current_confirmed_svg_hashes": True,
            "require_final_svg_quality_gate": True,
            "block_fragmented_paragraph_warnings": True,
            "require_conversion_trace": True,
            "require_text_frame_parity": True,
            "require_pptx_postflight": True,
        },
    }


def write_request(paths: ProjectPaths, text: str) -> Path:
    payload = request_payload(paths, text)
    payload["prepared_at"] = now()
    write_json(paths.pptx_request, payload)
    return paths.pptx_request


def request_valid(paths: ProjectPaths, text: str) -> bool:
    if not paths.pptx_request.is_file():
        return False
    try:
        actual = read_json(paths.pptx_request)
        expected = request_payload(paths, text)
    except (OSError, ValueError):
        return False
    return {key: actual.get(key) for key in expected} == expected


def _run(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"{label} failed: {detail}")
    return completed


def _runtime_python() -> str:
    configured = os.environ.get(RUNTIME_PYTHON_ENV, "").strip()
    if not configured:
        raise ValueError(
            "Load workspace dependencies and set command-scoped "
            f"{RUNTIME_PYTHON_ENV} to the returned Python executable."
        )
    path = Path(configured).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError(
            f"{RUNTIME_PYTHON_ENV} must be the absolute bundled Python executable"
        )
    probe = subprocess.run(
        [str(path), "-c", "import pptx"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode:
        raise ValueError(
            "PPTX runtime is unavailable. Load workspace dependencies and set "
            f"{RUNTIME_PYTHON_ENV} to the returned Python executable."
        )
    return str(path.resolve())


def _blocking_text_warnings(report: dict) -> list[str]:
    issues = report.get("categories", {}).get("introduced", {}).get("issues", [])
    warnings: list[str] = []
    if isinstance(issues, list):
        for issue in issues:
            message = issue.get("message", "") if isinstance(issue, dict) else ""
            if any(marker in message for marker in BLOCKING_TEXT_WARNING_MARKERS):
                filename = issue.get("file", "") if isinstance(issue, dict) else ""
                warnings.append(f"{filename}: {message}" if filename else message)
    return warnings


def _visual_fingerprint(root: ET.Element) -> str:
    """Hash visual XML while ignoring only the bridge's structure metadata."""
    def node_payload(element: ET.Element) -> object:
        attributes = {
            key: value
            for key, value in element.attrib.items()
            if key.rsplit("}", 1)[-1] not in FLAT_PROJECTION_ATTRS
        }
        return [
            element.tag,
            sorted(attributes.items()),
            element.text or "",
            element.tail or "",
            [node_payload(child) for child in list(element)],
        ]

    payload = json.dumps(node_payload(root), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_flat_projection(source: Path, destination: Path) -> dict[str, object]:
    """Write and attest a visual-equivalent flat SVG projection."""
    root = ET.parse(source).getroot()
    source_visual_fingerprint = _visual_fingerprint(root)
    removed_attributes = 0
    for element in root.iter():
        for attribute in tuple(element.attrib):
            if attribute.rsplit("}", 1)[-1] in FLAT_PROJECTION_ATTRS:
                del element.attrib[attribute]
                removed_attributes += 1
    ET.register_namespace("", SVG_NS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=False)
    projected_root = ET.parse(destination).getroot()
    projection_visual_fingerprint = _visual_fingerprint(projected_root)
    if projection_visual_fingerprint != source_visual_fingerprint:
        raise ValueError("flat projection changed visual SVG content")
    return {
        "transform": "strip-structure-metadata/v1",
        "confirmed_svg": str(source.resolve()),
        "confirmed_sha256": sha256(source),
        "conversion_svg": str(destination.resolve()),
        "conversion_sha256": sha256(destination),
        "visual_fingerprint": source_visual_fingerprint,
        "removed_structure_attributes": removed_attributes,
    }


def _annotate_trace_sources(
    trace_path: Path,
    slides: list[dict],
    projections: list[dict[str, object]],
) -> None:
    """Bind every temporary conversion source back to its confirmed authority."""
    trace = read_json(trace_path)
    traced_slides = trace.get("slides")
    if (
        not isinstance(traced_slides, list)
        or len(traced_slides) != len(slides)
        or len(projections) != len(slides)
    ):
        raise ValueError("conversion trace slide count does not match flat staging roster")
    for traced, expected, projection in zip(traced_slides, slides, projections):
        if not isinstance(traced, dict) or not isinstance(expected, dict):
            raise ValueError("invalid conversion trace entry during source restoration")
        if projection.get("confirmed_sha256") != expected.get("sha256"):
            raise ValueError("flat projection authority hash does not match export request")
        traced["svg"] = expected["path"]
        traced["source_bridge"] = projection
    write_json(trace_path, trace)


def _pptx_text_box_counts(pptx_path: Path, slide_count: int) -> list[int]:
    counts: list[int] = []
    with zipfile.ZipFile(pptx_path) as archive:
        for slide_number in range(1, slide_count + 1):
            name = f"ppt/slides/slide{slide_number}.xml"
            try:
                root = ET.fromstring(archive.read(name))
            except KeyError as exc:
                raise ValueError(f"PPTX is missing {name}") from exc
            counts.append(
                sum(
                    node.get("txBox") == "1"
                    for node in root.iter(f"{{{PRESENTATION_NS}}}cNvSpPr")
                )
            )
    return counts


def audit_text_frames(request: dict, output_path: Path, trace_path: Path) -> dict[str, object]:
    trace = read_json(trace_path)
    trace_slides = trace.get("slides")
    slides = request.get("slides")
    if not isinstance(trace_slides, list) or not isinstance(slides, list):
        raise ValueError("conversion trace or export request has no slide roster")
    if len(trace_slides) != len(slides):
        raise ValueError("conversion trace slide count does not match the confirmed SVG roster")
    pptx_counts = _pptx_text_box_counts(output_path, len(slides))
    audited: list[dict[str, object]] = []
    for index, (expected, traced, pptx_count) in enumerate(
        zip(slides, trace_slides, pptx_counts), start=1
    ):
        if not isinstance(expected, dict) or not isinstance(traced, dict):
            raise ValueError(f"invalid text-frame trace entry for slide {index}")
        traced_svg = Path(str(traced.get("svg", ""))).resolve()
        if traced_svg != Path(str(expected.get("path", ""))).resolve():
            raise ValueError(f"conversion trace source mismatch for slide {index}")
        preprocess = traced.get("preprocess")
        if not isinstance(preprocess, list):
            raise ValueError(f"conversion trace has no preprocess ledger for slide {index}")
        text_flow_steps = [
            item for item in preprocess
            if isinstance(item, dict) and item.get("action") == "flatten-positional-tspans"
        ]
        if any(item.get("text_flow") != TEXT_FLOW for item in text_flow_steps):
            raise ValueError(f"slide {index} was not converted with preserve text flow")
        events = traced.get("events")
        if not isinstance(events, list):
            raise ValueError(f"conversion trace has no element ledger for slide {index}")
        text_events = [item for item in events if isinstance(item, dict) and item.get("tag") == "text"]
        failed = [item for item in text_events if item.get("decision") != "native"]
        if failed:
            raise ValueError(f"slide {index} contains text that did not become native editable text")
        if len(text_events) != pptx_count:
            raise ValueError(
                f"slide {index} text-frame parity failed: trace={len(text_events)}, pptx={pptx_count}"
            )
        audited.append(
            {
                "slide_number": index,
                "slide_id": expected.get("slide_id"),
                "svg_text_frames": len(text_events),
                "pptx_text_boxes": pptx_count,
                "status": "passed",
            }
        )
    return {
        "schema": TEXT_AUDIT_SCHEMA,
        "status": "passed",
        "text_flow": TEXT_FLOW,
        "slides": audited,
        "audited_at": now(),
    }


def export_from_request(paths: ProjectPaths, text: str) -> Path:
    if not request_valid(paths, text):
        raise ValueError("PPTX export request is missing or stale; prepare it again")
    request = read_json(paths.pptx_request)
    python = _runtime_python()
    output_path = Path(str(request["output_path"]))
    trace_path = Path(str(request["conversion_trace_path"]))
    postflight_path = Path(str(request["postflight_report_path"]))
    slides = request.get("slides")
    if not isinstance(slides, list):
        raise ValueError("PPTX export request has no slide roster")
    with tempfile.TemporaryDirectory(prefix="ey-deck-pptx-") as staging_name:
        staging_root = Path(staging_name)
        staging_svg_output = staging_root / "svg_output"
        projections: list[dict[str, object]] = []
        for slide in slides:
            if not isinstance(slide, dict):
                raise ValueError("invalid slide entry in PPTX export request")
            source = Path(str(slide["path"]))
            projections.append(
                _write_flat_projection(source, staging_svg_output / source.name)
            )

        _run(
            [
                python,
                str(SVG_QUALITY_CHECKER),
                str(staging_root),
                "--quick-generate",
                "--stage",
                "final",
                "--json",
            ],
            "PPT Master final SVG quality gate",
        )
        staged_quality = staging_root / "validation" / "svg_quality_report.json"
        quality = read_json(staged_quality)
        blocking_text = _blocking_text_warnings(quality)
        if blocking_text:
            raise ValueError(
                "PPTX text-box preflight rejected fragmented paragraph source: "
                + " | ".join(blocking_text)
            )

        _run(
            [
                python,
                str(PPTX_EXPORTER),
                str(staging_root),
                "-o",
                str(output_path),
                "--quick-generate",
                "--no-notes",
                "--preserve-text",
                "--conversion-trace",
                str(trace_path),
            ],
            "PPT Master editable PPTX export",
        )
        _annotate_trace_sources(trace_path, slides, projections)
        paths.svg_quality_report.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_quality, paths.svg_quality_report)
        staged_postflight = (
            staging_root / "validation" / f"{output_path.stem}.report.json"
        )
        if not postflight_path.is_file() and staged_postflight.is_file():
            postflight_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_postflight, postflight_path)

    postflight = read_json(postflight_path)
    if postflight.get("status") not in {"passed", "passed-with-warnings"}:
        raise ValueError(f"PPTX postflight did not pass: {postflight.get('status')}")
    text_audit = audit_text_frames(request, output_path, trace_path)
    write_json(paths.pptx_text_audit, text_audit)
    write_json(
        paths.pptx_receipt,
        {
            "schema": RECEIPT_SCHEMA,
            "request_sha256": sha256(paths.pptx_request),
            "output_path": str(output_path.resolve()),
            "output_sha256": sha256(output_path),
            "quality_report_sha256": sha256(paths.svg_quality_report),
            "postflight_report_sha256": sha256(postflight_path),
            "conversion_trace_sha256": sha256(trace_path),
            "text_frame_audit_sha256": sha256(paths.pptx_text_audit),
            "slide_count": len(request["slides"]),
            "exported_at": now(),
        },
    )
    return output_path


def export_valid(paths: ProjectPaths, text: str) -> bool:
    if not request_valid(paths, text) or not paths.pptx_receipt.is_file():
        return False
    try:
        request = read_json(paths.pptx_request)
        receipt = read_json(paths.pptx_receipt)
        audit = read_json(paths.pptx_text_audit)
        output = Path(str(request["output_path"]))
        quality = Path(str(request["quality_report_path"]))
        postflight = Path(str(request["postflight_report_path"]))
        trace = Path(str(request["conversion_trace_path"]))
    except (KeyError, OSError, ValueError):
        return False
    required = (output, quality, postflight, trace, paths.pptx_text_audit)
    if any(not path.is_file() for path in required):
        return False
    return (
        receipt.get("schema") == RECEIPT_SCHEMA
        and receipt.get("request_sha256") == sha256(paths.pptx_request)
        and receipt.get("output_path") == str(output.resolve())
        and receipt.get("output_sha256") == sha256(output)
        and receipt.get("quality_report_sha256") == sha256(quality)
        and receipt.get("postflight_report_sha256") == sha256(postflight)
        and receipt.get("conversion_trace_sha256") == sha256(trace)
        and receipt.get("text_frame_audit_sha256") == sha256(paths.pptx_text_audit)
        and receipt.get("slide_count") == len(request.get("slides", []))
        and audit.get("schema") == TEXT_AUDIT_SCHEMA
        and audit.get("status") == "passed"
        and audit.get("text_flow") == TEXT_FLOW
    )
