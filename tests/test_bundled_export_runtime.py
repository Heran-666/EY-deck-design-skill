from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RUNTIME = SCRIPTS / "pptx_export_runtime"
sys.path.insert(0, str(SCRIPTS))

from svg_boundary import candidate_errors, protected_candidate_errors  # noqa: E402
from workflow_copy_contract import visible_copy_contract, visible_copy_errors  # noqa: E402
from workflow_export import prepare_export_workspace  # noqa: E402
from workflow_runtime import bind_stage2_runtime  # noqa: E402
from workflow_templates import page_template_binding, template_candidate_errors  # noqa: E402


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

    def test_flat_preparer_strips_structure_metadata_only_from_isolated_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "S01.svg"
            source.write_text(
                '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"
viewBox="0 0 1280 720" data-pptx-master="ey-cover"
data-pptx-master-name="EY Cover" data-pptx-layout="cover"
data-pptx-layout-name="EY Cover" data-pptx-show-master-shapes="true"
data-pptx-show-inherited-shapes="true">
<rect id="fixed" data-pptx-layer="master" data-pptx-editable="false"
x="0" y="0" width="1280" height="720" fill="#000000"/>
<g id="title" data-pptx-placeholder="title" data-pptx-idx="1"
data-pptx-bounds="80 80 800 80"><text data-pptx-carrier="true" x="80" y="140"
fill="#FFFFFF" font-family="Arial" font-size="32">Exact title</text></g>
</svg>''',
                encoding="utf-8",
            )
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
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(
                (project / "source_original" / "P01.svg").read_bytes(), source_bytes
            )
            normalized = project / "svg_output" / "P01.svg"
            parsed = ET.parse(normalized).getroot()
            forbidden = {
                "data-pptx-master",
                "data-pptx-master-name",
                "data-pptx-layout",
                "data-pptx-layout-name",
                "data-pptx-show-master-shapes",
                "data-pptx-show-inherited-shapes",
                "data-pptx-layer",
                "data-pptx-placeholder",
                "data-pptx-idx",
                "data-pptx-carrier",
            }
            self.assertFalse(any(
                attribute in element.attrib
                for element in parsed.iter()
                for attribute in forbidden
            ))
            self.assertEqual("".join(parsed.itertext()).strip(), "Exact title")
            manifest = json.loads(
                (project / "confirmed-svg-export.json").read_text(encoding="utf-8")
            )
            page = manifest["page_order"][0]
            self.assertEqual(page["normalization"]["flat_structure_metadata_removed"], 10)
            self.assertEqual(page["normalized_sha256"], file_sha256(normalized))
            self.assertNotEqual(page["source_sha256"], page["normalized_sha256"])

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

    def test_fixed_ending_allows_only_flat_structure_metadata_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "ending.svg"
            source.write_text(
                '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"
viewBox="0 0 1280 720" data-ey-fixed-ending="true"
data-pptx-master="ey-ending" data-pptx-layout="ending">
<image id="ending-source-slide" data-pptx-layer="layout"
data-pptx-editable="false" x="0" y="0" width="1280" height="720"
href="data:image/png;base64,AAAA"/>
</svg>''',
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
            normalized = project / "svg_output" / "P01.svg"
            self.assertNotEqual(source.read_bytes(), normalized.read_bytes())
            checked = subprocess.run(
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
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(source.read_bytes(), source_bytes)
            receipt = json.loads(
                (project / "validation" / "text_frame_topology.json").read_text(
                    encoding="utf-8"
                )
            )
            exact = receipt["pages"][0]["exact_copy"]
            self.assertEqual(exact["status"], "PASS")
            self.assertFalse(exact["byte_identity"])
            self.assertEqual(exact["equivalence_mode"], "flat-structure-metadata-only")
            self.assertEqual(exact["flat_structure_metadata_removed"], 3)

            normalized.write_text(
                normalized.read_text(encoding="utf-8").replace(
                    'width="1280"', 'width="1279"', 1
                ),
                encoding="utf-8",
            )
            blocked = subprocess.run(
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
            self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
            blocked_receipt = json.loads(
                (project / "validation" / "text_frame_topology.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(blocked_receipt["pages"][0]["exact_copy"]["status"], "FAIL")

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
- Framework version: 2.7
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
                ending_root = ET.parse(template_dir / "ending.svg").getroot()
                ending_image = next(
                    element
                    for element in ending_root.iter()
                    if element.tag.rsplit("}", 1)[-1] == "image"
                )
                ending_href = ending_image.get("href") or ending_image.get(
                    "{http://www.w3.org/1999/xlink}href"
                )
                self.assertIsNotNone(ending_href)
                ending_bytes = base64.b64decode(str(ending_href).split(",", 1)[1])
                packaged_media = [
                    package.read(name)
                    for name in names
                    if name.startswith("ppt/media/")
                ]
                self.assertIn(ending_bytes, packaged_media)

    @unittest.skipUnless(
        os.environ.get("EY_BUNDLED_PYTHON"),
        "set EY_BUNDLED_PYTHON to run the native Agenda export integration test",
    )
    def test_real_agenda_numbers_export_as_separate_editable_textboxes(self) -> None:
        bundled_python = Path(os.environ["EY_BUNDLED_PYTHON"]).resolve()
        labels = [
            "战略背景与目标",
            "行业趋势与关键挑战",
            "核心方法与工作路径",
            "重点任务与交付成果",
            "项目计划与里程碑",
            "治理机制与质量保障",
            "团队经验与下一步行动",
        ]
        blocks = "\n\n".join(
            f"#### S02-B{index}｜{label}" for index, label in enumerate(labels, 1)
        )
        section = f"""## S02｜目录

### On-slide content
- Title: 目录

{blocks}

### Visual Direction（Build-only）
- Page type: Agenda
- Visual priority: 标题后依次阅读七个章节名称
- Semantic relationship: 七个章节按汇报顺序并列展开
- Guardrails: 保留批准的名称与顺序；不得加入说明或摘要

### Sources
- On-slide source: None
- Source details: No external sources
"""
        contract = visible_copy_contract(section, "S02")

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "agenda-project"
            output = project / "svg_output"
            output.mkdir(parents=True)
            template_dir = ROOT / "assets" / "templates" / "ey-gradient-dark-v1"
            (output / "S01.svg").write_bytes((template_dir / "cover.svg").read_bytes())

            tree = ET.parse(template_dir / "agenda.svg")
            root = tree.getroot()
            title_group = next(element for element in root.iter() if element.get("id") == "agenda-title")
            title_text = next(element for element in title_group.iter() if element.tag.rsplit("}", 1)[-1] == "text")
            title_text.set("data-copy-id", "S02-title")
            title_text.text = "目录"
            region = next(element for element in root.iter() if element.get("id") == "agenda-content-region")
            cards = [element for element in region if element.tag.rsplit("}", 1)[-1] == "g"]
            self.assertEqual(len(cards), 7)
            for index, (card, label) in enumerate(zip(cards, labels), 1):
                texts = [element for element in card if element.tag.rsplit("}", 1)[-1] == "text"]
                self.assertEqual(len(texts), 2)
                texts[0].set("data-copy-id", f"S02-B{index}-number")
                texts[0].text = f"{index:02d}"
                texts[1].set("data-copy-id", f"S02-B{index}-heading")
                texts[1].text = label
            agenda_path = output / "S02.svg"
            tree.write(agenda_path, encoding="utf-8", xml_declaration=True)

            agenda_binding = page_template_binding("Agenda")
            self.assertIsNotNone(agenda_binding)
            self.assertEqual([], visible_copy_errors(agenda_path, contract))
            self.assertEqual([], template_candidate_errors(agenda_path, agenda_binding))

            (project / "framework.md").write_text(
                """# Presentation Framework

## Current position
- Framework version: 2.7
- Workflow version: 3.9
- Storyline version: 1.0
- Output filename: Agenda-contract-integration.pptx

## Project context
- Deliverable name: Agenda contract integration
- Audience: Leadership
- Deliverable type: Sharing deck
- Requested authoring mode: Standard
- Audience outcome: Navigate the presentation
- Core need: Verify Agenda export
- Storyline thesis: The agenda establishes the journey
- Scope boundaries: None
- Protected content: None

## Design hard rules
- Canvas: ppt169, SVG 1280 × 720
- Project-specific rules: None

## Confirmed Storyline

### S01｜封面
- Chapter: Opening
- Page type: Cover
- Narrative role: Open
- Content scope: Title
- Next connection: S02
- Authoring mode: Simplified
- Status: SVG confirmed
- Confirmed decisions: None
- Open items: None
- Confirmed version: A

### S02｜目录
- Chapter: Opening
- Page type: Agenda
- Narrative role: Establish navigation
- Content scope: Seven chapter labels
- Next connection: None
- Authoring mode: Simplified
- Status: SVG confirmed
- Confirmed decisions: None
- Open items: None
- Confirmed version: A
""",
                encoding="utf-8",
            )
            bind_stage2_runtime(project, bundled_python, "agenda-contract-integration")
            prepared = prepare_export_workspace(
                project,
                ["S01", "S02"],
                "Agenda-contract-integration.pptx",
            )
            result = subprocess.run(
                prepared["runner_command"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            terminal = json.loads(result.stdout.strip().splitlines()[-1])
            artifact = Path(terminal["artifact_path"])
            with zipfile.ZipFile(artifact) as package:
                slide = ET.fromstring(package.read("ppt/slides/slide2.xml"))
            namespaces = {
                "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            }
            shape_texts = [
                "".join(node.text or "" for node in shape.findall(".//a:t", namespaces))
                for shape in slide.findall(".//p:sp", namespaces)
            ]
            for index, label in enumerate(labels, 1):
                self.assertIn(f"{index:02d}", shape_texts)
                self.assertIn(label, shape_texts)
                self.assertNotIn(f"{index:02d} {label}", shape_texts)


if __name__ == "__main__":
    unittest.main()
