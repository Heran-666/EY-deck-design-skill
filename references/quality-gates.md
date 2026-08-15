# Quality-gate interpretation

Use this policy whenever the controller or export runner reports a failure.

## Gate ownership and reuse

| Gate | Retain here | Exclude from this gate |
|---|---|---|
| Stage 1 acceptance (`ppt-master-result`) | requested path and artifact identity; XML/root/canvas; self-containment and CSS-free boundary; exact visible-copy bindings; fixed typography scale; bound template root, fixed atoms, definitions, and placeholder contract | PPT Master's internal design reasoning or visual QA; candidate count; A/B distinction; user decision; deep native-PPTX compatibility |
| Browser preview | network isolation; font-ready rendering; exact DOM copy; computed visibility; non-empty and on-canvas bounds; equal-size PNGs; renderer/PNG/hash evidence | repeated XML/CSS/typography parsing when a current Stage 1 acceptance receipt matches; subjective design judgment; native-PPTX compatibility |
| Initial or revision presentation | mode-required single or A/B preview evidence; equal canonical canvas when comparing; targeted revision integrity; user-decision evidence; A/B hash and material-difference observations only for Standard pages | repeated Stage 1 acceptance checks; content reapproval; Stage 2 compatibility |
| Canonical handoff | exactly one confirmed SVG per page; page order; terminal states; confirmed/canonical/presentation hashes and receipts | design review; preview regeneration; candidate re-evaluation; deep SVG compatibility |
| Confirmed SVG export | staged hashes and runtime; pre-normalization topology detection; isolated deterministic normalization; exact-copy and topology rechecks; typography; converter-critical geometry, paint, reference, image, text-frame, and metadata compatibility | semantic design or copy re-review; another user decision after a proven identity-preserving repair; valid contextual colors/fonts; canonical-spelling and portability advice; optional grouping/animation hints as blockers |
| PPTX postflight and handoff | readable package; slide count; relationships; transition/animation OOXML; exported typography; required output; terminal-result integrity | upstream authoring, preview, candidate-decision, or semantic-design checks |

Treat one current Stage 1 acceptance receipt as sufficient evidence only when its
schema, artifact hash, packet hash, visible-copy-contract hash, and structured-template-contract hash match. If any
bound value changes, rerun Stage 1 acceptance. Never reuse it across the confirmed
export boundary.

## Hard blockers

Block only when continuing would invalidate approved meaning, evidence, deterministic handoff, native conversion, or the delivered package:

- schema/state corruption, stale hashes, wrong paths, missing receipts, or wrong page order;
- changed, missing, duplicated, hidden, or materially off-canvas approved visible copy;
- any visible text outside the fixed 40/24/18/14/12/10/8/6 pt typography scale; 40 pt is reserved for bound Cover and Section divider display titles;
- missing, stale, or changed template profile/prototype hashes, root Master/Layout identity, fixed template atoms/definitions (including exact template-fixed copy), or placeholder ids/types/bounds;
- missing mode-required user presentation or decision evidence;
- an authored SVG `<text>` that would become multiple native PowerPoint text
  boxes in merge mode;
- malformed SVG/XML, non-self-contained assets, unsupported rendering features, invalid geometry/paint/reference syntax, or metadata that changes conversion behavior;
- unreadable/corrupt PPTX, dangling relationships, wrong slide count, or invalid transition/animation OOXML;
- unavailable or changed bound runtimes and validators.

Flat export may remove structured-only Master/Layout/layer/placeholder metadata
from isolated Stage 2 working copies. Treat this as a permitted technical
normalization only when source bytes remain untouched, visible text remains
exact, and the normalization receipt records the removed-attribute count and
new working hash.

For Stage 1, use `design` for a candidate PPT Master must redesign, `content` for locked meaning that requires user approval, and `environment` for unavailable runtimes or permissions. Stage 2 retains `source-svg`, `user-decision`, and `environment` because it reports technical failures against confirmed inputs.

For Stage 1 content-frame fit, use `design` when the approved copy is sufficient
and PPT Master can repair typography, container geometry, or composition. Use
`content` only when the approved argument is materially incomplete and must be
reopened; never let visual production pad copy.

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
candidate repair by itself. A revision identical to its bound
base must likewise proceed to the equal-scale Base/Rn comparison and explicit user
confirmation, with the identity recorded as an advisory.

Keep A/B distinction and difference evidence advisory for `Standard` pages; it never blocks PPT Master production, comparison, or selection. A `Simplified` page must still pass the same A acceptance, browser visibility, explicit confirmation, canonical, export, and PPTX gates; skip only B and comparison-specific evidence.

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
  violation set. Do not reopen the user decision after that proven technical
  repair.
- If every SVG-gate error says a validator/import is unavailable, classify the block as `environment`, not `source-svg`.
