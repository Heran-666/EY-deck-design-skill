# Presentation framework memory contract

## Boundary

Create `framework.md` only after explicit approval of the complete Storyline.
It owns compact project context, page order, narrative intent, content state,
durable decisions, and unresolved items. It must not contain exact approved
copy/data, design directions, layout choices, visual style, SVG/PPTX details,
receipts, or bundled PPT Master internal state.

Before approval, use optional `working/intake-summary.md`. After approval, merge
only effective durable information into `framework.md`.

## Required structure

```markdown
# Presentation Framework

## Current position

- Framework version: 3.1
- Workflow version: 8.0
- Storyline version: 1.0
- Output filename: <plain filename ending in .pptx>

## Project context

- Deliverable name: <name>
- Audience: <primary audience>
- Deliverable type: <Proposal | Sharing deck | Training | Interpretation | Other: specific form>
- Audience outcome: <what the audience should understand, believe, decide, or do>
- Core need: <need>
- Storyline thesis: <thesis or organizing idea>
- Scope boundaries: <boundaries or None>
- Protected content: <scope or None>

## Confirmed Storyline

### S01｜<current title or purpose>

- Chapter: <chapter>
- Page type: <type>
- Narrative role: <why this page exists>
- Content scope: <compact semicolon-separated summary of the approved planned content units, not final copy>
- Next connection: <connection or None>
- Status: <allowed state>
- Confirmed decisions: <durable decisions not already evident in content.md; or None>
- Open items: <unresolved items or None>
```

Use one sequential Slide ID system only. After content approval, the controller
synchronizes the Storyline heading to the exact approved audience-facing title.
Do not duplicate approved copy in `Content scope` or `Confirmed decisions`.

When materializing an approved substantive page, preserve the three to five
distinct planned units from its Storyline `Content Summary` in `Content scope`;
compress wording and separate units with semicolons, but do not collapse the
scope to a vague topic label. Preserve the main claim plus the relevant
explanation, evidence, example, boundary, implication, or action that the user
approved. Keep structural pages role-appropriate and concise. This is planning
scope for later content authoring, not exact on-slide copy.

Every new Storyline starts with exactly one Cover at S01. At six or more
substantive pages, include one Agenda at S02 and at least one Section divider.
Give Cover, Agenda, Section divider, and Ending pages their normal Page type and
`Deferred template` Status by default. Preserve their Slide IDs and positions,
but do not draft exact on-slide copy. The user fills the editable Cover, Agenda,
and Section divider template fields after PPTX export. Ending is the approved
fixed closing page: preserve it literally and never add or modify content. Use
`reopen-content` only when the user explicitly requests custom design for an
editable structural page.

`Output filename` is one plain `.pptx` filename, never a path. Preserve an
explicit user filename; otherwise derive it once from the deliverable name. It
becomes the project-root output of the ordered-roster-to-PPTX stage. Workflow
8.0 records the output, postflight, conversion trace, and text-frame audit
outside `framework.md`.

For `Protected placeholder`, set both Page type and Status to
`Protected placeholder`. Put the exact approved instruction in `Content scope`;
it must begin with `[占位：` and state that AI must not generate, rewrite, or
supplement the page. An optional supplied literal SVG may live at
`protected_input/<Slide ID>.svg`, but workflow 8.0 does not validate, confirm,
or include protected placeholders in the PPTX roster. Export only explicitly
confirmed authored SVGs plus hash-bound `Deferred template` snapshots.

## Durable states

Use only:

1. `Not started`
2. `Content locked`
3. `SVG confirmed`
4. `Deferred template`
5. `Protected placeholder`

The controller always selects the first page that is neither `SVG confirmed`
nor `Deferred template` nor `Protected placeholder`. Content approval sets
`Content locked`; candidate preparation leaves that durable state unchanged;
explicit publication sets `SVG confirmed`. `Deferred template` is valid only
for Cover, Agenda, Section divider, and Ending page types. `Open items` must be
`None` before content locks or template deferral.

Derive transient progress from evidence under `working/`: a current content
review receipt means content is being reviewed, and a hash-bound page context
plus the complete initial request set means SVG decisions are in progress. Do
not write `Content reviewing` or `Awaiting SVG decision` into new or updated
frameworks. Accept those legacy values only long enough to finish or reopen an
existing pre-8.0 cycle.

Keep candidate versions and revision history out of this file. Their immutable
request, artifact, presentation, and decision receipts live under `working/`.
A content reopen returns to `Not started`; an SVG-only reopen returns to
`Content locked` and deletes the evidence from which transient SVG progress is
derived.

Keep `Narrative role`, `Next connection`, `Confirmed decisions`, and `Open
items` within 500 characters and `Content scope` within 700. Store a substantive
`Next connection` only between adjacent content pages; otherwise use `None`.

## Targeted loading

For content review, controller `next` emits Project context, the active
Storyline entry, and compact adjacent context. For SVG generation, it writes
one hash-bound page authoring context containing the single-SVG review plan,
complete approved content, structured page logic for substantive pages,
project/page context, and one self-contained prototype. It then binds the A
request or a later feedback-driven Rn request to that context. PPT Master
rereads the immutable context after re-entry or compaction and applies its
native content-expression rules. Previously confirmed pages and adjacent
Storyline context may inform consistency without becoming a second state
authority.
