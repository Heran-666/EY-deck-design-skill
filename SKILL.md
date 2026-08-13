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

1. **Storyline to confirmed SVGs:** confirm purpose and page authoring modes, approve the Storyline and exact page content, then author and confirm every page strictly in Slide ID order through EY's bundled page-authoring contract. End with one canonical SVG per page in `svg_output/`.
2. **Confirmed SVGs to editable PPTX:** immediately run EY's hash-bound deterministic confirmed-export command in the prepared external workspace.

## Ownership

| Owner | Owns |
|---|---|
| `framework.md` | compact project context, requested and effective authoring modes, approved Storyline, page state, unresolved decisions |
| `content.md` | exact approved copy, data, sources, and semantic Visual Direction |
| controller receipts | reusable hash-bound page preflight, transitions, rendered-preview evidence, user decisions, terminal results, and hashes |
| EY Page SVG Authoring | placeholder content, SVG concept within the bound Layout, composition, fit, and normal SVG checks |
| bundled structured template profile | fixed Master/Layout atoms, placeholder positions, template assets, and Page type mapping |
| EY bundled export runtime | technical normalization, structured Master/Layout generation, compatibility, native PPTX checking, and delivery |

Keep A/B/Rn candidates as applicable and all UI previews in `svg_working/`; keep exactly one canonical SVG per page in `svg_output/`. The controller owns file boundaries and evidence. The bundled Stage 2 runtime owns isolated technical normalization, compatibility, conversion, and final PPTX QA. PPT Master's current structured-template runtime is already bundled here; normal execution does not need to activate or read a separate global `$ppt-master` skill.

Treat visible copy marked `data-copy-scope="template-fixed"` as inherited Master/Layout content. Preserve it exactly, do not bind it to page `data-copy-id` values, and let the structured-template hash contract reject any change or deletion.

## Load only what the action needs

- New intake: read [references/deliverable-types.md](references/deliverable-types.md) and [references/authoring-modes.md](references/authoring-modes.md).
- Storyline or content reasoning: read [references/storyline-and-content.md](references/storyline-and-content.md) plus exactly the confirmed primary type policy: [Proposal](references/storyline-type-proposal.md), [Sharing deck](references/storyline-type-sharing-deck.md), [Training](references/storyline-type-training.md), [Interpretation](references/storyline-type-interpretation.md), or [Other](references/storyline-type-other.md). Read one additional type policy only when a confirmed secondary behavior materially changes the Storyline.
- Create, migrate, or reindex `framework.md`: read [references/framework-contract.md](references/framework-contract.md).
- First provisional content write or schema failure: read [references/output-contract.md](references/output-contract.md).
- External facts or citations: read [references/research-and-sources.md](references/research-and-sources.md).
- First SVG page: read [references/design-system.md](references/design-system.md), [references/structured-template-profile.md](references/structured-template-profile.md), and [references/page-svg-authoring.md](references/page-svg-authoring.md), then follow only the controller packet path/hash and requested version data.
- Initialization, migration, reopen, reindex, or recovery: read [references/presentation-workflow.md](references/presentation-workflow.md).
- Any `BLOCKED` result or quality-gate interpretation: read [references/quality-gates.md](references/quality-gates.md) before choosing a repair scope.

## Execute

Classify the supplied background as `Proposal`, `Sharing deck`, `Training`, `Interpretation`, or `Other: <specific form>`. State the basis briefly and obtain confirmation unless the user waives this gate. Then, before drafting the Storyline, ask the user to choose `Simplified` or `Standard` authoring under [references/authoring-modes.md](references/authoring-modes.md). Every deliverable type requires one opening Cover at S01. When the planned deck has at least six substantive pages, add an Agenda at S02 and at least one Section divider; shorter decks may use them when the narrative benefits. Agenda content uses only `Title` plus sequential top-level label blocks (`S02-B1`, `S02-B2`, ...); do not write a Subtitle, Core insight, Detail, description, table/chart payload, or supporting-detail line. The controller derives editable `01`, `02`, ... number bindings from that approved order, so never type numbers into an agenda-item label.

After type and authoring-mode confirmation, show the complete page sequence under the fixed display contract in [references/deliverable-types.md](references/deliverable-types.md): `Slide ID`, `Page title / purpose`, `Page type`, `Narrative role`, a bullet-point `Content Summary`, the conditionally applicable `Next connection`, and effective `Authoring mode`. Do not show `Review mode` or a separate `Protected status`; `Page type: Protected placeholder` already identifies protected pages. Obtain explicit Storyline approval. Always mark Cover, Agenda, and Section divider pages `Simplified`; initialize only content pages from the requested project mode. Create framework 2.6 / workflow 3.9 `framework.md` with the user-requested or deterministic `.pptx` filename. Call `load_workspace_dependencies` once in the parent context, then run controller `bootstrap --bundled-python <absolute bundled Python> --bundle-version <bundle version>`. If Chromium is sandbox-blocked, rerun that canonical command with browser-launch permission.

