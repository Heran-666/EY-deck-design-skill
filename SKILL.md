---
name: ey-deck-design
description: >
  Run a controller-governed EY presentation workflow from background and
  Storyline approval through user-confirmed SVG pages, then export those pages
  through a bundled deterministic native-PPTX runtime as one editable PPTX. Use
  only when the user explicitly invokes $ey-deck-design.
---

# EY Deck Design

Use the bundled controller as the workflow authority. Execute exactly two stages with no gate between them:

1. **Storyline to confirmed SVGs:** confirm purpose and Storyline, approve exact page content, author A/B SVGs through EY's bundled page-authoring contract, and bind the user's final choice. End with one canonical SVG per page in `svg_output/`.
2. **Confirmed SVGs to editable PPTX:** immediately run EY's hash-bound deterministic confirmed-export command in the prepared external workspace.

## Ownership

| Owner | Owns |
|---|---|
| `framework.md` | compact project context, approved Storyline, page state, unresolved decisions |
| `content.md` | exact approved copy, data, sources, and semantic Visual Direction |
| controller receipts | reusable hash-bound page preflight, transitions, rendered-preview evidence, selections, terminal results, and hashes |
| EY Page SVG Authoring | SVG concept, composition, construction, fit, and normal SVG checks |
| EY bundled export runtime | technical normalization, compatibility, native PPTX generation, checking, and delivery |

Keep A/B/Rn candidates and UI previews in `svg_working/`; keep exactly one canonical SVG per page in `svg_output/`. The controller owns file boundaries and evidence. The bundled Stage 2 runtime owns isolated technical normalization, compatibility, conversion, and final PPTX QA. Do not activate or read the global `$ppt-master` skill for this workflow.

## Load only what the action needs

- New intake: read [references/deliverable-types.md](references/deliverable-types.md).
- Storyline or content reasoning: read [references/storyline-and-content.md](references/storyline-and-content.md); for a confirmed Proposal also read [references/client-and-rfp-contexts.md](references/client-and-rfp-contexts.md).
- Create, migrate, or reindex `framework.md`: read [references/framework-contract.md](references/framework-contract.md).
- First provisional content write or schema failure: read [references/output-contract.md](references/output-contract.md).
- External facts or citations: read [references/research-and-sources.md](references/research-and-sources.md).
- First SVG page: read [references/design-system.md](references/design-system.md) and [references/page-svg-authoring.md](references/page-svg-authoring.md), then follow only the controller packet path/hash and requested version data.
- Initialization, migration, reopen, reindex, or recovery: read [references/presentation-workflow.md](references/presentation-workflow.md).
- Any `BLOCKED` result or quality-gate interpretation: read [references/quality-gates.md](references/quality-gates.md) before choosing a repair scope.

## Execute

Classify the supplied background as `Proposal`, `Sharing deck`, `Training`, `Interpretation`, or `Other: <specific form>`. State the basis briefly and obtain confirmation before drafting the Storyline unless the user waives this gate.

After type confirmation, show the complete page sequence and obtain explicit Storyline approval. Create framework 2.5 / workflow 3.7 `framework.md` with the user-requested or deterministic `.pptx` filename. Call `load_workspace_dependencies` once in the parent context, then run controller `bootstrap --bundled-python <absolute bundled Python> --bundle-version <bundle version>`. If Chromium is sandbox-blocked, rerun that canonical command with browser-launch permission.

On entry, re-entry, post-compaction, or uncertain state, run controller `next --format json` once. This command is read-only. Follow `action`, `command_when`, and the condition-matching command data. Run emitted `prepare-authoring` or `prepare-export` commands before their corresponding bounded action; each successful mutating command prints `NEXT_DIRECTIVE_JSON`, so do not immediately run `next` again. After context compaction, reload this skill, run a fresh `next --format json`, and never replay the last mutating command.

For content review, replace all of `working/provisional-content.md` with exactly the active sections listed in the controller's `provisional_content.expected_pages`; never append to the prior page's draft. Then run the printed `present-review` command, fix any reported schema errors, and rerun it. Explicit approval promotes those unchanged sections into `content.md`, records their hashes, clears handled open items, locks the pages, and removes the handled provisional file.

