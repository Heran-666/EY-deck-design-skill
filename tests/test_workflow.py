from __future__ import annotations

import io
import json
import os
import posixpath
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageStat


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ppt-master" / "scripts"))

from visual_review import _launch_browser  # noqa: E402
from page_svg_service import artifact_errors  # noqa: E402
from svg_to_pptx.drawingml.elements import (  # noqa: E402
    ImageValidationDependencyError,
    _valid_project_image_payload,
)
from svg_finalize.flatten_tspan import (  # noqa: E402
    flatten_text_with_tspans,
    text_carrier_integrity_errors,
)
from validate_deck_blueprint import _emphasis_errors, validate_page_logic  # noqa: E402
from validate_framework import validate as validate_framework  # noqa: E402
from framework_lib import page_entries  # noqa: E402
from workflow_content import provisional_content_errors  # noqa: E402
from workflow_io import sha256 as request_sha256  # noqa: E402
from workflow_ppt_master import (  # noqa: E402
    DESIGN_QUALITY_PROFILE,
    TEMPLATE_ROOT,
    materialize_template,
    template_name,
)
from workflow_paths import ProjectPaths  # noqa: E402
from workflow_pptx import (  # noqa: E402
    TEXT_FAILURE_SCHEMA,
    request_valid as pptx_request_valid,
    write_request as write_pptx_request,
)
from workflow_svg import initial_versions_for_page_type, record_candidate  # noqa: E402


CONTROLLER = ROOT / "scripts" / "workflow_controller.py"
SERVICE = ROOT / "ppt-master" / "scripts" / "page_svg_service.py"
SVG_RUNTIME = os.environ.get("EY_DECK_SVG_PYTHON", sys.executable)


FRAMEWORK_WITHOUT_ENDING = """# Presentation Framework

## Current position

- Framework version: 3.2
- Workflow version: 8.1
- Storyline version: 1.0
- Output filename: sample.pptx

## Project context

- Deliverable name: Sample
- Audience: Leadership
- Deliverable type: Sharing deck
- Audience outcome: Understand the decision
- Core need: Explain the recommendation
- Storyline thesis: One clear recommendation
- Reading mode: balanced
- Scope boundaries: Supplied facts only
- Protected content: None

## Confirmed Storyline

### S01｜Sample title

- Chapter: Opening
- Page type: Cover
- Narrative role: Establish the topic
- Page rhythm: anchor
- Content scope: Title and subtitle
- Next connection: None
- Status: Not started
- Confirmed decisions: None
- Open items: None
"""


CONTENT = """# Presentation Build Specification

## Deck build profile（Build-only）
- Language: English

## S01

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
- Page rhythm: dense
- Content scope: Recommendation detail
- Next connection: None
- Status: Not started
- Confirmed decisions: None
- Open items: None
"""


def ending_page(slide_id: str) -> str:
    return f"""
### {slide_id}｜Closing

- Chapter: Closing
- Page type: Ending
- Narrative role: Close the presentation
- Page rhythm: anchor
- Content scope: Use the approved fixed closing page unchanged
- Next connection: None
- Status: Deferred template
- Confirmed decisions: None
- Open items: None
"""


FRAMEWORK = FRAMEWORK_WITHOUT_ENDING.rstrip() + "\n\n" + ending_page("S02").lstrip()


def framework_with_second_page(second_page: str = SECOND_PAGE) -> str:
    return (
        FRAMEWORK_WITHOUT_ENDING.rstrip()
        + "\n\n"
        + second_page.lstrip()
        + "\n"
        + ending_page("S03").lstrip()
    )


DEFERRED_FRAMEWORK = framework_with_second_page().replace(
    "- Status: Not started",
    "- Status: Deferred template",
    1,
).replace("### S02｜Second page", "### S02｜Content page")


CONTENT_S02 = """# Presentation Build Specification

## Deck build profile（Build-only）
- Language: English

## S02

### Page logic（Build-only）
- Page objective: Explain the recommendation
- Audience move: From uncertainty to readiness to proceed
- Reasoning pattern: Recommendation and implication
- Argument chain: S02-B1 states the recommended action
- Relationship constraints: None
- Argument priority: Establish the action first

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


def multiline_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#222"/>
  <text x="80" y="120" fill="#fff" font-size="24">
    <tspan x="80" dy="0">同一段</tspan><tspan font-weight="700">文字应该</tspan>
    <tspan x="80" dy="36">连续呈现</tspan>
  </text>
</svg>
"""


def fragmented_paragraph_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#222"/>
  <g id="body" data-pptx-bounds="60 80 800 240">
    <text x="80" y="120" fill="#fff" font-size="24">This sentence continues across</text>
    <text x="80" y="156" fill="#fff" font-size="24">two sibling SVG text elements</text>
  </g>
</svg>
"""


def inline_dx_spacing_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="80" y="120"><tspan>Agent uses</tspan><tspan dx="4">deterministic controls</tspan></text>
</svg>
"""


def safe_absolute_y_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="80" y="120" font-size="24">
    <tspan x="80" y="120">Editable first line</tspan>
    <tspan x="80" y="156">Editable second line</tspan>
  </text>
</svg>
"""


def nonmergeable_relative_dy_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="80" y="120" font-size="10">
    <tspan x="80" dy="0">First row</tspan>
    <tspan x="80" dy="100">Distant independent row</tspan>
  </text>
</svg>
"""


