---
description: Composable page-level SVG variant service used by a parent workflow through a validated request contract.
---

# Page SVG Service

This is an EY-only internal service entrypoint, not a top-level presentation
route. Use it only when EY Deck Design supplies a validated
`ppt-master.page-svg-request.v3` JSON request with `caller: ey-deck-design` and
a hash-bound `ey-deck.page-authoring-context.v1`. Read v2 only for recovery of
an already active legacy cycle. EY
owns page order, content approval, candidate naming, user choice, and final
publication. PPT Master owns page design, SVG construction,
direct source-SVG inspection, and technical SVG quality.

## Entry

1. Run the attribution guard from the embedded PPT Master root.
2. Load workspace dependencies, set command-scoped `EY_DECK_SVG_PYTHON` to the
   returned absolute Python executable, and run the parent-provided
   `validate_request` command. Use that verified runtime for SVG validation and
   finalization. Do not load or invoke a browser-rendering capability for candidate QA.
3. Read the request's hash-bound `authoring_context`. Read `design_quality`, the
   EY-owned `candidate_plan`, and `template.design_spec.path` from that shared context and
   `variant_direction` from the candidate request, then read
   `references/strategist.md`, `references/strategist-template.md`,
   `references/executor-base.md`, and `references/executor-structured.md`. Load chart, table,
   structure, image, semantic-SVG, visual-style, image-palette, or effects
   references whenever the page benefits from them.
4. Execute the full internal design loop and write only `artifact_path` as its
   durable output.
5. Treat the first authored SVG as an internal draft. Complete every ordered
   `design_quality.visible_candidate_gate` pass, then run the parent-provided
   `record` command once. It atomically invokes the final `complete` validation
   and records the accepted candidate; do not run `complete` separately.

Do not accept another caller, initialize a PPT Master project, select a
top-level route, change EY state, export PPTX, or ask the user a question inside
this service.

## Full design loop

The service boundary limits lifecycle authority, not design capability. Perform
the complete PPT Master loop internally for every candidate:

1. **Strategist / information design** — determine the page's audience-facing message,
   information hierarchy, narrative connection, and most effective communication
   model. Translate `variant_direction` into a page-specific solution; never
   treat its role as a fixed layout recipe.
2. **Page composition** — establish one dominant visual idea and an intentional
   reading order through scale, position, contrast, whitespace, and semantic
   geometry before choosing local containers or decoration.
3. **Visual system** — apply the bound EY identity and inspect previously
   confirmed pages for deck consistency without copying their page composition.
4. **Specialist choice** — use the full chart, table, qualitative structure,
   imagery (photography/illustration), icon, typography, semantic SVG, and effects
   capabilities when they improve communication. Generate or source supporting
   images when the request and available tools permit it. Use one coherent icon
   language at semantically appropriate positions when it improves recognition,
   scanning, or visual rhythm; omit icons that have no clear communication job.
5. **Template application** — preserve the native Master/Layout contract while
   exercising full-page composition freedom. Placeholder bounds are native
   PowerPoint metadata, not SVG design limits. Use the complete 1280×720 canvas;
   do not impose a `y=650` cap, reserve a footer band, or add an EY-logo overlap
   QA gate.
6. **Executor** — hand-author a complete, editable SVG as an internal draft.
7. **Art-direction refinement** — actively replace generic dashboards, unjustified
   stacked cards, equal-column defaults, repeated rounded rectangles, icon-led
   decoration, or effects without a communication job. Refine hierarchy, rhythm,
   optical balance, edges, connectors, and emphasis until the page satisfies
   every `design_quality.must_have` and none of `design_quality.avoid`.
8. **Review and repair** — inspect the complete source SVG directly at full-slide
   coordinate scale. Review composition and craft as well as clipping, overlap,
   legibility, and template fidelity. Repair the owning SVG and reinspect the
   source before returning COMPLETE. The first visible candidate must never be
   merely the first draft.

Do not invoke Chromium, Playwright, or another browser renderer to QA candidate
content or appearance. Browser output is neither a prerequisite nor completion
evidence. Candidate acceptance rests on direct source-SVG review plus the
service's deterministic technical validation.

Keep internal strategy and design decisions inside PPT Master. They are not
additional parent-workflow gates or durable EY state.

## Independent variants

Honor the EY-owned adaptive `candidate_plan`; never change its versions or ask
for another confirmation. Structural and default substantive pages receive only
independent A. Pages with a verified dual-design need receive independent A and
B requests. Treat every emitted candidate as a complete solution to the same
locked content. For A/B, start each from the bound prototype and content; do not
use A as B's repair target. Difference is useful only when it creates a meaningful
user choice—never change facts or force novelty at the cost of quality. Prefer a
materially different communication model, information hierarchy, composition,
or visualization when two strong alternatives exist; cosmetic-only variation
is insufficient when a substantive alternative is available.

Honor each request's dynamically selected search role without weakening either
option. The adapter derives the paired roles from the page's approved content
form and approved user intent: Narrative role, Audience outcome, and Storyline
thesis. Treat the role as a search bias, not a prescribed layout. For an A/B
plan, use `alternative_contract` to ensure that A and B differ
materially in their communication model, information hierarchy, or
composition/visualization; do not fall back to one universal A/B axis.

Do not make A a generic safe draft or B an ornamental experiment. Both must
pass the same `design_quality` contract before the parent may display them.
For any A-only plan, apply its selected complete direction within the bound
template; do not invent B, an alternative contract, or a second lifecycle branch.

## Revisions

An Rn request has `mode: revision`, a hash-bound `base`, and non-empty user
`feedback`. Preserve the base except for the requested changes and necessary
dependent reflow. Do not silently broaden a targeted request into an unrelated
redesign. Preserve the same quality floor and repeat the visible-candidate gate.
A later Rn may use any currently displayed candidate as its base.

## Content and template invariants

- Preserve every approved visible word, number, source, and emphasis.
- Treat Emphasis as mandatory semantic priority, not an exhaustive style map.
  PPT Master may establish hierarchy among any existing text and may freely use
  non-text elements such as icons, shapes, color fields, and dividers, but must
  not add or rewrite audience-facing copy.
- Begin from the exact `template.prototype`; preserve its Master/Layout identity,
  fixed atoms, and placeholder contract.
- Honor the authoring context's `composition_space.mode: full-slide`. Do not treat the object-slot
  rectangle or any inherited placeholder bounds as a clipping, safety, or
  composition boundary.
- Keep the SVG self-contained, with `viewBox="0 0 1280 720"`; do not use
  `<style>`, `<script>`, `foreignObject`, remote URLs, or runtime placeholders.
- Hand-author the page SVG. Scripts may validate, render, or convert supporting
  assets but must not generate the page composition.
- Author one logical PowerPoint text box as one `<text>` element. Put mixed
  formatting and multiline content in child `<tspan>` runs; never author one
  paragraph's visual lines as sibling `<text>` elements. Treat the quality
  checker's fragmented-paragraph warning as blocking and repair it before
  returning COMPLETE.
- Inspect the complete source SVG at full-slide coordinate scale and repair clipping, overlap,
  off-canvas content, unreadable text, broken hierarchy, template drift, and
  unsupported SVG before returning COMPLETE. Do not use a Chromium render for
  this inspection.

Return BLOCKED only when locked content, the bound template, or the environment
makes completion impossible. Do not mutate upstream inputs to escape a block.
