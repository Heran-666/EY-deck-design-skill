#!/usr/bin/env python3
"""Anti-corruption adapter for confirmed EY SVGs -> editable PPTX export."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from framework_lib import h2_section, line_fields, page_entries
from workflow_io import now, read_json, sha256, write_json
from workflow_paths import ProjectPaths
from workflow_ppt_master import (
    deferred_template_text,
    materialize_template,
    template_path,
)
from workflow_svg import confirmation_valid


SKILL_ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = SKILL_ROOT / "ppt-master"
PPT_MASTER_SCRIPTS = PPT_MASTER_ROOT / "scripts"
if str(PPT_MASTER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PPT_MASTER_SCRIPTS))
from svg_finalize.flatten_tspan import text_carrier_integrity_errors  # noqa: E402
SERVICE_CONTRACT = PPT_MASTER_ROOT / "workflows" / "svg-deck-pptx-service.md"
SVG_QUALITY_CHECKER = PPT_MASTER_ROOT / "scripts" / "svg_quality_checker.py"
PPTX_EXPORTER = PPT_MASTER_ROOT / "scripts" / "svg_to_pptx.py"
REQUEST_SCHEMA = "ppt-master.svg-deck-pptx-request.v3"
RECEIPT_SCHEMA = "ey-deck.pptx-export.v1"
TEXT_AUDIT_SCHEMA = "ey-deck.pptx-text-frame-audit.v2"
TEXT_FLOW = "reflow"
TEXT_FAILURE_SCHEMA = "ey-deck.pptx-text-failure.v1"
RUNTIME_PYTHON_ENV = "EY_DECK_PPTX_PYTHON"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
DRAWINGML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
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


class TextCarrierIntegrityError(ValueError):
    """A slide-local editable-text failure that requires SVG reconfirmation."""

    def __init__(self, slide_id: str, source_kind: str, message: str) -> None:
        super().__init__(message)
        self.slide_id = slide_id
        self.source_kind = source_kind


def _output_filename(text: str) -> str:
    return line_fields(h2_section(text, "Current position"))["Output filename"]


def _slide_roster(paths: ProjectPaths, text: str) -> list[dict[str, str]]:
    roster: list[dict[str, str]] = []
    for page in page_entries(text):
        status = page.fields.get("Status")
        if status == "Protected placeholder":
            continue
        if status == "Deferred template":
            svg_path = paths.pptx_template(page.slide_id).resolve()
            if not svg_path.is_file():
                raise ValueError(f"deferred template snapshot is missing for {page.slide_id}")
            text_bindings = deferred_template_text(text, page)
            roster.append(
                {
                    "slide_id": page.slide_id,
                    "source_kind": "deferred-template",
                    "page_type": page.fields.get("Page type", ""),
                    "path": str(svg_path),
                    "sha256": sha256(svg_path),
                    "binding_sha256": hashlib.sha256(
                        json.dumps(
                            text_bindings,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            )
            continue
        if status == "SVG confirmed" and confirmation_valid(paths, page.slide_id):
            svg_path = (paths.svg_output / f"{page.slide_id}.svg").resolve()
            roster.append(
                {
                    "slide_id": page.slide_id,
                    "source_kind": "confirmed-svg",
                    "page_type": page.fields.get("Page type", ""),
                    "path": str(svg_path),
                    "sha256": sha256(svg_path),
                }
            )
            continue
        raise ValueError(f"{page.slide_id} has no exportable confirmed SVG or deferred template")
    if not roster:
        raise ValueError("no exportable slides are available for PPTX export")
    return roster


def _materialize_deferred_templates(paths: ProjectPaths, text: str) -> None:
    for page in page_entries(text):
        if page.fields.get("Status") == "Deferred template":
            materialize_template(
                template_path(page),
                paths.pptx_template(page.slide_id),
                text_bindings=deferred_template_text(text, page),
            )


def _atomic_copy(source: Path, destination: Path) -> None:
    """Replace one evidence file without exposing a partial write."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_current_postflight(
    postflight: dict,
    quality: dict,
    output_path: Path,
    slide_count: int,
) -> None:
    """Reject a postflight report that does not describe this export run."""
    output = postflight.get("output")
    source = postflight.get("source")
    report_fingerprint = (
        source.get("fingerprint", {}).get("digest")
        if isinstance(source, dict)
        else None
    )
    quality_fingerprint = quality.get("source_fingerprint", {}).get("digest")
    if (
        not isinstance(output, dict)
        or Path(str(output.get("path", ""))).resolve() != output_path.resolve()
    ):
        raise ValueError("PPTX postflight output path does not match this export")
    if output.get("bytes") != output_path.stat().st_size:
        raise ValueError("PPTX postflight output size does not match this export")
    if not isinstance(source, dict) or source.get("svg_slide_count") != slide_count:
        raise ValueError("PPTX postflight slide count does not match this export")
    if not report_fingerprint or report_fingerprint != quality_fingerprint:
        raise ValueError("PPTX postflight source fingerprint does not match this export")


