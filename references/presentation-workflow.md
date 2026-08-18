# Initialization and recovery

Load this file only for initialization, reopen, or controller-reported failure.
Recover through controller commands; never edit workflow state or receipts.

## Initialization

Work in the user-owned deck directory containing `framework.md`, not in the
skill directory. Resolve the controller from the skill root and run:

```bash
python3 <controller> bootstrap --project-dir <absolute-project-directory>
```

`bootstrap` validates framework 3.1 / workflow 8.0 and prints the next action;
it does not generate candidates or infer approval.

For a readable pre-8.0 project, run:

```bash
python3 <controller> upgrade-workflow --project-dir <absolute-project-directory>
```

`upgrade-workflow` changes only `Workflow version` to 8.0, validates the
framework, and prints the next action. It leaves content, page states, SVGs,
decisions, and receipts unchanged. Existing structural pages keep their current
lifecycle; template deferral is the default only for new frameworks.

## Content recovery

- Missing or invalid provisional content returns to `PRESENT_PAGE_REVIEW`.
- Editing provisional content invalidates its presentation receipt; present it
  again before approval.
- For any change to approved meaning, wording, data, sources, page order, or
  page count, run `reopen-content --page <Slide ID>`. It deletes the affected
  page's SVG requests, candidates, receipts, and confirmed output, then returns
  the page to content review.

## SVG recovery

- Before `prepare-svg-candidates`, load workspace dependencies and set
  command-scoped `EY_DECK_SVG_PYTHON` to the returned absolute Python path. If
  the runtime is unavailable, fail before changing state or candidate files;
  do not install another environment.
- Deferred template pages skip SVG preparation. Substantive pages and Cover,
  Agenda, or Section divider pages reopened for custom design start with one
  candidate: A. Present A before any revision or alternative. Keep the default
  Ending deferred and unchanged unless the user replaces its approved source.
- For a missing or invalid candidate, stay in
  `RUN_EMBEDDED_PPT_MASTER_SVG`, repair the requested artifact, and rerun
  `record`; do not create a new request.
- Editing a candidate invalidates its receipt and every presentation or
  confirmation bound to the old hash.
- After an environment failure, rerun the same Rn request; do not allocate a
  new version. Keep it bound to the displayed base and exact user feedback.
  The controller deletes the transient feedback file after embedding it.
- To restart visual work without changing approved content, run
  `reopen-svg --page <Slide ID>`. It deletes A/Rn artifacts, receipts, and the
  confirmed output, then starts again from A without archiving the old cycle.

## Confirmation recovery

The controller copies the confirmed candidate bytes to
`svg_output/<Slide ID>.svg`. Editing that candidate or the published SVG makes
confirmation stale. Follow `REPAIR_STALE_SVG_CONFIRMATION`; never hand-edit a
confirmed artifact or receipt.

## PPTX recovery

- `PREPARE_PPTX_EXPORT` snapshots the ordered roster of confirmed SVGs and
  deferred templates. Any source, framework, content, or output-filename change
  makes the request stale; prepare a new one.
- If `RUN_EMBEDDED_PPT_MASTER_PPTX` fails on the environment or a package, fix
  it and rerun the same request; confirmed SVGs remain unchanged.
- A fragmented-paragraph or text-frame failure originates in the source SVG.
  Run `reopen-svg --page <Slide ID>`, repair its logical text carrier, present
  and reconfirm it, then prepare a new export request.
- Editing the PPTX, report, trace, or audit invalidates the export receipt.
  Prepare and export again; never edit receipts.
