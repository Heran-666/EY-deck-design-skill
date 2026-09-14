# EY Review Boundaries Implementation Plan

> **For agentic workers:** Use Superpowers writing-skills for behavioral checks and test-driven-development for controller changes. Execute the accepted audit in this session; preserve pre-existing workspace edits.

**Goal:** Remove conflicting instructions and avoid repeated waits when the user has explicitly delegated review, while preserving default manual review and artifact integrity.

**Architecture:** Keep the existing serial controller and hash-bound content/SVG gates. Add one project-local review policy with explicit user instruction, optional review language/mode, and a delegation scope containing concrete page IDs and content/SVG stages. Record that policy in decisions; no batch scheduler or new deck schema.

**Tech Stack:** Python standard library, unittest, Markdown; existing bundled Python runtime for Pillow-dependent workflow tests.

## 1. Baseline

- [x] Preserve existing diffs and original skill files in a temporary audit directory.
- [x] Run an independent read-only scenario check for delegated review, expression-only edits, English difference review, and training authoring.
- [x] Add failing CLI tests in `tests/test_review_policy.py` before implementation.

## 2. Controller policy

Files: `scripts/workflow_review.py`, `scripts/workflow_controller.py`, `scripts/workflow_paths.py`, `scripts/workflow_svg.py`, `tests/test_review_policy.py`.

- [x] Add `set-review-policy --instruction <exact-user-request>` with optional `--language Chinese|English|source`, `--mode full|changes`, `--delegate-pages S02,S03`, and `--delegate-stages content,svg`. Omitted fields retain current settings. `--clear-delegation` restores manual decisions without resetting display preferences.
- [x] Reject empty instructions, unknown/duplicate pages and unsupported stages before writing. Bind page delegations to their Storyline scope and approved project context; scope changes return to manual review.
- [x] Default to Chinese/full/manual. Store policy at `working/review-policy.json`; keep existing action names and commands.
- [x] Return the effective decision policy in content and SVG decision directives. Under delegation, continue through normal commands after validation without another user wait. Save the exact authorization source with decision receipts.
- [x] Present changes only when a valid earlier source snapshot exists for the same page. Otherwise present the complete source. Bind approval to the full current source hash, never to a diff alone.
- [x] Keep stale content and stale SVG rejection intact. Review-language changes do not rewrite the deck language or approved source.

Run:

```bash
/Users/hz/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_review_policy.py -v
```

Expected baseline: nonzero failures for the missing policy command/behavior. Expected after implementation: all policy tests pass.

## 3. Skill corrections

Files: global `/Users/hz/.codex/AGENTS.md`; root `SKILL.md`; relevant files under `references/`; embedded `ppt-master/workflows/page-svg-service.md`.

- [x] Correct AGENTS typos and make premise checks conditional on a material issue.
- [x] Make Storyline waiver consistent across intake, root skill and framework contract; record the actual user waiver in durable project context.
- [x] Route expression-only feedback through SVG revisions; reserve content reopen for changed meaning or canonical source changes.
- [x] Document the review-policy command in one focused reference and route to it only for changed review preferences or delegated approval.
- [x] Remove generic Strategist from mandatory page-service reads, reuse valid context and runtime paths, and define targeted repair/verification stopping conditions.
- [x] Allow proposed learning objectives/exercises while preserving factual boundaries. Remove obsolete workflow-6-only migration wording.

## 4. Verification

- [x] Run updated scenarios independently against the new skill.
- [x] Run the full existing workflow suite plus new tests once; fix failures caused by this change and rerun affected checks.
- [x] Run Skill Creator `quick_validate.py` and `git diff --check` on changed files.
- [x] Inspect this turn's diff against the preserved baseline and report changes and validation results. Leave modifications available in the existing workspace.

Verification notes: The baseline agent obeyed higher-priority user instructions but identified local ambiguity and missing command support; no observed agent failure is claimed. Twelve initial CLI regressions failed before implementation. Independent forward scenarios now resolve all five decisions correctly. Code review found a title-scope omission; a failing regression was added and the fix was verified, alongside legitimate approved-title synchronization.

Final verification: 61 tests passed (14 new review-policy tests plus the existing workflow suite), including both actual PPTX export cases with the bundled runtime configured. Skill Creator validation and changed-file whitespace checks passed. All 166 unrelated pre-existing diff sections remained byte-for-byte unchanged.
