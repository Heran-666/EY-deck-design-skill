from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from test_workflow import (
    ROOT, SERVICE, SVG_RUNTIME, lock_deferred_deck_content,
    next_payload, prepare_candidates, run, svg,
)
from page_svg_service import artifact_errors
from workflow_pptx import _write_flat_projection
from workflow_svg import svg_errors
from svg_to_pptx.drawingml.converter import convert_svg_to_slide_shapes


SVG_NS = "http://www.w3.org/2000/svg"


def resource_svg(body: str) -> str:
    return svg("Resource test").replace(
        "</svg>",
        '<g id="resources" data-pptx-bounds="140 210 280 100">'
        + body + "</g></svg>",
    )


class SVGResourceTests(unittest.TestCase):
    def test_candidate_rejects_resolvable_external_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            icon = project / "icons" / "custom" / "shield.svg"
            icon.parent.mkdir(parents=True)
            icon.write_text(
                f'<svg xmlns="{SVG_NS}" viewBox="0 0 24 24">'
                '<path d="M2 2 L22 2 L12 22 Z"/></svg>'
            )
            Image.new("RGB", (24, 24), "blue").save(project / "photo.png")
            artifact = project / "page.svg"
            for body in (
                '<use data-icon="custom/shield" x="160" y="230" '
                'width="48" height="48" fill="#FFE600"/>',
                '<image href="photo.png" x="240" y="230" width="48" height="48"/>',
            ):
                with self.subTest(body=body):
                    artifact.write_text(resource_svg(body))
                    self.assertTrue(any("resource" in e for e in artifact_errors(artifact)))
                    self.assertTrue(any("resource" in e for e in svg_errors(artifact)))

    def test_export_rejects_external_resources_without_rewriting_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "page.svg"
            source.write_text(resource_svg('<image href="photo.png" x="160" y="230" width="48" height="48"/>'))
            original = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "resource"):
                _write_flat_projection(
                    source, project / "staging" / "page.svg",
                    slide_id="S02", source_kind="confirmed-svg",
                )
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((project / "staging" / "page.svg").exists())

    def test_embedded_svg_cannot_hide_external_or_icon_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "page.svg"
            for nested in (
                '<image href="photo.png" width="24" height="24"/>',
                '<use data-icon="custom/shield" width="24" height="24"/>',
            ):
                payload = f'<svg xmlns="{SVG_NS}" viewBox="0 0 24 24">{nested}</svg>'
                uri = "data:image/svg+xml;base64," + base64.b64encode(payload.encode()).decode()
                artifact.write_text(resource_svg(f'<image href="{uri}" x="160" y="230" width="48" height="48"/>'))
                with self.subTest(nested=nested):
                    self.assertTrue(any("resource" in e for e in svg_errors(artifact)))
            nested = f'<svg xmlns="{SVG_NS}"><defs><path id="p" d="M0 0 L24 24"/></defs><use href="#p"/></svg>'
            uri = "data:image/svg+xml;base64," + base64.b64encode(nested.encode()).decode()
            for body in (f'<rect fill="url({uri})"/>', f'<image src="{uri}"/>'):
                artifact.write_text(resource_svg(body))
                with self.subTest(body=body):
                    self.assertTrue(any("resource" in e for e in svg_errors(artifact)))

    def normalize(self, request: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [SVG_RUNTIME, str(SERVICE), "inline-resources", str(request), *args],
            text=True, capture_output=True, check=False,
        )

    def test_inline_resources_survive_source_deletion_and_editable_export(self) -> None:
        self.assertTrue(os.environ.get("EY_DECK_PPTX_PYTHON"), "Set bundled PPTX runtime for this integration test")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, "S02")
            artifact = project / "svg_working" / "S02" / "A.svg"
            image = artifact.parent / "photo.png"
            Image.new("RGB", (24, 24), "blue").save(image)
            payload = image.read_bytes()
            artifact.write_text(resource_svg(
                '<use data-icon="tabler-outline/shield" x="160" y="230" '
                'width="48" height="48" fill="#FFE600" stroke-width="2"/>'
                '<image href="photo.png" x="240" y="230" width="48" height="48"/>'
            ))
            request = project / "working" / "packets" / "S02" / "A.json"
            normalized = self.normalize(request)
            self.assertEqual(normalized.returncode, 0, normalized.stdout + normalized.stderr)
            root = ET.parse(artifact).getroot()
            self.assertFalse(list(root.iter(f"{{{SVG_NS}}}use")))
            self.assertTrue(list(root.iter(f"{{{SVG_NS}}}path")))
            href = next(root.iter(f"{{{SVG_NS}}}image")).get("href")
            self.assertEqual(base64.b64decode(href.partition(",")[2]), payload)
            self.assertEqual(artifact_errors(artifact), [])
            first = artifact.read_bytes()
            self.assertEqual(self.normalize(request).returncode, 0)
            self.assertEqual(artifact.read_bytes(), first)
            image.unlink()
            for command in (
                ("record-svg", "--page", "S02", "--version", "A"),
                ("present-svg", "--page", "S02", "--versions", "A"),
                ("confirm-svg", "--page", "S02", "--version", "A"),
                ("export-pptx",),
            ):
                result = run(project, *command)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(next_payload(project)["action"], "PPTX_STAGE_COMPLETE")
            with zipfile.ZipFile(project / "sample.pptx") as archive:
                slide = ET.fromstring(archive.read("ppt/slides/slide2.xml"))
                self.assertTrue(list(slide.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}custGeom")))
                self.assertEqual(len(list(slide.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}pic"))), 1)
                self.assertIn(payload, [archive.read(n) for n in archive.namelist() if n.startswith("ppt/media/")])
            audit = json.loads((project / "working" / "receipts" / "pptx" / "text-frames.json").read_text())
            self.assertEqual(audit["status"], "passed")

    def test_local_symbol_reuse_is_expanded_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, "S02")
            artifact = project / "svg_working" / "S02" / "A.svg"
            artifact.write_text(resource_svg(
                '<defs><path id="contour" d="M2 2 L22 2 L12 22 Z" fill="#FFE600"/>'
                '<symbol id="shield" viewBox="0 0 24 24"><use href="#contour"/></symbol></defs>'
                '<use href="#shield" x="160" y="230" width="48" height="48"/>'
            ))
            result = self.normalize(project / "working" / "packets" / "S02" / "A.json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(list(ET.parse(artifact).getroot().iter(f"{{{SVG_NS}}}use")))
            self.assertEqual(svg_errors(artifact), [])

    def test_recorded_version_cannot_be_inlined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, "S02")
            artifact = project / "svg_working" / "S02" / "A.svg"
            artifact.write_text(svg("Recorded version"))
            result = run(project, "record-svg", "--page", "S02", "--version", "A")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            request = project / "working" / "packets" / "S02" / "A.json"
            before = artifact.read_bytes()
            result = self.normalize(request)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("recorded", result.stdout)
            self.assertEqual(artifact.read_bytes(), before)
            for command in (
                ("present-svg", "--page", "S02", "--versions", "A"),
                ("confirm-svg", "--page", "S02", "--version", "A"),
                ("request-svg-revision", "--page", "S02", "--base", "A", "--feedback", "Add a shield icon"),
            ):
                result = run(project, *command)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            canonical = project / "svg_output" / "S02.svg"
            confirmed = canonical.read_bytes()
            revision = artifact.with_name("R1.svg")
            revision.write_text(resource_svg('<use data-icon="tabler-outline/shield" x="160" y="230" width="48" height="48" fill="#FFE600"/>'))
            result = self.normalize(request.with_name("R1.json"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(svg_errors(revision), [])
            self.assertEqual(artifact.read_bytes(), before)
            self.assertEqual(canonical.read_bytes(), confirmed)

    def test_custom_icon_keeps_non_square_geometry_and_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, "S02")
            icon_root = project / "custom-icons"
            icon = icon_root / "custom" / "wide.svg"
            icon.parent.mkdir(parents=True)
            icon.write_text(f'<svg xmlns="{SVG_NS}" viewBox="10 20 48 24"><path d="M10 20 H58 V44 H10 Z"/></svg>')
            artifact = project / "svg_working" / "S02" / "A.svg"
            artifact.write_text(resource_svg('<use data-icon="custom/wide" x="160" y="230" width="48" height="24" fill="#FFE600"/>'))
            result = self.normalize(project / "working" / "packets" / "S02" / "A.json", "--icons-dir", str(icon_root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            icon.unlink()
            slide = ET.fromstring(convert_svg_to_slide_shapes(artifact, resource_root=project)[0])
            namespace = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            transforms = [
                (e.find(namespace + "off"), e.find(namespace + "ext"))
                for e in slide.iter(namespace + "xfrm")
            ]
            self.assertTrue(any(
                off is not None and ext is not None
                and off.get("x") == str(160 * 9525) and off.get("y") == str(230 * 9525)
                and ext.get("cx") == str(48 * 9525) and ext.get("cy") == str(24 * 9525)
                for off, ext in transforms
            ), ET.tostring(slide).decode())

    def test_failed_inline_leaves_candidate_and_request_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, "S02")
            artifact = project / "svg_working" / "S02" / "A.svg"
            request = project / "working" / "packets" / "S02" / "A.json"
            packet = request.read_bytes()
            for href in ("missing.png", "https://example.com/photo.png"):
                artifact.write_text(resource_svg(
                    '<use data-icon="tabler-outline/shield" x="240" y="230" width="48" height="48" fill="#FFE600"/>'
                    f'<image href="{href}" x="160" y="230" width="48" height="48"/>'
                ))
                before = artifact.read_bytes()
                result = self.normalize(request)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(artifact.read_bytes(), before)
                self.assertEqual(request.read_bytes(), packet)


if __name__ == "__main__":
    unittest.main()
