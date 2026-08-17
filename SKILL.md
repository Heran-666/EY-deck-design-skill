---
name: ey-deck-design
description: >
  Create and approve EY Storylines and exact substantive slide content, defer
  Cover, Agenda, Section divider, and Ending pages to editable export templates,
  generate and confirm substantive page SVGs through the bundled PPT Master,
  and export the ordered roster as editable DrawingML PPTX. Use only when the
  user explicitly invokes $ey-deck-design.
---

# EY Deck Design

EY owns workflow and approvals; bundled `ppt-master/` owns page design and
native conversion. Call it only through EY adapters, never as a second
user-visible skill.

## Authority

| Owner | Authority |
|---|---|
| User | Approve Storyline/content; choose, revise, and confirm SVGs |
| EY controller | Order, state, paths, hashes, requests, receipts, publication, recovery |
| `framework.md` | Project context, confirmed Storyline, coarse page state |
| `content.md` | Exact approved copy, data, emphasis, page-local sources |
| Bundled PPT Master | Page strategy, design, SVG review/repair, DrawingML conversion, postflight |

Candidates live in `svg_working/<Slide ID>/`; only `confirm-svg` may publish one
to `svg_output/<Slide ID>.svg`. Keep candidate history and PPT Master internals
out of `framework.md`.

## Load by action

- Intake: [references/deliverable-types.md](references/deliverable-types.md)
- Storyline/content: [references/storyline-and-content.md](references/storyline-and-content.md) plus one confirmed type policy
- Framework creation/repair: [references/framework-contract.md](references/framework-contract.md)
- First content write or schema failure: [references/output-contract.md](references/output-contract.md)
- External facts: [references/research-and-sources.md](references/research-and-sources.md)
- SVG work: [references/svg-candidate-workflow.md](references/svg-candidate-workflow.md)
- PPTX work: [references/pptx-export-workflow.md](references/pptx-export-workflow.md)
- Initialization/recovery: [references/presentation-workflow.md](references/presentation-workflow.md)

## Storyline and framework

Confirm the deliverable type and complete Storyline before creating
`framework.md`. Each substantive page normally contains three to five specific
planned units supporting one claim; structural pages stay concise. S01 is Cover;
at six or more substantive pages, S02 is Agenda and at least one Section divider
is required. Set Cover, Agenda, Section divider, and Ending pages to `Deferred
template` unless the user explicitly requests custom design. Keep their Page
type and Slide ID; do not author exact copy for them.

Create framework 3.1 / workflow 8.0 with one plain `.pptx` output filename, then
run:

```bash
python3 <skill-root>/scripts/workflow_controller.py bootstrap --project-dir <absolute-project-directory>
```

## Controller discipline

On entry, recovery, or uncertain state, run `next --format json` once. Execute
only its current action, paths, and commands. Process only the first
non-terminal Slide ID. Never hand-edit state, infer approval, promote content,
or publish SVGs outside controller commands. Use `upgrade-workflow` only when
the controller requests migration from workflow 6.0.

## Content gate

Never create `content.md` sections for `Deferred template` pages. For
`PRESENT_PAGE_REVIEW`, replace `working/provisional-content.md` with exactly
the active page. Include final visible copy, complete data, emphasis, and
sources; exclude visual/layout direction. Run `present-review`, show the whole
page, and wait for explicit approval before `approve-content`.

Never invent client, EY, source, credential, case, people, capacity, fee,
schedule, tool, approval, learning, or business-outcome facts.

## SVG gate

For `PREPARE_SVG_CANDIDATES`, load workspace dependencies, set
`EY_DECK_SVG_PYTHON` to the returned absolute Python executable, and run the
emitted command. Deferred template pages never enter this gate. A structural
page explicitly activated with `reopen-content` receives A; substantive pages
default to A and upgrade to A/B only under the hash-bound adaptive plan.
Explicit single/dual decisions override automatic triggers. EY controls count,
not design direction.

For each `RUN_EMBEDDED_PPT_MASTER_SVG` request:

1. Read the request, hash-bound `authoring_context`, and `service_contract`.
2. Run `validate_request`.
3. Let PPT Master choose the communication model, hierarchy, visual concept,
   geometry, composition, and—when applicable—the meaningful A/B difference.
4. Complete information design, composition, art-direction refinement, direct
   source-SVG review, repair, and recheck before exposing the candidate. Do not
   use Chromium or another browser renderer for candidate QA.
5. Write only `artifact_path`, then run the emitted `record` command once.

Content pages use the full `1280×720` canvas. Placeholder bounds are native
metadata, not visual limits; do not add a `y=650` cap, footer reserve, or EY-logo
overlap gate.

Present emitted candidates at equal review scale. Confirm one displayed version
or bind exact user feedback to a displayed base and create immutable `R<n>`.
Present Base/Rn and repeat. Reopen content for copy/meaning changes; reopen SVG
for a design restart.

## PPTX export

After all authored pages are SVG-confirmed, run `PREPARE_PPTX_EXPORT` to freeze
the ordered mixed roster and hashes. It must materialize each deferred structural
template only here and retain its original Slide ID position. For
`RUN_EMBEDDED_PPT_MASTER_PPTX`, read its request and service contract, set
`EY_DECK_PPTX_PYTHON` from workspace dependencies, and run the emitted command.

Export through editable native DrawingML with flat Quick Generate structure,
`preserve` text flow, no notes, final SVG validation, conversion trace,
postflight, and text-frame parity. One logical text box is one SVG `<text>` with
child `<tspan>` runs. On text-frame failure, reopen and reconfirm the source SVG.
Deliver only after `PPTX_STAGE_COMPLETE`.
