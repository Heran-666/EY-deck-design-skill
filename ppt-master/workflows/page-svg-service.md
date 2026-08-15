---
description: Composable page-level SVG variant service used by a parent workflow through a validated request contract.
---

# Page SVG Service

This is an EY-only internal service entrypoint, not a top-level presentation
route. Use it only when EY Deck Design supplies a validated
`ppt-master.page-svg-request.v1` JSON request with `caller: ey-deck-design`. EY
owns page order, content approval, candidate naming, user choice, and final
publication. PPT Master owns page design, SVG construction,
visual inspection, and technical SVG quality.

## Entry

1. Run the attribution guard from the embedded PPT Master root.
2. Run `python3 scripts/page_svg_service.py validate-request <request.json>`.
3. Read the request, then read `strategist.md`, `strategist-template.md`,
   `executor-base.md`, and `executor-structured.md`. Load chart, table,
   structure, image, semantic-SVG, visual-style, image-palette, or effects
   references whenever the page benefits from them.
4. Write only `artifact_path`, then run
   `python3 scripts/page_svg_service.py complete <request.json>`.
5. Return the exact terminal JSON printed by `complete` to the parent.

Do not accept another caller, initialize a PPT Master project, select a
top-level route, change EY state, export PPTX, or ask the user a question inside
this service.

## Full design loop

The service boundary limits lifecycle authority, not design capability. Perform
the complete PPT Master loop internally for every candidate:

1. **Strategist** — determine the page's audience-facing message, information
   hierarchy, narrative connection, and most effective communication model.
2. **Visual system** — apply the bound EY identity and inspect previously
   confirmed pages for deck consistency without copying their page composition.
3. **Specialist choice** — use the full chart, table, qualitative structure,
   imagery (photography/illustration), icon, typography, semantic SVG, and effects
   capabilities when they improve communication. Generate or source supporting
   images when the request and available tools permit it.
4. **Template application** — preserve the native Master/Layout contract while
   exercising full freedom inside page-local content regions.
5. **Executor** — hand-author a complete, editable, export-ready SVG.
6. **Review and repair** — render or inspect at full-slide scale, run applicable
   technical checks, and repair the owning source until the candidate is ready.

Keep internal strategy and design decisions inside PPT Master. They are not
additional parent-workflow gates or durable EY state.

## Independent variants

Requests for A and B have `mode: independent`. Treat both as complete solutions
to the same locked content. Start each from the bound prototype and content;
do not use A as B's repair target. Difference is useful only when it creates a
meaningful user choice—never change facts or force novelty at the cost of
quality. Prefer a materially different communication model, information
hierarchy, composition, or visualization when two strong alternatives exist;
cosmetic-only variation is insufficient when a substantive alternative is
available.

## Revisions

An Rn request has `mode: revision`, a hash-bound `base`, and non-empty user
`feedback`. Preserve the base except for the requested changes and necessary
dependent reflow. Do not silently broaden a targeted request into an unrelated
redesign. A later Rn may use any currently displayed candidate as its base.

## Content and template invariants

- Preserve every approved visible word, number, source, and emphasis.
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
