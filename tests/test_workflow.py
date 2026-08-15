from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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

## S02｜Second page

### On-slide content
- Title: Second page

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


def prepare_candidates(project: Path) -> dict:
    prepared = run(project, "prepare-svg-candidates", "--page", "S01")
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    return next_payload(project)


def complete_candidate(project: Path, version: str, label: str) -> None:
    artifact = project / "svg_working" / "S01" / f"{version}.svg"
    assert artifact.parent.is_dir(), f"candidate directory was not prepared: {artifact.parent}"
    artifact.write_text(svg(label), encoding="utf-8")
    request = project / "working" / "packets" / "S01" / f"{version}.json"
    service = subprocess.run(
        ["python3", str(SERVICE), "complete", str(request)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert service.returncode == 0, service.stdout + service.stderr
    recorded = run(project, "record-svg", "--page", "S01", "--version", version)
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

    def test_ab_revision_and_confirmation_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")

            payload = prepare_candidates(project)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual([item["version"] for item in payload["requests"]], ["A", "B"])
            self.assertTrue((project / "svg_working" / "S01").is_dir())
            for item in payload["requests"]:
                request = json.loads(Path(item["request_path"]).read_text(encoding="utf-8"))
                self.assertEqual(request["mode"], "independent")
                self.assertEqual(request["caller"], "ey-deck-design")
                self.assertIsNone(request["base"])
                validated = subprocess.run(
                    ["python3", str(SERVICE), "validate-request", item["request_path"]],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(validated.returncode, 0, validated.stdout)

            complete_candidate(project, "A", "Option A")
            complete_candidate(project, "B", "Option B")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_OPTIONS")
            presented = run(project, "present-svg", "--page", "S01", "--versions", "A,B")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("![S01 A]", presented.stdout)
            self.assertEqual(next_payload(project)["action"], "COLLECT_SVG_DECISION")

            feedback = project / "working" / "revision-requests" / "S01.md"
            self.assertTrue(feedback.parent.is_dir())
            feedback.write_text("Increase the contrast of the decision statement.", encoding="utf-8")
            revised = run(
                project, "request-svg-revision", "--page", "S01", "--base", "B",
                "--feedback-file", str(feedback),
            )
            self.assertEqual(revised.returncode, 0, revised.stdout + revised.stderr)
            payload = next_payload(project)
            self.assertEqual(payload["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
            self.assertEqual(payload["requests"][0]["version"], "R1")
            request = json.loads((project / "working" / "packets" / "S01" / "R1.json").read_text())
            self.assertEqual(request["base"]["version"], "B")
            self.assertIn("Increase the contrast", request["feedback"])

            complete_candidate(project, "R1", "Revised option")
            self.assertEqual(next_payload(project)["action"], "PRESENT_SVG_REVISION")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "B,R1").returncode, 0)
            confirmed = run(project, "confirm-svg", "--page", "S01", "--version", "R1")
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            self.assertEqual(next_payload(project)["action"], "SVG_STAGE_COMPLETE")
            self.assertEqual((project / "svg_output" / "S01.svg").read_text(), svg("Revised option"))

            reopened = run(project, "reopen-svg", "--page", "S01")
            self.assertEqual(reopened.returncode, 0, reopened.stdout + reopened.stderr)
            self.assertFalse((project / "svg_working" / "S01").exists())
            self.assertFalse((project / "working" / "packets" / "S01").exists())
            self.assertFalse((project / "working" / "receipts" / "svg" / "S01").exists())
            self.assertFalse((project / "svg_output" / "S01.svg").exists())
            self.assertFalse((project / "working" / "history").exists())
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")
            payload = prepare_candidates(project)
            self.assertEqual([item["version"] for item in payload["requests"]], ["A", "B"])

    def test_stale_candidate_and_confirmation_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "A")
            complete_candidate(project, "B", "B")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A,B").returncode, 0)
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
            complete_candidate(project, "B", "B")
            self.assertEqual(run(project, "present-svg", "--page", "S01", "--versions", "A,B").returncode, 0)
            self.assertEqual(run(project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)

            provisional.write_text(CONTENT_S02, encoding="utf-8")
            self.assertEqual(run(project, "present-review").returncode, 0)
            self.assertEqual(run(project, "approve-content").returncode, 0)
            self.assertEqual(next_payload(project)["action"], "PREPARE_SVG_CANDIDATES")
            self.assertEqual(next_payload(project)["slide_id"], "S02")

    def test_full_design_service_contract_is_registered(self) -> None:
        contract = (ROOT / "ppt-master" / "workflows" / "page-svg-service.md").read_text(encoding="utf-8")
        for capability in ("Strategist", "chart", "table", "imagery", "semantic SVG", "Review and repair"):
            self.assertIn(capability, contract)
        internal = (ROOT / "ppt-master" / "INTERNAL.md").read_text(encoding="utf-8")
        self.assertIn("ppt-master.page-svg-request.v1", internal)
        self.assertFalse((ROOT / "ppt-master" / "SKILL.md").exists())
        self.assertFalse((ROOT / "ppt-master" / "agents" / "openai.yaml").exists())


if __name__ == "__main__":
    unittest.main()
