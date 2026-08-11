# Quality-gate interpretation

Use this policy whenever the controller or export runner reports a failure.

## Gate ownership and reuse

| Gate | Retain here | Exclude from this gate |
|---|---|---|
| Page preflight (`page-author-result`) | path and artifact identity; XML/root/canvas; self-containment and CSS-free boundary; exact visible-copy bindings; fixed typography scale | A/B distinction; rendered bounds; user choice; deep native-PPTX compatibility; package checks |
| Browser preview | network isolation; font-ready rendering; exact DOM copy; computed visibility; non-empty and on-canvas bounds; equal-size PNGs; renderer/PNG/hash evidence | repeated XML/CSS/typography parsing when a current preflight receipt matches; subjective design judgment; native-PPTX compatibility |
| A/B or revision comparison | equal canonical canvas; targeted revision integrity; displayed-preview and user-selection evidence; A/B hash and material-difference observations recorded as evidence | repeated page-preflight checks; content reapproval; Stage 2 compatibility |
| Canonical handoff | exactly one selected SVG per page; page order; terminal states; selected/canonical/presentation hashes and receipts | design review; preview regeneration; A/B re-evaluation; deep SVG compatibility |
| Confirmed SVG export | staged hashes and runtime; pre-normalization topology detection; isolated deterministic normalization; exact-copy and topology rechecks; typography; converter-critical geometry, paint, reference, image, text-frame, and metadata compatibility | semantic design or copy re-review; another A/B selection after a proven identity-preserving repair; valid contextual colors/fonts; canonical-spelling and portability advice; optional grouping/animation hints as blockers |
| PPTX postflight and handoff | readable package; slide count; relationships; transition/animation OOXML; exported typography; required output; terminal-result integrity | upstream authoring, preview, A/B, or semantic-design checks |

Treat one current page-preflight receipt as sufficient evidence only when its
schema, artifact hash, packet hash, and visible-copy-contract hash match. If any
bound value changes, rerun page preflight. Never reuse it across the confirmed
export boundary.

## Hard blockers

Block only when continuing would invalidate approved meaning, evidence, deterministic handoff, native conversion, or the delivered package:

- schema/state corruption, stale hashes, wrong paths, missing receipts, or wrong page order;
- changed, missing, duplicated, hidden, or materially off-canvas approved visible copy;
- any visible text outside the fixed 24/18/14/12/10/8/6 pt typography scale;
- missing user presentation/selection evidence;
- an authored SVG `<text>` that would become multiple native PowerPoint text
  boxes in merge mode;
- malformed SVG/XML, non-self-contained assets, unsupported rendering features, invalid geometry/paint/reference syntax, or metadata that changes conversion behavior;
- unreadable/corrupt PPTX, dangling relationships, wrong slide count, or invalid transition/animation OOXML;
- unavailable or changed bound runtimes and validators.

Use `source-svg` only for a defect in the named SVG bytes, `user-decision` only for unresolved meaning or approval, and `environment` for missing/changing runtimes, validators, permissions, or dependencies.

## Non-blocking findings

Never reopen content or design solely for:

- identical A/B artifact hashes, missing/empty A/B `material_differences` evidence,
  or a revision artifact identical to its bound base;
- valid contextual colors/fonts already present in a hash-bound confirmed SVG;
- canonical spelling recommendations for converter-compatible values;
- optional page-role, animation-anchor, grouping, or module-bound metadata;
- portability advice such as generic font stacks;
- wording-length or content-richness heuristics that require human semantic judgment.

Report these as `advisory` or `inherited`. `passed-with-warnings` still means the quality gate passed.
Identical A/B artifacts or insufficient A/B difference evidence must still proceed to the
equal-scale browser comparison and explicit user selection; they do not trigger
`RESOLVE_AB_CONFLICT` or candidate repair by themselves. A revision identical to its bound
base must likewise proceed to the equal-scale Base/Rn comparison and explicit user
confirmation, with the identity recorded as an advisory.

## Interpretation safeguards

- Compare canvases by canonical viewBox geometry, not raw `width`, `height`, comma, whitespace, or numeric spelling.
- Ignore wrapping whitespace without deleting meaningful English word spaces.
- Treat isolated analytical words such as “matrix” or “timeline” as content unless accompanied by a construction instruction.
- Treat an inert `class` attribute as metadata; block CSS dependencies such as `<style>`, external stylesheets, or `@import`.
- Accept both consistent absolute-`y` and relative-`dy` wrapped `<tspan>`
  authoring, but require merge-mode export to preserve the owning `<text>` as
  one native PowerPoint text box.
- Repair a missing parent `<text y>` automatically on the isolated Stage 2
  copy only when the unchanged first absolute-y line supplies an unambiguous
  baseline. Normalize mergeable paragraph blocks without splitting rejected
  blocks; then require exact-copy PASS and an empty post-normalization topology
  violation set. Do not reopen user selection after that proven technical
  repair.
- If every SVG-gate error says a validator/import is unavailable, classify the block as `environment`, not `source-svg`.
