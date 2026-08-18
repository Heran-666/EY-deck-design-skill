# Ordered slide roster to editable PPTX

Read only for `PREPARE_PPTX_EXPORT`, `RUN_EMBEDDED_PPT_MASTER_PPTX`, or PPTX
recovery.

## Boundary

The controller owns lifecycle and paths. `scripts/workflow_pptx.py` owns the
EY-to-PPT-Master adapter, hashes, invocation, and receipts. Bundled PPT Master
owns final SVG validation, editable DrawingML conversion, conversion trace,
and package postflight.

The roster may mix confirmed authored SVGs with structural template snapshots
created at export. Use the adapter only; never call the converter directly or
add another PPTX implementation to the controller.

## Text-frame contract

- Map each logical PowerPoint text box to one SVG `<text>`. Put semantically
  independent labels in separate carriers.
- Inline formatting: use non-positional `<tspan>` children and literal word
  spaces; never use `dx` as semantic whitespace.
- For visual wrapping, use same-x child `<tspan>` rows: `dy="0"` on the first row
  and positive relative `dy` thereafter. These are layout hints, not authored
  newlines. Rejoin them into one paragraph and let PowerPoint wrap it. Normalize
  only unambiguous, transform-free absolute-y stacks.
- Export EY-authored pages with explicit `reflow`; never use preserve, split,
  or `--no-merge`.
- Treat a high-confidence fragmented-paragraph warning as blocking.
- On every slide, require matching source, trace, and OOXML carrier counts. Each
  carrier must preserve characters, literal spaces, and semantic paragraph
  boundaries. Reject hard breaks introduced by visual wrap rows.

## Controller actions

1. Run the `PREPARE_PPTX_EXPORT` command once. For each `Deferred template`
   page, it materializes the matching self-contained Cover, Agenda, Section
   divider, or Ending snapshot, then creates a hash-bound ordered request. It
   does not build or design the deck. Use the fixed full-slide Ending asset
   unchanged.
2. For `RUN_EMBEDDED_PPT_MASTER_PPTX`, read the request and service contract.
   Call `load_workspace_dependencies`, set command-scoped
   `EY_DECK_PPTX_PYTHON` to the returned absolute Python executable, and run the
   exact emitted command. Do not install or search for alternate packages.
3. On failure, leave `svg_output/` unchanged:
   - Invalid authored SVG structure: reopen and reconfirm that page.
   - Invalid deferred snapshot: repair the bundled template upstream.
   - Environment or package failure: repair the environment and rerun the same
     request.
4. At `PPTX_STAGE_COMPLETE`, deliver only the `.pptx`. Keep the JSON
   postflight, conversion trace, and text audit as project-local evidence.
