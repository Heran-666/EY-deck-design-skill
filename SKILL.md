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

Classify the deliverable and complete Storyline before creating `framework.md`.
Confirm the type separately only when it is ambiguous; otherwise include it in
the Storyline approval. Follow the router and selected type policy.
Unless the user requests custom design, keep Cover, Agenda, Section divider,
and Ending in their ordered positions with `Deferred template` status and no
authored copy. Preserve the bundled Ending unchanged.

Create framework 3.2 / workflow 8.1 with the approved deck-level Reading mode,
each page's Page rhythm, and one plain `.pptx` output filename, then
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
3. Follow the service contract, preserve approved meaning and `page_logic`, and
   write only `artifact_path`.
4. Run the emitted `record` command once.

Present the emitted SVG at review scale and wait. On confirmation, publish that
exact version. Otherwise bind the exact feedback to the displayed SVG, create
one immutable `R<n>`, and present only that revision. Revise SVG for expression
changes within approved meaning; reopen content for changes to meaning, facts,
data, sources, or Page logic.

## PPTX export

At `EXPORT_EDITABLE_PPTX`, load workspace dependencies, set
`EY_DECK_PPTX_PYTHON`, and run the emitted command. The adapter freezes a stale
or missing roster before export and retains it for retries. Follow the bound
service contract for conversion and recovery. Deliver only after
`PPTX_STAGE_COMPLETE`.
