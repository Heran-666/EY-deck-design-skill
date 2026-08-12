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

1. **Storyline to confirmed SVGs:** confirm purpose and page authoring modes, approve the Storyline and exact page content, author the mode-required SVG candidate(s) through EY's bundled page-authoring contract, and bind the user's final decision. End with one canonical SVG per page in `svg_output/`.
2. **Confirmed SVGs to editable PPTX:** immediately run EY's hash-bound deterministic confirmed-export command in the prepared external workspace.

## Ownership

| Owner | Owns |
|---|---|
| `framework.md` | compact project context, requested and effective authoring modes, approved Storyline, page state, unresolved decisions |
| `content.md` | exact approved copy, data, sources, and semantic Visual Direction |
| controller receipts | reusable hash-bound page preflight, transitions, rendered-preview evidence, user decisions, terminal results, and hashes |
| EY Page SVG Authoring | SVG concept, composition, construction, fit, and normal SVG checks |
| EY bundled export runtime | technical normalization, compatibility, native PPTX generation, checking, and delivery |

Keep A/B/Rn candidates as applicable and all UI previews in `svg_working/`; keep exactly one canonical SVG per page in `svg_output/`. The controller owns file boundaries and evidence. The bundled Stage 2 runtime owns isolated technical normalization, compatibility, conversion, and final PPTX QA. Do not activate or read the global `$ppt-master` skill for this workflow.

## Load only what the action needs

- New intake: read [references/deliverable-types.md](references/deliverable-types.md) and [references/authoring-modes.md](references/authoring-modes.md).
- Storyline or content reasoning: read [references/storyline-and-content.md](references/storyline-and-content.md); for a confirmed Proposal also read [references/client-and-rfp-contexts.md](references/client-and-rfp-contexts.md).
- Create, migrate, or reindex `framework.md`: read [references/framework-contract.md](references/framework-contract.md).
- First provisional content write or schema failure: read [references/output-contract.md](references/output-contract.md).
- External facts or citations: read [references/research-and-sources.md](references/research-and-sources.md).
- First SVG page: read [references/design-system.md](references/design-system.md) and [references/page-svg-authoring.md](references/page-svg-authoring.md), then follow only the controller packet path/hash and requested version data.
- Initialization, migration, reopen, reindex, or recovery: read [references/presentation-workflow.md](references/presentation-workflow.md).
- Any `BLOCKED` result or quality-gate interpretation: read [references/quality-gates.md](references/quality-gates.md) before choosing a repair scope.

## Execute

Classify the supplied background as `Proposal`, `Sharing deck`, `Training`, `Interpretation`, or `Other: <specific form>`. State the basis briefly and obtain confirmation unless the user waives this gate. Then, before drafting the Storyline, ask the user to choose `Simplified` or `Standard` authoring under [references/authoring-modes.md](references/authoring-modes.md).

After type and authoring-mode confirmation, show the complete page sequence with each effective page `Authoring mode` and obtain explicit Storyline approval. Create framework 2.6 / workflow 3.8 `framework.md` with the user-requested or deterministic `.pptx` filename. Initialize every page mode from the requested project mode and exact Page type. Call `load_workspace_dependencies` once in the parent context, then run controller `bootstrap --bundled-python <absolute bundled Python> --bundle-version <bundle version>`. If Chromium is sandbox-blocked, rerun that canonical command with browser-launch permission.

On entry, re-entry, post-compaction, or uncertain state, run controller `next --format json` once. This command is read-only. Follow `action`, `command_when`, and the condition-matching command data. Run emitted `prepare-authoring` or `prepare-export` commands before their corresponding bounded action; each successful mutating command prints `NEXT_DIRECTIVE_JSON`, so do not immediately run `next` again. After context compaction, reload this skill, run a fresh `next --format json`, and never replay the last mutating command.

For content review, replace all of `working/provisional-content.md` with exactly the active sections listed in the controller's `provisional_content.expected_pages`; never append to the prior page's draft. Then run the printed `present-review` command, fix any reported schema errors, and rerun it. Explicit approval promotes those unchanged sections into `content.md`, records their hashes, clears handled open items, locks the pages, and removes the handled provisional file.

