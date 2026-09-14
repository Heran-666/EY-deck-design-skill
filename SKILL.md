---
name: ey-deck-design
description: >
  Create approved EY Storylines and page specifications, generate and confirm
  substantive-page SVGs through the bundled PPT Master, and export the ordered
  deck as editable DrawingML PPTX. Use only when the user explicitly invokes
  $ey-deck-design.
---

# EY Deck Design

EY owns workflow and approvals. Bundled `ppt-master/` owns page design and
native conversion; call it only through EY adapters, never as a second
user-visible skill.

## Authority

| Owner | Authority |
|---|---|
| User | Approve Storyline/content; review, refine, and confirm SVGs |
| EY controller | Order, state, paths, hashes, requests, receipts, publication, recovery |
| `framework.md` | Project context, confirmed Storyline, coarse page state |
| `content.md` | Approved page outline, logic, facts, data, emphasis intent, sources |
| Bundled PPT Master | Page wording, strategy, design, SVG review/repair, DrawingML conversion, postflight |

Candidates stay in `svg_working/<Slide ID>/`. Only `confirm-svg` may publish to
`svg_output/<Slide ID>.svg`. Keep candidate history and PPT Master internals out
of `framework.md`.

## Load by action

- Intake: [references/deliverable-types.md](references/deliverable-types.md)
- Storyline/content: [references/storyline-and-content.md](references/storyline-and-content.md) and the confirmed type policy
- Framework creation/repair: [references/framework-contract.md](references/framework-contract.md)
- First content write or schema failure: [references/output-contract.md](references/output-contract.md)
- External facts: [references/research-and-sources.md](references/research-and-sources.md)
- SVG work: [references/svg-candidate-workflow.md](references/svg-candidate-workflow.md)
- PPTX work: [references/pptx-export-workflow.md](references/pptx-export-workflow.md)
- Initialization/recovery: [references/presentation-workflow.md](references/presentation-workflow.md)
- Review language, difference review, or delegated approvals: [references/review-policy.md](references/review-policy.md)

## Storyline and framework

Default to complete Chinese Storyline and content reviews in chat; keep the
deck's requested output language. Apply explicit review preferences through
`references/review-policy.md` and preserve the source fidelity defined in
`references/storyline-and-content.md`.

Classify the deliverable and complete Storyline before creating `framework.md`.
Obtain Storyline approval unless the user explicitly waives that gate; record
the actual waiver as defined in `references/framework-contract.md`.
Confirm the type separately only when it is ambiguous; otherwise include it in
the Storyline approval. Follow the router and selected type policy.
Unless the user requests custom design, keep Cover, Agenda, Section divider,
and Ending in their ordered positions with `Deferred template` status and no
authored copy. Always place exactly one Ending last and preserve it unchanged.
At export, the deferred Cover fills its template label, title, and subtitle
from the approved framework; it never enters an SVG candidate cycle.

Create framework 3.2 / workflow 8.1 with the approved deck-level Reading mode,
each page's Page rhythm, and one plain `.pptx` output filename, then
run:

```bash
python3 <skill-root>/scripts/workflow_controller.py bootstrap --project-dir <absolute-project-directory>
```

## Controller discipline

On entry, recovery, or uncertain state, run `next --format json` once. For normal
progression, execute the returned current action, paths, and commands for the
first non-terminal Slide ID. For an explicit review-policy change or feedback
on a confirmed page, use its documented controller command, then resume `next`.
Never hand-edit state, infer approval, promote content, or publish SVGs outside
controller commands. Run `upgrade-workflow` only when
migration of a supported readable earlier workflow is needed.

## Content gate

Do not create `content.md` sections for `Deferred template` pages. At
`AUTHOR_PAGE_CONTENT`, replace `working/provisional-content.md` with exactly the
active page. Include the build-profile header only for the first approved page;
later pages reuse the canonical header. Include build-only Page logic, preferred
wording, complete facts and data, emphasis intent, and sources; exclude visual
or layout direction. Structural pages omit Page logic. Run `present-review`
and faithfully display its marked review under the effective review policy.
Default to the complete Chinese translation, including Page logic, without
summaries or file-link substitutions. Keep provisional and canonical content
in the requested deck language. Follow `decision_policy.mode`: for `manual`, wait
for explicit semantic approval; for `delegated`, review within the recorded
authorization and run `approve-content` without another approval wait.

Never invent client or EY facts, sources, credentials, cases, people, capacity,
fees, schedules, tools, approvals, or achieved learning or business outcomes.

## SVG gate

At `PREPARE_SVG_CANDIDATES`, reuse the session's valid bundled Python path or
load workspace dependencies if needed, set `EY_DECK_SVG_PYTHON`, and run the
emitted command. `Deferred template` pages never enter this gate. Each
substantive page—and each editable structural page explicitly activated with
`reopen-content`—receives exactly one initial SVG, A. Generate no alternative
before review.

For each `RUN_EMBEDDED_PPT_MASTER_SVG` request:

Read the request and hash-bound `authoring_context`, then execute the bound
`service_contract` once, including its request validation and final `record`.
Preserve approved meaning and `page_logic`; write only `artifact_path`.

Before source review and `record`, resolve material references under the service
contract: icons become inline geometry and pictures become embedded data. A
candidate must not depend on external material files at review or export.

Present the emitted SVG at review scale. Follow `decision_policy.mode`: wait for
confirmation when `manual`; when `delegated`, review and confirm within the
recorded scope without another user wait. Publish only that exact version.
For feedback, bind the exact request to the displayed SVG, create one immutable
`R<n>`, and present only that revision. Use `request-svg-revision` for expression
changes within approved meaning, including feedback on the current confirmed
SVG; preserve history and canonical content. Reopen content for changed meaning,
facts, data, sources, or Page logic.

## PPTX export

At `EXPORT_EDITABLE_PPTX`, reuse the session's valid bundled Python path or load
workspace dependencies if needed. Set `EY_DECK_PPTX_PYTHON` and run the emitted
command. The adapter freezes a stale
or missing roster before export and retains it for retries. Follow the bound
service contract for conversion and recovery. Deliver only after
`PPTX_STAGE_COMPLETE`.
