# Presentation framework memory contract

## Boundary

Create `framework.md` after the complete Storyline is explicitly approved or the
user explicitly waives Storyline approval.
It stores compact project context, page order, narrative intent, the approved
reading-mode and page-rhythm execution anchors, durable page state, decisions,
and unresolved items. Exclude approved copy or data, detailed design and layout
choices, visual style, SVG/PPTX details, receipts, and PPT Master internal state.

Before approval or waiver, use optional `working/intake-summary.md`. Afterwards,
move only durable information into `framework.md`. For a waiver, record its
scope and the actual user instruction in S01's `Confirmed decisions`. If the
instruction exceeds that field's limit, keep a concise scope and reference there
and preserve the exact instruction in `working/intake-summary.md`. Never record
a waiver that the user did not give. Later review preferences and delegated
decisions use the controller-owned [review policy](review-policy.md).

## Required structure

```markdown
# Presentation Framework

## Current position

- Framework version: 3.2
- Workflow version: 8.1
- Storyline version: 1.0
- Output filename: <plain filename ending in .pptx>

## Project context

- Deliverable name: <name>
- Audience: <primary audience>
- Deliverable type: <Proposal | Sharing deck | Training | Interpretation | Other: specific form>
- Audience outcome: <what the audience should understand, believe, decide, or do>
- Core need: <need>
- Storyline thesis: <thesis or organizing idea>
- Reading mode: <text | balanced | presentation>
- Scope boundaries: <boundaries or None>
- Protected content: <scope or None>

## Confirmed Storyline

### S01｜<current title or purpose>

- Chapter: <chapter>
- Page type: <type>
- Narrative role: <why this page exists>
- Page rhythm: <anchor | dense | breathing>
- Content scope: <compact semicolon-separated summary of the approved planned content units, not final copy>
- Next connection: <connection or None>
- Status: <allowed state>
- Confirmed decisions: <durable decisions not already evident in content.md; or None>
- Open items: <unresolved items or None>
```

Use one sequential Slide ID system. After content approval, the controller
synchronizes the Storyline heading to the approved audience-facing title. Do
not duplicate approved copy in `Content scope` or `Confirmed decisions`.

For each substantive page, preserve every approved `Content Summary` unit in
`Content scope`.
Compress them with semicolons, but retain the main claim and its approved
explanation, evidence, example, boundary, implication, or action. Do not reduce
the scope to a topic label or write final on-slide copy. Keep structural pages role-appropriate and concise.

Persist the Storyline-approved `Reading mode` and each page's `Page rhythm`.
Use `anchor` only for structural pages; use `dense` or `breathing` for
substantive pages. The visual design direction shown during Storyline review is
derived from this pair and is not stored as a second prose decision. During an
explicit legacy upgrade, use `balanced`; use `anchor` for structural pages and
`dense` for substantive pages.

Apply the structural shell from `deliverable-types.md`. Give Cover, Agenda,
Section divider, and Ending their normal Page type and `Deferred template`
status by default. Place exactly one Ending last and keep it unchanged. A
deferred Cover uses the project `Deliverable type` as its template label, its
Storyline heading as title, and `Content scope` as subtitle. The controller
fills those fields during export without creating an SVG candidate cycle.
Use `reopen-content` only when the user requests custom design for an editable
structural page.

`Output filename` must be one plain `.pptx` filename, never a path. Preserve a
user-specified name; otherwise derive it once from the deliverable name. The
export writes it to the project root. Store postflight, conversion trace, and
text-frame audit outside `framework.md`.

For a protected page, set both Page type and Status to `Protected placeholder`.
In `Content scope`, preserve the exact approved instruction beginning with
`[占位：`; it must forbid AI generation, rewriting, and supplementation. An
optional literal SVG may live at `protected_input/<Slide ID>.svg`, but workflow
8.0 does not validate, confirm, or export protected placeholders. Export only
confirmed authored SVGs and hash-bound `Deferred template` snapshots.

## Durable states

Use only:

1. `Not started`
2. `Content locked`
3. `SVG confirmed`
4. `Deferred template`
5. `Protected placeholder`

The controller selects the first page not in `SVG confirmed`, `Deferred
template`, or `Protected placeholder`. Content approval sets `Content locked`;
candidate preparation does not change it; publication sets `SVG confirmed`.
A feedback revision of the current confirmed SVG returns it to `Content locked`
until reconfirmed, retaining the prior candidate and decision history.
Only Cover, Agenda, Section divider, and Ending may use `Deferred template`.
`Open items` must be `None` before content lock or template deferral.

Derive transient progress from evidence under `working/`: a current review
receipt means content review; a hash-bound page context plus complete initial
requests means SVG review. Never write `Content reviewing` or `Awaiting SVG
decision` into new or updated frameworks. Accept legacy values only long enough
to finish or reopen a pre-8.0 cycle.

Keep candidate versions and revision history under `working/`, with their
immutable request, artifact, and decision receipts. Reopening
content returns the page to `Not started`; an explicit full SVG restart returns
it to `Content locked` and removes transient SVG evidence. Ordinary cosmetic or
expression feedback uses `request-svg-revision`, not a full restart.

Limit `Narrative role`, `Next connection`, `Confirmed decisions`, and `Open
items` to 500 characters each; limit `Content scope` to 700. Use a substantive
`Next connection` only between adjacent content pages; otherwise use `None`.

## Targeted loading

For content review, controller `next` emits project context, the active
Storyline entry, and compact adjacent context. For SVG generation, it writes
one hash-bound authoring context containing the execution anchors, complete
approved content, substantive-page logic, project/page context, at most two
consistency references, and one self-contained prototype. It binds A and later
feedback-driven Rn requests to that context. After re-entry or compaction, PPT
Master rereads it and applies its content-expression rules. References guide
consistency but never become state authority.