For every locked page, run the emitted `prepare-authoring` command, then author only the controller-requested version under [references/page-svg-authoring.md](references/page-svg-authoring.md). A `Simplified` page generates A only, shows one preview, and requires explicit confirmation or a targeted revision. A `Standard` page generates A and B from the same packet, shows them together at equal scale, and requires explicit A/B selection or a targeted revision. Use only the packet path/hash, requested artifact/version, visible-copy contract hash, and base/change note when applicable. Record the bounded action's one `COMPLETE` or `BLOCKED` JSON object with the controller. Inspect every required candidate before user display and use the emitted `repair_before_user_display` command for an agent-detected defect. Apply the detailed mode rules in [references/authoring-modes.md](references/authoring-modes.md). On `COMPLETE`, `page-author-result` records reusable hash-bound static/copy/typography PASS evidence; later presentation, revision, decision, and canonical-integrity gates reuse it only while all bound hashes remain unchanged. Chromium still performs its independent rendered-visible-copy gate. After every targeted revision in either mode, run `present-revision` and show the request-bound Base and Rn together at equal scale. After the explicit user decision, use `after_keep_base` to retain that displayed Base, `after_confirmation` to confirm that displayed Rn, or `for_targeted_changes` to revise from Rn; never select a version outside the displayed pair.

Never invent client, audience, source, EY, credential, case, people, capacity, fee, schedule, tool, approval, learning outcome, or business-outcome facts. Never silently rewrite locked content, sources, protected material, or a confirmed Visual Direction.

## Final handoff

When all pages are terminal, the controller prints `STAGE_1_COMPLETE`. Run the emitted `prepare-export` command; its next directive contains the runner command, hash-bound manifest, and required output path. Continue directly without a new approval or filename gate.

Run the printed `runner_command` exactly once. It is bound to EY's bundled export runtime, manifest hash, staged SVG hashes, required output path, bundled Python, and terminal validator. Do not activate `$ppt-master`, start a normal-path subtask, rediscover dependencies, inspect unrelated project data, install anything, or edit upstream SVGs.

Treat valid paints and typography already verified against `design-system.md` as inherited Stage 2 input. The isolated export lock describes those pages; it does not reopen semantic design governance. Block any visible text outside the fixed typography scale as `source-svg`. Never block confirmed export solely because a valid contextual color is absent from the synthesized stable-role palette. Unsupported paint syntax, broken references, stale hashes, or an explicit pre-lock brand violation remain blocking.

Treat `warning`, `advisory`, and `inherited` findings as non-blocking. Do not reopen content or design for them. A `BLOCKED` result must identify an integrity, exact-copy, user-evidence, export-compatibility, package-validity, or environment failure and must use the matching repair scope.

Do not rerun a passed page-level static gate solely because a later controller action reads the same unchanged SVG. Validate its receipt schema, artifact hash, packet hash, and copy-contract hash instead. Never reuse Stage 1 evidence as a substitute for Stage 2 validation: the confirmed-export boundary always rechecks the staged bytes, runtime, native compatibility, and PPTX package.

Treat text-frame topology solely as Stage 2 export compatibility, not as a Stage 1 user-review dimension. After binding and copying each confirmed SVG into the isolated export workspace, run the topology detector, deterministically normalize only the isolated copy, prove exact text identity against the untouched confirmed source, and rerun the topology detector before PPTX generation. Continue without another image display or user decision when both rechecks pass. If an authored SVG `<text>` still predicts multiple native PowerPoint text boxes, leave that unresolved block unsplit, report its `data-copy-id` in the topology receipt, and block before publishing the PPTX.

Record the runner's exact validated JSON object with `handoff-result`. A `COMPLETE` result delivers the final PPTX. A `BLOCKED` result follows controller recovery. Start a zero-history technical-repair subtask only if a future runner contract explicitly returns a non-terminal escalation directive; the current normal path never requires one.
