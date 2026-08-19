# Initialization and recovery

Load this file only for initialization, reopen, or controller-reported failure.
Recover through controller commands; never edit workflow state or receipts.

## Initialization

Work in the user-owned deck directory containing `framework.md`, not in the
skill directory. Resolve the controller from the skill root and run:

```bash
python3 <controller> bootstrap --project-dir <absolute-project-directory>
```

`bootstrap` validates framework 3.2 / workflow 8.1 and prints the next action;
it does not generate candidates or infer approval.

For a readable earlier project, run:

```bash
python3 <controller> upgrade-workflow --project-dir <absolute-project-directory>
```

`upgrade-workflow` migrates the framework to 3.2 / workflow 8.1, validates the
result before writing, and prints the next action. For framework 3.1, it adds
`Reading mode: balanced`, structural `Page rhythm: anchor`, and substantive
`Page rhythm: dense` only when those fields are absent. It leaves content,
page states, SVGs, decisions, and receipts unchanged. Existing structural pages
keep their current lifecycle; template deferral is the default only for new
frameworks.

## Content recovery

- Missing or invalid provisional content returns to `PRESENT_PAGE_REVIEW`.
- Editing provisional content invalidates its review binding; present it
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
- Editing a candidate invalidates its receipt and confirmation.
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

- `EXPORT_EDITABLE_PPTX` snapshots the ordered roster when its request is
  missing or stale, then exports it. Slide source or output-filename changes
  make the request stale; unrelated framework or content edits do not.
- On environment or package failure, fix it and rerun the same command; the
  current request and confirmed SVGs remain unchanged.
- A fragmented-paragraph or text-frame failure originates in the source SVG.
  Run `reopen-svg --page <Slide ID>`, repair its logical text carrier, present
  and reconfirm it, then rerun export.
- Editing the PPTX, report, trace, or audit invalidates the export receipt.
  Export again; never edit receipts.
