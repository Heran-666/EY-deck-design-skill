---
name: ey-deck-design
description: >
  Create and approve EY presentation Storylines and exact slide content, then
  use the bundled PPT Master to generate one complete SVG candidate by default
  and bounded A/B alternatives only for pages with a verified dual-design need,
  iterate from user-selected bases and feedback, publish only explicitly
  confirmed SVGs, and compile the confirmed SVG roster into an editable native
  DrawingML PPTX with text-frame integrity checks. Use only when the user
  explicitly invokes $ey-deck-design.
---

# EY Deck Design

Own the deck workflow, approved content, candidate lifecycle, and user gates.
Use the bundled PPT Master page-SVG service for all page strategy, visual design,
SVG authoring, source-SVG review, and technical QA.

Treat `ppt-master/` as an internal runtime package, never as a second skill. It
has no `SKILL.md` or UI metadata and may be called only through the EY request
adapter. The separately installed global `$ppt-master` remains the only
user-visible PPT Master skill.

## Ownership

| Owner | Responsibility |
|---|---|
| User | Approve Storyline and exact content; choose, revise, and confirm SVGs |
| EY controller | Order, states, paths, hashes, request packets, receipts, recovery, SVG publication, and final handoff |
| `framework.md` | Compact project context, Storyline, and coarse page state |
| `content.md` | Exact approved visible copy, data, emphasis, and page-local sources |
| Bundled PPT Master | Full page strategy, information design, template application, SVG construction, review and repair, native DrawingML conversion, and PPTX postflight |

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
- Any PPTX action: read [references/pptx-export-workflow.md](references/pptx-export-workflow.md).
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
at least one Section divider. Create framework 3.1 / workflow 7.0 with a stable
plain `.pptx` filename for the final export stage, then run:

```bash
python3 <skill-root>/scripts/workflow_controller.py bootstrap --project-dir <absolute-project-directory>
```

## Controller discipline

On entry, re-entry, post-compaction, or uncertain state, run controller
`next --format json` once. Follow only its current action and emitted paths and
commands. A successful mutation prints the next directive; do not immediately
replay `next`.

If `next` reports that an existing workflow 6.0 project requires version 7.0,
read the initialization/recovery reference and run `upgrade-workflow`. Do not
hand-edit the framework version or any lifecycle state.

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

For `PREPARE_SVG_CANDIDATES`, call `load_workspace_dependencies`, set the
command-scoped `EY_DECK_SVG_PYTHON` environment variable to its returned
absolute Python executable, then run the emitted command. Reuse that environment
for the emitted record command; do not install or search for another runtime.
The command creates one independent A request for Cover, Agenda, Section
divider, and Ending pages. For substantive pages, the EY controller writes an
automatic hash-bound `candidate_plan` after content locks: default to A; use A/B
only for approved chart/table evidence, explicit comparison or hierarchy,
high-stakes selection, or an explicit alternatives decision. An explicit
single-candidate decision overrides those triggers. Do not ask for another
per-page confirmation and do not let PPT Master choose the candidate count.

For `RUN_EMBEDDED_PPT_MASTER_SVG`, process every request independently:

1. Read the request JSON and its hash-bound `authoring_context`; read the
   context's `service_contract`.
2. Run `validate_request`.
3. Obey the context's `design_quality`, but derive the strongest communication
   model, information hierarchy, visual concept, geometry, and composition
   inside PPT Master from the complete approved content and project/page
   context. EY does not assign design roles or adaptation rules to candidates.
   When the candidate plan contains A/B, PPT Master chooses the most meaningful
   difference between two complete solutions without an upstream preset axis.
   Treat the first
   authored SVG as an internal draft; complete information design, page
   composition, art-direction refinement, direct source-SVG full-slide review,
   and source repair before the candidate becomes visible. Do not render the SVG
   in Chromium for content or visual QA.
4. Let the bundled PPT Master write only the request's `artifact_path` as the durable
   output of that internal loop.
5. Run `record` once. It atomically performs the final service `complete` check
   and writes the candidate receipt; do not run `complete` separately.

For Content pages, give PPT Master the complete 1280×720 slide for composition.
Treat placeholder bounds only as native PowerPoint metadata. Do not impose a
`y=650` or other inset content cap, reserve a footer band, or run an EY-logo
overlap QA check. This freedom includes imagery, mixed-format text, semantic
geometry, and page-specific compositions; do not reduce capability to avoid a
renderer or validation defect.

Make every planned candidate executive-grade. Use coherent icons where they
improve recognition, scanning, or visual rhythm, and omit them otherwise. When
the plan contains A/B, do not reduce A to a generic safe draft, B to an
ornamental experiment, or design quality to extra icons or effects. Do not
reduce B to a cosmetic variation when a meaningful alternative exists. Follow
PPT Master's own page-specific design judgment; the request does not supply
paired search roles or impose a universal A/B design axis.
Do not expose PPT Master's internal strategy as another EY approval gate.

Run the emitted presentation command for `PRESENT_SVG_OPTION`,
`PRESENT_SVG_OPTIONS`, or `PRESENT_SVG_REVISION`. Display every emitted SVG at
review scale and collect one explicit decision. Confirm one displayed version,
or write the user's concrete advice to the emitted feedback file and request a
revision from one displayed base. Each revision produces one immutable `R<n>`;
present Base/Rn for comparison and repeat until confirmation.

Only `confirm-svg` may copy a candidate into `svg_output/`. Reopen content when
approved meaning or exact copy changes; reopen SVG when only design should be
restarted. After the final SVG confirmation, the controller advances to
`PREPARE_PPTX_EXPORT`.

## PPTX export stage

Do not hand-edit confirmed SVGs during export. For `PREPARE_PPTX_EXPORT`, run the
emitted command to freeze the ordered SVG roster, hashes, output path, and
conversion contract. For `RUN_EMBEDDED_PPT_MASTER_PPTX`, read the emitted
service contract and request. Call `load_workspace_dependencies`, set the
command-scoped `EY_DECK_PPTX_PYTHON` environment variable to its returned
absolute Python executable, then run the emitted command. Do not search for or
install another runtime.

The export must use the bundled PPT Master's editable native DrawingML route,
flat Quick Generate structure, no speaker notes, explicit `preserve` text flow,
conversion tracing, final SVG quality checking, package postflight, and
per-slide text-frame parity auditing. One logical text box must be one SVG
`<text>` carrier; mixed formatting and multiline content belong in child
`<tspan>` runs. Never use `--no-merge` or accept paragraph-like lines split
across sibling `<text>` elements.

If text-frame preflight fails, reopen the named page's SVG stage and obtain
confirmation again; confirmed SVG bytes are immutable. Deliver only when the
controller reports `PPTX_STAGE_COMPLETE`, and return the final PPTX rather than
the intermediate request, reports, trace, or receipts unless the user asks.
