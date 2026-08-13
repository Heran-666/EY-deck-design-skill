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
from xml.etree import ElementTree as ET


SKILL = Path(
    os.environ.get(
        "EY_DECK_SKILL_UNDER_TEST",
        str(Path(__file__).resolve().parents[1]),
    )
).resolve()
SCRIPTS = SKILL / "scripts"
CONTROLLER = SCRIPTS / "workflow_controller.py"
REINDEX = SCRIPTS / "reindex_slides.py"
FAKE_RENDERER = Path(__file__).resolve().parent / "fake_preview_renderer.py"
FAKE_BUNDLED_PYTHON = Path(__file__).resolve().parent / "fake_bundled_python.py"
sys.path.insert(0, str(SCRIPTS))

from workflow_controller import (  # noqa: E402
    ab_presentation_valid,
    artifact_errors,
    candidate_errors,
    directive,
    directive_payload,
    ensure_authoring_packet,
    migrate_workflow,
    receipt_path,
    sha256,
    single_presentation_valid,
    text_sha256,
)
from framework_lib import page_entries  # noqa: E402
from validate_framework import validate as validate_framework  # noqa: E402
from validate_deck_blueprint import validate as validate_blueprint  # noqa: E402
from validate_terminal_result import validate_terminal_result  # noqa: E402
from workflow_spec import initial_authoring_mode  # noqa: E402


def framework(status: str = "Content locked", version: str = "3.8", slide_id: str = "S01") -> str:
    confirmed = "A" if status == "SVG confirmed" else "Pending"
    return f"""# Presentation Framework

## Current position

- Framework version: 2.6
- Workflow version: {version}
- Storyline version: 1.0
- Output filename: Test deck.pptx

## Project context

- Deliverable name: Test deck
- Audience: Leadership
- Deliverable type: Sharing deck
- Requested authoring mode: Standard
- Audience outcome: Understand the recommendation
- Core need: Explain the decision
- Storyline thesis: Evidence supports action
- Scope boundaries: None
- Protected content: None

## Design hard rules

- Canvas: ppt169, SVG 1280 × 720; exported at approximately 33.867 cm × 19.05 cm.
- Project-specific rules: None

## Confirmed Storyline

### {slide_id}｜Decision page

- Chapter: Main
- Page type: Standard content
- Narrative role: Explain the recommendation
- Content scope: Evidence and action
- Next connection: None
- Review mode: Page-by-page
- Authoring mode: Standard
- Status: {status}
- Confirmed decisions: None
- Open items: None
- Confirmed version: {confirmed}
"""


def content(slide_id: str = "S01") -> str:
    return f"""# Presentation Build Specification

## Deck build profile（Build-only）
- Language: English

## {slide_id}｜Decision page

### On-slide content
- Title: Decision page
- Core insight: Evidence supports action

#### {slide_id}-B1｜Evidence
- Detail: A complete and approved statement for leadership decision-making.

### Visual Direction（Build-only）
- Page type: Standard content
- Visual focus: The recommendation
- Information hierarchy: Conclusion first, evidence second
- Relationship to preserve: Evidence supports action
- Fixed constraints: Preserve approved copy
- Avoid: Weakening the conclusion

### Sources
- On-slide source: None
- Source details: No external sources
"""


def legacy_proposal_framework(status: str = "Content locked", version: str = "2.7") -> str:
    return (
        framework(status, version)
        .replace("# Presentation Framework", "# Proposal Framework", 1)
        .replace("- Deliverable name: Test deck", "- Proposal name: Test deck", 1)
        .replace("- Audience: Leadership", "- Client: Leadership", 1)
        .replace("- Deliverable type: Sharing deck", "- Proposal type: Formal RFP response", 1)
        .replace(
            "- Audience outcome: Understand the recommendation",
            "- Client decision: Understand the recommendation",
            1,
        )
        .replace("- Storyline thesis: Evidence supports action", "- Proposal thesis: Evidence supports action", 1)
    )


def svg(color: str = "#FFE600", extra: str = "", slide_id: str = "S01") -> str:
    root = ET.parse(
        SKILL / "assets" / "templates" / "ey-gradient-dark-v1" / "content.svg"
    ).getroot()
    groups = {child.get("id"): child for child in root if child.tag.endswith("g")}
    title = list(groups["content-title"])[0]
    title.set("data-copy-id", f"{slide_id}-title")
    title.text = "Decision page"
    subtitle = list(groups["content-subtitle"])[0]
    subtitle.text = ""
    region = groups["content-region"]
    for child in list(region):
        region.remove(child)
    ET.SubElement(region, "{http://www.w3.org/2000/svg}rect", {
        "x": "80", "y": "170", "width": "420", "height": "240", "fill": color,
    })
    for copy_id, y, size, value in (
        (f"{slide_id}-core-insight", "440", "16", "Evidence supports action"),
        (f"{slide_id}-B1-heading", "480", "18.6667", "Evidence"),
        (
            f"{slide_id}-B1-detail",
            "525",
            "13.3333",
            "A complete and approved statement for leadership decision-making.",
        ),
    ):
        node = ET.SubElement(region, "{http://www.w3.org/2000/svg}text", {
            "data-copy-id": copy_id,
            "x": "80",
            "y": y,
            "fill": "#FFFFFF",
            "font-family": "Microsoft YaHei",
            "font-size": size,
        })
        node.text = value
    if extra:
        wrapper = ET.fromstring(f'<g xmlns="http://www.w3.org/2000/svg">{extra}</g>')
        for child in list(wrapper):
            region.append(child)
    return ET.tostring(root, encoding="unicode")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def setup_locked(project: Path) -> Path:
    framework_path = project / "framework.md"
    framework_path.write_text(framework(), encoding="utf-8")
    content_path = project / "content.md"
    content_path.write_text(content(), encoding="utf-8")
    section = content().split("## S01｜", 1)[1]
    section = "## S01｜" + section
    write_json(receipt_path(project, "S01", "content"), {
        "slide_id": "S01",
        "content_sha256": text_sha256(section.rstrip() + "\n"),
        "approval_note": "approved",
    })
    return framework_path


def setup_ab(project: Path) -> None:
    text = (project / "framework.md").read_text(encoding="utf-8")
    _, pages = directive(text, project)
    packet = ensure_authoring_packet(text, project, pages[0])
    root = project / "svg_working" / "S01"
    root.mkdir(parents=True, exist_ok=True)
    a = root / "A.svg"
    b = root / "B.svg"
    a.write_text(svg("#FFE600"), encoding="utf-8")
    b.write_text(svg("#188CE5"), encoding="utf-8")
    for version, artifact in (("A", a), ("B", b)):
        terminal_result = {
            "status": "COMPLETE",
            "route": "page-svg-authoring",
            "artifact_path": str(artifact.resolve()),
        }
        if version == "B":
            terminal_result["material_differences"] = ["Different emphasis treatment"]
        write_json(receipt_path(project, "S01", f"{version}-authoring"), {
            "status": "COMPLETE",
            "route": "page-svg-authoring",
            "slide_id": "S01",
            "authoring_mode": "Standard",
            "version": version,
            "artifact_path": str(artifact.resolve()),
            "artifact_sha256": sha256(artifact),
            "packet_path": packet["packet_path"],
            "packet_sha256": packet["packet_sha256"],
            "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
            "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
            "preflight_gate": {
                "schema": "ey-deck.page-preflight.v2",
                "status": "PASS",
                "artifact_sha256": sha256(artifact),
                "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
                "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
            },
            "active": False,
            "terminal_result": terminal_result,
        })


