# Deliverable type routing

## Contents

1. Classify from the supplied background
2. Confirm the type
3. Confirm the authoring mode
4. Route to the type policy
5. Present the Storyline for approval

## 1. Classify from the supplied background

Review the user's objective, audience, source material, delivery setting, requested output, desired audience change, and constraints before asking about format. Infer the primary deliverable type:

- `Proposal`: seeks selection, approval, sponsorship, funding, or authorization for a proposed response, scope, approach, or commercial offer.
- `Sharing deck`: communicates experience, insights, progress, practices, or a point of view primarily to create understanding, alignment, or discussion.
- `Training`: builds knowledge or capability and requires explicit learning objectives, explanation, examples, practice, checks, or application support.
- `Interpretation`: explains and makes sense of supplied material, findings, policy, research, data, or an existing document, with emphasis on meaning, implications, uncertainty, and response.
- `Other: <specific form>`: names the actual form when none of the four types fits, such as decision briefing, workshop, readout, update, report-out, or keynote.

Classify by the audience outcome, not by the user's casual use of words such as “deck,” “presentation,” or “sharing.” Treat hybrids by their dominant purpose. Mention a secondary type only when it materially changes the Storyline.

Before drafting the Storyline, the minimum usable intake is the objective,
audience, desired audience change, source boundary, and any hard delivery
constraint. Ask only for missing items that would change the sequence or make a
claim unsupported; optional context may remain `None`. Also obtain any input
that the selected type policy marks as required, such as `why now` and the
intended ending for a Sharing deck.

## 2. Confirm the type

Give one concise preliminary judgment after reviewing the background:

`根据现有背景，我初步判断这是 <type>，因为 <purpose/audience basis>。请确认；如果不准确，请告诉我更希望它作为哪种形式。`

If two types remain genuinely plausible, recommend one and name only the closest alternative with the consequence for structure. Ask no more than the minimum additional question needed to distinguish them. Do not present a page sequence before confirmation unless the user explicitly asks to proceed without the gate.

Treat a direct correction as confirmation of the corrected type. Record the confirmed type in the temporary intake summary and later in `framework.md`; do not repeatedly reconfirm it unless the user's objective changes.

## 3. Confirm the authoring mode

After type confirmation and before Storyline drafting, ask the user to choose `Simplified` or `Standard` under [authoring-modes.md](authoring-modes.md). Record the choice in temporary intake context and later as project-level `Requested authoring mode`. Do not infer the choice from urgency, deck length, or deliverable type.

## 4. Route to the type policy

Apply this universal structural shell before the selected type policy:

- place exactly one `Cover` at S01 for every deliverable type;
- when there are at least six substantive pages, place one `Agenda` at S02 and
  at least one `Section divider` before the relevant major chapter;
- allow Agenda or divider pages in shorter decks when they materially improve
  navigation, but do not add them as decoration;
- mark Cover, Agenda, and Section divider pages `Simplified`; apply the user's
  requested mode only to substantive content pages.

Agenda uses its dedicated two-column numbered-card Layout while owning its directory
composition as editable page content.

After confirmation, read [storyline-and-content.md](storyline-and-content.md) and exactly one primary type policy:

| Confirmed primary type | Type policy |
|---|---|
| `Proposal` | [storyline-type-proposal.md](storyline-type-proposal.md) |
| `Sharing deck` | [storyline-type-sharing-deck.md](storyline-type-sharing-deck.md) |
| `Training` | [storyline-type-training.md](storyline-type-training.md) |
| `Interpretation` | [storyline-type-interpretation.md](storyline-type-interpretation.md) |
| `Other: <specific form>` | [storyline-type-other.md](storyline-type-other.md) |

Each type policy must define these sections:

1. `Audience outcome`: activation condition and required intake context;
2. `Storyline logic`: the type-specific audience journey and sequencing rules;
3. optional type-only context or variants;
4. `Safeguards`: failure modes and unsupported behaviors to prevent;
5. `Completion checks`: conditions the proposed Storyline must satisfy.

Treat each type policy as the sole owner of that type's Storyline sequence, required inputs, safeguards, and completion checks. To add a new primary type, create one policy with this contract, add one route above, expose its direct conditional link in `SKILL.md`, and extend the `Deliverable type` schema and validator. Do not copy type-specific rules back into this router or into `storyline-and-content.md`.

For a hybrid, choose one primary type and only the necessary secondary behavior. Read one additional type policy only when that secondary behavior materially changes the Storyline. Surface conflicting audience outcomes before drafting, and keep `Deliverable type` set to the confirmed primary type.

## 5. Present the Storyline for approval

For every confirmed type, briefly explain the overall narrative arc and how it serves the confirmed audience outcome, then show the complete page sequence beginning with S01 Cover. Use the following fixed field order for every displayed page:

1. `Slide ID`
2. `Page title / purpose`
3. `Page type`
4. `Narrative role`
5. `Content Summary`
6. `Next connection`
7. `Authoring mode`

Format `Content Summary` as a short bullet list, normally two to four bullets. Each bullet summarizes one distinct content block, claim, evidence group, or audience takeaway planned for the page. Keep it at Storyline level: do not draft exact on-slide copy, invent unsupported facts, or include visual-design instructions.

Show a substantive `Next connection` only when the current page is a content page and the immediately following page is also a content page. Explain which specific claim, evidence, question, conclusion, or implication on the current page creates the need for the following page; do not merely write “leads to the next page.” Display `Not applicable` when the current page is structural or protected, has no following page, or the next page is a Cover, Agenda, Section divider/chapter page, Ending/closing page, or Protected placeholder.

Do not display a separate `Protected status`; `Page type: Protected placeholder` is sufficient to identify a protected page in the Storyline.

Use this page block unless a compact table can preserve the bullet hierarchy and all fields without ambiguity:

```markdown
### <Slide ID>｜<Page title / purpose>

- Page type: <type>
- Narrative role: <why this page exists>
- Content Summary:
  - <planned content point>
  - <planned content point>
- Next connection: <specific content-to-content bridge | Not applicable>
- Authoring mode: <Simplified | Standard | Not applicable>
```

Obtain explicit approval before creating `framework.md` or `content.md`, unless the user expressly waives the Storyline gate. After approval, all types use the same controller-governed workflow, with each page following its own effective authoring mode.
