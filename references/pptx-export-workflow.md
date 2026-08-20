# Ordered SVG roster to editable PPTX

Read only for `EXPORT_EDITABLE_PPTX`, `PPTX_STAGE_COMPLETE`, or export recovery.

The controller owns lifecycle and paths. `scripts/workflow_pptx.py` owns roster
freezing, hashes, invocation, and receipts. Bundled PPT Master owns validation,
DrawingML conversion, trace production, text parity, and package postflight.

## Export

1. Load workspace dependencies and set command-scoped
   `EY_DECK_PPTX_PYTHON` to the returned Python executable.
2. Run the emitted `export-pptx` command. It materializes deferred structural
   snapshots, binds deferred Cover text from `framework.md`, and writes a
   hash-bound roster only when the current request is missing or stale, then
   exports from that roster.
3. On environment failure, rerun the same command; the frozen request remains.
4. On source-SVG text failure, reopen and reconfirm the authored page. Repair a
   deferred template upstream.
5. Deliver only the `.pptx` at `PPTX_STAGE_COMPLETE`; keep reports and traces as
   project-local evidence.

Every export replaces its postflight report and verifies that the report's
output, slide count, and source fingerprint belong to the current run.

The roster contains only export inputs and output evidence paths. Framework,
content, fixed conversion rules, and upstream template-source metadata are not
copied into it.
