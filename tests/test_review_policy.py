"""Behavioral checks for explicit review preferences and scoped delegation."""

import json
import tempfile
import unittest
from pathlib import Path

from test_workflow import (
    CONTENT, FRAMEWORK, complete_candidate, framework_with_second_page,
    next_payload, prepare_candidates, run,
)
from workflow_io import sha256
from workflow_paths import ProjectPaths


class ReviewPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.paths = ProjectPaths(self.project)
        self.paths.framework.write_text(FRAMEWORK, encoding="utf-8")
        self.paths.working.mkdir()
        self.paths.provisional.write_text(CONTENT, encoding="utf-8")

    def command(self, *args):
        result = run(self.project, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def policy(self, *args, instruction="Review S01 content and SVG on my behalf."):
        return self.command("set-review-policy", "--instruction", instruction, *args)

    def delegate(self, stages="content,svg"):
        self.policy("--delegate-pages", "S01", "--delegate-stages", stages)

    def ready_svg(self):
        self.command("present-review")
        self.command("approve-content")
        prepare_candidates(self.project)
        complete_candidate(self.project, "A", "Approved copy")

    def test_default_stays_manual_chinese_and_full(self):
        self.command("present-review")
        payload = next_payload(self.project)
        self.assertEqual(payload.get("decision_policy", {}).get("mode"), "manual")
        self.assertEqual(payload["review_contract"]["display_mode"], "full-chinese-review")
        self.assertEqual(payload["review_contract"]["display_language"], "Chinese")

    def test_delegation_applies_only_to_named_page_and_stage(self):
        self.paths.framework.write_text(framework_with_second_page(), encoding="utf-8")
        self.delegate("content")
        self.command("present-review")
        self.assertEqual(next_payload(self.project)["decision_policy"]["mode"], "delegated")
        self.command("approve-content")
        prepare_candidates(self.project)
        complete_candidate(self.project, "A", "Approved copy")
        shown = self.command("present-svg", "--page", "S01", "--versions", "A")
        self.assertEqual(json.loads(shown.stdout[shown.stdout.index('{'):])["decision_policy"]["mode"], "manual")
        self.command("confirm-svg", "--page", "S01", "--version", "A")
        # Advancing past S01 must not give S02 its delegation.
        from workflow_review import decision_policy
        self.assertEqual(decision_policy(self.paths, self.paths.framework.read_text(), "S02", "content")["mode"], "manual")

    def test_scope_change_returns_to_manual_review(self):
        self.delegate()
        self.paths.framework.write_text(FRAMEWORK.replace("Title and subtitle", "Different audience claim"), encoding="utf-8")
        self.command("present-review")
        self.assertEqual(next_payload(self.project)["decision_policy"]["mode"], "manual")

    def test_storyline_title_change_returns_to_manual_review(self):
        self.delegate()
        self.paths.framework.write_text(FRAMEWORK.replace("S01｜Sample title", "S01｜Reject the recommendation"), encoding="utf-8")
        self.command("present-review")
        self.assertEqual(next_payload(self.project)["decision_policy"]["mode"], "manual")

    def test_approved_title_sync_retains_svg_delegation(self):
        self.delegate()
        self.paths.provisional.write_text(CONTENT.replace("- Title: Sample title", "- Title: A clearer title"), encoding="utf-8")
        self.ready_svg()
        self.assertIn("S01｜A clearer title", self.paths.framework.read_text())
        shown = self.command("present-svg", "--page", "S01", "--versions", "A")
        self.assertEqual(json.loads(shown.stdout[shown.stdout.index('{'):])["decision_policy"]["mode"], "delegated")

    def test_delegation_records_source_and_survives_display_preference_update(self):
        self.delegate()
        self.policy("--language", "English", instruction="Review in English from now on.")
        self.command("present-review")
        self.command("approve-content")
        receipt = json.loads((self.paths.working / "receipts/content/S01.json").read_text())
        decision = receipt["decision_policy"]
        self.assertEqual(decision["mode"], "delegated")
        self.assertEqual(decision["instruction"], "Review S01 content and SVG on my behalf.")
        self.assertEqual(receipt["provisional_sha256"], sha256(self.paths.content))

    def test_display_only_preference_does_not_delegate(self):
        self.policy("--language", "English", "--mode", "changes", instruction="English differences only.")
        self.command("present-review")
        payload = next_payload(self.project)
        self.assertEqual(payload["decision_policy"]["mode"], "manual")
        self.assertEqual(payload["review_contract"]["display_language"], "English")
        self.assertEqual(payload["review_contract"]["display_mode"], "full-review")
        self.assertEqual(self.paths.provisional.read_text(), CONTENT)

    def test_changes_review_keeps_full_current_source_as_approval_authority(self):
        self.command("present-review")
        self.policy("--language", "English", "--mode", "changes", instruction="Use English, showing only changes.")
        changed = CONTENT.replace("Approve the recommendation.", "Discuss the recommendation.")
        self.paths.provisional.write_text(changed, encoding="utf-8")
        self.assertNotEqual(run(self.project, "approve-content").returncode, 0)
        shown = self.command("present-review")
        self.assertIn("-- Detail: Approve the recommendation.", shown.stdout)
        self.assertIn("+- Detail: Discuss the recommendation.", shown.stdout)
        self.assertEqual(next_payload(self.project)["review_contract"]["display_mode"], "changes-review")
        self.command("approve-content")
        self.assertEqual(self.paths.content.read_text(), changed)

    def test_language_change_requires_fresh_display_without_rewriting_source(self):
        self.command("present-review")
        self.policy("--language", "English", instruction="Use English for review.")
        self.assertNotEqual(run(self.project, "approve-content").returncode, 0)
        self.assertEqual(self.paths.provisional.read_text(), CONTENT)
        self.command("present-review")
        self.command("approve-content")
        self.assertEqual(self.paths.content.read_text(), CONTENT)

    def test_unknown_or_corrupt_diff_baseline_falls_back_to_full(self):
        self.policy("--mode", "changes", instruction="Show only differences after a complete baseline.")
        first = self.command("present-review")
        self.assertIn(CONTENT.strip(), first.stdout)
        receipt = json.loads(self.paths.content_review.read_text())
        receipt["review_source"] = "Untrusted replacement baseline"
        self.paths.content_review.write_text(json.dumps(receipt))
        second = self.command("present-review")
        self.assertIn(CONTENT.strip(), second.stdout)
        self.assertNotIn("Untrusted replacement baseline", second.stdout)

    def test_clear_delegation_keeps_display_settings(self):
        self.delegate()
        self.policy("--language", "English", instruction="Review in English.")
        self.policy("--clear-delegation", instruction="I will approve all subsequent versions myself.")
        self.command("present-review")
        payload = next_payload(self.project)
        self.assertEqual(payload["decision_policy"]["mode"], "manual")
        self.assertEqual(payload["review_contract"]["display_language"], "English")

    def test_invalid_policy_request_is_non_mutating(self):
        self.delegate()
        path = self.paths.working / "review-policy.json"
        original = path.read_bytes()
        for args in (
            ("--instruction", " ", "--language", "English"),
            ("--instruction", "Delegate unknown page", "--delegate-pages", "S99", "--delegate-stages", "content"),
            ("--instruction", "Missing stages", "--delegate-pages", "S01"),
            ("--instruction", "Duplicate pages", "--delegate-pages", "S01,S01", "--delegate-stages", "content"),
            ("--instruction", "Unknown stage", "--delegate-pages", "S01", "--delegate-stages", "export"),
        ):
            with self.subTest(args=args):
                result = run(self.project, "set-review-policy", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(path.read_bytes(), original)

    def test_svg_delegation_records_provenance_but_rejects_changed_bytes(self):
        self.delegate()
        self.ready_svg()
        shown = self.command("present-svg", "--page", "S01", "--versions", "A")
        self.assertEqual(json.loads(shown.stdout[shown.stdout.index('{'):])["decision_policy"]["mode"], "delegated")
        candidate = self.paths.candidate("S01", "A")
        original = candidate.read_bytes()
        candidate.write_bytes(original + b"\n")
        self.assertNotEqual(run(self.project, "confirm-svg", "--page", "S01", "--version", "A").returncode, 0)
        candidate.write_bytes(original)
        self.command("confirm-svg", "--page", "S01", "--version", "A")
        receipt = json.loads(self.paths.decision_receipt("S01").read_text())
        self.assertEqual(receipt["decision_policy"]["mode"], "delegated")
        self.assertEqual(receipt["artifact_sha256"], sha256(candidate))

    def test_confirmed_svg_expression_revision_preserves_history_and_content(self):
        self.ready_svg()
        self.command("confirm-svg", "--page", "S01", "--version", "A")
        before_content = self.paths.content.read_bytes()
        before_svg = self.paths.candidate("S01", "A").read_bytes()
        before_decision = json.loads(self.paths.decision_receipt("S01").read_text())
        self.command("request-svg-revision", "--page", "S01", "--base", "A", "--feedback", "Shorten the wording without changing meaning.")
        self.assertEqual(self.paths.content.read_bytes(), before_content)
        self.assertEqual(self.paths.candidate("S01", "A").read_bytes(), before_svg)
        self.assertTrue(self.paths.packet("S01", "R1").is_file())
        self.assertEqual(next_payload(self.project)["action"], "RUN_EMBEDDED_PPT_MASTER_SVG")
        self.assertIn("- Status: Content locked", self.paths.framework.read_text())
        complete_candidate(self.project, "R1", "Shorter copy")
        self.command("confirm-svg", "--page", "S01", "--version", "R1")
        self.assertEqual(next_payload(self.project)["action"], "EXPORT_EDITABLE_PPTX")
        history = self.paths.decision_receipt("S01").parent / "decisions" / "A.json"
        self.assertTrue(history.is_file(), "prior version approval evidence must survive reconfirmation")
        self.assertEqual(json.loads(history.read_text()), before_decision)


if __name__ == "__main__":
    unittest.main()