def request_payload(paths: ProjectPaths, text: str) -> dict[str, object]:
    filename = _output_filename(text)
    return {
        "schema": REQUEST_SCHEMA,
        "caller": "ey-deck-design",
        "slides": _slide_roster(paths, text),
        "output_path": str(paths.pptx_output(filename).resolve()),
        "quality_report_path": str(paths.svg_quality_report.resolve()),
        "postflight_report_path": str(paths.pptx_postflight_report(filename).resolve()),
        "conversion_trace_path": str(paths.pptx_conversion_trace(filename).resolve()),
        "text_frame_audit_path": str(paths.pptx_text_audit.resolve()),
    }


def write_request(paths: ProjectPaths, text: str) -> Path:
    _materialize_deferred_templates(paths, text)
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


def _write_flat_projection(
    source: Path,
    destination: Path,
    *,
    slide_id: str,
    source_kind: str,
) -> dict[str, object]:
    """Write and attest a visual-equivalent flat SVG projection."""
    root = ET.parse(source).getroot()
    text_errors = text_carrier_integrity_errors(root)
    if text_errors:
        raise TextCarrierIntegrityError(
            slide_id,
            source_kind,
            f"{slide_id} violates editable text-carrier integrity: "
            + " | ".join(text_errors)
        )
    source_text_carriers = _assign_stable_text_carrier_ids(root, slide_id)
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
        "source_kind": source_kind,
        "source_path": str(source.resolve()),
        "source_sha256": sha256(source),
        "confirmed_svg": str(source.resolve()),
        "confirmed_sha256": sha256(source),
        "conversion_svg": str(destination.resolve()),
        "conversion_sha256": sha256(destination),
        "visual_fingerprint": source_visual_fingerprint,
        "removed_structure_attributes": removed_attributes,
        "source_text_carriers": source_text_carriers,
    }


def _assign_stable_text_carrier_ids(root: ET.Element, slide_id: str) -> list[str]:
    """Assign deterministic bridge-only ids to otherwise anonymous text carriers."""
    used: set[str] = set()
    for element in root.iter():
        element_id = (element.get("id") or "").strip()
        if not element_id:
            continue
        if element_id in used:
            raise ValueError(f"duplicate SVG id prevents stable carrier mapping: {element_id}")
        used.add(element_id)

    carriers: list[str] = []
    for ordinal, element in enumerate(root.iter(f"{{{SVG_NS}}}text"), start=1):
        carrier_id = (element.get("id") or "").strip()
        if not carrier_id:
            base = f"ey-text-{slide_id}-{ordinal:03d}"
            carrier_id = base
            suffix = 2
            while carrier_id in used:
                carrier_id = f"{base}-{suffix}"
                suffix += 1
            element.set("id", carrier_id)
            used.add(carrier_id)
        carriers.append(carrier_id)
    return carriers


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
        if projection.get("source_kind") != expected.get("source_kind"):
            raise ValueError("flat projection source kind does not match export request")
        traced["svg"] = expected["path"]
        traced["source_bridge"] = projection
    write_json(trace_path, trace)


def _append_text_token(tokens: list[dict[str, str]], value: str) -> None:
    if not value:
        return
    if tokens and tokens[-1].get("kind") == "text":
        tokens[-1]["value"] = tokens[-1].get("value", "") + value
    else:
        tokens.append({"kind": "text", "value": value})


def _ooxml_text_sequence(text_body: ET.Element) -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    paragraphs = text_body.findall(f"{{{DRAWINGML_NS}}}p")
    for paragraph_index, paragraph in enumerate(paragraphs):
        if paragraph_index:
            tokens.append({"kind": "paragraph"})
        for child in list(paragraph):
            if child.tag == f"{{{DRAWINGML_NS}}}br":
                tokens.append({"kind": "hard-break"})
                continue
            if child.tag not in {
                f"{{{DRAWINGML_NS}}}r",
                f"{{{DRAWINGML_NS}}}fld",
            }:
                continue
            for text_node in child.iter(f"{{{DRAWINGML_NS}}}t"):
                _append_text_token(tokens, text_node.text or "")
    return tokens