def setup_presented_revision(
    project: Path,
    *,
    base_version: str = "A",
    revision_color: str = "#FFFACC",
) -> str:
    setup_locked(project)
    setup_ab(project)
    presented_ab = run(project, "present-ab")
    assert presented_ab.returncode == 0, presented_ab.stdout + presented_ab.stderr
    requested = run(
        project,
        "request-revision",
        "--page",
        "S01",
        "--base",
        base_version,
        "--note",
        "Make the evidence relationship clearer",
    )
    assert requested.returncode == 0, requested.stdout + requested.stderr
    active = json.loads(
        receipt_path(project, "S01", "revision-active").read_text(encoding="utf-8")
    )
    revision_id = str(active["revision_id"])
    prepared = run(project, "prepare-authoring", "--page", "S01")
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    revision = project / "svg_working" / "S01" / f"{revision_id}.svg"
    revision.write_text(
        svg(revision_color, '<circle cx="700" cy="300" r="80" fill="#FFE600"/>'),
        encoding="utf-8",
    )
    completed = run(
        project,
        "page-author-result",
        "--result-json",
        json.dumps({
            "status": "COMPLETE",
            "route": "page-svg-authoring",
            "artifact_path": str(revision.resolve()),
        }),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    presented_revision = run(project, "present-revision")
    assert (
        presented_revision.returncode == 0
    ), presented_revision.stdout + presented_revision.stderr
    return revision_id


def setup_batch_ab(project: Path) -> None:
    first = framework("Content locked").replace(
        "- Review mode: Page-by-page", "- Review mode: Batch"
    )
    second = framework("Content locked", slide_id="S02").replace(
        "- Review mode: Page-by-page", "- Review mode: Batch"
    )
    second = second[second.index("### S02｜") :]
    framework_text = first.rstrip() + "\n\n" + second
    (project / "framework.md").write_text(framework_text, encoding="utf-8")

    first_content = content("S01")
    second_content = content("S02")
    second_content = second_content[second_content.index("## S02｜") :]
    combined_content = first_content.rstrip() + "\n\n" + second_content
    (project / "content.md").write_text(combined_content, encoding="utf-8")

    for page in page_entries(framework_text):
        slide_id = page.slide_id
        start = combined_content.index(f"## {slide_id}｜")
        next_start = combined_content.find("\n## S", start + 1)
        section = combined_content[start:] if next_start < 0 else combined_content[start:next_start]
        section = section.rstrip() + "\n"
        write_json(receipt_path(project, slide_id, "content"), {
            "slide_id": slide_id,
            "content_sha256": text_sha256(section),
            "approval_note": "approved",
        })
        packet = ensure_authoring_packet(framework_text, project, page)
        root = project / "svg_working" / slide_id
        root.mkdir(parents=True, exist_ok=True)
        a = root / "A.svg"
        b = root / "B.svg"
        a.write_text(svg("#FFE600", slide_id=slide_id), encoding="utf-8")
        b.write_text(svg("#188CE5", slide_id=slide_id), encoding="utf-8")
        for version, artifact in (("A", a), ("B", b)):
            terminal_result = {
                "status": "COMPLETE",
                "route": "page-svg-authoring",
                "artifact_path": str(artifact.resolve()),
            }
            if version == "B":
                terminal_result["material_differences"] = ["Different emphasis treatment"]
            write_json(receipt_path(project, slide_id, f"{version}-authoring"), {
                "status": "COMPLETE",
                "route": "page-svg-authoring",
                "slide_id": slide_id,
                "authoring_mode": "Standard",
                "version": version,
                "artifact_path": str(artifact.resolve()),
                "artifact_sha256": sha256(artifact),
                "packet_path": packet["packet_path"],
                "packet_sha256": packet["packet_sha256"],
                "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
                "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
                "preflight_gate": {
                    "schema": "ey-deck.page-preflight.v2",
                    "status": "PASS",
                    "artifact_sha256": sha256(artifact),
                    "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
                    "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
                },
                "active": False,
                "terminal_result": terminal_result,
            })


def prepare_authoring(project: Path, slide_id: str = "S01") -> subprocess.CompletedProcess[str]:
    return run(project, "prepare-authoring", "--page", slide_id)


def prepare_export(project: Path) -> subprocess.CompletedProcess[str]:
    if not (project / "working" / "receipts" / "stage2-runtime.json").is_file():
        doctor = run(project, "doctor")
        if doctor.returncode != 0:
            return doctor
    return run(project, "prepare-export")


def run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["EY_PREVIEW_RENDERER"] = str(FAKE_RENDERER)
    env["EY_BUNDLED_PYTHON"] = str(FAKE_BUNDLED_PYTHON)
    env["EY_BUNDLE_VERSION"] = "test-bundle"
    return subprocess.run(
        [sys.executable, str(CONTROLLER), *args, "framework.md", "--project-dir", str(project)],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_canonical(
    project: Path,
    *args: str,
    env_overrides: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["EY_PREVIEW_RENDERER"] = str(FAKE_RENDERER)
    env["EY_BUNDLED_PYTHON"] = str(FAKE_BUNDLED_PYTHON)
    env["EY_BUNDLE_VERSION"] = "test-bundle"
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, str(CONTROLLER), *args, "--project-dir", str(project)],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def protected_framework() -> str:
    return (
        framework("Protected placeholder")
        .replace("- Page type: Standard content", "- Page type: Protected placeholder")
        .replace("- Authoring mode: Standard", "- Authoring mode: Not applicable")
        .replace("- Content scope: Evidence and action", "- Content scope: [占位：插入用户批准的受保护页面；AI不得生成、改写或补充]")
        .replace("- Confirmed version: Pending", "- Confirmed version: Not applicable")
    )


class LightweightWorkflowTests(unittest.TestCase):
    def test_initial_authoring_mode_mapping(self) -> None:
        self.assertEqual(initial_authoring_mode("Simplified", "Standard content"), "Simplified")
        self.assertEqual(initial_authoring_mode("Standard", "Cover"), "Simplified")
        self.assertEqual(initial_authoring_mode("Standard", "Agenda"), "Simplified")
        self.assertEqual(initial_authoring_mode("Standard", "Section divider"), "Simplified")
        self.assertEqual(initial_authoring_mode("Standard", "Chart-led"), "Standard")
        self.assertEqual(
            initial_authoring_mode("Simplified", "Protected placeholder"),
            "Not applicable",
        )

    def test_new_multi_page_storyline_requires_opening_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework.md"
            first = framework("Not started", version="3.9")
            second = framework("Not started", version="3.9", slide_id="S02")
            second = second[second.index("### S02｜") :]
            path.write_text(first.rstrip() + "\n\n" + second, encoding="utf-8")
            errors = validate_framework(path, None)
            self.assertTrue(any("requires one opening Cover at S01" in item for item in errors))

    def test_long_storyline_requires_agenda_and_divider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework.md"
            cover = (
                framework("Not started", version="3.9")
                .replace("- Page type: Standard content", "- Page type: Cover")
                .replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            )
            pages = [cover.rstrip()]
            for index in range(2, 8):
                slide_id = f"S{index:02d}"
                page = framework("Not started", version="3.9", slide_id=slide_id)
                pages.append(page[page.index(f"### {slide_id}｜") :].rstrip())
            path.write_text("\n\n".join(pages) + "\n", encoding="utf-8")
            errors = validate_framework(path, None)
            self.assertTrue(any("requires an Agenda" in item for item in errors))
            self.assertTrue(any("requires at least one Section divider" in item for item in errors))

    def test_sequential_loop_selects_first_unfinished_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            cover = (
                framework("Not started")
                .replace("- Page type: Standard content", "- Page type: Cover")
                .replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            )
            second = framework("Not started", slide_id="S02")
            second = second[second.index("### S02｜") :]
            text = cover.rstrip() + "\n\n" + second
            action, pages = directive(text, project)
            self.assertEqual(action, "PRESENT_PAGE_REVIEW")
            self.assertEqual([page.slide_id for page in pages], ["S01"])

            advanced = text.replace(
                "- Status: Not started",
                "- Status: SVG confirmed",
                1,
            ).replace(
                "- Confirmed version: Pending",
                "- Confirmed version: A",
                1,
            )
            action, pages = directive(advanced, project)
            self.assertEqual(action, "PRESENT_PAGE_REVIEW")
            self.assertEqual([page.slide_id for page in pages], ["S02"])

    def test_mixed_batch_metadata_does_not_override_slide_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first = (
                framework("Awaiting SVG decision")
                .replace("- Review mode: Page-by-page", "- Review mode: Batch")
                .replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            )
            second = framework(
                "Awaiting SVG decision", slide_id="S02"
            ).replace("- Review mode: Page-by-page", "- Review mode: Batch")
            second = second[second.index("### S02｜") :]
            text = first.rstrip() + "\n\n" + second

            payload = directive_payload(text, project, CONTROLLER)

            self.assertEqual(payload["action"], "COLLECT_SVG_DECISION")
            self.assertEqual(payload["pages"], ["S01"])
            self.assertIn("single A preview", payload["command_when"])
            self.assertEqual(
                payload["decision_requirements"],
                [
                    {
                        "slide_id": "S01",
                        "authoring_mode": "Simplified",
                        "required_display": "single-A-preview",
                        "allowed_selections": ["A"],
                        "allowed_repair_versions": ["A"],
                    }
                ],
            )
            simplified_repair = payload["commands"]["repair_before_user_display"]
            self.assertIn("--page S01 --version A", simplified_repair)
            self.assertNotIn("<A_OR_B>", simplified_repair)
            self.assertIn(
                "--selections S01=A",
                payload["commands"]["after_confirmation_or_selection"],
            )

    def test_sequential_simplified_repair_command_never_allows_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first = (
                framework("Awaiting SVG decision")
                .replace("- Review mode: Page-by-page", "- Review mode: Batch")
                .replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            )
            second = (
                framework("Awaiting SVG decision", slide_id="S02")
                .replace("- Review mode: Page-by-page", "- Review mode: Batch")
                .replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            )
            second = second[second.index("### S02｜") :]
            text = first.rstrip() + "\n\n" + second

            payload = directive_payload(text, project, CONTROLLER)

            repair = payload["commands"]["repair_before_user_display"]
            self.assertIn("--page S01 --version A", repair)
            self.assertNotIn("<A_OR_B>", repair)
            self.assertEqual(
                [item["allowed_selections"] for item in payload["decision_requirements"]],
                [["A"]],
            )

    def test_simplified_page_skips_b_and_confirms_single_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            framework_path = project / "framework.md"
            simplified = framework_path.read_text(encoding="utf-8").replace(
                "- Requested authoring mode: Standard",
                "- Requested authoring mode: Simplified",
            ).replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            framework_path.write_text(simplified, encoding="utf-8")

            self.assertEqual(prepare_authoring(project).returncode, 0)
            a_path = project / "svg_working" / "S01" / "A.svg"
            a_path.parent.mkdir(parents=True, exist_ok=True)
            a_path.write_text(svg(), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(a_path.resolve()),
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(run(project, "next", "--format", "json").stdout)
            self.assertEqual(payload["action"], "PRESENT_SINGLE_OPTION")
            self.assertFalse((a_path.parent / "B.svg").exists())

            presented = run(project, "present-single")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertTrue(single_presentation_valid(project, "S01"))
            payload = json.loads(run(project, "next", "--format", "json").stdout)
            self.assertEqual(payload["action"], "COLLECT_SVG_DECISION")
            self.assertIn("S01=A", payload["commands"]["after_confirmation_or_selection"])

            rejected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=B",
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Simplified confirmation must use A", rejected.stdout)

            confirmed = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            final_framework = framework_path.read_text(encoding="utf-8")
            self.assertIn("- Status: SVG confirmed", final_framework)
            self.assertIn("- Confirmed version: A", final_framework)
            self.assertTrue(receipt_path(project, "S01", "svg-decision").is_file())

    def test_framework_rejects_duplicate_fields_and_unmanaged_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework.md"
            path.write_text(
                framework().replace(
                    "- Status: Content locked",
                    "- Status: Not started\n- Status: Content locked",
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("duplicate field: Status" in error for error in validate_framework(path, None)))
            path.write_text(
                framework().replace(
                    "## Design hard rules",
                    "## Unmanaged duplicate memory\n- Rule: stale\n\n## Design hard rules",
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("exactly these H2 sections" in error for error in validate_framework(path, None)))

    def test_framework_rejects_multiple_covers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "framework.md"
            first = framework("Not started").replace(
                "- Page type: Standard content", "- Page type: Cover"
            )
            page = first[first.index("### S01｜"):].replace("S01", "S02")
            path.write_text(first.rstrip() + "\n\n" + page, encoding="utf-8")
            errors = validate_framework(path, None)
            self.assertTrue(any("only one Cover" in error for error in errors))

    def test_init_requires_successful_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(framework("Not started"), encoding="utf-8")
            blocked = run(project, "init")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("run controller doctor", blocked.stdout)
            doctor = run(project, "doctor")
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            doctor_receipt = json.loads(
                (project / "working" / "receipts" / "environment-doctor.json").read_text()
            )
            self.assertEqual(
                doctor_receipt["checks"]["preview"]["chromium_executable"],
                str(FAKE_RENDERER),
            )
            self.assertEqual(
                doctor_receipt["checks"]["stage2_runtime"]["bundled_python"],
                str(FAKE_BUNDLED_PYTHON),
            )
            self.assertIn("ey_export_runtime", doctor_receipt["checks"])
            self.assertNotIn("ppt_master_skill", doctor_receipt["checks"])
            self.assertTrue((project / "working" / "receipts" / "preview-runtime.json").is_file())
            self.assertTrue((project / "working" / "receipts" / "stage2-runtime.json").is_file())
            initialized = run(project, "init")
            self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
            self.assertTrue((project / "AGENTS.md").is_file())

    def test_bootstrap_combines_doctor_init_and_next_directive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(framework("Not started"), encoding="utf-8")
            result = run(project, "bootstrap")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue(
                (project / "working" / "receipts" / "environment-doctor.json").is_file()
            )
            self.assertIn("NEXT_DIRECTIVE_JSON", result.stdout)
            self.assertIn('"action": "PRESENT_PAGE_REVIEW"', result.stdout)

    def test_canonical_cli_infers_framework_and_returns_structured_review_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(framework("Not started"), encoding="utf-8")
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True, exist_ok=True)
            provisional.write_text(content(), encoding="utf-8")
            next_result = run_canonical(project, "next", "--format", "json")
            self.assertEqual(next_result.returncode, 0, next_result.stdout + next_result.stderr)
            payload = json.loads(next_result.stdout)
            self.assertIn("present-review", payload["commands"]["run"])
            self.assertNotIn("framework.md", payload["commands"]["run"])
            self.assertNotIn("validation_command", payload)
            self.assertEqual(payload["provisional_content"]["write_mode"], "replace")
            self.assertEqual(payload["provisional_content"]["expected_pages"], ["S01"])
            self.assertEqual(
                payload["provisional_content"]["path"], str(provisional.resolve())
            )
            self.assertEqual(
                payload["review_context"]["project_context"]["Deliverable name"],
                "Test deck",
            )
            self.assertEqual(payload["review_context"]["target_pages"][0]["slide_id"], "S01")
            validated = run_canonical(project, "validate-review")
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            self.assertIn("S01", validated.stdout)

            low_level = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_deck_blueprint.py"),
                    "--content",
                    str(provisional),
                    "--framework",
                    str(project / "framework.md"),
                    "--page",
                    "S01",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(low_level.returncode, 0, low_level.stdout + low_level.stderr)

    def test_doctor_bound_preview_runtime_ignores_later_discovery_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            self.assertEqual(run_canonical(project, "doctor").returncode, 0)
            setup_ab(project)
            presented = run_canonical(
                project,
                "present-ab",
                env_overrides={"EY_PREVIEW_RENDERER": "/missing/renderer"},
            )
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("A/B design choice", presented.stdout)

    def test_output_filename_updates_through_controller(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(framework("Not started"), encoding="utf-8")
            updated = run(
                project,
                "set-output-filename",
                "--filename",
                "Leadership final.pptx",
            )
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            self.assertIn(
                "- Output filename: Leadership final.pptx",
                (project / "framework.md").read_text(encoding="utf-8"),
            )

    def test_page_authoring_mode_can_change_before_svg_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(
                framework("Not started"), encoding="utf-8"
            )
            updated = run(
                project,
                "update-page",
                "--page",
                "S01",
                "--authoring-mode",
                "Simplified",
            )
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            self.assertIn(
                "- Authoring mode: Simplified",
                (project / "framework.md").read_text(encoding="utf-8"),
            )

    def test_locked_page_requires_explicit_authoring_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            framework_path = setup_locked(project)
            action, pages = directive(framework_path.read_text(encoding="utf-8"), project)
            self.assertEqual(action, "PREPARE_SVG_A")
            self.assertEqual([page.slide_id for page in pages], ["S01"])

    def test_next_is_read_only_and_prepare_materializes_authoring_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            result = run(project, "next", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action"], "PREPARE_SVG_A")
            self.assertEqual(payload["pages"], ["S01"])
            self.assertIn("prepare-authoring", payload["commands"]["run"])
            self.assertFalse((project / "working" / "packets" / "S01-authoring.md").exists())
            prepared = prepare_authoring(project)
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            self.assertTrue((project / "svg_working" / "S01").is_dir())
            payload = json.loads(run(project, "next", "--format", "json").stdout)
            self.assertEqual(payload["action"], "GENERATE_SVG_A")
            self.assertIn("page-author-result", payload["commands"]["record_result"])
            packet = Path(payload["packet_path"])
            self.assertTrue(packet.is_file())
            self.assertEqual(payload["packet_sha256"], sha256(packet))
            self.assertEqual(payload["template_layout"], "content")
            prototype = Path(payload["template_prototype"])
            self.assertTrue(prototype.is_file())
            self.assertEqual(payload["template_prototype_sha256"], sha256(prototype))
            self.assertNotIn("Evidence supports action", result.stdout)

    def test_present_ab_uses_standalone_local_image_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            presented = run(project, "present-ab")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("### A｜EY option A", presented.stdout)
            self.assertIn("### B｜EY option B", presented.stdout)
            self.assertRegex(presented.stdout, r"(?m)^!\[S01 A PNG preview\]\(<.*\.png>\)$")
            self.assertRegex(presented.stdout, r"(?m)^!\[S01 B PNG preview\]\(<.*\.png>\)$")
            self.assertNotIn("| A｜EY option A | B｜EY option B |", presented.stdout)
            self.assertNotRegex(presented.stdout, r"(?m)^\|.*PNG preview.*\|$")

    def test_provisional_content_is_promoted_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(framework("Not started"), encoding="utf-8")
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True)
            provisional.write_text(content(), encoding="utf-8")
            presented = run(project, "present-review")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            approved = run(
                project,
                "advance",
                "--event",
                "content-approved",
                "--page",
                "S01",
                "--note",
                "Approved exactly as shown",
            )
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            self.assertEqual((project / "content.md").read_text(encoding="utf-8"), content())
            self.assertFalse(provisional.exists())
            updated = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Status: Content locked", updated)
            self.assertIn("- Open items: None", updated)

    def test_provisional_page_mismatch_reports_expected_found_and_replace_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            framework_path = project / "framework.md"
            page_two = framework("Not started", slide_id="S02")
            page_two = page_two[page_two.index("### S02｜") :]
            framework_path.write_text(
                framework_path.read_text(encoding="utf-8").rstrip()
                + "\n\n"
                + page_two,
                encoding="utf-8",
            )
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            selected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            provisional = project / "working" / "provisional-content.md"
            provisional.parent.mkdir(parents=True, exist_ok=True)
            stale = content("S01").rstrip() + "\n\n" + content("S02")
            provisional.write_text(stale, encoding="utf-8")

            blocked = run(project, "present-review")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("expected S02; found S01,S02", blocked.stdout)
            self.assertIn("replace the entire file instead of appending", blocked.stdout)

            provisional.write_text(content("S02"), encoding="utf-8")
            presented = run(project, "present-review")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)

    def test_page_author_block_is_recorded_and_environment_retry_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            self.assertEqual(prepare_authoring(project).returncode, 0)
            blocked = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "BLOCKED",
                    "route": "page-svg-authoring",
                    "stage": "authoring",
                    "slide_ids": ["S01"],
                    "reason": "renderer unavailable",
                    "repair_scope": "environment",
                    "resume_from": "retry A",
                }),
            )
            self.assertEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
            self.assertIn("RESOLVE_PAGE_AUTHOR_BLOCK", blocked.stdout)
            resumed = run(project, "resume-page-author", "--page", "S01")
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            self.assertIn("GENERATE_SVG_A", resumed.stdout)

    def test_page_author_complete_results_flow_into_controller_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            self.assertEqual(prepare_authoring(project).returncode, 0)
            root = project / "svg_working" / "S01"
            self.assertTrue(root.is_dir())
            a = root / "A.svg"
            a.write_text(svg("#FFE600"), encoding="utf-8")
            recorded_a = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(a.resolve()),
                }),
            )
            self.assertEqual(recorded_a.returncode, 0, recorded_a.stdout + recorded_a.stderr)
            self.assertIn("GENERATE_SVG_B", recorded_a.stdout)
            b = root / "B.svg"
            b.write_text(svg("#188CE5"), encoding="utf-8")
            recorded_b = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(b.resolve()),
                    "material_differences": ["Different emphasis color and hierarchy"],
                }),
            )
            self.assertEqual(recorded_b.returncode, 0, recorded_b.stdout + recorded_b.stderr)
            self.assertIn("PRESENT_AB_OPTIONS", recorded_b.stdout)
            self.assertFalse((root / "ab-manifest.json").exists())

    def test_b_complete_without_material_differences_records_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            self.assertEqual(prepare_authoring(project).returncode, 0)
            root = project / "svg_working" / "S01"
            self.assertTrue(root.is_dir())
            a = root / "A.svg"
            a.write_text(svg("#FFE600"), encoding="utf-8")
            self.assertEqual(run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(a.resolve()),
                }),
            ).returncode, 0)
            b = root / "B.svg"
            b.write_text(svg("#188CE5"), encoding="utf-8")
            recorded = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(b.resolve()),
                }),
            )
            self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)
            self.assertIn("PRESENT_AB_OPTIONS", recorded.stdout)
            receipt = json.loads(
                (project / "working" / "receipts" / "S01-B-authoring.json").read_text()
            )
            self.assertEqual(
                receipt["advisories"],
                ["S01 B result has missing or insufficient material_differences evidence"],
            )

    def test_candidate_boundary_is_small_and_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.svg"
            path.write_text(svg(), encoding="utf-8")
            self.assertEqual(candidate_errors(path), [])
            path.write_text(svg(extra='<image href="https://example.com/a.png"/>'), encoding="utf-8")
            self.assertTrue(any("not self-contained" in item for item in candidate_errors(path)))

    def test_present_and_select_promotes_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            presented = run(project, "present-ab")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("A/B design choice", presented.stdout)
            preview_receipt = json.loads(
                (project / "svg_working" / "S01" / "preview" / "A.json").read_text()
            )
            self.assertEqual(preview_receipt["schema_version"], "ey-deck.preview-binding.v3")
            self.assertEqual(preview_receipt["chromium_executable"], str(FAKE_RENDERER))
            selected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=B",
            )
            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            updated = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Status: SVG confirmed", updated)
            self.assertEqual(
                (project / "svg_output" / "S01.svg").read_bytes(),
                (project / "svg_working" / "S01" / "B.svg").read_bytes(),
            )
            self.assertTrue(receipt_path(project, "S01", "svg-decision").is_file())

    def test_selection_json_has_no_ambiguous_primary_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            result = run(project, "next", "--format", "json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action"], "COLLECT_SVG_DECISION")
            self.assertNotIn("command", payload)
            self.assertEqual(
                set(payload["commands"]),
                {
                    "repair_before_user_display",
                    "after_confirmation_or_selection",
                    "for_targeted_changes",
                },
            )
            self.assertEqual(
                payload["commands"]["after_confirmation_or_selection"].count("--page S01"),
                1,
            )
            self.assertFalse(receipt_path(project, "S01", "svg-qa").exists())

    def test_pre_display_candidate_defect_reauthors_same_b_slot_without_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            a_path = project / "svg_working" / "S01" / "A.svg"
            a_hash = sha256(a_path)
            self.assertEqual(run(project, "present-ab").returncode, 0)

            repaired = run(
                project,
                "repair-candidate",
                "--page",
                "S01",
                "--version",
                "B",
                "--note",
                "Title and subtitle overlap",
            )
            self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
            self.assertEqual(sha256(a_path), a_hash)
            self.assertTrue(receipt_path(project, "S01", "A-authoring").is_file())
            self.assertFalse((project / "svg_working" / "S01" / "B.svg").exists())
            self.assertFalse(receipt_path(project, "S01", "B-authoring").exists())
            self.assertFalse(receipt_path(project, "S01", "ab-presentation").exists())
            self.assertTrue((project / "svg_working" / "S01" / "preview" / "A.json").is_file())
            self.assertFalse((project / "svg_working" / "S01" / "preview" / "B.json").exists())
            self.assertFalse(list((project / "svg_working" / "S01").glob("R*.svg")))
            self.assertFalse(list((project / "working" / "receipts").glob("S01-R*.json")))

            next_result = run(project, "next", "--format", "json")
            self.assertEqual(next_result.returncode, 0, next_result.stdout + next_result.stderr)
            self.assertEqual(json.loads(next_result.stdout)["action"], "GENERATE_SVG_B")

            b_path = project / "svg_working" / "S01" / "B.svg"
            b_path.write_text(svg("#35A36F"), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(b_path.resolve()),
                    "material_differences": ["Repaired B keeps a distinct emphasis treatment"],
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            presented = run(project, "present-ab")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            self.assertIn("### A｜EY option A", presented.stdout)
            self.assertIn("### B｜EY option B", presented.stdout)
            self.assertFalse(list((project / "svg_working" / "S01").glob("R*.svg")))
            self.assertFalse(list((project / "working" / "receipts").glob("S01-R*.json")))

    def test_later_batch_page_cannot_be_repaired_before_current_page_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_batch_ab(project)
            presented = run(project, "present-ab")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)

            selectable = run(project, "next", "--format", "json")
            self.assertEqual(selectable.returncode, 0, selectable.stdout + selectable.stderr)
            payload = json.loads(selectable.stdout)
            self.assertEqual(payload["pages"], ["S01"])
            self.assertIn("--page S01", payload["commands"]["repair_before_user_display"])

            repaired = run(
                project,
                "repair-candidate",
                "--page",
                "S02",
                "--version",
                "B",
                "--note",
                "S02 title overlap",
            )
            self.assertNotEqual(repaired.returncode, 0)
            self.assertIn("S02 is not in the active page group", repaired.stdout)
            framework_text = (project / "framework.md").read_text(encoding="utf-8")
            self.assertEqual(framework_text.count("- Status: Content locked"), 1)
            self.assertEqual(framework_text.count("- Status: Awaiting SVG decision"), 1)
            self.assertTrue(receipt_path(project, "S01", "ab-presentation").exists())
            self.assertFalse(receipt_path(project, "S02", "ab-presentation").exists())

            next_result = run(project, "next", "--format", "json")
            self.assertEqual(next_result.returncode, 0, next_result.stdout + next_result.stderr)
            next_payload = json.loads(next_result.stdout)
            self.assertEqual(next_payload["action"], "COLLECT_SVG_DECISION")
            self.assertEqual(next_payload["pages"], ["S01"])

            confirmed = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            ready = run(project, "next", "--format", "json")
            self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
            ready_payload = json.loads(ready.stdout)
            self.assertEqual(ready_payload["action"], "PRESENT_AB_OPTIONS")
            self.assertEqual(ready_payload["pages"], ["S02"])

    def test_deleted_preview_blocks_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            self.assertTrue(ab_presentation_valid(project, "S01"))
            preview_receipt = json.loads(
                (project / "svg_working" / "S01" / "preview" / "A.json").read_text()
            )
            (project / preview_receipt["preview_png"]).unlink()
            self.assertFalse(ab_presentation_valid(project, "S01"))
            selected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertNotEqual(selected.returncode, 0)
            self.assertFalse((project / "svg_output" / "S01.svg").exists())

    def test_targeted_revision_can_be_confirmed_without_qa_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            requested = run(
                project,
                "request-revision",
                "--page",
                "S01",
                "--base",
                "A",
                "--note",
                "Make the evidence relationship clearer",
            )
            self.assertEqual(requested.returncode, 0, requested.stdout + requested.stderr)
            prepared = run(project, "prepare-authoring", "--page", "S01")
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            revision = project / "svg_working" / "S01" / "R1.svg"
            revision.write_text(svg("#FFFACC", '<circle cx="700" cy="300" r="80" fill="#FFE600"/>'), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(revision.resolve()),
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            presented = run(project, "present-revision")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)
            confirmed = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=R1",
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
            self.assertIn("- Confirmed version: R1", (project / "framework.md").read_text())
            request = json.loads(
                receipt_path(project, "S01", "R1-request").read_text()
            )
            self.assertEqual(request["resolution"], "revision-confirmed")
            self.assertEqual(request["selected_version"], "R1")

    def test_targeted_revision_base_can_be_retained_from_displayed_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            revision_id = setup_presented_revision(project)

            payload = json.loads(run(project, "next", "--format", "json").stdout)
            self.assertEqual(payload["action"], "COLLECT_REVISION_CONFIRMATION")
            self.assertEqual(payload["user_display"]["allowed_selections"], ["A", revision_id])
            self.assertIn("S01=A", payload["commands"]["after_keep_base"])
            self.assertIn(
                f"S01={revision_id}", payload["commands"]["after_confirmation"]
            )

            retained = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertEqual(retained.returncode, 0, retained.stdout + retained.stderr)
            self.assertIn("- Confirmed version: A", (project / "framework.md").read_text())
            self.assertEqual(
                (project / "svg_output" / "S01.svg").read_bytes(),
                (project / "svg_working" / "S01" / "A.svg").read_bytes(),
            )
            request = json.loads(
                receipt_path(project, "S01", f"{revision_id}-request").read_text()
            )
            self.assertFalse(request["active"])
            self.assertEqual(request["resolution"], "base-retained")
            self.assertEqual(request["selected_version"], "A")
            decision = json.loads(
                receipt_path(project, "S01", "svg-decision").read_text()
            )
            self.assertEqual(
                decision["presentation_receipt"],
                f"working/receipts/S01-{revision_id}-presentation.json",
            )

    def test_revision_confirmation_rejects_version_outside_displayed_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_presented_revision(project)
            rejected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=B",
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("displayed Base A or active Revision R1", rejected.stdout)
            self.assertFalse((project / "svg_output" / "S01.svg").exists())
            active = json.loads(
                receipt_path(project, "S01", "revision-active").read_text()
            )
            self.assertTrue(active["active"])

    def test_revision_base_retention_rejects_stale_presentation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_presented_revision(project)
            base = project / "svg_working" / "S01" / "A.svg"
            base.write_text(svg("#A6A6A6"), encoding="utf-8")
            rejected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((project / "svg_output" / "S01.svg").exists())

    def test_chained_revision_can_retain_current_base_but_not_older_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first_revision = setup_presented_revision(project)
            requested = run(
                project,
                "request-revision",
                "--page",
                "S01",
                "--base",
                first_revision,
                "--note",
                "Reduce the visual emphasis",
            )
            self.assertEqual(requested.returncode, 0, requested.stdout + requested.stderr)
            active = json.loads(
                receipt_path(project, "S01", "revision-active").read_text()
            )
            second_revision = str(active["revision_id"])
            revision = project / "svg_working" / "S01" / f"{second_revision}.svg"
            revision.write_text(svg("#D9D9D9"), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(revision.resolve()),
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            presented = run(project, "present-revision")
            self.assertEqual(presented.returncode, 0, presented.stdout + presented.stderr)

            rejected = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertNotEqual(rejected.returncode, 0)
            retained = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                f"S01={first_revision}",
            )
            self.assertEqual(retained.returncode, 0, retained.stdout + retained.stderr)
            self.assertIn(
                f"- Confirmed version: {first_revision}",
                (project / "framework.md").read_text(),
            )

    def test_simplified_revision_can_retain_displayed_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            framework_path = setup_locked(project)
            simplified = framework_path.read_text(encoding="utf-8").replace(
                "- Requested authoring mode: Standard",
                "- Requested authoring mode: Simplified",
            ).replace("- Authoring mode: Standard", "- Authoring mode: Simplified")
            framework_path.write_text(simplified, encoding="utf-8")

            self.assertEqual(prepare_authoring(project).returncode, 0)
            a_path = project / "svg_working" / "S01" / "A.svg"
            a_path.parent.mkdir(parents=True, exist_ok=True)
            a_path.write_text(svg(), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(a_path.resolve()),
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(run(project, "present-single").returncode, 0)
            requested = run(
                project,
                "request-revision",
                "--page",
                "S01",
                "--base",
                "A",
                "--note",
                "Reduce the emphasis",
            )
            self.assertEqual(requested.returncode, 0, requested.stdout + requested.stderr)
            self.assertEqual(prepare_authoring(project).returncode, 0)
            revision = project / "svg_working" / "S01" / "R1.svg"
            revision.write_text(svg("#D9D9D9"), encoding="utf-8")
            completed = run(
                project,
                "page-author-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(revision.resolve()),
                }),
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(run(project, "present-revision").returncode, 0)
            retained = run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            )
            self.assertEqual(retained.returncode, 0, retained.stdout + retained.stderr)
            decision = json.loads(
                receipt_path(project, "S01", "svg-decision").read_text()
            )
            self.assertEqual(decision["authoring_mode"], "Simplified")
            self.assertEqual(decision["confirmed_version"], "A")

    def test_confirmed_page_is_bound_only_to_selection_and_canonical_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            self.assertEqual(run(
                project, "advance", "--event", "svg-confirmed", "--page", "S01",
                "--selections", "S01=A",
            ).returncode, 0)
            text = (project / "framework.md").read_text(encoding="utf-8")
            self.assertEqual(artifact_errors(text, project), [])
            (project / "svg_output" / "S01.svg").write_text(svg("#A6A6A6"), encoding="utf-8")
            self.assertTrue(any("canonical SVG changed" in item for item in artifact_errors(text, project)))

    def test_confirmed_body_page_hands_off_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            self.assertEqual(run(
                project, "advance", "--event", "svg-confirmed", "--page", "S01",
                "--selections", "S01=A",
            ).returncode, 0)
            result = run(project, "next")
            self.assertIn("STAGE_1_COMPLETE", result.stdout)
            self.assertNotIn("CHECKPOINT", result.stdout)
            self.assertEqual(prepare_export(project).returncode, 0)
            payload = json.loads(run(project, "next", "--format", "json").stdout)
            manifest = json.loads(Path(payload["export_manifest"]).read_text())
            self.assertEqual(manifest["pptx_structure"], "structured")
            self.assertEqual(
                [(item["slide_id"], item["asset_role"]) for item in manifest["ordered_slides"]],
                [("S01", "storyline"), ("EY-END", "fixed-ending")],
            )
            bundle = manifest["template_bundle"]
            self.assertTrue(Path(bundle["structure_manifest_path"]).is_file())

    def test_protected_page_materializes_with_only_identity_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            result = run(project, "materialize-protected")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            canonical = project / "svg_output" / "S01.svg"
            self.assertTrue(canonical.is_file())
            self.assertTrue(receipt_path(project, "S01", "protected").is_file())
            receipts = sorted(path.name for path in (project / "working" / "receipts").glob("S01-*.json"))
            self.assertEqual(receipts, ["S01-protected.json"])
            self.assertIn("STAGE_1_COMPLETE", result.stdout)
            canonical.write_text(svg("#188CE5"), encoding="utf-8")
            self.assertTrue(any("protected canonical SVG" in item for item in artifact_errors(
                (project / "framework.md").read_text(encoding="utf-8"), project
            )))

    def test_invalid_protected_svg_fails_minimum_boundary_without_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            protected = project / "protected_input" / "S01.svg"
            protected.parent.mkdir(parents=True)
            protected.write_text(svg(extra='<image href="https://example.com/a.png"/>'), encoding="utf-8")
            result = run(project, "materialize-protected")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not self-contained", result.stdout)
            self.assertFalse((project / "svg_output" / "S01.svg").exists())

    def test_protected_source_change_invalidates_canonical_and_long_instruction_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            instruction = "[占位：" + "关键要求" * 70 + "；AI不得生成、改写或补充]"
            text = protected_framework().replace(
                "[占位：插入用户批准的受保护页面；AI不得生成、改写或补充]",
                instruction,
            )
            (project / "framework.md").write_text(text, encoding="utf-8")
            materialized = run(project, "materialize-protected")
            self.assertEqual(materialized.returncode, 0, materialized.stdout + materialized.stderr)
            canonical = project / "svg_output" / "S01.svg"
            self.assertIn(instruction, canonical.read_text(encoding="utf-8"))

            source = project / "protected_input" / "S01.svg"
            source.parent.mkdir(parents=True)
            source.write_text(svg("#188CE5"), encoding="utf-8")
            action, pages = directive(text, project)
            self.assertEqual(action, "MATERIALIZE_PROTECTED_PAGES")
            self.assertEqual([page.slide_id for page in pages], ["S01"])

    def test_handoff_complete_is_bound_to_current_svg_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            self.assertEqual(run(project, "materialize-protected").returncode, 0)
            self.assertEqual(prepare_export(project).returncode, 0)
            handoff = run(project, "next", "--format", "json")
            payload = json.loads(handoff.stdout)
            pptx = Path(payload["required_output_path"])
            pptx.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(pptx, "w") as package:
                package.writestr("ppt/slides/slide1.xml", "<slide/>")
                package.writestr("ppt/slides/slide2.xml", "<slide/>")
            valid_pptx = pptx.read_bytes()
            result = run(
                project,
                "handoff-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "confirmed-svg-export",
                    "artifact_path": str(pptx.resolve()),
                }),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("DELIVERY_COMPLETE", result.stdout)
            self.assertIn(str(pptx), result.stdout)
            pptx.write_bytes(b"tampered")
            self.assertIn("STAGE_1_COMPLETE", run(project, "next").stdout)
            pptx.write_bytes(valid_pptx)
            (project / "svg_output" / "S01.svg").write_text(svg("#188CE5"), encoding="utf-8")
            self.assertNotEqual(run(project, "next").returncode, 0)

    def test_handoff_rejects_output_inside_ey_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            self.assertEqual(run(project, "materialize-protected").returncode, 0)
            self.assertEqual(prepare_export(project).returncode, 0)
            wrong = project / "Test deck.pptx"
            wrong.write_bytes(b"wrong-location")
            rejected = run(
                project,
                "handoff-result",
                "--result-json",
                json.dumps({
                    "status": "COMPLETE",
                    "route": "confirmed-svg-export",
                    "artifact_path": str(wrong.resolve()),
                }),
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("manifest output path", rejected.stdout)

    def test_stage_one_handoff_defines_bundled_runner_and_path_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            self.assertEqual(run(project, "materialize-protected").returncode, 0)
            result = run(project, "next", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action"], "PREPARE_CONFIRMED_EXPORT")
            self.assertIn("prepare-export", payload["commands"]["run"])
            prepared = prepare_export(project)
            self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
            result = run(project, "next", "--format", "json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action"], "RUN_CONFIRMED_EXPORT")
            self.assertEqual(payload["route"], "$ey-deck-design / Confirmed SVG Export")
            self.assertIn("bundled deterministic", payload["executor"])
            self.assertTrue(Path(payload["export_manifest"]).is_file())
            self.assertEqual(
                payload["runner_command"][0],
                str(FAKE_BUNDLED_PYTHON),
            )
            self.assertTrue(payload["required_output_path"].endswith("Test deck.pptx"))
            self.assertNotIn("svg_paths", payload)
            self.assertIn("handoff-result", result.stdout)

            payload = json.loads(run(project, "next", "--format", "json").stdout)
            manifest_path = Path(payload["export_manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "ey-deck.confirmed-svg-export.v4")
            self.assertEqual(manifest["pptx_structure"], "flat")
            self.assertEqual(manifest["ordered_slides"][-1]["slide_id"], "EY-END")
            self.assertEqual(manifest["ordered_slides"][-1]["asset_role"], "fixed-ending")
            self.assertEqual(
                manifest["runtime_bindings"]["bundled_python"],
                str(FAKE_BUNDLED_PYTHON),
            )
            validator = Path(manifest["terminal_result_contract"]["validator_path"])
            self.assertTrue(validator.is_file())
            self.assertNotIn("json_schema_path", manifest["terminal_result_contract"])
            invalid = subprocess.run(
                [
                    sys.executable,
                    str(validator),
                    "--manifest",
                    str(manifest_path),
                    "--result-json",
                    json.dumps({
                        "status": "BLOCKED",
                        "route": "confirmed-svg-export",
                        "stage": "export",
                        "slide_ids": [],
                        "reason": "runtime unavailable",
                        "repair_scope": "environment",
                        "resume_from": "retry export",
                    }),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("non-empty slide_ids", invalid.stdout)

    def test_environment_handoff_block_retries_without_reopening_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            self.assertEqual(run(project, "materialize-protected").returncode, 0)
            self.assertEqual(prepare_export(project).returncode, 0)
            blocked = run(
                project,
                "handoff-result",
                "--result-json",
                json.dumps({
                    "status": "BLOCKED",
                    "route": "confirmed-svg-export",
                    "stage": "export",
                    "slide_ids": ["S01"],
                    "reason": "output directory unavailable",
                    "repair_scope": "environment",
                    "resume_from": "retry export",
                }),
            )
            self.assertEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
            self.assertIn("RESOLVE_HANDOFF_BLOCK", blocked.stdout)
            resumed = run(project, "resume-handoff")
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            self.assertIn("STAGE_1_COMPLETE", resumed.stdout)
            self.assertTrue((project / "svg_output" / "S01.svg").is_file())

    def test_source_svg_handoff_reopens_normal_page_without_open_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            setup_locked(project)
            setup_ab(project)
            self.assertEqual(run(project, "present-ab").returncode, 0)
            self.assertEqual(run(
                project,
                "advance",
                "--event",
                "svg-confirmed",
                "--page",
                "S01",
                "--selections",
                "S01=A",
            ).returncode, 0)
            self.assertEqual(prepare_export(project).returncode, 0)
            blocked = run(
                project,
                "handoff-result",
                "--result-json",
                json.dumps({
                    "status": "BLOCKED",
                    "route": "confirmed-svg-export",
                    "stage": "svg-gate",
                    "slide_ids": ["S01"],
                    "reason": "confirmed source requires a technical SVG replacement",
                    "repair_scope": "source-svg",
                    "resume_from": "re-author S01",
                }),
            )
            self.assertEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
            resumed = run(
                project,
                "resume-handoff",
                "--page",
                "S01",
                "--note",
                "replace the source SVG",
            )
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            updated = (project / "framework.md").read_text(encoding="utf-8")
            self.assertIn("- Status: Content locked", updated)
            self.assertIn("- Open items: None", updated)
            self.assertIn("PREPARE_SVG_A", resumed.stdout)

    def test_source_svg_handoff_block_reopens_only_changed_protected_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "framework.md").write_text(protected_framework(), encoding="utf-8")
            protected = project / "protected_input" / "S01.svg"
            protected.parent.mkdir(parents=True)
            protected.write_text(svg("#FFE600"), encoding="utf-8")
            self.assertEqual(run(project, "materialize-protected").returncode, 0)
            self.assertEqual(prepare_export(project).returncode, 0)
            blocked = run(
                project,
                "handoff-result",
                "--result-json",
                json.dumps({
                    "status": "BLOCKED",
                    "route": "confirmed-svg-export",
                    "stage": "svg-gate",
                    "slide_ids": ["S01"],
                    "reason": "confirmed source requires replacement",
                    "repair_scope": "source-svg",
                    "resume_from": "replace S01 and retry",
                }),
            )
            self.assertEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
            unchanged = run(project, "resume-handoff", "--page", "S01", "--note", "replace source")
            self.assertNotEqual(unchanged.returncode, 0)
            protected.write_text(svg("#188CE5"), encoding="utf-8")
            resumed = run(project, "resume-handoff", "--page", "S01", "--note", "replace source")
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            self.assertIn("MATERIALIZE_PROTECTED_PAGES", resumed.stdout)
            rematerialized = run(project, "materialize-protected")
            self.assertEqual(rematerialized.returncode, 0, rematerialized.stdout + rematerialized.stderr)
            self.assertEqual((project / "svg_output" / "S01.svg").read_bytes(), protected.read_bytes())

    def test_migration_resets_inflight_old_selection_and_preserves_old_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "content.md").write_text(content(), encoding="utf-8")
            old = framework("Content locked", "2.7").replace(
                "- Framework version: 2.6", "- Framework version: 2.2"
            ).replace(
                "- Storyline version: 1.0",
                "- Storyline version: 1.0\n"
                "- Final PPTX owner: PPT Master\n"
                "- Final PPTX requirement: legacy requirement\n"
                "- Last checkpoint: None",
            ).replace(
                "- Next connection: None",
                "- Previous connection: None\n- Next connection: None",
            ).replace(
                "- Status: Content locked", "- Status: SVG selected"
            ).replace("- Confirmed version: Pending", "- Confirmed version: A")
            migrated = migrate_workflow(old, project)
            self.assertIn("- Framework version: 2.6", migrated)
            self.assertIn("- Workflow version: 3.8", migrated)
            self.assertNotIn("- Last checkpoint:", migrated)
            self.assertNotIn("- Final PPTX owner:", migrated)
            self.assertNotIn("- Final PPTX requirement:", migrated)
            self.assertNotIn("- Previous connection:", migrated)
            self.assertIn("- Status: Content locked", migrated)
            self.assertIn("- Confirmed version: Pending", migrated)

    def test_migration_initializes_project_and_page_authoring_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            old = (
                framework("Not started")
                .replace("- Framework version: 2.6", "- Framework version: 2.5")
                .replace("- Workflow version: 3.8", "- Workflow version: 3.7")
                .replace("- Requested authoring mode: Standard\n", "")
                .replace("- Page type: Standard content", "- Page type: Cover")
                .replace("- Authoring mode: Standard\n", "")
                .replace("- Confirmed version:", "- Selected version:")
            )
            migrated = migrate_workflow(old, project)
            self.assertIn("- Requested authoring mode: Standard", migrated)
            self.assertIn("- Authoring mode: Simplified", migrated)
            self.assertIn("- Confirmed version: Pending", migrated)
            self.assertNotIn("- Selected version:", migrated)

    def test_migration_preserves_valid_legacy_confirmed_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "content.md").write_text(content(), encoding="utf-8")
            a_path = project / "svg_working" / "S01" / "A.svg"
            final_path = project / "svg_output" / "S01.svg"
            a_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            a_path.write_text(svg(), encoding="utf-8")
            final_path.write_text(svg(), encoding="utf-8")
            old = (
                framework("SVG confirmed")
                .replace("- Framework version: 2.6", "- Framework version: 2.5")
                .replace("- Workflow version: 3.8", "- Workflow version: 3.7")
                .replace("- Requested authoring mode: Standard\n", "")
                .replace("- Authoring mode: Standard\n", "")
                .replace("- Confirmed version:", "- Selected version:")
            )
            migrated = migrate_workflow(old, project)
            (project / "framework.md").write_text(migrated, encoding="utf-8")
            self.assertIn("- Status: SVG confirmed", migrated)
            self.assertIn("- Authoring mode: Standard", migrated)
            self.assertEqual(validate_framework(project / "framework.md", project), [])
            self.assertEqual(artifact_errors(migrated, project), [])

    def test_normal_validation_rejects_legacy_schema_and_migrate_converts_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "content.md").write_text(
                content().replace(
                    "# Presentation Build Specification",
                    "# Proposal Build Specification",
                    1,
                ),
                encoding="utf-8",
            )
            path = project / "framework.md"
            old = legacy_proposal_framework()
            path.write_text(old, encoding="utf-8")
            self.assertTrue(any("run migrate" in item for item in validate_framework(path, None)))

            migrated = migrate_workflow(old, project)
            path.write_text(migrated, encoding="utf-8")
            self.assertEqual(validate_framework(path, None), [])
            self.assertTrue(migrated.startswith("# Presentation Framework\n"))
            self.assertIn("- Deliverable type: Proposal", migrated)
            self.assertIn("Legacy proposal type: Formal RFP response", migrated)
            self.assertNotIn("- Proposal name:", migrated)
            self.assertTrue(
                (project / "content.md").read_text(encoding="utf-8").startswith(
                    "# Presentation Build Specification"
                )
            )

    def test_reindex_dry_run_maps_nonsequential_slide_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            path = project / "framework.md"
            path.write_text(framework("Not started", slide_id="S03"), encoding="utf-8")
            preview = subprocess.run(
                [sys.executable, str(REINDEX), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertIn("S03 -> S01", preview.stdout)

    def test_build_spec_validator_enforces_declared_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid_cases = {
                "old-heading": content().replace(
                    "# Presentation Build Specification", "# Proposal Build Specification", 1
                ),
                "emphasis-style": content().replace(
                    "- Detail: A complete and approved statement for leadership decision-making.",
                    "- Detail: A complete and approved statement for leadership decision-making.\n"
                    "- Emphasis:\n  - “complete”｜闪烁",
                ),
                "source-field": content().replace(
                    "- Source details: No external sources",
                    "- Source details: No external sources\n- License: invented",
                ),
                "hierarchy-level": content().replace(
                    "#### S01-B1｜Evidence", "###### S01-B1｜Evidence"
                ),
            }
            expected_fragments = {
                "old-heading": "compact Deck build profile",
                "emphasis-style": "unsupported Emphasis style",
                "source-field": "Sources has unsupported fields",
                "hierarchy-level": "must use heading level 4",
            }
            for name, value in invalid_cases.items():
                path = root / f"{name}.md"
                path.write_text(value, encoding="utf-8")
                errors = validate_blueprint(path)
                self.assertTrue(
                    any(expected_fragments[name] in item for item in errors),
                    (name, errors),
                )

    def test_terminal_result_validator_rejects_unsupported_fields(self) -> None:
        manifest = {
            "ordered_slides": [{"slide_id": "S01"}],
            "required_output_path": "/tmp/not-created.pptx",
        }
        errors = validate_terminal_result(manifest, {
            "status": "BLOCKED",
            "route": "confirmed-svg-export",
            "stage": "export",
            "reason": "missing dependency",
            "repair_scope": "environment",
            "resume_from": "export",
            "slide_ids": ["S01"],
            "commentary": "not allowed",
        })
        self.assertTrue(any("unsupported fields" in item for item in errors))

    def test_reindex_refreshes_nested_receipt_hashes_for_confirmed_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            framework_path = project / "framework.md"
            framework_path.write_text(framework("SVG confirmed", slide_id="S03"), encoding="utf-8")
            (project / "content.md").write_text(content("S03"), encoding="utf-8")
            working_svg = project / "svg_working" / "S03" / "A.svg"
            working_svg.parent.mkdir(parents=True)
            working_svg.write_text(svg(slide_id="S03"), encoding="utf-8")
            canonical = project / "svg_output" / "S03.svg"
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(working_svg.read_bytes())
            framework_text = framework_path.read_text(encoding="utf-8")
            _, pages = directive(framework_text, project)
            packet = ensure_authoring_packet(framework_text, project, pages[0])
            section = content("S03").split("## S03｜", 1)[1]
            section = "## S03｜" + section
            write_json(receipt_path(project, "S03", "content"), {
                "slide_id": "S03",
                "content_sha256": text_sha256(section.rstrip() + "\n"),
            })
            write_json(receipt_path(project, "S03", "A-authoring"), {
                "status": "COMPLETE",
                "route": "page-svg-authoring",
                "slide_id": "S03",
                "authoring_mode": "Standard",
                "version": "A",
                "artifact_path": str(working_svg.resolve()),
                "artifact_sha256": sha256(working_svg),
                "packet_path": packet["packet_path"],
                "packet_sha256": packet["packet_sha256"],
                "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
                "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
                "preflight_gate": {
                    "schema": "ey-deck.page-preflight.v2",
                    "status": "PASS",
                    "artifact_sha256": sha256(working_svg),
                    "visible_copy_contract_sha256": packet["visible_copy_contract_sha256"],
                    "template_structure_contract_sha256": packet["template_structure_contract_sha256"],
                },
                "active": False,
                "terminal_result": {
                    "status": "COMPLETE",
                    "route": "page-svg-authoring",
                    "artifact_path": str(working_svg.resolve()),
                },
            })
            presentation = receipt_path(project, "S03", "ab-presentation")
            write_json(presentation, {"slide_id": "S03", "historical": True})
            write_json(receipt_path(project, "S03", "svg-decision"), {
                "slide_id": "S03",
                "authoring_mode": "Standard",
                "confirmed_version": "A",
                "confirmed_sha256": sha256(working_svg),
                "presentation_receipt": str(presentation.relative_to(project)),
                "presentation_receipt_sha256": sha256(presentation),
                "canonical_sha256": sha256(canonical),
            })
            applied = subprocess.run(
                [sys.executable, str(REINDEX), str(framework_path), "--apply"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            updated = framework_path.read_text(encoding="utf-8")
            self.assertEqual(validate_framework(framework_path, project), [])
            self.assertEqual(artifact_errors(updated, project), [])


if __name__ == "__main__":
    unittest.main()
