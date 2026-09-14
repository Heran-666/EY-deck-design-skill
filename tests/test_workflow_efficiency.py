"""Bounded I/O regressions without weakening lifecycle validation."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_workflow import CONTROLLER, complete_candidate, lock_content, prepare_candidates
import workflow_controller
import workflow_pptx
import workflow_review


class WorkflowEfficiencyTests(unittest.TestCase):
    def test_svg_display_resolves_one_decision_for_both_message_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock_content(project)
            prepare_candidates(project)
            complete_candidate(project, "A", "One complete statement")
            before = (project / "framework.md").read_bytes()
            output = io.StringIO()
            with mock.patch.object(workflow_review, "load_policy", wraps=workflow_review.load_policy) as policy_reads:
                with contextlib.redirect_stdout(output):
                    workflow_controller.handle_present_svg(project, before.decode(), "S01", "A", CONTROLLER)
            payload = json.loads(output.getvalue()[output.getvalue().index("{"):])
            self.assertEqual(policy_reads.call_count, 1)
            self.assertIn(payload["decision_rules"], output.getvalue().split("{", 1)[0])
            self.assertEqual(payload["decision_policy"]["mode"], "manual")
            self.assertEqual((project / "framework.md").read_bytes(), before)

    def test_flat_projection_hashes_each_source_once_per_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source, destination = project / "source.svg", project / "stage.svg"
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
                   'data-pptx-master="master"><text x="10" y="40">Complete statement</text></svg>')
            source.write_text(svg, encoding="utf-8")
            original_hash = workflow_pptx.sha256(source)
            with mock.patch.object(workflow_pptx, "sha256", wraps=workflow_pptx.sha256) as hashes:
                first = workflow_pptx._write_flat_projection(source, destination, slide_id="S01", source_kind="confirmed-svg")
                source_calls = [call for call in hashes.call_args_list if call.args[0] == source]
                self.assertEqual(len(source_calls), 1)
            self.assertEqual(first["source_sha256"], original_hash)
            self.assertEqual(first["confirmed_sha256"], original_hash)
            self.assertEqual(source.read_text(), svg)
            self.assertNotIn("data-pptx-master", destination.read_text())
            source.write_text(svg.replace("Complete statement", "Changed statement"), encoding="utf-8")
            second = workflow_pptx._write_flat_projection(source, destination, slide_id="S01", source_kind="confirmed-svg")
            self.assertNotEqual(first["source_sha256"], second["source_sha256"])
            self.assertEqual(second["source_sha256"], second["confirmed_sha256"])


if __name__ == "__main__":
    unittest.main()
