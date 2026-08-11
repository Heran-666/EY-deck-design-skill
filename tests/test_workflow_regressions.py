"""Focused regressions for the current EY Deck Design workflow contract."""

from __future__ import annotations

import ast
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from preview_renderer import preview_paths  # noqa: E402
import workflow_authoring as authoring  # noqa: E402
import workflow_cli  # noqa: E402
import workflow_controller as controller  # noqa: E402
from workflow_copy_contract import (  # noqa: E402
    visible_copy_contract,
    visible_copy_errors,
)
from workflow_doctor import preview_failure_issue  # noqa: E402
from workflow_controller import reopen_pages  # noqa: E402


CONTENT = r"""## S01｜Approved title

### On-slide content
- Title: Approved title
- Subtitle: Approved subtitle
- Core insight: Approved insight

#### S01-B1｜Visible parent
- Child logic（Build-only）: Never render this sentence.

##### S01-B1.1｜Visible child
- Detail: Exact visible detail.
- Emphasis:
  - “visible”｜关键重点

#### S01-B2｜Visible table
- Table purpose（Build-only）: Never render this purpose.

| Header A | Header B |
|---|---|
| Cell A | Cell B \| qualified |

- Table note: Visible note.

### Visual Direction（Build-only）
- Page type: Interpretation
- Visual focus: Never render this direction.
- Information hierarchy: Never render this hierarchy.
- Relationship to preserve: Never render this relationship.
- Fixed constraints: Never render this constraint.
- Avoid: Never render this warning.

### Sources
- On-slide source: Approved source.
- Source details: Never render source details.
"""


class ControllerArchitectureTests(unittest.TestCase):
    def test_public_controller_remains_a_thin_facade(self) -> None:
        source = Path(controller.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertEqual(functions, {"main"})

    def test_cli_uses_explicit_handlers_for_every_public_command(self) -> None:
        expected = {
            "advance",
            "audit",
            "bootstrap",
            "doctor",
            "handoff-result",
            "init",
            "materialize-protected",
            "next",
            "page-author-result",
            "prepare-authoring",
            "prepare-export",
            "present-ab",
            "present-review",
            "present-revision",
            "repair-ab-candidate",
            "request-revision",
            "resume-handoff",
            "resume-page-author",
            "set-output-filename",
            "update-page",
            "validate-review",
        }
        self.assertEqual(set(workflow_cli.COMMAND_HANDLERS), expected)


def annotated_svg(contract: dict, *, extra: str = "") -> str:
    elements = []
    y = 30
    for item in contract["items"]:
        if item["required"]:
            elements.append(
                f'<text data-copy-id="{item["id"]}" x="10" y="{y}">{item["text"]}</text>'
            )
            y += 20
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
        'viewBox="0 0 1280 720">'
        + "".join(elements)
        + extra
        + "</svg>"
    )


