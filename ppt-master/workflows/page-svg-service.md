---
description: Composable page-level SVG variant service used by a parent workflow through a validated request contract.
---

# Page SVG Service

This is an EY-only internal service entrypoint, not a top-level presentation
route. Use it only when EY Deck Design supplies a validated
`ppt-master.page-svg-request.v2` JSON request with `caller: ey-deck-design`. EY
owns page order, content approval, candidate naming, user choice, and final
publication. PPT Master owns page design, SVG construction,
visual inspection, and technical SVG quality.

## Entry

1. Run the attribution guard from the embedded PPT Master root.
2. Run the parent-provided `validate_request` command. Reuse that command's
   absolute Python executable for finalization, preview, and render QA.
3. Read the request, including `design_quality` and `variant_direction`, then
   read `references/strategist.md`, `references/strategist-template.md`,
   `references/executor-base.md`, and `references/executor-structured.md`. Load chart, table,
   structure, image, semantic-SVG, visual-style, image-palette, or effects
   references whenever the page benefits from them.
4. Execute the full internal design loop and write only `artifact_path` as its
   durable output.
5. Treat the first authored SVG as an internal draft. Complete every ordered
   `design_quality.visible_candidate_gate` pass, then run
   the parent-provided `complete` command.
6. Return the exact terminal JSON printed by `complete` to the parent.

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
   exercising full freedom inside page-local content regions.
6. **Executor** — hand-author a complete, editable SVG as an internal draft.
7. **Art-direction refinement** — actively replace generic dashboards, unjustified
   stacked cards, equal-column defaults, repeated rounded rectangles, icon-led
   decoration, or effects without a communication job. Refine hierarchy, rhythm,
   optical balance, edges, connectors, and emphasis until the page satisfies
   every `design_quality.must_have` and none of `design_quality.avoid`.
8. **Review and repair** — render or inspect the complete page at slide
   scale. Review composition and craft as well as clipping, overlap, legibility,
   and template fidelity. Repair the owning SVG and recheck it before returning
   COMPLETE. The first visible candidate must never be merely the first draft.

Keep internal strategy and design decisions inside PPT Master. They are not
additional parent-workflow gates or durable EY state.

## Independent variants

Cover, Agenda, Section divider, and Ending receive only independent A as their
initial candidate. Other authored pages receive independent A and B requests.
Treat every emitted candidate as a complete solution to the same locked content.
For A/B, start each from the bound prototype and content; do not use A as B's
repair target. Difference is useful only when it creates a meaningful user
choice—never change facts or force novelty at the cost of quality. Prefer a
materially different communication model, information hierarchy, composition,
or visualization when two strong alternatives exist; cosmetic-only variation
is insufficient when a substantive alternative is available.

Honor the bound search bias without weakening either option:

- **A / `clarity-led-editorial`** — prioritize immediate comprehension,
  deliberate whitespace, confident typography, and restrained editorial rhythm.
- **B / `concept-led-spatial`** — prioritize an equally polished spatial model,
  relationship, progression, contrast, or page-specific visual metaphor.

Do not make A a generic safe draft or B an ornamental experiment. Both must
pass the same `design_quality` contract before the parent may display them.
For an A-only structural page, apply A's clarity-led direction within the bound
template and the page role; do not invent B or a second lifecycle branch.

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
- Keep the SVG self-contained, with `viewBox="0 0 1280 720"`; do not use
  `<style>`, `<script>`, `foreignObject`, remote URLs, or runtime placeholders.
- Hand-author the page SVG. Scripts may validate, render, or convert supporting
  assets but must not generate the page composition.
- Inspect the complete page at slide scale and repair clipping, overlap,
  off-canvas content, unreadable text, broken hierarchy, template drift, and
  unsupported SVG before returning COMPLETE.

Return BLOCKED only when locked content, the bound template, or the environment
makes completion impossible. Do not mutate upstream inputs to escape a block.
