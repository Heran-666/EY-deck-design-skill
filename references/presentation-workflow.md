# Recovery and structural changes

Read this file only for initialization, migration, reopen, reindex, or a
controller-reported block. Normal work follows `next --format json`.

## Initialization

Work in the user-owned deck directory containing `framework.md`, never in the
skill installation directory. Resolve `<controller>` to
`<skill-root>/scripts/workflow_controller.py`, where `<skill-root>` contains
`SKILL.md`. Create framework 2.8 / workflow 4.2 `framework.md`, call
`load_workspace_dependencies` once, and copy its reported `Python executable`
and `Bundle version` into:

```bash
<python-executable> <controller> bootstrap --project-dir <absolute-deck-directory> --bundled-python <python-executable> --bundle-version <bundle-version>
```

`bootstrap` audits the framework, binds bundled Python and the Embedded PPT
Master Stage 2 runtime, runs a self-contained browser-preview smoke test, checks
that the external export root is writable, installs the managed `AGENTS.md`
block, and prints the next directive. Keep `doctor` and `init` for recovery.

If preview startup is sandbox-blocked, use the returned `retry_command` and
stable approval prefix or configure `EY_PREVIEW_*`. Set `EY_EXPORT_ROOT` only to
an external directory.

## Stage 1 recovery

Stage 1 always operates on the first non-terminal Slide ID. For each candidate,
run the emitted `prepare-ppt-master` command. The current Codex task then assumes
the bounded Embedded PPT Master role and completes design, SVG authoring,
rendering, visual QA, and internal repair; do not activate another skill,
subagent, or runner. Record its terminal object with `ppt-master-result`.

`ppt-master-result` is the single Stage 1 submission boundary. A COMPLETE result
binds the requested artifact, packet, visible-copy contract, structured-template
contract, and acceptance schema. Presentation and canonical audits reuse that
receipt only while all bound hashes remain unchanged.

`present-single`, `present-ab`, and `present-revision` create rendered,
hash-bound display evidence; they do not prove that the user saw the previews.
Inspect every required preview before sending it. If a visible defect remains
after PPT Master reported COMPLETE, use `repair-candidate` for the same A/B slot.
For a user-requested revision, repair the same Rn slot when needed, then show the
exact Base and Rn together and accept only the displayed pair.

For a Stage 1 BLOCKED result:

- `environment`: fix the runtime and run the emitted `resume-page-author` command.
- `design`: retain locked content, reopen the candidate request, and rerun PPT Master.
- `content`: reopen exact copy, data, sources, or semantic meaning for user approval.

The controller does not inspect PPT Master's internal design notes or repair
steps. A design recovery archives candidate artifacts and outer evidence only;
a content recovery also invalidates the content-lock receipt.

## Stage 2 recovery

Run the emitted `prepare-export` command. The controller stages confirmed SVG
copies in an external workspace, appends the fixed Ending, and writes a manifest
with page order, hashes, output path, runtime fingerprint, terminal validator,
and structured-template bindings when applicable.

Run the returned Embedded PPT Master Stage 2 command exactly once. It owns
topology detection, isolated normalization, exact-copy proof, Master/Layout
construction, native conversion, compatibility checks, and PPTX package QA.
Stage 2 never mutates confirmed source SVGs and never relies on Stage 1 receipts
in place of its own checks.

Only a terminal BLOCKED result invokes recovery. Warnings, advisories, inherited
observations, and optional portability notes do not reopen pages.

- `environment`: fix the external condition and run `resume-handoff` without pages.
- `source-svg`: reopen only named normal pages at `Content locked`; protected pages require changed valid input bytes.
- `user-decision`: reopen only named normal pages at `Content reviewing` and record the unresolved decision.

## Migration and reindex

Run controller `migrate` only for an explicit older project, then rerun `doctor`.
Migration upgrades schema metadata, installs the managed `AGENTS.md`, preserves
valid confirmed artifacts when possible, and archives obsolete Design Decision,
outer Visual QA, preview, and transition evidence.

After explicit approval of insertion, deletion, or reorder, preview
`reindex_slides.py` and add `--apply` only after confirming the mapping. Reindex
is blocked during `Content reviewing`, `Content locked`, or
`Awaiting SVG decision`. It remaps framework/content IDs, candidates, packets,
manifests, receipts, and nested hashes; removes stale previews; and voids prior
Stage 2 results. Retain the backup until controller `audit` passes.
