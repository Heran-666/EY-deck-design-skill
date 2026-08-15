---
name: ey-deck-design
description: >
  Control an EY presentation workflow from background, deliverable-type and
  Storyline approval through locked page content and user-confirmed SVGs, then
  delegate complete Stage 1 visual production and Stage 2 editable-PPTX export
  to the bundled Embedded PPT Master. Use only when the user explicitly invokes
  $ey-deck-design.
---

# EY Deck Design

Act as the workflow and content-control layer. Use the bundled controller as the
only authority for page order, state, paths, hashes, receipts, recovery, user
display, decisions, and final handoff. Delegate all visual design, SVG
construction, internal visual QA, export normalization, native-PPTX conversion,
and technical package QA to Embedded PPT Master.

## Ownership

| Owner | Owns |
|---|---|
| User | Storyline, exact content approval, candidate choice, revision confirmation |
| EY Deck Design | intake, content, sources, authoring mode, workflow state, candidate/version requests, user gates, evidence, recovery, delivery |
| `framework.md` | compact project context, approved Storyline, page modes, state, unresolved decisions |
| `content.md` | exact approved copy, data, sources, emphasis, and semantic Visual Direction |
| Embedded PPT Master Stage 1 | page design, information visualization, SVG construction, rendering, visual QA, and internal repair |
| Embedded PPT Master Stage 2 | isolated normalization, Master/Layout construction, native PPTX conversion, compatibility, package QA |

Do not expose Embedded PPT Master's internal Design Decisions, design memory, or
visual-review steps as controller state or user approval gates. The controller
binds only the subsystem interfaces: locked input, requested version and output,
artifact identity, exact copy, template integrity, preview evidence, user
decision, export manifest, and terminal result.

Keep candidates and previews in `svg_working/`; keep exactly one user-confirmed
SVG per Storyline page in `svg_output/`. Never activate or read a separate global
`$ppt-master` skill.

The project directory is the user-owned working directory that contains the
deck's `framework.md`; it is never this skill's installation directory. Resolve
the controller as `<skill-root>/scripts/workflow_controller.py`, where
`<skill-root>` is the directory containing this `SKILL.md`.

## Load only what the current action needs

- New intake: read [references/deliverable-types.md](references/deliverable-types.md) and [references/authoring-modes.md](references/authoring-modes.md).
- Storyline or content: read [references/storyline-and-content.md](references/storyline-and-content.md) plus exactly the confirmed primary type policy: [Proposal](references/storyline-type-proposal.md), [Sharing deck](references/storyline-type-sharing-deck.md), [Training](references/storyline-type-training.md), [Interpretation](references/storyline-type-interpretation.md), or [Other](references/storyline-type-other.md).
- Create, migrate, or reindex `framework.md`: read [references/framework-contract.md](references/framework-contract.md).
- First provisional content write or schema failure: read [references/output-contract.md](references/output-contract.md).
- External facts or citations: read [references/research-and-sources.md](references/research-and-sources.md).
- `RUN_PPT_MASTER_*` or `RUN_PPT_MASTER_EXPORT`: read [references/embedded-ppt-master.md](references/embedded-ppt-master.md) and follow only the supplied hash-bound packet or manifest.
- Initialization, migration, reopen, reindex, or recovery: read [references/presentation-workflow.md](references/presentation-workflow.md).
- Any `BLOCKED` result: read [references/quality-gates.md](references/quality-gates.md) before using the emitted recovery command.

## Intake and Storyline

Classify the background as `Proposal`, `Sharing deck`, `Training`,
`Interpretation`, or `Other: <specific form>` and obtain confirmation unless the
user waives the gate. Then ask the user to choose `Simplified` or `Standard`.

Every deck begins with one Cover at S01. At six or more substantive pages, add
an Agenda at S02 and at least one Section divider. Cover, Agenda, and Section
divider pages are always `Simplified`; other normal pages inherit the requested
project mode. Protected placeholders use `Not applicable`.

Show the complete Storyline using the fixed contract in
[references/deliverable-types.md](references/deliverable-types.md) and obtain
explicit approval before creating `framework.md`. Create framework 2.7 / workflow
4.1 with the requested or deterministic `.pptx` filename. Call
`load_workspace_dependencies` once, then run controller `bootstrap` with the
reported `Python executable` and `Bundle version`. Use the directory containing
the new `framework.md` as `--project-dir`.

## Controller execution

On entry, re-entry, post-compaction, or uncertain state, reload this skill and
run controller `next --format json` once. Treat its packet, artifact, preview,
manifest, receipt paths, and hashes as recovery authority. Follow only `action`,
`command_when`, and the matching command data. A successful mutation already
prints the next directive; do not replay it or immediately call `next` again.

Process only the first non-terminal Slide ID.

For content review, replace all of `working/provisional-content.md` with exactly
the active sections listed by `provisional_content.expected_pages`. Run the
printed `present-review` command. Explicit user approval promotes those unchanged
sections into `content.md`, records hashes, clears handled open items, and locks
the page.

For each required candidate, follow this outer chain:

1. `PREPARE_PPT_MASTER_*`: materialize the locked packet.
2. `RUN_PPT_MASTER_*`: in the current Codex task, assume the bounded Embedded
   PPT Master Stage 1 role. Design, author, render, visually review, internally
   repair, and return one terminal Stage 1 JSON object. This is not a separate
   skill, subagent, process, or controller state.
3. Record the result with the emitted `ppt-master-result` command.
4. Run the emitted presentation command, inspect the exact rendered preview,
   then show it to the user and collect the mode-required decision.

`Simplified` requests A only. `Standard` requests A and B from the same locked
content, then shows both at equal scale. Candidate similarity and missing
`material_differences` remain advisories. A targeted revision binds one displayed
Base and one Rn; show both together and accept only that pair.

Never invent client, audience, source, EY, credential, case, people, capacity,
fee, schedule, tool, approval, learning outcome, or business-outcome facts.
Never silently rewrite locked content, protected material, or confirmed semantic
Visual Direction.

Map user decisions by meaning to the exact controller command already emitted:
confirmation selects the displayed A, an ordinal choice selects the displayed A
or B, and a revision request must state the displayed Base plus the targeted
change. Do not construct a decision command from memory.

## Final handoff

After every Storyline page is terminal, the controller prints
`STAGE_1_COMPLETE`. Run `prepare-export`, then run the emitted Embedded PPT Master
Stage 2 `runner_command` exactly once. It is bound to the confirmed SVG manifest,
staged hashes, structured-template profile when applicable, fixed Ending,
required output path, runtime, and terminal validator.

The bundled fixed Ending is an export-only prototype, not a Storyline page. It
is exempt from Storyline approval, content review, Stage 1 production, and
candidate approval, and Stage 2 always appends it after the confirmed pages.

Record the runner's exact JSON with `handoff-result`. Deliver a `COMPLETE` PPTX.
For `BLOCKED`, use only the controller's matching recovery command and scope.
Warnings, advisories, and inherited observations never reopen content or design.
