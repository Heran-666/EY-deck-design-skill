---
description: Composable page-level single-SVG review service used by a parent workflow through a validated request contract.
---

# Page SVG Service

## Scope

This EY-only internal service accepts a validated
`ppt-master.page-svg-request.v4` with `caller: ey-deck-design` and a
hash-bound `ey-deck.page-authoring-context.v6`. Read request v2 only to recover
an active legacy cycle.

EY owns content, order, candidate naming, user choice, and publication. PPT
Master owns design, SVG construction, direct source inspection, and technical
quality. Do not initialize a PPT Master project, choose a top-level route,
change EY state, export PPTX, or question the user here.

## Entry

1. Run the embedded-root attribution guard.
2. Reuse the current session's valid bundled Python path, or load workspace
   dependencies if unknown or unavailable. Set command-scoped
   `EY_DECK_SVG_PYTHON` to that executable and run the request's `validate_request`.
3. Read the bound authoring context, including `communication.consumption_mode`,
   `page_rhythm`, `page_logic`, `design_quality_profile`, approved content,
   project/page context, the bound `template.design_spec.path`, and exact
   prototype. Load the applicable core construction rules in
   `references/executor-base.md` and template rules in
   `references/executor-structured.md`. Use relevant sections of
   `references/plan-core.md` or `references/strategist-template.md` only for an
   unresolved page-level design choice; `references/strategist.md` is not an
   entry requirement. Load specialist references only for objects being drawn.
   Reuse unchanged reference sections already in valid context; reread changed
   or uncertain bindings instead of reloading every reference for each page.
4. For A, follow Full design loop; for Rn, follow Initial SVG and revisions.
   Write only `artifact_path`.
5. Apply Resource inlining before the applicable source review. After the
   bounded repair/validation gate passes,
   run `record` once. It
   binds the exact request and artifact accepted by final `complete` validation.

## Upstream 6.4 integration boundary

The shared references are design/construction authorities inside this service.
Generic Default/Quick routing, confirmation stages, three-direction planning,
whole-deck roster sweeps, project initialization, preview launch, spec/lock
creation, notes, motion, narration, and export commands never execute here.
Evaluate capability triggers over the current request only; load an unforeseen
module before drawing the affected object.

Use these bindings wherever a shared reference expects a plan or lock:

| Generic reference input | EY service authority |
|---|---|
| Page brief / §IX semantic content | `approved_content` and `page_logic` |
| Core message / Audience move / Relationships | `page_logic`'s approved claim, audience move, argument chain, and relationship constraints; structural pages use the bound page context |
| Reading mode / page rhythm | `communication.consumption_mode` and `page_rhythm` |
| Identity, typography, spacing, template mapping | Bound `template.design_spec` and exact `template.prototype` |
| Roster / consistency / revision | Current Slide ID, `consistency_references`, and the request's exact base/feedback |

Composition sketches are References; EY identity, fixed atoms, literal
requirements, and approved meaning remain binding. Use the new text-measurement,
contour vocabulary, topology, gradients, inline emphasis, and technical checks
without creating another user gate or changing the candidate cycle.

Native Office Math markers (`data-pptx-inline-formula` and
`data-pptx-replace-with="formula"`) are not enabled in this integration: EY's
text audit currently compares ordinary DrawingML runs and semantic paragraphs.
Do not author these markers or activate native Chart/Table replacement at export;
charts/tables continue through their visible editable shape/text representation.
The supporting compiler may remain bundled as a converter dependency.

## Resource inlining

This EY-local rule replaces shared Executor's project-pool-only lookup and
missing-resource return for material preparation. It does not activate the
generic project's resource workflow. Select suitable icons from the bundled
`templates/icons/` library or an exact user-provided icon root, and use exact
existing picture files supplied for the current request. Preserve mandatory
assets and approved meaning; optional assets may yield to another expression.
Do not search/download remote pictures, generate new assets, invent evidence,
copy resource pools, or introduce another user gate here.

**EY icon expression** — the shared icon README's single stylistic-library
selection rule does not bind this service. Choose by semantic fit; cross-library
selection is allowed. Maintain coherence through contour language, fill/outline
treatment, stroke weight, palette, and visual weight rather than library
membership. Preserve authentic brand identity and use brand marks only for the
brands they identify. The external-asset generation restriction above does not
prohibit hand-authoring original icon geometry directly in the current page SVG;
it follows the same supported-SVG, approved-meaning, and template contracts.

Before reviewing a draft that contains material references, run:

```bash
<bundled-python> <embedded-root>/scripts/page_svg_service.py inline-resources <absolute-request-path>
```

Use the same executable, script root, and request as `validate_request`.
The default icon root is the bundled library. For an exact existing custom
library root, pass `--icons-dir <absolute-icon-root>`; identifiers remain
`library/name`. Picture hrefs may identify exact local files by absolute path or
relative to the candidate, only during drafting.

The helper expands icon and static same-document `<use>` instances, then embeds
picture bytes as data URIs without compression, cropping, or resampling. It
changes only the requested draft, atomically, and leaves it unchanged on failure.
The controller-issued `candidate_receipt_path` must be present and not yet
recorded; recorded versions are rejected even if already closed. Already closed
unrecorded drafts need no rewrite. It never authors composition or changes
fixed template atoms; do not use it on an ordinary recorded/confirmed version.
Legacy requests without that field remain readable but cannot run this helper;
inline their unrecorded draft through ordinary page edits, or use a new
controller-issued Rn for a recorded version. Never invent a receipt path.

