# Confirmed SVG to editable PPTX

Read this file only for `PREPARE_PPTX_EXPORT`,
`RUN_EMBEDDED_PPT_MASTER_PPTX`, or PPTX recovery.

## Boundary

The controller owns lifecycle and paths. `scripts/workflow_pptx.py` owns the
EY-to-PPT-Master adapter, hashes, invocation, and receipts. Bundled PPT Master
owns final SVG validation, editable DrawingML conversion, conversion trace, and
package postflight. Do not call the converter directly or create a second PPTX
implementation in the controller.

## Text-frame contract

- One logical PowerPoint text box equals one SVG `<text>` carrier.
- Use non-positional `<tspan>` children for inline mixed formatting.
- Use positioned child `<tspan>` rows for authored multiline text.
- Keep semantically independent labels in separate `<text>` carriers.
- Export with explicit `preserve` text flow. Never use split/`--no-merge`.
- Treat the quality checker's high-confidence fragmented-paragraph warning as
  blocking even though it is advisory in generic PPT Master workflows.
- Require conversion-trace-to-OOXML text-box count parity on every slide.

## Controller actions

1. Run `PREPARE_PPTX_EXPORT`'s command once. It creates a hash-bound request;
   it does not create the deck.
2. On `RUN_EMBEDDED_PPT_MASTER_PPTX`, read the request and its service contract,
   call `load_workspace_dependencies`, set command-scoped
   `EY_DECK_PPTX_PYTHON` to the returned absolute Python executable, then run
   the exact emitted command. Do not install or discover alternate packages.
3. On failure, do not modify `svg_output/`. Reopen and reconfirm an affected
   page when source SVG structure is wrong; otherwise repair the environment
   and rerun.
4. On `PPTX_STAGE_COMPLETE`, deliver only the `.pptx`. The JSON postflight,
   trace, and text audit remain project-local evidence.
