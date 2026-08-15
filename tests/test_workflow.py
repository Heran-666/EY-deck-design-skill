from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ppt-master" / "scripts"))

from visual_review import _launch_browser  # noqa: E402
from validate_deck_blueprint import _emphasis_errors  # noqa: E402
from validate_framework import validate as validate_framework  # noqa: E402
from workflow_ppt_master import TEMPLATE_ROOT, materialize_template, template_name  # noqa: E402
from workflow_svg import initial_versions_for_page_type  # noqa: E402


CONTROLLER = ROOT / "scripts" / "workflow_controller.py"
SERVICE = ROOT / "ppt-master" / "scripts" / "page_svg_service.py"


FRAMEWORK = """# Presentation Framework

## Current position

- Framework version: 3.1
- Workflow version: 6.0
- Storyline version: 1.0
- Output filename: sample.pptx

## Project context

- Deliverable name: Sample
- Audience: Leadership
- Deliverable type: Sharing deck
- Audience outcome: Understand the decision
- Core need: Explain the recommendation
- Storyline thesis: One clear recommendation
- Scope boundaries: Supplied facts only
- Protected content: None

## Confirmed Storyline

### S01｜Sample title

- Chapter: Opening
- Page type: Cover
- Narrative role: Establish the topic
- Content scope: Title and subtitle
- Next connection: None
- Status: Not started
- Confirmed decisions: None
- Open items: None
"""


CONTENT = """# Presentation Build Specification

## Deck build profile（Build-only）
- Language: English

## S01｜Sample title

### On-slide content
- Title: Sample title

#### S01-B1｜Decision
- Detail: Approve the recommendation.

### Sources
- On-slide source: None
- Source details: No external sources
"""


SECOND_PAGE = """
### S02｜Second page

- Chapter: Main
- Page type: Standard content
- Narrative role: Explain the recommendation
- Content scope: Recommendation detail
- Next connection: None
- Status: Not started
- Confirmed decisions: None
- Open items: None
"""


CONTENT_S02 = """# Presentation Build Specification

## Deck build profile（Build-only）
- Language: English

## S02｜A sharper title

### On-slide content
- Title: A sharper title

#### S02-B1｜Recommendation
- Detail: Proceed with the selected path.

### Sources
- On-slide source: None
- Source details: No external sources
"""


