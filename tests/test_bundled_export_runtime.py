from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RUNTIME = SCRIPTS / "pptx_export_runtime"
sys.path.insert(0, str(SCRIPTS))

from svg_boundary import candidate_errors, protected_candidate_errors  # noqa: E402
from workflow_export import prepare_export_workspace  # noqa: E402
from workflow_runtime import bind_stage2_runtime  # noqa: E402


CSS_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<style>
  .title { fill: #FFFFFF; font-family: Arial; font-size: 32px; }
  g .body { fill: #D9D9D9; font-size: 13.3333px; }
  #foot { fill: #A6A6A6; font-size: 8px; }
</style>
<rect width="1280" height="720" fill="#000000"/>
<g><text class="title" x="80" y="80">Title</text>
<text class="body" x="80" y="140">Body one</text>
<text class="body" x="80" y="180">Body two</text>
<text class="body" x="80" y="220">Body three</text></g>
<text id="foot" x="80" y="680">Foot</text>
</svg>'''


TOPOLOGY_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<rect width="1280" height="720" fill="#000000"/>
<text data-copy-id="S01-detail" x="100" fill="#FFFFFF" font-family="Arial" font-size="16">
  <tspan x="100" y="120"><tspan>Exact </tspan><tspan font-weight="700">first line</tspan></tspan>
  <tspan x="100" y="144">Exact second line</tspan>
</text>
</svg>'''


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BundledExportRuntimeTests(unittest.TestCase):
    def test_authored_css_boundary_is_strict_but_protected_input_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S01.svg"
            path.write_text(CSS_SVG, encoding="utf-8")
            self.assertTrue(any("inline CSS" in item for item in candidate_errors(path)))
            self.assertEqual(protected_candidate_errors(path), [])

    def test_preparer_inlines_css_before_deriving_confirmed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S01.svg"
            source.write_text(CSS_SVG, encoding="utf-8")
            source_bytes = source.read_bytes()
            project = root / "export"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "prepare_confirmed_svg_export.py"),
                    "--project-dir",
                    str(project),
                    str(source),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            normalized = (project / "svg_output" / "P01.svg").read_text(encoding="utf-8")
            self.assertNotIn("<style", normalized)
            self.assertNotIn("class=", normalized)
            self.assertIn("font-size:32px", normalized)
            self.assertEqual((project / "source_original" / "P01.svg").read_bytes(), source_bytes)
            manifest = json.loads(
                (project / "confirmed-svg-export.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["schema"], "ey-deck.confirmed-svg-export-runtime.v1"
            )
            self.assertEqual(
                manifest["typography_policy"]["observed_pptx_pt_counts"],
                {"24": 1, "10": 3, "6": 1},
            )
            page = manifest["page_order"][0]
            self.assertEqual(
                page["typography"]["observed_pptx_pt_counts"],
                {"24": 1, "10": 3, "6": 1},
            )
            self.assertNotEqual(page["source_sha256"], page["normalized_sha256"])
            self.assertTrue(page["normalization"]["changed"])

    def test_preparer_blocks_css_it_cannot_prove_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S01.svg"
            source.write_text(
                CSS_SVG.replace(".title {", ".title:hover {"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "prepare_confirmed_svg_export.py"),
                    "--project-dir",
                    str(root / "export"),
                    str(source),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported CSS selector", result.stdout)

    def test_stage_two_repairs_topology_on_isolated_copy_and_rechecks_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S01.svg"
            source.write_text(TOPOLOGY_SVG, encoding="utf-8")
            source_bytes = source.read_bytes()
            project = root / "export"
            prepared = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "prepare_confirmed_svg_export.py"),
                    "--project-dir",
                    str(project),
                    str(source),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            normalized = project / "svg_output" / "P01.svg"
            before_topology_hash = file_sha256(normalized)
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "normalize_text_frame_topology.py"),
                    "--project-dir",
                    str(project),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(
                (project / "source_original" / "P01.svg").read_bytes(),
                source_bytes,
            )
            receipt = json.loads(
                (project / "validation" / "text_frame_topology.json").read_text(
                    encoding="utf-8"
                )
            )
            page = receipt["pages"][0]
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(page["detected_before"][0]["copy_id"], "S01-detail")
            self.assertEqual(page["detected_before"][0]["predicted_text_boxes"], 2)
            self.assertEqual(page["parent_baseline_repairs"][0]["parent_y"], "120")
            self.assertEqual(page["paragraph_blocks_normalized"], 1)
            self.assertEqual(page["exact_copy"]["status"], "PASS")
            self.assertEqual(page["detected_after"], [])
            self.assertNotEqual(before_topology_hash, file_sha256(normalized))
            manifest = json.loads(
                (project / "confirmed-svg-export.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["page_order"][0]["normalized_sha256"],
                file_sha256(normalized),
            )

    def test_stage_two_leaves_unrepairable_topology_visible_to_recheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S01.svg"
            source.write_text(
                TOPOLOGY_SVG.replace(
                    '<tspan x="100" y="144">Exact second line</tspan>',
                    '<tspan x="160" y="144">Exact second line</tspan>',
                ),
                encoding="utf-8",
            )
            source_bytes = source.read_bytes()
            project = root / "export"
            prepared = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "prepare_confirmed_svg_export.py"),
                    "--project-dir",
                    str(project),
                    str(source),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "normalize_text_frame_topology.py"),
                    "--project-dir",
                    str(project),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(source.read_bytes(), source_bytes)
            receipt = json.loads(
                (project / "validation" / "text_frame_topology.json").read_text(
                    encoding="utf-8"
                )
            )
            page = receipt["pages"][0]
            self.assertEqual(receipt["blocked_slide_ids"], ["S01"])
            self.assertEqual(page["exact_copy"]["status"], "PASS")
            self.assertEqual(page["detected_after"][0]["copy_id"], "S01-detail")
            self.assertEqual(page["detected_after"][0]["predicted_text_boxes"], 2)

    @unittest.skipUnless(
        os.environ.get("EY_BUNDLED_PYTHON"),
        "set EY_BUNDLED_PYTHON to run the native PPTX export integration test",
    )
    def test_hash_bound_runner_exports_two_confirmed_pages(self) -> None:
        bundled_python = Path(os.environ["EY_BUNDLED_PYTHON"]).resolve()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ey-project"
            output = project / "svg_output"
            output.mkdir(parents=True)
            template_dir = ROOT / "assets" / "templates" / "ey-gradient-dark-v1"
            (output / "S01.svg").write_bytes((template_dir / "cover.svg").read_bytes())
            (output / "S02.svg").write_bytes((template_dir / "content.svg").read_bytes())
            (project / "framework.md").write_text(
                """# Presentation Framework

## Current position
- Framework version: 2.6
- Workflow version: 3.8
- Storyline version: 1.0
- Output filename: EY-confirmed-export.pptx

## Project context
- Deliverable name: Runtime integration
- Audience: Test
- Deliverable type: Sharing deck
- Requested authoring mode: Standard
- Audience outcome: Test export
- Core need: Test export
- Storyline thesis: Test export
- Scope boundaries: None
- Protected content: None

## Design hard rules
- Canvas: ppt169, SVG 1280 × 720
- Project-specific rules: None

## Confirmed Storyline

### S01｜Cover
- Chapter: Opening
- Page type: Cover
- Narrative role: Open
- Content scope: Title
- Next connection: S02
- Review mode: Page-by-page
- Authoring mode: Simplified
- Status: SVG confirmed
- Confirmed decisions: None
- Open items: None
- Confirmed version: A

### S02｜Content
- Chapter: Main
- Page type: Standard content
- Narrative role: Explain
- Content scope: Content
- Next connection: None
- Review mode: Page-by-page
- Authoring mode: Standard
- Status: SVG confirmed
- Confirmed decisions: None
- Open items: None
- Confirmed version: A
""",
                encoding="utf-8",
            )
            bind_stage2_runtime(project, bundled_python, "integration-test")
            prepared = prepare_export_workspace(
                project,
                ["S01", "S02"],
                "EY-confirmed-export.pptx",
            )
            result = subprocess.run(
                prepared["runner_command"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            terminal = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(terminal["status"], "COMPLETE")
            artifact = Path(terminal["artifact_path"])
            self.assertTrue(artifact.is_file())
            self.assertGreater(artifact.stat().st_size, 0)
            with zipfile.ZipFile(artifact) as package:
                names = package.namelist()
                self.assertEqual(
                    len([name for name in names if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml")]),
                    2,
                )
                self.assertEqual(
                    len([name for name in names if name.startswith("ppt/slideLayouts/slideLayout") and name.endswith(".xml")]),
                    5,
                )
                self.assertEqual(
                    len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]),
                    3,
                )


if __name__ == "__main__":
    unittest.main()