For every locked page, run the emitted `prepare-authoring` command, then author both A and B from the same hash-bound packet under [references/page-svg-authoring.md](references/page-svg-authoring.md). Use only the packet path/hash, requested artifact/version, visible-copy contract hash, and base/change note when applicable. Record its one `COMPLETE` or `BLOCKED` JSON object with the controller. B `COMPLETE` should include concise `material_differences`; identical A/B hashes or missing/empty difference evidence are non-blocking advisories and must continue to equal-scale comparison and explicit user selection. On `COMPLETE`, `page-author-result` runs the page static/copy/typography preflight once and records reusable hash-bound PASS evidence. Later A/B, revision, selection, and canonical-integrity gates reuse that evidence only while the artifact and copy-contract hashes remain unchanged; Chromium still performs its independent rendered-visible-copy gate. The controller rejects `<style>`, class dependencies, missing/changed/unbound visible copy, off-canvas or hidden required text, and visible text outside the typography scale in `design-system.md`; it creates content-addressed equal-size previews. Inspect both candidates before showing them to the user. If either has a defect, run the emitted `repair_before_user_display` command for that same A or B slot, regenerate it, and then show A and B together; never create Rn for an agent-detected pre-display defect. Do not run candidate repair solely because A/B are identical or lack difference notes. Create Rn only after the user has seen A/B and requests targeted changes, or asks to revise an already confirmed page. After every targeted revision, run the emitted `present-revision` command and send its complete comparison to the user in one message: show the request-bound `base_version` and the new Rn side by side at equal scale, label both versions, and never show Rn alone. A Revision identical to its bound Base is a non-blocking advisory and must still be shown and explicitly confirmed. For a chained revision, use the controller-bound base (normally the immediately preceding Rn) and repeat the same paired display. Do not run `after_confirmation` until the user has seen that exact Base/Rn pair and explicitly confirms the Rn.

Never invent client, audience, source, EY, credential, case, people, capacity, fee, schedule, tool, approval, learning outcome, or business-outcome facts. Never silently rewrite locked content, sources, protected material, or a confirmed Visual Direction.

## Final handoff

When all pages are terminal, the controller prints `STAGE_1_COMPLETE`. Run the emitted `prepare-export` command; its next directive contains the runner command, hash-bound manifest, and required output path. Continue directly without a new approval or filename gate.

Run the printed `runner_command` exactly once. It is bound to EY's bundled export runtime, manifest hash, staged SVG hashes, required output path, bundled Python, and terminal validator. Do not activate `$ppt-master`, start a normal-path subtask, rediscover dependencies, inspect unrelated project data, install anything, or edit upstream SVGs.

Treat valid paints and typography already verified against `design-system.md` as inherited Stage 2 input. The isolated export lock describes those pages; it does not reopen semantic design governance. Block any visible text outside the fixed typography scale as `source-svg`. Never block confirmed export solely because a valid contextual color is absent from the synthesized stable-role palette. Unsupported paint syntax, broken references, stale hashes, or an explicit pre-lock brand violation remain blocking.

Treat `warning`, `advisory`, and `inherited` findings as non-blocking. Do not reopen content or design for them. A `BLOCKED` result must identify an integrity, exact-copy, user-evidence, export-compatibility, package-validity, or environment failure and must use the matching repair scope.

Do not rerun a passed page-level static gate solely because a later controller action reads the same unchanged SVG. Validate its receipt schema, artifact hash, packet hash, and copy-contract hash instead. Never reuse Stage 1 evidence as a substitute for Stage 2 validation: the confirmed-export boundary always rechecks the staged bytes, runtime, native compatibility, and PPTX package.

Treat text-frame topology as export compatibility, not an advisory: one authored SVG `<text>` intended as one logical text box must remain exactly one native PowerPoint text box. The runtime may normalize consistent absolute-`y` or relative-`dy` wrapped tspans on its isolated copy; if it still predicts a split, block before publishing the PPTX.

Record the runner's exact validated JSON object with `handoff-result`. A `COMPLETE` result delivers the final PPTX. A `BLOCKED` result follows controller recovery. Start a zero-history technical-repair subtask only if a future runner contract explicitly returns a non-terminal escalation directive; the current normal path never requires one.