def run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["EY_DECK_SVG_PYTHON"] = SVG_RUNTIME
    return subprocess.run(
        [sys.executable, str(CONTROLLER), *args, "--project-dir", str(project)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
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
    assert "- Status: Not started" in (project / "framework.md").read_text(encoding="utf-8")
    assert "Content reviewing" not in (project / "framework.md").read_text(encoding="utf-8")
    approved = run(project, "approve-content")
    assert approved.returncode == 0, approved.stdout + approved.stderr


def lock_deferred_deck_content(project: Path) -> None:
    (project / "framework.md").write_text(DEFERRED_FRAMEWORK, encoding="utf-8")
    provisional = project / "working" / "provisional-content.md"
    provisional.parent.mkdir(parents=True)
    provisional.write_text(CONTENT_S02, encoding="utf-8")
    presented = run(project, "present-review")
    assert presented.returncode == 0, presented.stdout + presented.stderr
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
    recorded = run(project, "record-svg", "--page", page_id, "--version", version)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr


def prepare_export_request(project: Path) -> Path:
    text = (project / "framework.md").read_text(encoding="utf-8")
    return write_pptx_request(ProjectPaths(project), text)


class WorkflowTests(unittest.TestCase):
    def test_content_review_emits_complete_page_and_directive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(FRAMEWORK, encoding="utf-8")
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True)
            provisional.write_text(CONTENT, encoding="utf-8")

            presented = run(project, "present-review")

            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            begin = "===== BEGIN COMPLETE CONTENT REVIEW S01 ====="
            end = "===== END COMPLETE CONTENT REVIEW S01 ====="
            review = presented.stdout.split(begin, 1)[1].split(end, 1)[0].strip()
            self.assertEqual(review, CONTENT.strip())
            self.assertIn("omit any section or block", presented.stdout)
            self.assertIn("approve-content", presented.stdout)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "COLLECT_CONTENT_DECISION")
            self.assertEqual(payload["review_contract"]["display_mode"], "full-chinese-review")
            self.assertEqual(payload["review_contract"]["display_language"], "Chinese")
            self.assertIn("Do not summarize", payload["review_contract"]["instruction"])

    def test_chinese_review_preserves_requested_deck_language_and_source_content(self) -> None:
        for language in ("English", "Chinese"):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                content = CONTENT.replace("Language: English", f"Language: {language}")
                (project / "framework.md").write_text(FRAMEWORK, encoding="utf-8")
                provisional = project / "working" / "provisional-content.md"
                provisional.parent.mkdir(parents=True)
                provisional.write_text(content, encoding="utf-8")

                presented = run(project, "present-review")
                self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
                contract = next_payload(project)["review_contract"]
                self.assertEqual(contract["display_language"], "Chinese")
                self.assertIn(contract["instruction"], presented.stdout)
                self.assertIn("Translate", contract["instruction"])
                self.assertEqual(provisional.read_text(encoding="utf-8"), content)

                approved = run(project, "approve-content")
                self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
                self.assertEqual((project / "content.md").read_text(encoding="utf-8"), content)

    def test_missing_pillow_is_dependency_failure_not_invalid_raster(self) -> None:
        original_import = __import__

        def blocked_pillow(name, *args, **kwargs):
            if name == "PIL" or name.startswith("PIL."):
                raise ImportError("simulated missing Pillow")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=blocked_pillow):
            with self.assertRaisesRegex(
                ImageValidationDependencyError,
                "not classified as invalid",
            ):
                _valid_project_image_payload("png", b"validity is intentionally unknown")

    def test_phase_one_workflow_migrates_without_changing_page_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            legacy = framework_with_second_page().replace(
                "- Framework version: 3.2", "- Framework version: 3.1"
            )
            legacy = legacy.replace("- Workflow version: 8.1", "- Workflow version: 8.0")
            legacy = legacy.replace("- Reading mode: balanced\n", "")
            legacy = legacy.replace("- Page rhythm: anchor\n", "")
            legacy = legacy.replace("- Page rhythm: dense\n", "")
            (project / "framework.md").write_text(legacy, encoding="utf-8")

            upgraded = run(project, "upgrade-workflow")

            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            text = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Framework version: 3.2", text)
            self.assertIn("- Workflow version: 8.1", text)
            self.assertIn("- Reading mode: balanced", text)
            self.assertIn("- Page rhythm: anchor", text)
            self.assertIn("- Page rhythm: dense", text)
            self.assertIn("- Status: Not started", text)
            self.assertIn('"action": "AUTHOR_PAGE_CONTENT"', upgraded.stdout)

    def test_phase_one_migration_does_not_mutate_an_invalid_framework(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            legacy = FRAMEWORK.replace("- Framework version: 3.2", "- Framework version: 3.1")
            legacy = legacy.replace("- Workflow version: 8.1", "- Workflow version: 6.0")
            legacy = legacy.replace("- Reading mode: balanced\n", "")
            legacy = legacy.replace("- Page rhythm: anchor\n", "")
            legacy = legacy.replace("- Output filename: sample.pptx", "- Output filename: invalid.txt")
            framework = project / "framework.md"
            framework.write_text(legacy, encoding="utf-8")

            upgraded = run(project, "upgrade-workflow")

            self.assertNotEqual(upgraded.returncode, 0)
            self.assertIn("Output filename", upgraded.stdout)
            self.assertIn("- Workflow version: 6.0", framework.read_text(encoding="utf-8"))

    def test_workflow_seven_is_readable_for_non_mutating_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            legacy = FRAMEWORK.replace("- Workflow version: 8.1", "- Workflow version: 7.0")
            (project / "framework.md").write_text(legacy, encoding="utf-8")

            upgraded = run(project, "upgrade-workflow")

            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            text = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Workflow version: 8.1", text)
            self.assertIn("- Status: Not started", text)

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

    def test_deferred_structural_pages_skip_content_and_svg_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(DEFERRED_FRAMEWORK, encoding="utf-8")

            first = next_payload(project)

            self.assertEqual(first["action"], "AUTHOR_PAGE_CONTENT")
            self.assertEqual(first["slide_id"], "S02")
            self.assertFalse((project / "svg_working" / "S01").exists())
            self.assertFalse((project / "svg_working" / "S03").exists())

    def test_deferred_template_status_rejects_substantive_page_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            invalid = FRAMEWORK.replace("- Page type: Cover", "- Page type: Standard content")
            invalid = invalid.replace("- Status: Not started", "- Status: Deferred template")
            framework = project / "framework.md"
            framework.write_text(invalid, encoding="utf-8")

            errors = validate_framework(framework, project)

            self.assertTrue(any("Deferred template status requires" in item for item in errors))

    def test_framework_requires_one_final_ending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            framework = project / "framework.md"
            framework.write_text(FRAMEWORK_WITHOUT_ENDING, encoding="utf-8")

            errors = validate_framework(framework, project)

            self.assertIn("Confirmed Storyline must contain exactly one Ending: None", errors)

            content_after_ending = SECOND_PAGE.replace("S02", "S03")
            framework.write_text(
                FRAMEWORK_WITHOUT_ENDING.rstrip()
                + "\n\n"
                + ending_page("S02").lstrip()
                + "\n"
                + content_after_ending.lstrip(),
                encoding="utf-8",
            )

            self.assertIn("Ending must be the final page", validate_framework(framework, project))

    def test_fixed_ending_cannot_be_reopened_for_content_or_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(DEFERRED_FRAMEWORK, encoding="utf-8")

            for command in ("reopen-content", "reopen-svg"):
                result = run(project, command, "--page", "S03")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fixed Ending", result.stdout)

    def test_all_deferred_deck_prepares_export_without_content_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            deferred_only = FRAMEWORK.replace(
                "- Status: Not started",
                "- Status: Deferred template",
            )
            (project / "framework.md").write_text(deferred_only, encoding="utf-8")

            self.assertEqual(next_payload(project)["action"], "EXPORT_EDITABLE_PPTX")
            prepare_export_request(project)
            request = json.loads(
                (project / "working" / "packets" / "pptx" / "export.json").read_text()
            )
            self.assertNotIn("content_sha256", request)
            self.assertNotIn("framework_sha256", request)
            self.assertEqual(request["slides"][0]["source_kind"], "deferred-template")

    def test_svg_runtime_is_required_before_candidate_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            env = dict(os.environ)
            env.pop("EY_DECK_SVG_PYTHON", None)
            prepared = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "prepare-svg-candidates",
                    "--page",
                    "S01",
                    "--project-dir",
                    str(project),
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertNotEqual(prepared.returncode, 0)
            self.assertIn("EY_DECK_SVG_PYTHON", prepared.stdout)
            self.assertIn("- Status: Content locked", (project / "framework.md").read_text())
            self.assertFalse((project / "svg_working" / "S01").exists())

    def test_svg_runtime_is_required_before_revision_allocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "Option A")
            self.assertEqual(
                run(project, "present-svg", "--page", "S01", "--versions", "A").returncode,
                0,
            )
            env = dict(os.environ)
            env.pop("EY_DECK_SVG_PYTHON", None)

            revised = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "request-svg-revision",
                    "--page",
                    "S01",
                    "--base",
                    "A",
                    "--feedback",
                    "Increase contrast.",
                    "--project-dir",
                    str(project),
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(revised.returncode, 0)
            self.assertIn("EY_DECK_SVG_PYTHON", revised.stdout)
            self.assertFalse((project / "working" / "packets" / "S01" / "R1.json").exists())

    def test_later_provisional_content_reuses_canonical_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True)
            provisional.write_text(
                CONTENT_S02[CONTENT_S02.index("## S02"):],
                encoding="utf-8",
            )
            page = page_entries(framework_with_second_page())[1]

            errors = provisional_content_errors(
                provisional,
                [page],
                CONTENT,
            )

            self.assertEqual(errors, [])

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
            framework.write_text(
                FRAMEWORK_WITHOUT_ENDING + "".join(pages) + ending_page("S08"),
                encoding="utf-8",
            )

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

    def test_framework_validates_visual_execution_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            framework = project / "framework.md"
            framework.write_text(
                FRAMEWORK.replace("- Reading mode: balanced", "- Reading mode: cinematic"),
                encoding="utf-8",
            )
            self.assertIn(
                "Reading mode must be text, balanced, or presentation",
                validate_framework(framework, project),
            )

            framework.write_text(
                FRAMEWORK.replace("- Page rhythm: anchor", "- Page rhythm: dense"),
                encoding="utf-8",
            )
            self.assertIn(
                "S01 structural Page rhythm must be anchor",
                validate_framework(framework, project),
            )

            legacy = FRAMEWORK.replace("- Reading mode: balanced\n", "").replace(
                "- Page rhythm: anchor\n",
                "",
            )
            framework.write_text(legacy, encoding="utf-8")
            errors = validate_framework(framework, project)
            self.assertIn("Project context is missing Reading mode", errors)
            self.assertIn("S01 is missing Page rhythm", errors)

            substantive_anchor = framework_with_second_page().replace(
                "- Page rhythm: dense",
                "- Page rhythm: anchor",
                1,
            )
            framework.write_text(substantive_anchor, encoding="utf-8")
            self.assertIn(
                "S02 substantive Page rhythm must be dense or breathing",
                validate_framework(framework, project),
            )

    def test_record_svg_requires_service_complete_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(svg("Candidate"), encoding="utf-8")
            packet = project / "working" / "packets" / "S01" / "A.json"
            request = json.loads(packet.read_text(encoding="utf-8"))
            request["mode"] = "untrusted-mode"
            packet.write_text(json.dumps(request), encoding="utf-8")

            recorded = run(project, "record-svg", "--page", "S01", "--version", "A")

            self.assertNotEqual(recorded.returncode, 0)
            self.assertIn("mode must be independent or revision", recorded.stdout)
            self.assertFalse((project / "working" / "receipts" / "svg" / "S01" / "A.json").exists())

    def test_candidate_receipt_rejects_post_validation_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(svg("Candidate"), encoding="utf-8")
            packet = project / "working" / "packets" / "S01" / "A.json"

            with self.assertRaisesRegex(ValueError, "changed after validation"):
                record_candidate(
                    ProjectPaths(project),
                    "S01",
                    "A",
                    packet_sha256=request_sha256(packet),
                    artifact_sha256="0" * 64,
                )

            self.assertFalse(
                (project / "working" / "receipts" / "svg" / "S01" / "A.json").exists()
            )

    def test_stale_shared_page_context_returns_to_candidate_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            context_path = project / "working" / "packets" / "S01" / "context.json"
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["approved_content_sha256"] = "0" * 64
            context_path.write_text(json.dumps(context), encoding="utf-8")

            payload = next_payload(project)

            self.assertEqual(payload["action"], "PREPARE_SVG_CANDIDATES")
            repaired = prepare_candidates(project)
            self.assertEqual(repaired["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")

    def test_v4_page_context_is_regenerated_without_breaking_the_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            context_path = project / "working" / "packets" / "S01" / "context.json"
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["schema"] = "ey-deck.page-authoring-context.v4"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")
            repaired = prepare_candidates(project)
            self.assertEqual(repaired["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            regenerated = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(regenerated["schema"], "ey-deck.page-authoring-context.v6")

    def test_single_structural_revision_and_confirmation_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            self.assertIn("\n## S01\n", (project / "content.md").read_text(encoding="utf-8"))
            self.assertNotIn("## S01｜Sample title", (project / "content.md").read_text(encoding="utf-8"))
            self.assertIn("- Status: Content locked", (project / "framework.md").read_text(encoding="utf-8"))
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")

            payload = prepare_candidates(project)
            framework_after_prepare = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Status: Content locked", framework_after_prepare)
            self.assertNotIn("Awaiting SVG decision", framework_after_prepare)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A"])
            self.assertTrue((project / "svg_working" / "S01").is_dir())
            shared_contexts = set()
            shared_prototypes = set()
            for item in payload["requests"]:
                request = json.loads(Path(item["request_path"]).read_text(encoding="utf-8"))
                self.assertEqual(request["schema"], "ppt-master.page-svg-request.v4")
                self.assertEqual(request["mode"], "independent")
                self.assertEqual(request["caller"], "ey-deck-design")
                self.assertIsNone(request["base"])
                context_path = Path(request["authoring_context"]["path"])
                self.assertEqual(request["authoring_context"]["sha256"], request_sha256(context_path))
                context = json.loads(context_path.read_text(encoding="utf-8"))
                shared_contexts.add(context_path)
                self.assertEqual(context["schema"], "ey-deck.page-authoring-context.v6")
                self.assertNotIn("direction_contract", context)
                self.assertEqual(context["communication"]["consumption_mode"], "balanced")
                self.assertEqual(
                    context["communication"]["objective"],
                    "Explain the recommendation; success means Understand the decision",
                )
                self.assertEqual(context["page_rhythm"], "anchor")
                self.assertNotIn("visual_design_direction", context)
                self.assertEqual(context["composition_mode"], "full-slide")
                self.assertEqual(context["design_quality_profile"], DESIGN_QUALITY_PROFILE)
                self.assertNotIn("approved_content_source_sha256", context)
                self.assertNotIn("variant_direction", request)
                validate_python = shlex.split(item["validate_request"])[0]
                self.assertTrue(Path(validate_python).is_absolute())
                self.assertNotIn("complete", item)
                prototype = Path(context["template"]["prototype"])
                shared_prototypes.add(prototype)
                self.assertTrue(
                    prototype.is_relative_to((project / "working" / "template-prototypes").resolve())
                )
                design_spec = context["template"]["design_spec"]
                design_spec_path = Path(design_spec["path"])
                self.assertEqual(
                    design_spec_path,
                    (TEMPLATE_ROOT / "templates" / "design_spec.md").resolve(),
                )
                self.assertEqual(design_spec["sha256"], request_sha256(design_spec_path))
                image_hrefs = [
                    element.attrib.get("href", "")
                    for element in ET.parse(prototype).getroot().iter()
                    if element.tag.rsplit("}", 1)[-1] == "image"
                ]
                self.assertTrue(image_hrefs)
                self.assertTrue(all(href.startswith("data:image/") for href in image_hrefs))
                validated = subprocess.run(
                    [SVG_RUNTIME, str(SERVICE), "validate-request", item["request_path"]],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(validated.returncode, 0, validated.stdout)
            self.assertEqual(len(shared_contexts), 1)
            self.assertEqual(len(shared_prototypes), 1)

            invalid_request = project / "working" / "invalid-request.json"
            original_request = json.loads(
                (project / "working" / "packets" / "S01" / "A.json").read_text(encoding="utf-8")
            )
            original_context = json.loads(
                Path(original_request["authoring_context"]["path"]).read_text(encoding="utf-8")
            )

            def write_invalid_context(payload: dict, name: str) -> None:
                context_path = project / "working" / f"{name}.json"
                context_path.write_text(json.dumps(payload), encoding="utf-8")
                invalid_payload = dict(original_request)
                invalid_payload["authoring_context"] = {
                    "path": str(context_path.resolve()),
                    "sha256": request_sha256(context_path),
                }
                invalid_request.write_text(json.dumps(invalid_payload), encoding="utf-8")

            missing_quality = dict(original_context)
            del missing_quality["design_quality_profile"]
            write_invalid_context(missing_quality, "missing-quality")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("design_quality_profile must be", rejected.stdout)

            missing_design_spec = json.loads(json.dumps(original_context))
            del missing_design_spec["template"]["design_spec"]
            write_invalid_context(missing_design_spec, "missing-design-spec")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("template.design_spec must be an object", rejected.stdout)

            invalid_reading_mode = json.loads(json.dumps(original_context))
            invalid_reading_mode["communication"]["consumption_mode"] = "cinematic"
            write_invalid_context(invalid_reading_mode, "invalid-reading-mode")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(
                "communication.consumption_mode must be text, balanced, or presentation",
                rejected.stdout,
            )

            invalid_structural_rhythm = json.loads(json.dumps(original_context))
            invalid_structural_rhythm["page_rhythm"] = "dense"
            write_invalid_context(invalid_structural_rhythm, "invalid-structural-rhythm")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("structural page_rhythm must be anchor", rejected.stdout)

            stale_design_spec = json.loads(json.dumps(original_context))
            stale_design_spec["template"]["design_spec"]["sha256"] = "0" * 64
            write_invalid_context(stale_design_spec, "stale-design-spec")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("template design spec SHA-256 mismatch", rejected.stdout)

            missing_composition = dict(original_context)
            del missing_composition["composition_mode"]
            write_invalid_context(missing_composition, "missing-composition")
            rejected = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "validate-request", str(invalid_request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("composition_mode must be full-slide", rejected.stdout)

            complete_candidate(project, "A", "Option A")
            candidate_receipt = json.loads(
                (project / "working" / "receipts" / "svg" / "S01" / "A.json").read_text()
            )
            self.assertEqual(candidate_receipt["schema"], "ey-deck.svg-candidate.v2")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTION")
            presented = run(project, "present-svg", "--page", "S01", "--versions", "A")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("![S01 A]", presented.stdout)
            self.assertIn("The SVG is displayed at review scale", presented.stdout)
            self.assertIn("COLLECT_SVG_DECISION", presented.stdout)
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTION")

            revised = run(
                project, "request-svg-revision", "--page", "S01", "--base", "A",
                "--feedback", "Increase the contrast of the decision statement.",
            )
            self.assertEqual(revised.returncode, 0, revised.stdout + revised.stderr)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual(payload["requests"][0]["version"], "R1")
            request = json.loads((project / "working" / "packets" / "S01" / "R1.json").read_text())
            self.assertEqual(request["base"]["version"], "A")
            self.assertIn("Increase the contrast", request["feedback"])
            context = json.loads(Path(request["authoring_context"]["path"]).read_text())
            self.assertEqual(context["design_quality_profile"], DESIGN_QUALITY_PROFILE)
            self.assertNotIn("variant_direction", request)

            complete_candidate(project, "R1", "Revised option")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_REVISION")
            rejected_pair = run(project, "present-svg", "--page", "S01", "--versions", "A,R1")
            self.assertNotEqual(rejected_pair.returncode, 0)
            self.assertIn("exactly one version", rejected_pair.stdout)
            presented_revision = run(project, "present-svg", "--page", "S01", "--versions", "R1")
            self.assertEqual(
                presented_revision.returncode,
                0,
                presented_revision.stdout + presented_revision.stderr,
            )
            self.assertIn("![S01 R1]", presented_revision.stdout)
            self.assertNotIn("![S01 A]", presented_revision.stdout)
            revised_again = run(
                project, "request-svg-revision", "--page", "S01", "--base", "R1",
                "--feedback", "Tighten the spacing around the conclusion.",
            )
            self.assertEqual(
                revised_again.returncode,
                0,
                revised_again.stdout + revised_again.stderr,
            )
            request_r2 = json.loads(
                (project / "working" / "packets" / "S01" / "R2.json").read_text()
            )
            self.assertEqual(request_r2["base"]["version"], "R1")
            complete_candidate(project, "R2", "Second revision")
            presented_r2 = run(project, "present-svg", "--page", "S01", "--versions", "R2")
            self.assertEqual(presented_r2.returncode, 0, presented_r2.stdout + presented_r2.stderr)
            self.assertIn("![S01 R2]", presented_r2.stdout)
            self.assertNotIn("![S01 R1]", presented_r2.stdout)
            confirmed = run(project, "confirm-svg", "--page", "S01", "--version", "R2")
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            decision_receipt = json.loads(
                (project / "working" / "receipts" / "svg" / "S01" / "decision.json").read_text()
            )
            self.assertEqual(decision_receipt["schema"], "ey-deck.svg-decision.v2")
            self.assertNotIn("confirmed_sha256", decision_receipt)
            self.assertEqual(next_payload(project)["action"], "EXPORT_EDITABLE_PPTX")
            self.assertEqual((project / "svg_output" / "S01.svg").read_text(), svg("Second revision"))

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

    def test_content_template_and_service_allow_full_slide_composition(self) -> None:
        template_root = ET.parse(
            TEMPLATE_ROOT / "templates" / "content.svg"
        ).getroot()
        content_region = next(
            element for element in template_root
            if element.attrib.get("id") == "content-region"
        )
        self.assertEqual(content_region.attrib["data-pptx-bounds"], "0 0 1280 720")
        structure_errors = artifact_errors(
            TEMPLATE_ROOT / "templates" / "content.svg"
        )
        self.assertEqual(structure_errors, [])
        self.assertFalse(any("Quick Generate" in error for error in structure_errors))

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(
                """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#000000"/>
  <text x="48" y="690" fill="#FFFFFF" font-size="18">Content below the former y=650 cap</text>
</svg>
""",
                encoding="utf-8",
            )
            request = project / "working" / "packets" / "S01" / "A.json"
            completed = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "complete", str(request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

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

    def test_substantive_page_logic_is_required_and_block_bound(self) -> None:
        section = """## S02

### Page logic（Build-only）
- Page objective: Explain the recommendation
- Audience move: From uncertainty to readiness to proceed
- Reasoning pattern: Recommendation and implication
- Argument chain: S02-B1 establishes the action before S02-B2 states the implication
- Relationship constraints: S02-B2 is an implication, not a second option
- Argument priority: Establish the action before its implication

### On-slide content
- Title: Recommendation

#### S02-B1｜Action
- Detail: Proceed with the selected path.

#### S02-B2｜Implication
- Detail: Begin implementation planning.
"""
        self.assertEqual(validate_page_logic("S02", section, "Standard content"), [])
        missing = validate_page_logic(
            "S02",
            section.replace("### Page logic（Build-only）", "### Removed logic"),
            "Standard content",
        )
        self.assertTrue(any("missing Page logic" in error for error in missing))
        unknown = validate_page_logic(
            "S02",
            section.replace("S02-B2 is an implication", "S02-B9 is an implication"),
            "Standard content",
        )
        self.assertTrue(any("unknown blocks: S02-B9" in error for error in unknown))
        structural = validate_page_logic("S02", section, "Agenda")
        self.assertTrue(any("structural page" in error for error in structural))

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

    def test_confirmed_svg_roster_prepares_hash_bound_pptx_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "Export source")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)

            prepare_export_request(project)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "EXPORT_EDITABLE_PPTX")
            request = json.loads((project / "working" / "packets" / "pptx" / "export.json").read_text())
            self.assertEqual(request["schema"], "ppt-master.svg-deck-pptx-request.v3")
            self.assertEqual(request["slides"][0]["slide_id"], "S01")
            self.assertEqual(request["slides"][0]["source_kind"], "confirmed-svg")
            self.assertNotIn("conversion", request)
            self.assertNotIn("quality_policy", request)
            self.assertNotIn("content_path", request)
            self.assertNotIn("framework_path", request)
            self.assertEqual(Path(request["output_path"]), (project / "sample.pptx").resolve())
            framework = project / "framework.md"
            framework.write_text(
                framework.read_text(encoding="utf-8").replace(
                    "- Core need: Explain the recommendation",
                    "- Core need: Explain the approved recommendation",
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                pptx_request_valid(ProjectPaths(project), framework.read_text(encoding="utf-8"))
            )

            renamed = run(project, "set-output-filename", "--filename", "renamed.pptx")
            self.assertEqual(renamed.returncode, 0, renamed.stdout + renamed.stderr)
            self.assertEqual(next_payload(project)["action"], "EXPORT_EDITABLE_PPTX")

    def test_current_text_failure_receipt_routes_back_to_svg_reconfirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "Export source")
            self.assertEqual(
                run(project, "present-svg", "--page", "S01", "--versions", "A").returncode,
                0,
            )
            self.assertEqual(
                run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode,
                0,
            )
            prepare_export_request(project)
            request = project / "working" / "packets" / "pptx" / "export.json"
            failure = project / "working" / "receipts" / "pptx" / "text-failure.json"
            failure.parent.mkdir(parents=True, exist_ok=True)
            failure.write_text(
                json.dumps(
                    {
                        "schema": TEXT_FAILURE_SCHEMA,
                        "request_sha256": request_sha256(request),
                        "slide_id": "S01",
                        "source_kind": "confirmed-svg",
                        "reason": "text continuity failed",
                        "recovery": "reopen-svg-and-reconfirm",
                    }
                ),
                encoding="utf-8",
            )

            directive = next_payload(project)

            self.assertEqual(directive["action"], "REOPEN_PPTX_TEXT_SOURCE")
            self.assertEqual(directive["slide_id"], "S01")
            self.assertIn("reopen-svg", directive["commands"]["reopen"])

    def test_pptx_roster_injects_deferred_templates_in_framework_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            self.assertEqual(next_payload(project)["slide_id"], "S02")
            prepare_candidates(project, page_id="S02")
            complete_candidate(project, "A", "Authored content", page_id="S02")
            self.assertEqual(
                run(project, "present-svg", "--page", "S02", "--versions", "A").returncode,
                0,
            )
            confirmed = run(project, "confirm-svg", "--page", "S02", "--version", "A")
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            directive = next_payload(project)
            self.assertEqual(directive["action"], "EXPORT_EDITABLE_PPTX")

            prepare_export_request(project)
            request = json.loads(
                (project / "working" / "packets" / "pptx" / "export.json").read_text()
            )
            self.assertEqual([item["slide_id"] for item in request["slides"]], ["S01", "S02", "S03"])
            self.assertEqual(
                [item["source_kind"] for item in request["slides"]],
                ["deferred-template", "confirmed-svg", "deferred-template"],
            )
            for slide_id in ("S01", "S03"):
                snapshot = project / "working" / "packets" / "pptx" / "templates" / f"{slide_id}.svg"
                self.assertTrue(snapshot.is_file())
                hrefs = [
                    element.attrib.get("href", "")
                    for element in ET.parse(snapshot).getroot().iter()
                    if element.tag.rsplit("}", 1)[-1] == "image"
                ]
                self.assertTrue(hrefs)
                self.assertTrue(all(href.startswith("data:image/") for href in hrefs))
                self.assertFalse((project / "svg_working" / slide_id).exists())
            cover_root = ET.parse(
                project / "working" / "packets" / "pptx" / "templates" / "S01.svg"
            ).getroot()
            cover_text = {}
            for element in cover_root.iter():
                element_id = element.attrib.get("id")
                if element_id in {"cover-project-type", "cover-title", "cover-subtitle"}:
                    carrier = next(
                        child
                        for child in element.iter()
                        if child.tag.rsplit("}", 1)[-1] == "text"
                    )
                    cover_text[element_id] = carrier.text
            self.assertEqual(
                cover_text,
                {
                    "cover-project-type": "Sharing deck",
                    "cover-title": "Sample title",
                    "cover-subtitle": "Title and subtitle",
                },
            )
            self.assertFalse((project / "svg_output" / "S01.svg").exists())
            framework_path = project / "framework.md"
            framework_path.write_text(
                framework_path.read_text(encoding="utf-8").replace(
                    "### S01｜Sample title",
                    "### S01｜Updated title",
                ),
                encoding="utf-8",
            )
            self.assertFalse(
                pptx_request_valid(
                    ProjectPaths(project),
                    framework_path.read_text(encoding="utf-8"),
                )
            )

    def test_embedded_ppt_master_exports_editable_text_with_frame_parity(self) -> None:
        runtime = os.environ.get("EY_DECK_PPTX_PYTHON")
        if not runtime:
            self.skipTest("PPTX runtime is not available; set EY_DECK_PPTX_PYTHON")
        available = subprocess.run(
            [runtime, "-c", "import pptx"],
            text=True,
            capture_output=True,
            check=False,
        )
        if available.returncode:
            self.skipTest("PPTX runtime is not available; set EY_DECK_PPTX_PYTHON")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(multiline_svg(), encoding="utf-8")
            request = project / "working" / "packets" / "S01" / "A.json"
            service = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "complete", str(request)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(service.returncode, 0, service.stdout + service.stderr)
            recorded = run(project, "record-svg", "--page", "S01", "--version", "A")
            self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)
            exported = run(project, "export-pptx")

            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "PPTX_STAGE_COMPLETE")
            self.assertTrue((project / "sample.pptx").is_file())
            audit = json.loads((project / "working" / "receipts" / "pptx" / "text-frames.json").read_text())
            self.assertEqual(audit["status"], "passed")
            self.assertEqual(audit["text_flow"], "reflow")
            self.assertEqual(audit["slides"][0]["source_svg_text_carriers"], 1)
            self.assertEqual(audit["slides"][0]["conversion_text_events"], 1)
            self.assertEqual(audit["slides"][0]["pptx_text_boxes"], 1)
            self.assertEqual(len(audit["slides"][0]["carriers"]), 1)
            with zipfile.ZipFile(project / "sample.pptx") as archive:
                slide_root = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
            exported_text = "".join(
                node.text or ""
                for node in slide_root.iter(
                    "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                )
            )
            self.assertEqual(exported_text, "同一段文字应该连续呈现")
            self.assertFalse(
                any(
                    node.tag == "{http://schemas.openxmlformats.org/drawingml/2006/main}br"
                    for node in slide_root.iter()
                )
            )
            trace = json.loads(
                (project / "validation" / "sample.trace.json").read_text(encoding="utf-8")
            )
            bridge = trace["slides"][0]["source_bridge"]
            self.assertEqual(bridge["transform"], "strip-structure-metadata/v1")
            self.assertEqual(bridge["confirmed_svg"], str((project / "svg_output" / "S01.svg").resolve()))
            self.assertEqual(bridge["confirmed_sha256"], request_sha256(project / "svg_output" / "S01.svg"))
            self.assertGreaterEqual(bridge["removed_structure_attributes"], 0)
            audited = run(project, "audit")
            self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)
            self.assertIn("editable PPTX workflow audit passed", audited.stdout)

    def test_deferred_templates_export_in_order_with_fixed_ending(self) -> None:
        runtime = os.environ.get("EY_DECK_PPTX_PYTHON")
        if not runtime:
            self.skipTest("PPTX runtime is not available; set EY_DECK_PPTX_PYTHON")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_deferred_deck_content(project)
            prepare_candidates(project, page_id="S02")
            complete_candidate(project, "A", "Editable content", page_id="S02")
            self.assertEqual(
                run(project, "present-svg", "--page", "S02", "--versions", "A").returncode,
                0,
            )
            self.assertEqual(
                run(project, "confirm-svg", "--page", "S02", "--version", "A").returncode,
                0,
            )
            stale_postflight = project / "validation" / "sample.report.json"
            stale_postflight.parent.mkdir(parents=True, exist_ok=True)
            stale_postflight.write_text(
                json.dumps({"status": "passed", "stale": True}),
                encoding="utf-8",
            )
            exported = run(project, "export-pptx")

            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            output = project / "sample.pptx"
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                slide_xml = sorted(
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )
                ending_rels = ET.fromstring(
                    archive.read("ppt/slides/_rels/slide3.xml.rels")
                )
                ending_media = [
                    posixpath.normpath(
                        posixpath.join("ppt/slides", relation.attrib["Target"])
                    )
                    for relation in ending_rels
                    if relation.attrib.get("Type", "").endswith("/image")
                ]
                ending_asset = TEMPLATE_ROOT / "images" / "ending-slide.png"
                self.assertEqual(len(ending_media), 1)
                exported_ending = Image.open(
                    io.BytesIO(archive.read(ending_media[0]))
                ).convert("RGBA")
                approved_ending = Image.open(ending_asset).convert("RGBA").resize(
                    exported_ending.size,
                    Image.Resampling.LANCZOS,
                )
                ending_diff = ImageStat.Stat(
                    ImageChops.difference(exported_ending, approved_ending)
                )
                self.assertLess(
                    max(ending_diff.mean),
                    0.5,
                    f"fixed Ending pixels changed: size={exported_ending.size}, mean={ending_diff.mean}",
                )
            self.assertEqual(len(slide_xml), 3)
            current_postflight = json.loads(stale_postflight.read_text(encoding="utf-8"))
            self.assertNotIn("stale", current_postflight)
            self.assertEqual(current_postflight["source"]["svg_slide_count"], 3)
            audit = json.loads(
                (project / "working" / "receipts" / "pptx" / "text-frames.json").read_text()
            )
            self.assertEqual(
                [item["slide_id"] for item in audit["slides"]],
                ["S01", "S02", "S03"],
            )
            self.assertGreater(audit["slides"][0]["pptx_text_boxes"], 0)
            self.assertEqual(audit["slides"][2]["pptx_text_boxes"], 0)
            trace = json.loads(
                (project / "validation" / "sample.trace.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [item["source_bridge"]["source_kind"] for item in trace["slides"]],
                ["deferred-template", "confirmed-svg", "deferred-template"],
            )

    def test_page_service_blocks_one_paragraph_split_into_sibling_text_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            artifact = project / "svg_working" / "S01" / "A.svg"
            artifact.write_text(fragmented_paragraph_svg(), encoding="utf-8")
            request = project / "working" / "packets" / "S01" / "A.json"

            completed = subprocess.run(
                [SVG_RUNTIME, str(SERVICE), "complete", str(request)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("PPTX text-frame integrity", completed.stdout)
            self.assertIn("sibling <text> elements", completed.stdout)

    def test_page_service_blocks_dx_visual_spacing_without_literal_space(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "dx.svg"
            artifact.write_text(inline_dx_spacing_svg(), encoding="utf-8")

            errors = artifact_errors(artifact)

            self.assertTrue(any("positional dx" in item for item in errors))
            self.assertTrue(any("literal whitespace" in item for item in errors))

    def test_safe_absolute_y_rows_normalize_to_one_reflow_text_carrier(self) -> None:
        root = ET.fromstring(safe_absolute_y_svg())

        self.assertEqual(text_carrier_integrity_errors(root), [])
        changed = flatten_text_with_tspans(
            ET.ElementTree(root),
            merge_paragraphs=True,
            preserve_line_breaks=False,
        )

        self.assertTrue(changed)
        texts = list(root.iter("{http://www.w3.org/2000/svg}text"))
        self.assertEqual(len(texts), 1)
        rows = list(texts[0])
        self.assertTrue(all(row.get("y") is None for row in rows))
        self.assertEqual(texts[0].get("data-paragraph-line-height"), "36")
        self.assertEqual(rows[1].get("data-paragraph-soft-break"), "1")

    def test_preserve_preflight_blocks_source_carrier_that_would_split_one_to_many(self) -> None:
        root = ET.fromstring(nonmergeable_relative_dy_svg())

        errors = text_carrier_integrity_errors(root)

        self.assertTrue(any("1→N" in item for item in errors))

    def test_real_s02_text_fixture_is_blocked_before_pptx_export(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "henkel-s02-text-carriers.svg"

        errors = text_carrier_integrity_errors(ET.parse(fixture).getroot())

        self.assertTrue(any("positional dx" in item for item in errors))
        self.assertTrue(any("absolute-y rows" in item for item in errors))

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
                [SVG_RUNTIME, str(SERVICE), "complete", str(project / "working" / "packets" / "S01" / "A.json")],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("remote URL", result.stdout)

    def test_later_page_content_does_not_stale_a_confirmed_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(
                framework_with_second_page(), encoding="utf-8"
            )
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
            planning = next_payload(project)
            self.assertEqual(planning["action"], "PREPARE_SVG_CANDIDATES")
            self.assertEqual(planning["slide_id"], "S02")
            self.assertEqual(planning["versions"], ["A"])
            payload = prepare_candidates(project, "S02")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A"])
            requests = {}
            context_descriptors = set()
            prototype_paths = set()
            for item in payload["requests"]:
                request = json.loads(Path(item["request_path"]).read_text(encoding="utf-8"))
                requests[item["version"]] = request
                descriptor = request["authoring_context"]
                context_descriptors.add((descriptor["path"], descriptor["sha256"]))
                context = json.loads(Path(descriptor["path"]).read_text(encoding="utf-8"))
                prototype_paths.add(context["template"]["prototype"])
                self.assertLessEqual(len(context["consistency_references"]), 2)
                self.assertNotIn("confirmed_pages", context)
                self.assertEqual(
                    context["page_logic"],
                    {
                        "page_objective": "Explain the recommendation",
                        "audience_move": "From uncertainty to readiness to proceed",
                        "reasoning_pattern": "Recommendation and implication",
                        "argument_chain": "S02-B1 states the recommended action",
                        "relationship_constraints": "None",
                        "argument_priority": "Establish the action first",
                    },
                )
            self.assertEqual(len(context_descriptors), 1)
            self.assertEqual(len(prototype_paths), 1)
            self.assertNotIn("variant_direction", requests["A"])
            complete_candidate(project, "A", "Content A", page_id="S02")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTION")
            presented = run(project, "present-svg", "--page", "S02", "--versions", "A")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("The SVG is displayed at review scale", presented.stdout)

    def test_default_initial_candidate_is_single(self) -> None:
        for page_type in ("Cover", "Agenda", "Section divider", "Ending", "Standard content"):
            with self.subTest(page_type=page_type):
                self.assertEqual(initial_versions_for_page_type(page_type), ("A",))
        self.assertEqual(template_name("Ending"), "ending.svg")

    def test_explicit_alternatives_still_generate_one_initial_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            second_page = SECOND_PAGE.replace(
                "- Confirmed decisions: None",
                "- Confirmed decisions: Provide two design options",
            )
            (project / "framework.md").write_text(
                framework_with_second_page(second_page),
                encoding="utf-8",
            )
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True)
            provisional.write_text(CONTENT, encoding="utf-8")
            self.assertEqual(run(project, "present-review").returncode, 0)
            self.assertEqual(run(project, "approve-content").returncode, 0)
            prepare_candidates(project)
            complete_candidate(project, "A", "Cover")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)

            provisional.write_text(CONTENT_S02, encoding="utf-8")
            self.assertEqual(run(project, "present-review").returncode, 0)
            self.assertEqual(run(project, "approve-content").returncode, 0)
            planning = next_payload(project)
            self.assertEqual(planning["versions"], ["A"])

            payload = prepare_candidates(project, "S02")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A"])
            requests = {
                item["version"]: json.loads(Path(item["request_path"]).read_text())
                for item in payload["requests"]
            }
            for item in payload["requests"]:
                validated = subprocess.run(
                    [SVG_RUNTIME, str(SERVICE), "validate-request", item["request_path"]],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            context_path = Path(requests["A"]["authoring_context"]["path"])
            context = json.loads(context_path.read_text())
            self.assertEqual(context["communication"]["consumption_mode"], "balanced")
            self.assertEqual(context["page_rhythm"], "dense")
            self.assertNotIn("visual_design_direction", context)
            self.assertNotIn("variant_direction", requests["A"])

    def test_ppt_master_candidate_variants_are_not_classified_upstream(self) -> None:
        source = (ROOT / "scripts" / "workflow_ppt_master.py").read_text(encoding="utf-8")
        for removed_control in (
            "VARIANT_PAIRS",
            "STRUCTURAL_DIRECTIONS",
            "adaptation_rule",
            "variant_direction",
            "alternative_contract",
            "VISUAL_DESIGN_DIRECTIONS",
            "visual_design_direction",
        ):
            self.assertNotIn(removed_control, source)
        self.assertNotIn("visible_candidate_gate", source)
        quality_text = (
            ROOT / "ppt-master" / "workflows" / "page-svg-service.md"
        ).read_text(encoding="utf-8").casefold()
        for removed_aesthetic_rule in (
            "dashboard",
            "stacked-card",
            "equal columns",
            "rounded rectangles",
        ):
            self.assertNotIn(removed_aesthetic_rule, quality_text)

    def test_agenda_is_editable_and_ending_is_fixed_without_added_content(self) -> None:
        agenda = TEMPLATE_ROOT / "templates" / "agenda.svg"
        source = agenda.read_text(encoding="utf-8")
        root = ET.parse(agenda).getroot()
        region = next(element for element in root.iter() if element.attrib.get("id") == "agenda-content-region")
        self.assertEqual(region.attrib.get("data-pptx-binding"), "proxy")
        self.assertIn("Section title", source)
        self.assertTrue(any(child.tag.rsplit("}", 1)[-1] == "rect" for child in region))
        agenda_text = [
            element
            for element in region.iter()
            if element.tag.rsplit("}", 1)[-1] == "text"
        ]
        self.assertEqual(len(agenda_text), 1)

        ending = TEMPLATE_ROOT / "templates" / "ending.svg"
        ending_source = ending.read_text(encoding="utf-8")
        ending_root = ET.parse(ending).getroot()
        self.assertEqual(ending_root.attrib.get("data-ey-fixed-ending"), "true")
        self.assertIn("ending-slide.png", ending_source)
        self.assertNotIn("ending-background.png", ending_source)
        self.assertEqual(
            [element.tag.rsplit("}", 1)[-1] for element in ending_root],
            ["image"],
        )
        self.assertFalse(
            any(element.tag.rsplit("}", 1)[-1] == "text" for element in ending_root.iter())
        )

    def test_full_design_service_contract_is_registered(self) -> None:
        contract = (ROOT / "ppt-master" / "workflows" / "page-svg-service.md").read_text(encoding="utf-8")
        for capability in ("Strategist", "chart", "table", "imagery", "semantic SVG", "Review and repair"):
            self.assertIn(capability, contract)
        internal = (ROOT / "ppt-master" / "INTERNAL.md").read_text(encoding="utf-8")
        self.assertIn("ppt-master.page-svg-request.v4", internal)
        self.assertIn("ppt-master.svg-deck-pptx-request.v3", internal)
        export_contract = (ROOT / "ppt-master" / "workflows" / "svg-deck-pptx-service.md").read_text(encoding="utf-8")
        self.assertIn("reflow", export_contract)
        self.assertIn("text box", export_contract)
        self.assertIn("postflight", export_contract)
        self.assertIn("content-over-capacity", contract)
        self.assertIn("Hard rule — EY fit completion", contract)
        executor = (ROOT / "ppt-master" / "references" / "executor-base.md").read_text(encoding="utf-8")
        candidate_workflow = (ROOT / "references" / "svg-candidate-workflow.md").read_text(encoding="utf-8")
        self.assertNotIn("content-over-capacity", executor)
        self.assertNotIn("content-over-capacity", candidate_workflow)
        self.assertFalse((ROOT / "ppt-master" / "SKILL.md").exists())
        self.assertFalse((ROOT / "ppt-master" / "agents" / "openai.yaml").exists())

    def test_storyline_richness_contract_is_registered(self) -> None:
        routing = (ROOT / "references" / "deliverable-types.md").read_text(encoding="utf-8")
        storyline = (ROOT / "references" / "storyline-and-content.md").read_text(encoding="utf-8")
        framework = (ROOT / "references" / "framework-contract.md").read_text(encoding="utf-8")

        self.assertIn("normally three to\nfive bullets", routing)
        self.assertIn("normally three to five planned content blocks", storyline)
        self.assertIn("Reading mode × Page rhythm", storyline)
        self.assertIn("Visual design direction", routing)
        self.assertIn("preserve the three to five\ndistinct planned units", framework)
        self.assertIn("execution anchors", framework)
        self.assertIn("Keep structural pages role-appropriate and concise", framework)


if __name__ == "__main__":
    unittest.main()
