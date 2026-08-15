---
name: ey-deck-design
description: >
  Create and approve EY presentation Storylines and exact slide content, then
  use the bundled PPT Master to generate one complete SVG for Cover, Agenda,
  Section divider, and Ending pages and two alternatives for substantive pages,
  iterate from user-selected bases and feedback, and publish only explicitly
  confirmed SVGs. Use only when the user explicitly invokes $ey-deck-design.
---

# EY Deck Design

Own the deck workflow, approved content, candidate lifecycle, and user gates.
Use the bundled PPT Master page-SVG service for all page strategy, visual design,
SVG authoring, and visual/technical QA.

Treat `ppt-master/` as an internal runtime package, never as a second skill. It
has no `SKILL.md` or UI metadata and may be called only through the EY request
adapter. The separately installed global `$ppt-master` remains the only
user-visible PPT Master skill.

## Ownership

| Owner | Responsibility |
|---|---|
| User | Approve Storyline and exact content; choose, revise, and confirm SVGs |
| EY controller | Order, states, paths, hashes, request packets, receipts, recovery, and publication |
| `framework.md` | Compact project context, Storyline, and coarse page state |
| `content.md` | Exact approved visible copy, data, emphasis, and page-local sources |
| Bundled PPT Master | Full page strategy, information design, template application, SVG construction, review, and repair |

Keep candidates in `svg_working/<Slide ID>/`. Publish exactly one confirmed
artifact per authored page to `svg_output/<Slide ID>.svg`. Do not put candidate
versions, revision text, or PPT Master internals in `framework.md`.

## Load only what the current action needs

- Intake: read [references/deliverable-types.md](references/deliverable-types.md).
- Storyline/content: read [references/storyline-and-content.md](references/storyline-and-content.md) and exactly one confirmed type policy.
- Create or repair `framework.md`: read [references/framework-contract.md](references/framework-contract.md).
- First content write or schema failure: read [references/output-contract.md](references/output-contract.md).
- External facts or citations: read [references/research-and-sources.md](references/research-and-sources.md).
- Any SVG action: read [references/svg-candidate-workflow.md](references/svg-candidate-workflow.md).
- Initialization, reopen, or recovery: read [references/presentation-workflow.md](references/presentation-workflow.md).

## Intake and Storyline

Classify the deliverable as `Proposal`, `Sharing deck`, `Training`,
`Interpretation`, or `Other: <specific form>` and obtain confirmation unless the
user waives it. Draft and obtain approval for the complete Storyline before
creating `framework.md`.

Make each substantive page's Storyline plan content-rich: normally include
three to five specific planned content units that together establish the main
claim and the relevant explanation, evidence, example, boundary, implication,
or action. Do not use vague topic labels or pad unsupported material. Keep
Cover, Agenda, Section divider, protected, and closing pages appropriately
concise for their structural role.

Begin with Cover at S01. At six or more substantive pages, add Agenda at S02 and
at least one Section divider. Create framework 3.1 / workflow 6.0 with a stable
plain `.pptx` filename reserved for the future export stage, then run:

```bash
python3 <skill-root>/scripts/workflow_controller.py bootstrap --project-dir <absolute-project-directory>
```

## Controller discipline

On entry, re-entry, post-compaction, or uncertain state, run controller
`next --format json` once. Follow only its current action and emitted paths and
commands. A successful mutation prints the next directive; do not immediately
replay `next`.

Process only the first non-terminal Slide ID. Never mutate workflow state,
promote content, publish an SVG, or infer a user decision outside controller
commands.

## Content gate

For `PRESENT_PAGE_REVIEW`, replace all of
`working/provisional-content.md` with exactly the active page. Write final
on-slide copy, complete data, emphasis, and sources; include no visual direction
or layout instruction. Run `present-review`, show the full content, and wait for
explicit approval before `approve-content`.

Never invent client, audience, source, EY, credential, case, people, capacity,
fee, schedule, tool, approval, learning outcome, or business-outcome facts.

## SVG gate

For `PREPARE_SVG_CANDIDATES`, run the emitted command. It creates one independent
A request for Cover, Agenda, Section divider, and Ending pages. It creates
independent A and B requests from the same locked content for every other
authored page.

For `RUN_EMBEDDED_PPT_MASTER_SVG`, process every request independently:

1. Read its `service_contract` and request JSON.
2. Run `validate_request`.
3. Obey the request's `design_quality` and `variant_direction`. Treat the first
   authored SVG as an internal draft; complete information design, page
   composition, art-direction refinement, full-slide review, and source repair
   before the candidate becomes visible.
4. Let the bundled PPT Master write only `requested_artifact` as the durable
   output of that internal loop.
5. Run `complete`, then run `record` only for a COMPLETE result.

Make both A and B executive-grade. Use coherent icons where they improve
recognition, scanning, or visual rhythm, and omit them otherwise. Do not reduce
A to a generic safe draft, B to an ornamental experiment, or design quality to
extra icons or effects. Do not reduce B to a cosmetic variation when a
meaningful alternative exists.
Do not expose PPT Master's internal strategy as another EY approval gate.

Run the emitted presentation command for `PRESENT_SVG_OPTION`,
`PRESENT_SVG_OPTIONS`, or `PRESENT_SVG_REVISION`. Display every emitted SVG at
review scale and collect one explicit decision. Confirm one displayed version,
or write the user's concrete advice to the emitted feedback file and request a
revision from one displayed base. Each revision produces one immutable `R<n>`;
present Base/Rn for comparison and repeat until confirmation.

Only `confirm-svg` may copy a candidate into `svg_output/`. Reopen content when
approved meaning or exact copy changes; reopen SVG when only design should be
restarted. Deliver the confirmed SVG set only when the controller reports
`SVG_STAGE_COMPLETE`.

## Current delivery boundary

Stop at `SVG_STAGE_COMPLETE`. A later skill version may add a separate
confirmed-SVG-to-PPTX export stage, but the current workflow must not initialize,
simulate, or invoke that future stage. `Output filename` is reserved metadata;
it does not imply that this version produces a PPTX.
