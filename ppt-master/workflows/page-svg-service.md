---
description: Composable page-level single-SVG review service used by a parent workflow through a validated request contract.
---

# Page SVG Service

## Scope

This EY-only internal service accepts a validated
`ppt-master.page-svg-request.v3` with `caller: ey-deck-design` and a
hash-bound `ey-deck.page-authoring-context.v1`. Read v2 only to recover an
active legacy cycle.

EY owns content, order, candidate naming, user choice, and publication. PPT
Master owns design, SVG construction, direct source inspection, and technical
quality. Do not initialize a PPT Master project, choose a top-level route,
change EY state, export PPTX, or question the user here.

## Entry

1. Run the embedded-root attribution guard.
2. Load workspace dependencies; set command-scoped `EY_DECK_SVG_PYTHON` to the
   returned Python executable; run the request's `validate_request` command.
3. Read the bound authoring context, including `design_quality`,
   `candidate_plan`, approved content, project/page context, and
   `template.design_spec.path`. Then read `references/strategist.md`,
   `references/strategist-template.md`, `references/executor-base.md`, and
   `references/executor-structured.md`; load specialist references only when
   useful.
4. Run the full design loop and write only `artifact_path`.
5. Complete every `design_quality.visible_candidate_gate` pass, then run
   `record` once. It performs final `complete` validation atomically.

## Full design loop

1. **Strategist / information design** — recover intent from the hash-bound
   context; determine message, hierarchy, narrative connection, communication
   model, visual concept, geometry, and composition.
2. **Page composition** — establish one dominant idea and reading order through
   scale, position, contrast, whitespace, and semantic geometry.
3. **Visual system and template** — apply the bound EY identity and maintain
   deck coherence without copying prior compositions. Preserve Master/Layout
   identity and fixed atoms. Placeholder bounds are metadata, not design limits;
   use the full 1280×720 canvas.
4. **Specialist choice** — use chart, table, qualitative structure, imagery,
   icons, typography, semantic SVG, and effects when they improve
   communication. Keep one coherent icon language and omit decorative icons.
5. **Executor** — hand-author a complete editable SVG as an internal draft.
6. **Art-direction refinement** — refine hierarchy, rhythm, optical balance,
   connectors, emphasis, and chosen treatments until all
   `design_quality.must_have` requirements pass.
7. **Review and repair** — inspect the complete source SVG at full-slide scale
   for composition, craft, clipping, overlap, legibility, and template fidelity;
   repair and reinspect before returning COMPLETE.

Do not use Chromium, Playwright, or another browser renderer for candidate QA.
Direct source-SVG review and deterministic validation are the completion
evidence. Keep internal design decisions inside PPT Master.

## Initial SVG and revisions

Follow the EY-owned `candidate_plan`: build one complete A solution and do not
invent B or another initial option. EY supplies no candidate role, adaptation
rule, or layout.

For Rn, bind the one displayed base and non-empty user feedback. Preserve the
base except for requested changes and necessary reflow. Repeat the same quality
gate; do not broaden a targeted revision into an unrelated redesign. Return one
revised SVG for the next review round.

## Invariants

- Preserve every approved visible word, number, source, and Emphasis. Emphasis
  defines mandatory semantic priority, not a complete style map. Do not add or
  rewrite audience-facing copy.
- Begin from the exact `template.prototype`; preserve its Master/Layout,
  fixed atoms, and placeholder contract.
- Agenda's composite region is blank: PPT Master owns item grouping, numbering,
  typography, geometry, and composition.
- Honor `composition_space.mode: full-slide`. Do not impose a `y=650` cap,
  footer reserve, EY-logo overlap gate, or placeholder clipping boundary.
- Use a self-contained `viewBox="0 0 1280 720"` SVG. Do not use `<style>`,
  `<script>`, `foreignObject`, remote URLs, or runtime placeholders.
- Hand-author page composition. Scripts may validate, render, or convert
  supporting assets, but may not generate it.
- Represent each logical PowerPoint text box with one `<text>` element and
  child `<tspan>` runs. Fragmented paragraphs are blocking.
- Inspect and repair the complete source SVG for off-canvas content, clipping,
  overlap, illegibility, broken hierarchy, template drift, and unsupported SVG.

Return BLOCKED only when locked content, the bound template, or the environment
makes completion impossible. Never mutate upstream inputs to escape a block.
