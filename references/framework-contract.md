# Presentation framework memory contract

## 1. Boundary and creation gate

Create `framework.md` only after explicit approval of the complete Storyline. It owns durable project meaning, project-specific hard rules, the requested project authoring mode, Storyline intent and adjacency, each effective page authoring mode, page state, effective cross-page decisions, and unresolved items.

It must not contain generic workflow policy, exact approved slide copy/data, Visual Directions, standard artifact paths, receipts, review transcripts, rejected alternatives, or cached controller outputs. Those belong respectively to the Skill/controller, `content.md`, working evidence, or temporary conversation/intake notes.

Before approval, use optional `working/intake-summary.md`. After approval, merge only effective durable information into `framework.md`; do not retain a second memory authority.

## 2. Required structure

```markdown
# Presentation Framework

## Current position

- Framework version: 2.7
- Workflow version: 4.1
- Storyline version: 1.0
- Output filename: <user-requested or deterministic plain filename ending in .pptx>

## Project context

- Deliverable name: <name>
- Audience: <primary audience>
- Deliverable type: <Proposal | Sharing deck | Training | Interpretation | Other: specific form>
- Requested authoring mode: <Simplified | Standard>
- Audience outcome: <what the audience should understand, believe, decide, or do>
- Core need: <need>
- Storyline thesis: <thesis or organizing idea>
- Scope boundaries: <boundaries or None>
- Protected content: <scope or None>

## Design hard rules

- Canvas: ppt169, SVG 1280 × 720; exported at approximately 33.867 cm × 19.05 cm.
- Project-specific rules: <only project/client-specific visual, brand, content, or asset constraints; or None>

## Confirmed Storyline

### S01｜<current title or purpose>

- Chapter: <chapter>
- Page type: <type>
- Narrative role: <why this page exists>
- Content scope: <compact scope, not final copy>
- Next connection: <connection or None>
- Authoring mode: <Simplified | Standard | Not applicable>
- Status: <allowed state>
- Confirmed decisions: <only durable decisions not already evident in content.md; or None>
- Open items: <unresolved items or None>
- Confirmed version: <A | B | Rn | Pending | Not applicable>
```

Use one sequential Slide ID system only; do not add Page Keys. Initialize `Requested authoring mode` and every effective page `Authoring mode` under [authoring-modes.md](authoring-modes.md). After content approval, the controller synchronizes the Storyline heading to the exact approved audience-facing title. Do not duplicate approved copy in `Content scope` or `Confirmed decisions`.

Every new Storyline starts with exactly one `Cover` at S01. At six or more
substantive pages, include one `Agenda` at S02 and at least one `Section
divider`. Cover, Agenda, and Section divider pages must use `Simplified`;
content pages use the project selection. Agenda binds the dedicated Agenda
template base.

Keep Design hard rules to exactly the two fields above and keep Project-specific rules within 1,200 characters. Put generic EY rules nowhere in this file. Project context fields are compact framing, not an intake transcript or source register. Set `Deliverable type` to the user-confirmed primary type; for a proposal, retain its Formal RFP response, Client-development proposal, or Hybrid subtype inside `Core need`, `Scope boundaries`, or `Confirmed decisions` only when it materially governs the work.

Legacy schemas are accepted only by controller `migrate`; normal commands reject them.

`Output filename` is one plain `.pptx` filename, never a path. Preserve an explicit user filename; otherwise derive it once from the deliverable name. If it changes later, use controller `set-output-filename`; do not hand-edit workflow memory. Stage 2 ownership and output requirements are controller policy, not project memory. Stage 2 receives a controller-generated export manifest containing staged SVG paths, hashes, and the required output path.

For `Protected placeholder`, set Page type and Status to `Protected placeholder`, set Authoring mode and Confirmed version to `Not applicable`, and put the exact approved insertion instruction in Content scope. It must begin with `[占位：` and explicitly state that AI must not generate, rewrite, or supplement the protected page. The controller copies `protected_input/<Slide ID>.svg` unchanged when supplied; otherwise it materializes only this deterministic placeholder into `svg_output/`. It records source/canonical identity after the minimum file-boundary check; typography-scale compliance and compatibility belong to the bundled Stage 2 final gate.

## 3. Durable states

Use only:

1. `Not started`
2. `Content reviewing`
3. `Content locked`
4. `Awaiting SVG decision`
5. `SVG confirmed`
6. `Protected placeholder`

The controller derives the workflow stage, Stage 1 subflow, active page, next action, artifact readiness, and paths. Stage 1 always selects the first non-terminal Slide ID and completes that page before moving forward. Do not store derived state. `Reopened` is an event, not a state. Content-scope reopening returns to `Content reviewing`; design-scope reopening retains approved content and returns to `Content locked`.

`Open items` must be `None` before content can lock. Keep `Narrative role`, `Next connection`, `Confirmed decisions`, and `Open items` within 500 characters; keep `Content scope` within 700 characters. Store a substantive `Next connection` only for a content page followed immediately by another content page; name the specific claim, evidence, question, conclusion, or implication that creates the transition. Use `None` for structural or protected pages, the last page, and any page followed by a Cover, Agenda, Section divider or chapter page, Ending or closing page, or Protected placeholder. Do not store the inverse relation. Replace superseded decisions instead of appending history.

## 4. Targeted loading

For content review, controller `next` emits Project context, project-specific hard rules, the active Storyline entry, and compact adjacent context. Before Stage 1 it materializes one hash-bound packet containing the approved `content.md` section, visible-copy contract, page mode, adjacent-page context, project constraints, and bound template. Embedded PPT Master owns all design reasoning, SVG construction, and visual QA inside that packet boundary. `next --format json` returns the packet, requested artifact, preview, manifest, and receipt paths and hashes needed to recover after context compaction.

Do not load the complete Storyline during ordinary page work.

## 5. Structural changes and migration

For insertion, deletion, reorder, migration, and their recovery rules, read [presentation-workflow.md](presentation-workflow.md). Keep this file as the schema authority only.