At review and COMPLETE, icons are ordinary inline SVG geometry and pictures are
embedded data, including recursively closed SVG pictures. No `<use>` or external
material reference remains. Supported local paint/clip/filter references stay
legal. Resource inlining is not a visual or technical completion gate: perform
the existing source review and final `record` on the resulting exact draft.
If existing confirmed resources need closure, author the requested Rn and
reconfirm; export never performs this transformation.

## Full design loop

1. **Strategist / information design** — apply
   `communication.consumption_mode` and `page_rhythm` together before choosing
   the information model, using Executor's reading-mode check and per-page
   layout-rhythm discipline. For substantive pages, preserve the
   approved objective, audience move, argument chain, relationship constraints,
   and argument priority in `page_logic`. Follow `executor-base.md`'s `content
   vs expression` rule for wording and text texture. Determine the communication
   model, visual concept, geometry, and composition without rendering build-only
   text.
2. **Page composition** — establish one dominant idea and reading order through
   scale, position, contrast, whitespace, and semantic geometry.
3. **Visual system and template** — apply the bound EY identity and maintain
   deck coherence without copying prior compositions. Preserve Master/Layout
   identity and fixed atoms. Placeholder bounds are metadata, not design limits;
   use the full 1280×720 canvas.
4. **Specialist choice** — use chart, table, qualitative structure, imagery,
   icons, typography, semantic SVG, and effects when they improve
   communication. Icons may serve recognition, navigation, grouping, visual
   rhythm, or emphasis; avoid icon clutter with no communication purpose.
   Apply the EY icon expression rule above.
5. **Executor** — hand-author a complete editable SVG as an internal draft.
6. **Art-direction refinement** — assess hierarchy, rhythm, optical balance,
   connectors, emphasis, and chosen treatments against the
   `ey-executive-editorial-v3` quality profile; repair specific unmet criteria.
7. **Review and repair** — inspect the complete source SVG at full-slide scale
   for composition, craft, clipping, overlap, legibility, and template fidelity;
   combine identified repairs in one pass and verify once before returning
   COMPLETE. Once the source review and deterministic checks pass, stop.
   Repeat only for new changes, failed checks, or a specific unresolved defect;
   do not keep polishing a passing page for hypothetical improvements.

Do not use Chromium, Playwright, or another browser renderer for candidate QA.
Direct source-SVG review and deterministic validation are the completion
evidence. Keep internal design decisions inside PPT Master.

## Initial SVG and revisions

Build one complete A solution. EY supplies no separate wording policy, candidate design role, or layout.

For Rn, bind the one displayed base and non-empty user feedback. Preserve the
base except for requested changes and necessary reflow. Review the affected
elements and their page-level consequences, then run the required deterministic
validation once on the final artifact. Apply the same bounded repair discipline;
do not restart unrelated planning or broaden a targeted revision into a redesign.
Return one revised SVG for the next review round.

## Invariants

- Follow `executor-base.md`'s `content vs expression` hard rule. Concise
  connective copy that introduces no new claim is an expression choice.
- **Hard rule — EY fit completion**: For a substantive page in this service, if
  information-equivalent content cannot fit after changing expression, reflow,
  geometry, and composition, delete non-essential material in
  `page_logic.argument_priority` order. Remove repeated explanation, redundant
  examples, optional context, low-priority elaboration, and connective copy
  first. Omit secondary evidence only when the remaining evidence still
  supports the claim. Preserve literal requirements and anything whose omission
  changes the conclusion, accuracy, decision boundary, or audience move. Do not
  return `content-over-capacity` for upstream content repair; complete the
  strongest faithful page that fits. This service-local rule replaces only the
  generic capacity return for EY substantive pages; it does not relax literal
  requirements or any mirror/preservation path.
- This service has no project-root `design_spec.md` or `spec_lock.md`.
  `communication.consumption_mode` and `page_rhythm` are its authoritative
  execution anchors. While operating in this service, do not trigger Executor's
  missing-lock recovery merely because those project-root artifacts do not
  exist.
- Require structured `page_logic` for substantive pages and omit it for Cover,
  Agenda, Section divider, Ending, and protected placeholder pages. Treat it as
  semantic authority, not layout direction or visible copy.
- Begin from the exact `template.prototype`; preserve its Master/Layout,
  fixed atoms, and placeholder contract.
- Agenda's composite region is blank: PPT Master owns item grouping, numbering,
  typography, geometry, and composition.
- Honor `composition_mode: full-slide`. Do not impose a `y=650` cap,
  footer reserve, EY-logo overlap gate, or placeholder clipping boundary.
- Use a self-contained `viewBox="0 0 1280 720"` SVG. Do not use `<style>`,
  `<script>`, `foreignObject`, remote URLs, or runtime placeholders.
- Hand-author page composition. Scripts may validate, render, or convert
  supporting assets, but may not generate it.
- Represent each logical PowerPoint text box with one `<text>` element. Keep
  inline-formatting `<tspan>` runs non-positional with literal word spaces; use
  same-x rows with first `dy="0"` and later positive relative `dy` for multiline
  text. Non-zero `dx`, ambiguous absolute `y`, and fragmented paragraphs block.
- During `complete`, run the exact preserve-mode positional-tspan transform on
  an in-memory copy. Block any source `<text>` carrier that becomes 1→N.
- Inspect and repair the complete source SVG for off-canvas content, clipping,
  overlap, illegibility, broken hierarchy, template drift, and unsupported SVG.

Return BLOCKED only when locked content, the bound template, or the environment
makes completion impossible. Never mutate upstream inputs to escape a block.
