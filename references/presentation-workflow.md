# Recovery and structural changes

Read this file only for initialization, migration, reopen, reindex, or a controller-reported block. Normal work follows `next --format json` and its condition-matching command data.

## Initialization

Create framework 2.6 / workflow 3.9 `framework.md` with project and page authoring modes from [authoring-modes.md](authoring-modes.md), call `load_workspace_dependencies` in the parent context, then run the single normal-path command:

```bash
python3 <controller> bootstrap --project-dir . --bundled-python <absolute-bundled-python> --bundle-version <bundle-version>
```

`bootstrap` runs the framework audit, validates and binds the bundled Python plus Pillow/lxml/python-pptx versions, fingerprints EY's bundled confirmed-export runtime, launches a real self-contained SVG preview smoke test, checks that the export root is writable and outside the EY project, installs the managed `AGENTS.md` block, and prints the next structured directive. Keep `doctor` and `init` only as recovery commands. A browser sandbox failure returns `PREVIEW_BROWSER_SANDBOX_BLOCKED`, the exact invoking command as `retry_command`, and the stable controller `approval_prefix`; rerun that command with browser-launch permission or configure `EY_PREVIEW_*`. The same rule applies to `present-single`, `present-ab`, and `present-revision`. Set `EY_EXPORT_ROOT` only to an external directory.

The explicit `advance --event reopen` recovery runs before strict artifact
audits. Use a design-scope reopen when a legacy authored page lacks the current
visible-copy bindings; the controller archives its old SVG evidence and returns
the page to `Content locked` for clean mode-required reauthoring.

## Page-authoring recovery

Run the emitted `prepare-authoring` command before the bounded authoring action. Stage 1 always operates on the first non-terminal Slide ID, beginning with S01 Cover and continuing in exact Storyline order; no body-first or structural-page batch exists. Record each exact terminal JSON with the printed `page-author-result` command. For `Simplified`, stop initial authoring after A and run `present-single`; require explicit A confirmation or a targeted revision. For `Standard`, continue through B and `present-ab`; a `COMPLETE` B result should include `material_differences`, and the controller derives the A/B comparison summary from both authoring receipts. Identical A/B hashes or missing/empty difference evidence are advisories and continue to comparison and explicit user selection.

`present-single` and `present-ab` create hash-bound rendered presentation evidence; neither proves that the user saw the output. Inspect every required candidate before sending it. Follow the directive's per-page `decision_requirements`. For an agent-detected defect, run the emitted `repair_before_user_display` command, or the matching page-specific command when a batch mixes modes: the controller archives only that candidate slot, its preflight, its preview, and the stale page presentation receipt, then returns that page to same-slot authoring while preserving unrelated page decisions. Show the repaired single option or full A/B comparison as required by its page mode. Use `request-revision` and Rn only for targeted changes requested after user display or after confirmation.

`present-revision` creates the same kind of hash-bound rendered comparison for the revision request's exact `base_version` and new Rn; its receipt proves that both previews were rendered and remained unchanged, not that the user saw them. A byte-identical Base/Rn pair is a non-blocking advisory and still proceeds to comparison and an explicit decision. Send the complete Base/Rn comparison in one user-facing message, with each equal-canvas preview in its own standalone image block and both version labels visible. Never place local preview images inside a Markdown table, and never send or describe Rn as a standalone replacement. If the user retains the displayed Base, run `after_keep_base`; if the user confirms the displayed Rn, run `after_confirmation`. If the user requests another targeted change, run `for_targeted_changes` so the current Rn becomes the next request's base, then repeat the paired display. Never select a version outside the current displayed pair.

`page-author-result` is the single page-preflight submission boundary. A
successful receipt binds the static SVG boundary, visible-copy contract, fixed
typography scale, structured-template prototype/contract, artifact hash, packet
hash, and copy-contract hash. Initial and
revision presentation, decision, and canonical audits reuse that receipt when
all bound hashes still match; they rerun only their owned comparison, rendered
visibility, user-evidence, or canonical-integrity checks. Legacy receipts
without the current preflight schema fall back to the former deep validation.
Changing a page-preflight rule requires a new preflight schema value so older
receipts cannot silently bypass the new rule.

