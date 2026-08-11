# Recovery and structural changes

Read this file only for initialization, migration, reopen, reindex, or a controller-reported block. Normal work follows `next --format json` and its condition-matching command data.

## Initialization

Create framework 2.5 / workflow 3.7 `framework.md`, call `load_workspace_dependencies` in the parent context, then run the single normal-path command:

```bash
python3 <controller> bootstrap --project-dir . --bundled-python <absolute-bundled-python> --bundle-version <bundle-version>
```

`bootstrap` runs the framework audit, validates and binds the bundled Python plus Pillow/lxml/python-pptx versions, fingerprints EY's bundled confirmed-export runtime, launches a real self-contained SVG preview smoke test, checks that the export root is writable and outside the EY project, installs the managed `AGENTS.md` block, and prints the next structured directive. Keep `doctor` and `init` only as recovery commands. A browser sandbox failure returns `PREVIEW_BROWSER_SANDBOX_BLOCKED`, the exact invoking command as `retry_command`, and the stable controller `approval_prefix`; rerun that command with browser-launch permission or configure `EY_PREVIEW_*`. The same rule applies to `present-ab` and `present-revision`. Set `EY_EXPORT_ROOT` only to an external directory.

The explicit `advance --event reopen` recovery runs before strict artifact
audits. Use a design-scope reopen when a legacy authored page lacks the current
visible-copy bindings; the controller archives its old SVG evidence and returns
the page to `Content locked` for clean A/B reauthoring.

## Page-authoring recovery

Run the emitted `prepare-authoring` command before the bounded authoring action. Record each exact terminal JSON with the printed `page-author-result` command. A `COMPLETE` B result should include `material_differences`; the controller derives the A/B comparison summary from the two authoring receipts. Identical A/B hashes or missing/empty difference evidence are recorded as advisories and continue to comparison and explicit user selection.

`present-ab` creates a hash-bound rendered comparison; it does not by itself prove that the user saw it. Inspect both rendered candidates before sending the comparison. For an agent-detected defect, run the emitted `repair_before_user_display` command: the controller archives only that A/B slot, its preflight, its preview, and the stale comparison receipt, then returns to same-slot authoring while retaining the other candidate and locked content. Show both repaired A/B options together. Use `request-revision` and Rn only for targeted changes requested by the user after A/B display or after confirmation.

`present-revision` creates the same kind of hash-bound rendered comparison for the revision request's exact `base_version` and new Rn; its receipt proves that both previews were rendered and remained unchanged, not that the user saw them. A byte-identical Base/Rn pair is a non-blocking advisory and still proceeds to comparison and explicit confirmation. Send the complete Base/Rn comparison in one user-facing message, with both previews side by side at equal scale and both version labels visible. Never send or describe Rn as a standalone replacement. If the user requests another targeted change, run the emitted `for_targeted_changes` command so the current Rn becomes the next request's base, then repeat the paired display. Run `after_confirmation` only after explicit confirmation of the displayed Rn.

`page-author-result` is the single page-preflight submission boundary. A
successful receipt binds the static SVG boundary, visible-copy contract, fixed
typography scale, artifact hash, packet hash, and copy-contract hash. A/B and
revision presentation, selection, and canonical audits reuse that receipt when
all bound hashes still match; they rerun only their owned comparison, rendered
visibility, user-evidence, or canonical-integrity checks. Legacy receipts
without the current preflight schema fall back to the former deep validation.
Changing a page-preflight rule requires a new preflight schema value so older
receipts cannot silently bypass the new rule.

For `BLOCKED`:

- `environment`: fix the runtime and run the printed `resume-page-author --page ...`.
- `source-svg` or `user-decision`: use `--scope design` to retain approved content or `--scope content` to reopen copy, data, sources, or meaning; include the resolution note.
- `RESOLVE_AB_CONFLICT`: reopen design with the printed command for remaining blocking comparison-integrity failures. Identical A/B hashes or insufficient A/B difference evidence never trigger this action. This is corruption recovery, not a normal workflow gate.

Design reopen retains the content receipt. Content reopen invalidates it. Both archive affected candidates, packets, previews, selection evidence, and canonical SVGs.

## Stage 2 recovery

Run the emitted `prepare-export` command. The controller stages confirmed SVG copies in an external export workspace and writes one hash-bound manifest with their order, hashes, output filename, required output path, bundled exporter fingerprint, validated Python runtime, and terminal-result validator. Run the printed deterministic exporter command directly. It normalizes only isolated technical copies, treats observed confirmed paints and typography already verified against the fixed scale as inherited input, runs the SVG/PPTX gates, and validates its exact terminal JSON before returning it. A valid contextual color missing from the synthesized stable-role palette is inherited evidence, never a Stage 2 block by itself; an out-of-scale visible text size is a `source-svg` block.

Stage 2 never trusts the reusable page-preflight receipt in place of its own
checks. It independently verifies the staged SVG hashes, normalization,
typography, native-conversion compatibility, PPTX package, and terminal result.

Only a reported blocking error may produce `BLOCKED`. Warnings, advisories,
inherited observations, portability notes, and optional authoring hints stay in
the report and do not reopen a page. Route validator/import/runtime failures to
`environment`; route exact-copy, SVG-compatibility, or page-source failures to
`source-svg`; route unresolved approval or selection evidence to
`user-decision`. See [quality-gates.md](quality-gates.md) for the complete
classification.

- `environment`: fix the external condition and run `resume-handoff` without pages.
- `source-svg`: reopen only named normal pages at `Content locked`; a Protected page requires a changed valid `protected_input` SVG.
- `user-decision`: reopen only named normal pages at `Content reviewing` and record the unresolved decision in `Open items`.

## Migration and reindex

Run controller `migrate` only for an explicit older project, then rerun `doctor` before continuing. Migration upgrades schema metadata, installs managed `AGENTS.md`, preserves valid content/artifacts, and archives obsolete evidence. Normal commands reject legacy schemas; hidden positional file arguments remain only for backward-compatible automation.

After explicit approval of insertion, deletion, or reorder, preview `reindex_slides.py`; add `--apply` only after confirming the mapping. Reindex is blocked during `Content reviewing`, `Content locked`, or `Awaiting SVG selection`. It transactionally remaps framework/content IDs, SVGs, packets, manifests, receipts, and nested hashes; removes stale previews; and voids any earlier Stage 2 result. Retain the backup until controller `audit` passes.
