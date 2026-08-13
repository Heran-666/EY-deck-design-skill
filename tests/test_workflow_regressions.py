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
from workflow_templates import page_template_binding, template_candidate_errors  # noqa: E402
from svg_boundary import candidate_errors  # noqa: E402


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
            "present-single",
            "present-review",
            "present-revision",
            "repair-candidate",
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

    def test_non_editable_template_fixed_copy_is_inherited(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        fixed = (
            '<text data-copy-scope="template-fixed" data-pptx-layer="layout" '
            'data-pptx-editable="false">Fixed template tagline.</text>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.svg"
            path.write_text(annotated_svg(contract, extra=fixed), encoding="utf-8")
            self.assertEqual([], visible_copy_errors(path, contract))

    def test_template_fixed_scope_cannot_hide_page_authored_copy(self) -> None:
        contract = visible_copy_contract(CONTENT, "S01")
        hidden = '<text data-copy-scope="template-fixed">Invented page copy.</text>'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.svg"
            path.write_text(annotated_svg(contract, extra=hidden), encoding="utf-8")
            errors = visible_copy_errors(path, contract)
            self.assertTrue(
                any("must be a non-editable Master/Layout text atom" in error for error in errors)
            )

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

    def test_pretty_printed_tspans_do_not_inject_visible_copy_spaces(self) -> None:
        section = """## S01｜转向“持续 / hello world

### On-slide content
- Title: 转向“持续 / hello world
"""
        contract = visible_copy_contract(section, "S01")
        compact = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<text data-copy-id="S01-title" x="10" y="30">'
            '<tspan>转向</tspan><tspan>“持续 / hello</tspan> <tspan>world</tspan>'
            '</text></svg>'
        )
        formatted = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">\n'
            '  <text data-copy-id="S01-title" x="10" y="30">\n'
            '    <tspan>转向</tspan>\n'
            '    <tspan>“持续 / hello</tspan> <tspan>world</tspan>\n'
            '  </text>\n'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, svg in (("compact.svg", compact), ("formatted.svg", formatted)):
                path = root / name
                path.write_text(svg, encoding="utf-8")
                self.assertEqual([], visible_copy_errors(path, contract), name)

    def test_xml_space_preserve_keeps_line_break_whitespace_significant(self) -> None:
        section = """## S01｜转向“持续

### On-slide content
- Title: 转向“持续
"""
        contract = visible_copy_contract(section, "S01")
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<text data-copy-id="S01-title" x="10" y="30" xml:space="preserve">'
            '<tspan>转向</tspan>\n  <tspan>“持续</tspan>'
            '</text></svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preserved.svg"
            path.write_text(svg, encoding="utf-8")
            errors = visible_copy_errors(path, contract)
            self.assertTrue(any("S01-title changed" in error for error in errors))


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
                "authoring_mode": "Standard",
                "packet_path": "/bound/packet.md",
                "packet_sha256": "packet-hash",
                "visible_copy_contract_sha256": "copy-hash",
                "visible_copy_contract": {"contract_sha256": "copy-hash"},
                "template_structure_contract_sha256": "template-hash",
            }
            result = {
                "status": "COMPLETE",
                "route": "page-svg-authoring",
                "slide_id": "S01",
                "authoring_mode": "Standard",
                "version": "A",
                "artifact_path": str(artifact.resolve()),
                "artifact_sha256": artifact_sha256,
                "packet_path": packet["packet_path"],
                "packet_sha256": packet["packet_sha256"],
                "visible_copy_contract_sha256": "copy-hash",
                "template_structure_contract_sha256": "template-hash",
                "preflight_gate": {
                    "schema": controller.PAGE_PREFLIGHT_GATE_SCHEMA,
                    "status": "PASS",
                    "artifact_sha256": artifact_sha256,
                    "visible_copy_contract_sha256": "copy-hash",
                    "template_structure_contract_sha256": "template-hash",
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


class StructuredTemplateContractTests(unittest.TestCase):
    def test_agenda_uses_dedicated_layout(self) -> None:
        agenda = page_template_binding("Agenda")
        divider = page_template_binding("Section divider")
        self.assertIsNotNone(agenda)
        self.assertIsNotNone(divider)
        assert agenda is not None and divider is not None
        self.assertEqual(agenda["layout_key"], "agenda")
        self.assertNotEqual(agenda["prototype_path"], divider["prototype_path"])
        self.assertNotEqual(
            agenda["structure_contract_sha256"],
            divider["structure_contract_sha256"],
        )
        prototype_text = Path(agenda["prototype_path"]).read_text(encoding="utf-8")
        self.assertEqual(prototype_text.count(">Agenda item</text>"), 7)
        self.assertNotIn("Short supporting detail", prototype_text)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "S02.svg"
            prototype = Path(agenda["prototype_path"])
            authored = prototype.read_text(encoding="utf-8").replace(
                "</svg>",
                '<text data-copy-id="S02-B1-heading" x="820" y="260" '
                'fill="#FFFFFF" font-size="18.6667">01 First chapter</text>\n</svg>',
            )
            candidate.write_text(authored, encoding="utf-8")
            self.assertEqual(template_candidate_errors(candidate, agenda), [])

    def test_ending_has_dedicated_fixed_layout(self) -> None:
        ending = page_template_binding("Ending")
        self.assertIsNotNone(ending)
        assert ending is not None
        self.assertEqual(ending["layout_key"], "ending")
        prototype = Path(ending["prototype_path"])
        self.assertIn('data-ey-fixed-ending="true"', prototype.read_text(encoding="utf-8"))
        self.assertEqual(template_candidate_errors(prototype, ending), [])


class ContentFitPolicyTests(unittest.TestCase):
    def _svg(self, *, font_size: str, lines: int, justification: str = "") -> str:
        density = (
            f' data-density-justification="{justification}"' if justification else ""
        )
        tspans = "".join(
            f'<tspan x="80" y="{180 + index * 20}">Body line {index + 1}</tspan>'
            for index in range(lines)
        )
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
            'viewBox="0 0 1280 720" data-pptx-layout="content">'
            f'<text data-copy-id="S01-B1-detail" x="80" y="180" '
            f'font-size="{font_size}"{density}>{tspans}</text></svg>'
        )

    def test_short_8pt_body_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.svg"
            path.write_text(self._svg(font_size="10.6667", lines=4), encoding="utf-8")
            self.assertTrue(any("content-fit policy" in error for error in candidate_errors(path)))

    def test_10pt_or_genuinely_dense_8pt_body_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = {
                "ten.svg": self._svg(font_size="13.3333", lines=3),
                "five-lines.svg": self._svg(font_size="10.6667", lines=5),
                "dense.svg": self._svg(
                    font_size="10.6667", lines=3, justification="dense-table"
                ),
            }
            for name, svg in cases.items():
                path = root / name
                path.write_text(svg, encoding="utf-8")
                self.assertEqual([], candidate_errors(path), name)

    def test_page_type_mapping_and_fixed_atom_tamper_detection(self) -> None:
        binding = page_template_binding("Section divider")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["layout_key"], "divider")
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "S02.svg"
            prototype = Path(binding["prototype_path"])
            candidate.write_bytes(prototype.read_bytes())
            self.assertEqual(template_candidate_errors(candidate, binding), [])
            candidate.write_text(
                candidate.read_text(encoding="utf-8").replace(
                    'id="divider-rule"',
                    'id="divider-rule-tampered"',
                    1,
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any(
                    "fixed Master/Layout atoms" in item
                    for item in template_candidate_errors(candidate, binding)
                )
            )

    def test_cover_fixed_tagline_is_hash_protected(self) -> None:
        binding = page_template_binding("Cover")
        self.assertIsNotNone(binding)
        assert binding is not None
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "S01.svg"
            prototype = Path(binding["prototype_path"])
            candidate.write_bytes(prototype.read_bytes())
            candidate.write_text(
                candidate.read_text(encoding="utf-8").replace(
                    "The better the world works.",
                    "The better the slide works.",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                any(
                    "fixed Master/Layout atoms" in item
                    for item in template_candidate_errors(candidate, binding)
                )
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
- Confirmed version: A
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
        self.assertIn("- Confirmed version: Pending", updated)


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
