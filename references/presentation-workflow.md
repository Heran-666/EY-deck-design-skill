# Initialization and recovery

Read this file only for initialization, reopen, or controller-reported failure.

## Initialization

Work in the user-owned deck directory containing `framework.md`, never in this
skill's installation directory. Resolve the controller from the skill root and
run:

```bash
python3 <controller> bootstrap --project-dir <absolute-project-directory>
```

Bootstrap validates framework 3.1 / workflow 8.0 and prints one next action. It
does not generate a candidate or infer approval.

For a readable pre-8.0 project, run:

```bash
python3 <controller> upgrade-workflow --project-dir <absolute-project-directory>
```

This command changes only `Workflow version` to 8.0, validates the complete
framework, and prints the next action. It does not change content, page states,
SVGs, decisions, or receipts. Existing structural pages therefore keep their
current authored lifecycle; only new frameworks default them to template deferral.

## Content recovery

- A missing or invalid provisional file returns to `PRESENT_PAGE_REVIEW`.
- Editing provisional content invalidates its presentation receipt; present it
  again before approval.
- Use `reopen-content --page <Slide ID>` for any approved meaning, wording,
  data, source, page-order, or page-count change.
- Reopening content deletes that page's old SVG requests, candidates, receipts,
  and confirmed output before returning to content review.

## SVG recovery

- Before `prepare-svg-candidates`, load workspace dependencies and set
  command-scoped `EY_DECK_SVG_PYTHON` to the returned absolute Python
  executable. A missing or incapable runtime must fail before page state or
  candidate files change; do not install an alternate environment.
- Deferred template pages never reach `prepare-svg-candidates`. A Cover, Agenda,
  or Section divider explicitly reopened for custom design creates only A.
  Every substantive page also creates only A. Chart/table content, comparisons,
  high-stakes decisions, and requests for alternatives do not create a second
  initial SVG; the user reviews A before any further work.
- Keep the default Ending deferred and literal. Never modify, supplement, or
  reopen it for design unless the user explicitly replaces the approved source.
- A missing/invalid candidate remains in `RUN_EMBEDDED_PPT_MASTER_SVG`; repair
  the same requested artifact and rerun `record`, which performs the service
  completion check and candidate recording atomically.
- A candidate artifact edit invalidates its receipt and any presentation or
  confirmation that bound the old hash.
- A revision request binds its displayed base and exact feedback. Rerun the same
  Rn request after an environment failure; do not allocate a new version. The
  emitted feedback file is transient and is deleted after its exact text is
  embedded in the Rn request.
- Use `reopen-svg --page <Slide ID>` to delete the current page's A/Rn,
  receipts, and confirmed output, then restart from one A using unchanged
  approved content. Reopen does not archive the deleted visual cycle.

## Confirmation recovery

The controller publishes exact candidate bytes to `svg_output/<Slide ID>.svg`.
Editing either the selected candidate or published SVG makes the confirmation
stale. Follow `REPAIR_STALE_SVG_CONFIRMATION` and reopen the SVG stage; never
hand-edit a confirmed artifact or receipt.

## PPTX recovery

- `PREPARE_PPTX_EXPORT` snapshots the ordered roster of confirmed SVGs and
  deferred structural templates. Any source, framework, content, or
  output-filename change makes that request stale.
- A failed `RUN_EMBEDDED_PPT_MASTER_PPTX` leaves confirmed SVGs unchanged. Fix
  environment or package failures and rerun the same request.
- A fragmented-paragraph or text-frame failure is upstream design evidence:
  run `reopen-svg --page <Slide ID>`, repair one logical text carrier, present
  and confirm it again, then prepare a fresh export request.
- A PPTX, report, trace, or audit edit invalidates the export receipt. Prepare
  and export again; never edit receipts.