class VisibleCopyContractTests(unittest.TestCase):
    def test_contract_includes_visible_fields_and_excludes_build_only(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        texts = {item["text"] for item in contract["items"]}
        self.assertIn("Approved title", texts)
        self.assertIn("Visible parent", texts)
        self.assertIn("Exact visible detail.", texts)
        self.assertIn("Header A", texts)
        self.assertIn("Cell B | qualified", texts)
        self.assertIn("Approved source.", texts)
        self.assertFalse(any("Never render" in text for text in texts))

    def test_exact_annotated_svg_passes(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.svg"
            path.write_text(annotated_svg(contract), encoding="utf-8")
            self.assertEqual([], visible_copy_errors(path, contract))

    def test_unbound_build_only_copy_is_rejected(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.svg"
            path.write_text(
                annotated_svg(contract, extra="<text>Never render this sentence.</text>"),
                encoding="utf-8",
            )
            errors = visible_copy_errors(path, contract)
            self.assertTrue(any("unbound visible SVG text" in error for error in errors))

    def test_changed_and_missing_copy_are_rejected(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        svg = annotated_svg(contract)
        svg = svg.replace("Approved title", "Changed title", 1)
        svg = svg.replace(
            '<text data-copy-id="S01-subtitle" x="10" y="50">Approved subtitle</text>',
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.svg"
            path.write_text(svg, encoding="utf-8")
            errors = visible_copy_errors(path, contract)
            self.assertTrue(any("S01-title changed" in error for error in errors))
            self.assertTrue(any("missing required visible-copy id S01-subtitle" in error for error in errors))


class PagePreflightReuseTests(unittest.TestCase):
    def test_current_receipt_reuses_pass_until_artifact_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifact = project / "A.svg"
            artifact.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"/>',
                encoding="utf-8",
            )
            receipt = project / "authoring.json"
            receipt.write_text("{}", encoding="utf-8")
            artifact_sha256 = controller.sha256(artifact)
            packet = {
                "packet_path": "/bound/packet.md",
                "packet_sha256": "packet-hash",
                "visible_copy_contract_sha256": "copy-hash",
                "visible_copy_contract": {"contract_sha256": "copy-hash"},
            }
            result = {
                "status": "COMPLETE",
                "route": "page-svg-authoring",
                "slide_id": "S01",
                "version": "A",
                "artifact_path": str(artifact.resolve()),
                "artifact_sha256": artifact_sha256,
                "packet_path": packet["packet_path"],
                "packet_sha256": packet["packet_sha256"],
                "visible_copy_contract_sha256": "copy-hash",
                "preflight_gate": {
                    "schema": controller.PAGE_PREFLIGHT_GATE_SCHEMA,
                    "status": "PASS",
                    "artifact_sha256": artifact_sha256,
                    "visible_copy_contract_sha256": "copy-hash",
                },
            }
            patches = (
                mock.patch.object(authoring, "page_author_result_path", return_value=receipt),
                mock.patch.object(authoring, "selected_working_path", return_value=artifact),
                mock.patch.object(authoring, "current_authoring_packet", return_value=packet),
                mock.patch.object(authoring, "read_json", return_value=result),
            )
            with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
                authoring,
                "candidate_errors",
                side_effect=AssertionError("static gate reran"),
            ), mock.patch.object(
                authoring,
                "visible_copy_errors",
                side_effect=AssertionError("copy gate reran"),
            ):
                self.assertTrue(
                    controller.page_author_completion_valid(project, "S01", "A")
                )

            artifact.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><rect/></svg>',
                encoding="utf-8",
            )
            with mock.patch.object(
                authoring, "page_author_result_path", return_value=receipt
            ), mock.patch.object(
                authoring, "selected_working_path", return_value=artifact
            ), mock.patch.object(
                authoring, "current_authoring_packet", return_value=packet
            ), mock.patch.object(authoring, "read_json", return_value=result):
                self.assertFalse(
                    controller.page_author_completion_valid(project, "S01", "A")
                )


class PreviewRegressionTests(unittest.TestCase):
    def test_preview_png_path_changes_with_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "svg_working" / "S01" / "B.svg"
            source.parent.mkdir(parents=True)
            source.write_text('<svg viewBox="0 0 1280 720"/>', encoding="utf-8")
            first_png, first_receipt = preview_paths(project, "S01", "B")
            source.write_text('<svg viewBox="0 0 1280 720"><rect/></svg>', encoding="utf-8")
            second_png, second_receipt = preview_paths(project, "S01", "B")
            self.assertNotEqual(first_png, second_png)
            self.assertEqual(first_receipt, second_receipt)
            self.assertTrue(first_png.name.startswith("B-"))

    def test_sandbox_error_is_typed(self) -> None:
        issue = preview_failure_issue(
            RuntimeError("bootstrap_check_in failed: Permission denied (1100)")
        )
        self.assertEqual("PREVIEW_BROWSER_SANDBOX_BLOCKED", issue["code"])

    def test_non_sandbox_error_is_typed(self) -> None:
        issue = preview_failure_issue(RuntimeError("Chromium executable is missing"))
        self.assertEqual("PREVIEW_BROWSER_UNAVAILABLE", issue["code"])

    def test_visible_copy_error_has_source_repair_scope(self) -> None:
        issue = preview_failure_issue(
            RuntimeError("visible-copy gate failed: S01-title outside the preview canvas")
        )
        self.assertEqual("PREVIEW_VISIBLE_COPY_BLOCKED", issue["code"])
        self.assertEqual("source-svg", issue["repair_scope"])


class RecoveryRegressionTests(unittest.TestCase):
    def test_legacy_confirmed_page_can_be_reopened_for_strict_reauthoring(self) -> None:
        framework = """## Confirmed Storyline

### S01｜Approved title
- Chapter: Main
- Page type: Interpretation
- Narrative role: Explain
- Next connection: End
- Review mode: Page-by-page
- Status: SVG confirmed
- Selected version: A
- Confirmed decisions: Approved
- Open items: None
"""
        with tempfile.TemporaryDirectory() as tmp:
            updated = reopen_pages(
                framework,
                Path(tmp),
                ["S01"],
                "design",
                "Apply the visible-copy contract",
            )
        self.assertIn("- Status: Content locked", updated)
        self.assertIn("- Selected version: Pending", updated)


class DocumentationRegressionTests(unittest.TestCase):
    def test_local_markdown_links_resolve_from_their_document_directory(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        markdown_files = [skill_root / "SKILL.md", *sorted((skill_root / "references").glob("*.md"))]
        broken: list[str] = []
        for document in markdown_files:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                value = target.strip().strip("<>")
                if value.startswith(("http://", "https://", "#", "/")):
                    continue
                path_value = value.split("#", 1)[0]
                if path_value and not (document.parent / path_value).resolve().exists():
                    broken.append(f"{document.name}: {target}")
        self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