def _pptx_text_boxes(
    pptx_path: Path,
    slide_count: int,
) -> list[dict[int, list[dict[str, str]]]]:
    slides: list[dict[int, list[dict[str, str]]]] = []
    with zipfile.ZipFile(pptx_path) as archive:
        for slide_number in range(1, slide_count + 1):
            name = f"ppt/slides/slide{slide_number}.xml"
            try:
                root = ET.fromstring(archive.read(name))
            except KeyError as exc:
                raise ValueError(f"PPTX is missing {name}") from exc
            boxes: dict[int, list[dict[str, str]]] = {}
            for shape in root.iter(f"{{{PRESENTATION_NS}}}sp"):
                nonvisual = shape.find(f"{{{PRESENTATION_NS}}}nvSpPr")
                text_body = shape.find(f"{{{PRESENTATION_NS}}}txBody")
                if nonvisual is None or text_body is None:
                    continue
                shape_props = nonvisual.find(f"{{{PRESENTATION_NS}}}cNvSpPr")
                shape_identity = nonvisual.find(f"{{{PRESENTATION_NS}}}cNvPr")
                if (
                    shape_props is None
                    or shape_props.get("txBox") != "1"
                    or shape_identity is None
                ):
                    continue
                shape_id = int(shape_identity.get("id", "0"))
                if shape_id in boxes:
                    raise ValueError(
                        f"PPTX slide {slide_number} contains duplicate text-box shape id {shape_id}"
                    )
                boxes[shape_id] = _ooxml_text_sequence(text_body)
            slides.append(boxes)
    return slides