On entry, re-entry, post-compaction, or uncertain state, run controller `next --format json` once. This command is read-only. Follow `action`, `command_when`, and the condition-matching command data. Run emitted `prepare-authoring` or `prepare-export` commands before their corresponding bounded action; each successful mutating command prints `NEXT_DIRECTIVE_JSON`, so do not immediately run `next` again. After context compaction, reload this skill, run a fresh `next --format json`, and never replay the last mutating command.

For content review, replace all of `working/provisional-content.md` with exactly the active sections listed in the controller's `provisional_content.expected_pages`; never append to the prior page's draft. Then run the printed `present-review` command, fix any reported schema errors, and rerun it. Explicit approval promotes those unchanged sections into `content.md`, records their hashes, clears handled open items, locks the pages, and removes the handled provisional file.

Process only the first non-terminal slide in Storyline order. Complete its content review, SVG generation, display, and explicit confirmation before the controller advances to the next Slide ID; never prioritize body pages over Cover, Agenda, or Section divider pages, and never batch later pages past the first unfinished page. For every locked page, run the emitted `prepare-authoring` command, then author only the controller-requested version under [references/page-svg-authoring.md](references/page-svg-authoring.md). A `Simplified` page generates A only, shows one preview, and requires explicit confirmation or a targeted revision. A `Standard` page generates A and B from the same packet, shows them together at equal scale, and requires explicit A/B selection or a targeted revision. Use only the packet path/hash, requested artifact/version, visible-copy contract hash, bound template prototype/hash/contract, and base/change note when applicable. Start from that exact prototype and change only permitted page content. Record the bounded action's one `COMPLETE` or `BLOCKED` JSON object with the controller. Inspect every required candidate before user display and use the emitted `repair_before_user_display` command for an agent-detected defect. Apply the detailed mode rules in [references/authoring-modes.md](references/authoring-modes.md). On `COMPLETE`, `page-author-result` records reusable hash-bound static/copy/typography/template PASS evidence; later presentation, revision, decision, and canonical-integrity gates reuse it only while all bound hashes remain unchanged. Chromium still performs its independent rendered-visible-copy gate. After every targeted revision in either mode, run `present-revision` and show the request-bound Base and Rn together at equal scale. After the explicit user decision, use `after_keep_base` to retain that displayed Base, `after_confirmation` to confirm that displayed Rn, or `for_targeted_changes` to revise from Rn; never select a version outside the displayed pair.

Never invent client, audience, source, EY, credential, case, people, capacity, fee, schedule, tool, approval, learning outcome, or business-outcome facts. Never silently rewrite locked content, sources, protected material, or a confirmed Visual Direction.

## Final handoff

When all pages are terminal, the controller prints `STAGE_1_COMPLETE`. Run the emitted `prepare-export` command; its next directive contains the runner command, hash-bound manifest, and required output path. Continue directly without a new approval or filename gate.

Run the printed `runner_command` exactly once. It is bound to EY's bundled export runtime, manifest hash, staged SVG hashes, structured template profile/prototype hashes when applicable, required output path, bundled Python, and terminal validator. Do not activate `$ppt-master`, start a normal-path subtask, rediscover dependencies, inspect unrelated project data, install anything, or edit upstream SVGs.

Treat valid paints and typography already verified against `design-system.md` as inherited Stage 2 input. The isolated export lock describes those pages; it does not reopen semantic design governance. Block any visible text outside the fixed typography scale as `source-svg`. Never block confirmed export solely because a valid contextual color is absent from the synthesized stable-role palette. Unsupported paint syntax, broken references, stale hashes, or an explicit pre-lock brand violation remain blocking.

Treat `warning`, `advisory`, and `inherited` findings as non-blocking. Do not reopen content or design for them. A `BLOCKED` result must identify an integrity, exact-copy, user-evidence, export-compatibility, package-validity, or environment failure and must use the matching repair scope.

Do not rerun a passed page-level static gate solely because a later controller action reads the same unchanged SVG. Validate its receipt schema, artifact hash, packet hash, and copy-contract hash instead. Never reuse Stage 1 evidence as a substitute for Stage 2 validation: the confirmed-export boundary always rechecks the staged bytes, runtime, native compatibility, and PPTX package.

For an all-authored deck, Stage 2 emits `mode: structured` and reuses the bound two-Master/five-Layout profile. A deck containing a protected placeholder emits `mode: flat` so protected source bytes are not reauthored. In both modes, append the bundled fixed Ending prototype after every confirmed Storyline page; never expose it to content review, authoring, or user revision. Treat text-frame topology solely as Stage 2 export compatibility, not as a Stage 1 user-review dimension. After binding and copying each confirmed SVG plus the fixed Ending into the isolated export workspace, run the topology detector, deterministically normalize only the isolated copy, prove exact text identity against the untouched confirmed source, and rerun topology before PPTX generation. Continue without another image display or user decision when both rechecks pass. If an authored SVG `<text>` still predicts multiple native PowerPoint text boxes, leave that unresolved block unsplit, report its `data-copy-id` in the topology receipt, and block before publishing the PPTX.

Record the runner's exact validated JSON object with `handoff-result`. A `COMPLETE` result delivers the final PPTX. A `BLOCKED` result follows controller recovery. Start a zero-history technical-repair subtask only if a future runner contract explicitly returns a non-terminal escalation directive; the current normal path never requires one.