def svg(label: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#222"/>
  <text x="80" y="120" fill="#fff">{label}</text>
</svg>
"""


def run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CONTROLLER), *args, "--project-dir", str(project)],
        text=True,
        capture_output=True,
        check=False,
    )


def next_payload(project: Path) -> dict:
    result = run(project, "next", "--format", "json")
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def lock_content(project: Path) -> None:
    (project / "framework.md").write_text(FRAMEWORK, encoding="utf-8")
    provisional = project / "working" / "provisional-content.md"
    provisional.parent.mkdir(parents=True)
    provisional.write_text(CONTENT, encoding="utf-8")
    assert run(project, "present-review").returncode == 0
    approved = run(project, "approve-content")
    assert approved.returncode == 0, approved.stdout + approved.stderr


def prepare_candidates(project: Path, page_id: str = "S01") -> dict:
    prepared = run(project, "prepare-svg-candidates", "--page", page_id)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    return next_payload(project)


def complete_candidate(project: Path, version: str, label: str, page_id: str = "S01") -> None:
    artifact = project / "svg_working" / page_id / f"{version}.svg"
    assert artifact.parent.is_dir(), f"candidate directory was not prepared: {artifact.parent}"
    artifact.write_text(svg(label), encoding="utf-8")
    request = project / "working" / "packets" / page_id / f"{version}.json"
    service = subprocess.run(
        ["python3", str(SERVICE), "complete", str(request)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert service.returncode == 0, service.stdout + service.stderr
    recorded = run(project, "record-svg", "--page", page_id, "--version", version)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr


class WorkflowTests(unittest.TestCase):
    def test_bootstrap_creates_provisional_content_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(FRAMEWORK, encoding="utf-8")
            self.assertFalse((project / "working").exists())

            bootstrapped = run(project, "bootstrap")

            self.assertEqual(bootstrapped.returncode, 0, bootstrapped.stdout + bootstrapped.stderr)
            payload = json.loads(bootstrapped.stdout)
            provisional = Path(payload["provisional_content"]["path"])
            self.assertEqual(provisional, (project / "working" / "provisional-content.md").resolve())
            self.assertTrue(provisional.parent.is_dir())

    def test_framework_enforces_navigation_shell_and_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            pages = []
            for index in range(2, 8):
                next_connection = "Use this claim to open the next content page" if index < 7 else "None"
                pages.append(
                    f"""
### S{index:02d}｜Content {index}

- Chapter: Main
- Page type: Standard content
- Narrative role: Advance the argument
- Content scope: Claim; evidence; implication
- Next connection: {next_connection}
- Status: Not started
- Confirmed decisions: None
- Open items: None
"""
                )
            framework = project / "framework.md"
            framework.write_text(FRAMEWORK + "".join(pages), encoding="utf-8")

            errors = validate_framework(framework, project)

            self.assertIn("At six or more substantive pages, S02 must be Agenda", errors)
            self.assertIn(
                "At six or more substantive pages, at least one Section divider is required",
                errors,
            )

            invalid_connection = FRAMEWORK.replace(
                "- Next connection: None",
                "- Next connection: This structural page should not bridge",
                1,
            )
            framework.write_text(invalid_connection, encoding="utf-8")
            errors = validate_framework(framework, project)
            self.assertIn("S01 Next connection must be None outside adjacent content pages", errors)

    def test_record_svg_requires_service_complete_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(svg("Candidate"), encoding="utf-8")
            packet = project / "working" / "packets" / "S01" / "A.json"
            request = json.loads(packet.read_text(encoding="utf-8"))
            request["caller"] = "untrusted-caller"
            packet.write_text(json.dumps(request), encoding="utf-8")

            recorded = run(project, "record-svg", "--page", "S01", "--version", "A")

            self.assertNotEqual(recorded.returncode, 0)
            self.assertIn("caller must be ey-deck-design", recorded.stdout)
            self.assertFalse((project / "working" / "receipts" / "svg" / "S01" / "A.json").exists())

    def test_single_structural_revision_and_confirmation_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")

            payload = prepare_candidates(project)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A"])
            self.assertTrue((project / "svg_working" / "S01").is_dir())
            expected_roles = {"A": "clarity-led-editorial"}
            for item in payload["requests"]:
                request = json.loads(Path(item["request_path"]).read_text(encoding="utf-8"))
                self.assertEqual(request["schema"], "ppt-master.page-svg-request.v2")
                self.assertEqual(request["mode"], "independent")
                self.assertEqual(request["caller"], "ey-deck-design")
                self.assertIsNone(request["base"])
                self.assertEqual(request["design_quality"]["profile"], "ey-executive-editorial-v2")
                self.assertTrue(
                    any("icon elements" in rule for rule in request["design_quality"]["must_have"])
                )
                self.assertEqual(
                    request["design_quality"]["visible_candidate_gate"],
                    [
                        "information_design",
                        "page_composition",
                        "art_direction_refinement",
                        "full_slide_render_review",
                        "source_repair_and_recheck",
                    ],
                )
                self.assertEqual(request["variant_direction"]["role"], expected_roles[item["version"]])
                validate_python = shlex.split(item["validate_request"])[0]
                complete_python = shlex.split(item["complete"])[0]
                self.assertTrue(Path(validate_python).is_absolute())
                self.assertEqual(validate_python, complete_python)
                prototype = Path(request["template"]["prototype"])
                self.assertTrue(
                    prototype.is_relative_to((project / "working" / "template-prototypes").resolve())
                )
                image_hrefs = [
                    element.attrib.get("href", "")
                    for element in ET.parse(prototype).getroot().iter()
                    if element.tag.rsplit("}", 1)[-1] == "image"
                ]
                self.assertTrue(image_hrefs)
                self.assertTrue(all(href.startswith("data:image/") for href in image_hrefs))
                validated = subprocess.run(
                    ["python3", str(SERVICE), "validate-request", item["request_path"]],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(validated.returncode, 0, validated.stdout)

            invalid_request = project / "working" / "invalid-request.json"
            invalid_payload = json.loads(
                (project / "working" / "packets" / "S01" / "A.json").read_text(encoding="utf-8")
            )
            del invalid_payload["design_quality"]
            invalid_request.write_text(json.dumps(invalid_payload), encoding="utf-8")
            rejected = subprocess.run(
                ["python3", str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("design_quality must be an object", rejected.stdout)

            complete_candidate(project, "A", "Option A")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTION")
            presented = run(project, "present-svg", "--page", "S01", "--versions", "A")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("![S01 A]", presented.stdout)
            self.assertIn("The SVG is displayed at review scale", presented.stdout)
            self.assertEqual(next_payload(project)["action"], "COLLECT_SVG_DECISION")

            feedback = project / "working" / "revision-requests" / "S01.md"
            self.assertTrue(feedback.parent.is_dir())
            feedback.write_text("Increase the contrast of the decision statement.", encoding="utf-8")
            revised = run(
                project, "request-svg-revision", "--page", "S01", "--base", "A",
                "--feedback-file", str(feedback),
            )
            self.assertEqual(revised.returncode, 0, revised.stdout + revised.stderr)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual(payload["requests"][0]["version"], "R1")
            request = json.loads((project / "working" / "packets" / "S01" / "R1.json").read_text())
            self.assertEqual(request["base"]["version"], "A")
            self.assertIn("Increase the contrast", request["feedback"])
            self.assertEqual(request["design_quality"]["profile"], "ey-executive-editorial-v2")
            self.assertEqual(request["variant_direction"]["role"], "revision")
            self.assertEqual(request["variant_direction"]["base_version"], "A")

            complete_candidate(project, "R1", "Revised option")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_REVISION")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A,R1").returncode, 0)
            confirmed = run(project, "confirm-svg", "--page", "S01", "--version", "R1")
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            self.assertEqual(next_payload(project)["action"], "SVG_STAGE_COMPLETE")
            self.assertEqual((project / "svg_output" / "S01.svg").read_text(), svg("Revised option"))

            reopened = run(project, "reopen-svg", "--page", "S01")
            self.assertEqual(reopened.returncode, 0, reopened.stdout + reopened.stderr)
            self.assertFalse((project / "svg_working" / "S01").exists())
            self.assertFalse((project / "working" / "packets" / "S01").exists())
            self.assertFalse((project / "working" / "template-prototypes" / "S01").exists())
            self.assertFalse((project / "working" / "receipts" / "svg" / "S01").exists())
            self.assertFalse((project / "svg_output" / "S01.svg").exists())
            self.assertFalse((project / "working" / "history").exists())
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")
            payload = prepare_candidates(project)
            self.assertEqual([item["version"] for item in payload["requests"]], ["A"])

    def test_all_structural_templates_materialize_as_self_contained_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for name in ("cover.svg", "agenda.svg", "divider.svg", "ending.svg"):
                target = materialize_template(
                    TEMPLATE_ROOT / "templates" / name,
                    output / name,
                )
                hrefs = [
                    element.attrib.get("href", "")
                    for element in ET.parse(target).getroot().iter()
                    if element.tag.rsplit("}", 1)[-1] == "image"
                ]
                self.assertTrue(hrefs, name)
                self.assertTrue(all(href.startswith("data:image/") for href in hrefs), name)

    def test_emphasis_accepts_same_block_visible_text_and_rejects_build_only_text(self) -> None:
        valid = """#### S01-B1｜调整或升级
- Emphasis:
  - “调整或升级”｜关键重点

#### S01-B2｜路径比较
- Table purpose（Build-only）: Support a comparison

| 方案 | 建议 |
|---|---|
| A | 升级路径 |

- Emphasis:
  - “升级路径”｜次级重点
"""
        self.assertEqual(_emphasis_errors(valid), [])

        invalid = """#### S01-B1｜公开标题
- Child logic（Build-only）: 隐藏逻辑
- Emphasis:
  - “隐藏逻辑”｜闪烁
"""
        errors = _emphasis_errors(invalid)
        self.assertTrue(any("visible text in the same block" in error for error in errors))
        self.assertTrue(any("unsupported Emphasis style" in error for error in errors))

        malformed = """#### S01-B1｜公开标题
- Detail: 公开内容
- Emphasis:
  - \"公开内容\" | 关键重点
"""
        errors = _emphasis_errors(malformed)
        self.assertTrue(any("malformed Emphasis annotation" in error for error in errors))

        empty = """#### S01-B1｜公开标题
- Detail: 公开内容
- Emphasis:
"""
        errors = _emphasis_errors(empty)
        self.assertTrue(any("must contain at least one annotation" in error for error in errors))

    def test_visual_review_falls_back_to_installed_chrome(self) -> None:
        sentinel = object()

        class Chromium:
            def __init__(self) -> None:
                self.calls: list[dict[str, str]] = []

            def launch(self, **kwargs):
                self.calls.append(kwargs)
                if not kwargs:
                    raise RuntimeError("managed Chromium is absent")
                return sentinel

        chromium = Chromium()
        playwright = type("Playwright", (), {"chromium": chromium})()
        self.assertIs(_launch_browser(playwright), sentinel)
        self.assertEqual(chromium.calls, [{}, {"channel": "chrome"}])

    def test_stale_candidate_and_confirmation_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "A")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)
            (project / "svg_output" / "S01.svg").write_text(svg("tampered"), encoding="utf-8")
            payload = next_payload(project)
            self.assertEqual(payload["action"], "REPAIR_STALE_SVG_CONFIRMATION")

    def test_service_rejects_remote_svg_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><image href="https://example.com/x.png"/></svg>',
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(SERVICE), "complete", str(project / "working" / "packets" / "S01" / "A.json")],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("remote URL", result.stdout)

    def test_later_page_content_does_not_stale_a_confirmed_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(FRAMEWORK.rstrip() + "\n\n" + SECOND_PAGE.lstrip(), encoding="utf-8")
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True)
            provisional.write_text(CONTENT, encoding="utf-8")
            self.assertEqual(run(project, "present-review").returncode, 0)
            self.assertEqual(run(project, "approve-content").returncode, 0)
            prepare_candidates(project)
            complete_candidate(project, "A", "A")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)

            provisional.write_text(CONTENT_S02, encoding="utf-8")
            self.assertEqual(run(project, "present-review").returncode, 0)
            self.assertEqual(run(project, "approve-content").returncode, 0)
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")
            self.assertEqual(next_payload(project)["slide_id"], "S02")
            payload = prepare_candidates(project, "S02")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A", "B"])
            expected_roles = {"A": "clarity-led-editorial", "B": "concept-led-spatial"}
            for item in payload["requests"]:
                request = json.loads(Path(item["request_path"]).read_text(encoding="utf-8"))
                self.assertEqual(request["variant_direction"]["role"], expected_roles[item["version"]])
            complete_candidate(project, "A", "Content A", page_id="S02")
            complete_candidate(project, "B", "Content B", page_id="S02")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTIONS")
            presented = run(project, "present-svg", "--page", "S02", "--versions", "A,B")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("Both SVGs are displayed at the same scale", presented.stdout)

    def test_structural_page_types_use_one_initial_candidate(self) -> None:
        for page_type in ("Cover", "Agenda", "Section divider", "Ending"):
            with self.subTest(page_type=page_type):
                self.assertEqual(initial_versions_for_page_type(page_type), ("A",))
        self.assertEqual(initial_versions_for_page_type("Standard content"), ("A", "B"))
        self.assertEqual(template_name("Ending"), "ending.svg")

    def test_full_design_service_contract_is_registered(self) -> None:
        contract = (ROOT / "ppt-master" / "workflows" / "page-svg-service.md").read_text(encoding="utf-8")
        for capability in ("Strategist", "chart", "table", "imagery", "semantic SVG", "Review and repair"):
            self.assertIn(capability, contract)
        internal = (ROOT / "ppt-master" / "INTERNAL.md").read_text(encoding="utf-8")
        self.assertIn("ppt-master.page-svg-request.v2", internal)
        self.assertFalse((ROOT / "ppt-master" / "SKILL.md").exists())
        self.assertFalse((ROOT / "ppt-master" / "agents" / "openai.yaml").exists())

    def test_storyline_richness_contract_is_registered(self) -> None:
        routing = (ROOT / "references" / "deliverable-types.md").read_text(encoding="utf-8")
        storyline = (ROOT / "references" / "storyline-and-content.md").read_text(encoding="utf-8")
        framework = (ROOT / "references" / "framework-contract.md").read_text(encoding="utf-8")

        self.assertIn("normally three to\nfive bullets", routing)
        self.assertIn("normally three to five planned content blocks", storyline)
        self.assertIn("preserve the three to five\ndistinct planned units", framework)
        self.assertIn("Keep structural pages role-appropriate and concise", framework)


if __name__ == "__main__":
    unittest.main()