def audit_text_frames(request: dict, output_path: Path, trace_path: Path) -> dict[str, object]:
    trace = read_json(trace_path)
    trace_slides = trace.get("slides")
    slides = request.get("slides")
    if not isinstance(trace_slides, list) or not isinstance(slides, list):
        raise ValueError("conversion trace or export request has no slide roster")
    if len(trace_slides) != len(slides):
        raise ValueError("conversion trace slide count does not match the ordered slide roster")
    pptx_slides = _pptx_text_boxes(output_path, len(slides))
    audited: list[dict[str, object]] = []
    for index, (expected, traced, pptx_boxes) in enumerate(
        zip(slides, trace_slides, pptx_slides), start=1
    ):
        if not isinstance(expected, dict) or not isinstance(traced, dict):
            raise ValueError(f"invalid text-frame trace entry for slide {index}")
        slide_id = str(expected.get("slide_id") or f"slide-{index}")
        source_kind = str(expected.get("source_kind") or "confirmed-svg")

        def fail(message: str) -> None:
            raise TextCarrierIntegrityError(slide_id, source_kind, message)

        traced_svg = Path(str(traced.get("svg", ""))).resolve()
        if traced_svg != Path(str(expected.get("path", ""))).resolve():
            fail(f"conversion trace source mismatch for slide {index}")
        preprocess = traced.get("preprocess")
        if not isinstance(preprocess, list):
            fail(f"conversion trace has no preprocess ledger for slide {index}")
        text_flow_steps = [
            item for item in preprocess
            if isinstance(item, dict) and item.get("action") == "flatten-positional-tspans"
        ]
        if any(item.get("text_flow") != TEXT_FLOW for item in text_flow_steps):
            fail(f"slide {index} was not converted with reflow text flow")
        events = traced.get("events")
        if not isinstance(events, list):
            fail(f"conversion trace has no element ledger for slide {index}")
        text_events = [item for item in events if isinstance(item, dict) and item.get("tag") == "text"]
        failed = [item for item in text_events if item.get("decision") != "native"]
        if failed:
            fail(f"slide {index} contains text that did not become native editable text")
        source_bridge = traced.get("source_bridge")
        source_carriers = (
            source_bridge.get("source_text_carriers")
            if isinstance(source_bridge, dict)
            else None
        )
        if not isinstance(source_carriers, list) or not all(
            isinstance(item, str) and item for item in source_carriers
        ):
            fail(f"slide {index} trace has no stable source text-carrier roster")
        event_ids = [item.get("id") for item in text_events]
        if any(not isinstance(item, str) or not item for item in event_ids):
            fail(f"slide {index} contains an unaddressable converted text carrier")
        if len(set(source_carriers)) != len(source_carriers):
            fail(f"slide {index} source text-carrier ids are not unique")
        if len(set(event_ids)) != len(event_ids):
            fail(f"slide {index} converted text-carrier ids are not unique")

        source_count = len(source_carriers)
        conversion_count = len(text_events)
        pptx_count = len(pptx_boxes)
        if not (source_count == conversion_count == pptx_count):
            fail(
                f"slide {index} text-carrier conservation failed: "
                f"source={source_count}, conversion={conversion_count}, pptx={pptx_count}"
            )
        if set(source_carriers) != set(event_ids):
            fail(f"slide {index} source-to-conversion carrier mapping failed")

        carrier_audit: list[dict[str, object]] = []
        for event in text_events:
            carrier_id = str(event["id"])
            shape_id = event.get("shape_id")
            expected_sequence = event.get("text_sequence")
            if not isinstance(shape_id, int) or shape_id not in pptx_boxes:
                fail(
                    f"slide {index} carrier {carrier_id} has no one-to-one PPTX text-box shape"
                )
            if not isinstance(expected_sequence, list):
                fail(
                    f"slide {index} carrier {carrier_id} has no conversion text sequence"
                )
            actual_sequence = pptx_boxes[shape_id]
            if any(token.get("kind") == "hard-break" for token in actual_sequence):
                fail(
                    f"slide {index} carrier {carrier_id} contains a DrawingML hard "
                    "break; visual SVG wrap rows must reflow as continuous text"
                )
            if expected_sequence != actual_sequence:
                fail(
                    f"slide {index} carrier {carrier_id} text continuity failed: "
                    f"conversion={expected_sequence!r}, pptx={actual_sequence!r}"
                )
            carrier_audit.append(
                {
                    "carrier_id": carrier_id,
                    "pptx_shape_id": shape_id,
                    "status": "passed",
                }
            )
        audited.append(
            {
                "slide_number": index,
                "slide_id": expected.get("slide_id"),
                "source_svg_text_carriers": source_count,
                "conversion_text_events": conversion_count,
                "pptx_text_boxes": pptx_count,
                "carriers": carrier_audit,
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


def _export_from_request_impl(paths: ProjectPaths, text: str) -> Path:
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
                _write_flat_projection(
                    source,
                    staging_svg_output / f"{slide['slide_id']}.svg",
                    slide_id=str(slide["slide_id"]),
                    source_kind=str(slide.get("source_kind", "confirmed-svg")),
                )
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
            first_warning = blocking_text[0]
            affected = next(
                (
                    item for item in slides
                    if isinstance(item, dict)
                    and f"{item.get('slide_id')}.svg" in first_warning
                ),
                slides[0],
            )
            raise TextCarrierIntegrityError(
                str(affected.get("slide_id", "unknown")),
                str(affected.get("source_kind", "confirmed-svg")),
                "PPTX text-box preflight rejected fragmented paragraph source: "
                + " | ".join(blocking_text),
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
                "--reflow-text",
                "--conversion-trace",
                str(trace_path),
            ],
            "PPT Master editable PPTX export",
        )
        _annotate_trace_sources(trace_path, slides, projections)
        staged_postflight = (
            staging_root / "validation" / f"{output_path.stem}.report.json"
        )
        if not staged_postflight.is_file():
            raise ValueError("PPT Master did not produce a postflight report")
        staged_postflight_payload = read_json(staged_postflight)
        _validate_current_postflight(
            staged_postflight_payload,
            quality,
            output_path,
            len(slides),
        )
        _atomic_copy(staged_quality, paths.svg_quality_report)
        _atomic_copy(staged_postflight, postflight_path)

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


def export_from_request(paths: ProjectPaths, text: str) -> Path:
    """Export and persist a slide-local recovery receipt for text failures."""
    if not request_valid(paths, text):
        write_request(paths, text)
    try:
        output = _export_from_request_impl(paths, text)
    except TextCarrierIntegrityError as exc:
        write_json(
            paths.pptx_text_failure,
            {
                "schema": TEXT_FAILURE_SCHEMA,
                "request_sha256": sha256(paths.pptx_request),
                "slide_id": exc.slide_id,
                "source_kind": exc.source_kind,
                "reason": str(exc),
                "recovery": (
                    "reopen-svg-and-reconfirm"
                    if exc.source_kind == "confirmed-svg"
                    else "repair-deferred-template-upstream"
                ),
                "failed_at": now(),
            },
        )
        raise
    if paths.pptx_text_failure.exists():
        paths.pptx_text_failure.unlink()
    return output


def text_failure(paths: ProjectPaths) -> dict[str, object] | None:
    """Return a current text-failure receipt bound to the active export request."""
    if not paths.pptx_text_failure.is_file() or not paths.pptx_request.is_file():
        return None
    try:
        failure = read_json(paths.pptx_text_failure)
    except (OSError, ValueError):
        return None
    if (
        failure.get("schema") != TEXT_FAILURE_SCHEMA
        or failure.get("request_sha256") != sha256(paths.pptx_request)
    ):
        return None
    return failure


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
