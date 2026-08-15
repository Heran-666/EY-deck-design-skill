# Initialization and recovery

Read this file only for initialization, reopen, or controller-reported failure.

## Initialization

Work in the user-owned deck directory containing `framework.md`, never in this
skill's installation directory. Resolve the controller from the skill root and
run:

```bash
python3 <controller> bootstrap --project-dir <absolute-project-directory>
```

Bootstrap validates framework 3.1 / workflow 6.0 and prints one next action. It
does not generate a candidate or infer approval.

## Content recovery

- A missing or invalid provisional file returns to `PRESENT_PAGE_REVIEW`.
- Editing provisional content invalidates its presentation receipt; present it
  again before approval.
- Use `reopen-content --page <Slide ID>` for any approved meaning, wording,
  data, source, page-order, or page-count change.
- Reopening content deletes that page's old SVG requests, candidates, receipts,
  and confirmed output before returning to content review.

## SVG recovery

- `prepare-svg-candidates` creates A and B requests only for the active
  content-locked page.
- A missing/invalid candidate remains in `RUN_EMBEDDED_PPT_MASTER_SVG`; repair
  the same requested artifact and rerun the service completion check.
- A candidate artifact edit invalidates its receipt and any presentation or
  confirmation that bound the old hash.
- A revision request binds its displayed base and exact feedback. Rerun the same
  Rn request after an environment failure; do not allocate a new version.
- Use `reopen-svg --page <Slide ID>` to delete the current page's A/B/Rn,
  receipts, and confirmed output, then restart A/B from unchanged approved
  content. Reopen does not archive the deleted visual cycle.

## Confirmation recovery

The controller publishes exact candidate bytes to `svg_output/<Slide ID>.svg`.
Editing either the selected candidate or published SVG makes the confirmation
stale. Follow `REPAIR_STALE_SVG_CONFIRMATION` and reopen the SVG stage; never
hand-edit a confirmed artifact or receipt.
