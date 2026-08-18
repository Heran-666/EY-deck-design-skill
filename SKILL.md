---
name: ey-deck-design
description: >
  Create approved EY Storylines and page specifications, generate and confirm
  substantive-page SVGs through the bundled PPT Master, and export the ordered
  deck as editable DrawingML PPTX. Use only when the user explicitly invokes
  $ey-deck-design.
---

# EY Deck Design

EY owns workflow and approvals. Bundled `ppt-master/` owns page design and
native conversion; call it only through EY adapters, never as a second
user-visible skill.

## Authority

| Owner | Authority |
|---|---|
| User | Approve Storyline/content; review, refine, and confirm SVGs |
| EY controller | Order, state, paths, hashes, requests, receipts, publication, recovery |
| `framework.md` | Project context, confirmed Storyline, coarse page state |
| `content.md` | Approved page outline, logic, facts, data, emphasis intent, sources |
| Bundled PPT Master | Page wording, strategy, design, SVG review/repair, DrawingML conversion, postflight |

Candidates stay in `svg_working/<Slide ID>/`. Only `confirm-svg` may publish to
`svg_output/<Slide ID>.svg`. Keep candidate history and PPT Master internals out
of `framework.md`.

## Load by action

- Intake: [references/deliverable-types.md](references/deliverable-types.md)
- Storyline/content: [references/storyline-and-content.md](references/storyline-and-content.md) and the confirmed type policy
- Framework creation/repair: [references/framework-contract.md](references/framework-contract.md)
- First content write or schema failure: [references/output-contract.md](references/output-contract.md)
- External facts: [references/research-and-sources.md](references/research-and-sources.md)
- SVG work: [references/svg-candidate-workflow.md](references/svg-candidate-workflow.md)
- PPTX work: [references/pptx-export-workflow.md](references/pptx-export-workflow.md)
- Initialization/recovery: [references/presentation-workflow.md](references/presentation-workflow.md)

## Storyline and framework

Confirm the deliverable type and complete Storyline before creating
`framework.md`. Follow the router and confirmed type policy for page structure.
Unless the user requests custom design, keep Cover, Agenda, Section divider,
and Ending in their ordered positions with `Deferred template` status and no
authored copy. Preserve the bundled Ending unchanged.

Create framework 3.1 / workflow 8.0 with one plain `.pptx` output filename, then
run:

```bash
python3 <skill-root>/scripts/workflow_controller.py bootstrap --project-dir <absolute-project-directory>
```

## Controller discipline

On entry, recovery, or uncertain state, run `next --format json` once. Execute
only the returned current action, paths, and commands for the first
non-terminal Slide ID. Never hand-edit state, infer approval, promote content,
or publish SVGs outside controller commands. Run `upgrade-workflow` only when
the controller requests migration from workflow 6.0.

## Content gate

Do not create `content.md` sections for `Deferred template` pages. At
`PRESENT_PAGE_REVIEW`, replace `working/provisional-content.md` with exactly the
active page. Include build-only Page logic, preferred wording, complete facts
and data, emphasis intent, and sources; exclude visual or layout direction.
Structural pages omit Page logic. Run `present-review`, reproduce the complete
marked review, and show the full page—including Page logic—without summaries or
file-link substitutions. Run `approve-content` only after explicit semantic
approval.

Never invent client or EY facts, sources, credentials, cases, people, capacity,
fees, schedules, tools, approvals, learning, or business outcomes.

## SVG gate

At `PREPARE_SVG_CANDIDATES`, load workspace dependencies, set
`EY_DECK_SVG_PYTHON` to the returned absolute Python executable, and run the
emitted command. `Deferred template` pages never enter this gate. Each
substantive page—and each editable structural page explicitly activated with
`reopen-content`—receives exactly one initial SVG, A. Generate no alternative
before review.

For each `RUN_EMBEDDED_PPT_MASTER_SVG` request:

1. Read the request, hash-bound `authoring_context`, and `service_contract`.
2. Run `validate_request`.
3. Preserve the approved argument and relationships from `page_logic`. Apply
   PPT Master's `content vs expression` rule, and let it choose the information
   model, hierarchy, visual concept, geometry, and composition.
4. Finish information design, composition, art-direction refinement, direct
   source-SVG review, repair, and recheck before presentation. Do not use a
   browser renderer for candidate QA.
5. Write only `artifact_path`; run the emitted `record` command once.

Content pages use the full `1280×720` canvas. Placeholder bounds are native
metadata, not visual limits; do not add a `y=650` cap, footer reserve, or EY-logo
overlap gate.

Present the emitted SVG at review scale and wait. On confirmation, publish that
exact version. Otherwise bind the exact feedback to the displayed SVG, create
one immutable `R<n>`, and present only that revision. Revise SVG for expression
changes within approved meaning; reopen content for changes to meaning, facts,
data, sources, or Page logic.

## PPTX export

After all authored pages are SVG-confirmed, run `PREPARE_PPTX_EXPORT` to freeze
the ordered roster and hashes. Materialize deferred structural templates only
here, at their original Slide ID positions. For
`RUN_EMBEDDED_PPT_MASTER_PPTX`, read its request and service contract, set
`EY_DECK_PPTX_PYTHON` from workspace dependencies, and run the emitted command.

Export editable native DrawingML with flat Quick Generate structure, `reflow`
text flow, no notes, final SVG validation, conversion trace, postflight, and
text-frame parity. Map one logical text box to one SVG `<text>`. Keep inline
`<tspan>` runs non-positional with literal spaces; rejoin same-x `dy` wrap rows
as continuous text, not DrawingML hard breaks. Use paragraph boundaries only
for semantically separate text. Require source/trace/PPTX carrier conservation
and per-carrier OOXML text continuity. On failure, reopen and reconfirm the
source SVG. Deliver only after `PPTX_STAGE_COMPLETE`.