For `BLOCKED`:

- `environment`: fix the runtime and run the printed `resume-page-author --page ...`.
- `source-svg` or `user-decision`: use `--scope design` to retain approved content or `--scope content` to reopen copy, data, sources, or meaning; include the resolution note.
- `RESOLVE_AB_CONFLICT`: apply only to `Standard` pages and reopen design with the printed command for remaining blocking comparison-integrity failures. Identical A/B hashes or insufficient A/B difference evidence never trigger this action. This is corruption recovery, not a normal workflow gate.

Design reopen retains the content receipt. Content reopen invalidates it. Both archive affected candidates, packets, previews, decision evidence, and canonical SVGs.

## Stage 2 recovery

Run the emitted `prepare-export` command. The controller stages confirmed SVG copies in an external export workspace, appends the hash-bound fixed Ending prototype, and writes one manifest with their order, hashes, output filename, required output path, bundled exporter fingerprint, validated Python runtime, terminal-result validator, and—when every Storyline page is authored—the structured template profile and prototype hashes. Run the printed deterministic exporter command directly. It binds and preserves an untouched source copy, detects text-frame topology, deterministically normalizes only the isolated working copy, proves exact text identity, and reruns topology before PPTX generation. A successful technical normalization continues without another image display or user decision. The runtime then creates two native Masters and five Layouts from the staged template profile, treats observed confirmed paints and typography already verified against the fixed scale as inherited input, preserves the fixed Ending page's source typography exception, runs the remaining SVG/PPTX gates, and validates its exact terminal JSON before returning it. A mixed deck containing a Protected placeholder uses flat structure to avoid reauthoring protected bytes while still appending the Ending. A valid contextual color missing from the synthesized stable-role palette is inherited evidence, never a Stage 2 block by itself; an out-of-scale visible text size outside the fixed Ending asset is a `source-svg` block.

Stage 2 never trusts the reusable page-preflight receipt in place of its own
checks. It independently verifies the staged SVG hashes, pre-normalization
topology, isolated-copy normalization, exact-copy identity, post-normalization
topology, typography, native-conversion compatibility, PPTX package, and
terminal result. Store the topology loop evidence in
`validation/text_frame_topology.json`; never rewrite the untouched source copy.

Only a reported blocking error may produce `BLOCKED`. Warnings, advisories,
inherited observations, portability notes, and optional authoring hints stay in
the report and do not reopen a page. Route validator/import/runtime failures to
`environment`; route exact-copy, SVG-compatibility, or page-source failures to
`source-svg`; route unresolved approval or decision evidence to
`user-decision`. See [quality-gates.md](quality-gates.md) for the complete
classification.

- `environment`: fix the external condition and run `resume-handoff` without pages.
- `source-svg`: reopen only named normal pages at `Content locked`; a Protected page requires a changed valid `protected_input` SVG.
- `user-decision`: reopen only named normal pages at `Content reviewing` and record the unresolved decision in `Open items`.

## Migration and reindex

Run controller `migrate` only for an explicit older project, then rerun `doctor` before continuing. Migration upgrades schema metadata, installs managed `AGENTS.md`, preserves valid content/artifacts, and archives obsolete evidence. Normal commands reject legacy schemas; hidden positional file arguments remain only for backward-compatible automation.

After explicit approval of insertion, deletion, or reorder, initialize inserted-page modes under [authoring-modes.md](authoring-modes.md), preview `reindex_slides.py`, and add `--apply` only after confirming the mapping. Reindex is blocked during `Content reviewing`, `Content locked`, or `Awaiting SVG decision`. It transactionally remaps framework/content IDs, SVGs, packets, manifests, receipts, and nested hashes; removes stale previews; and voids any earlier Stage 2 result. Retain the backup until controller `audit` passes.
