# Deliverable type routing

## Contents

1. Classify from the supplied background
2. Confirm the type
3. Route to the type policy
4. Present the Storyline for approval

## 1. Classify from the supplied background

Review the objective, audience, source material, delivery setting, requested
output, desired audience change, and constraints. Infer the primary type:

- `Proposal`: seeks approval, selection, sponsorship, funding, or authorization
  for a response, scope, approach, or commercial offer.
- `Sharing deck`: shares experience, insights, progress, practices, or a point of
  view to build understanding, alignment, or discussion.
- `Training`: builds knowledge or capability through learning objectives,
  explanation, examples, practice, checks, or application support.
- `Interpretation`: explains supplied material, findings, policy, research,
  data, or documents, emphasizing meaning, implications, uncertainty, and
  response.
- `Other: <specific form>`: names the actual form when none of the above fits,
  such as decision briefing, workshop, readout, update, report-out, or keynote.

Classify by audience outcome, not casual labels such as “deck,” “presentation,”
or “sharing.” For hybrids, choose the dominant purpose and add a secondary type
only when it changes the Storyline.

Before drafting, obtain the objective, audience, desired audience change,
source boundary, hard delivery constraints, and any input required by the
selected type policy. Ask only for missing information that would change the
sequence or leave a claim unsupported; optional context may remain `None`.

## 2. Confirm the type

Give one concise preliminary judgment after reviewing the background:

`根据现有背景，我初步判断这是 <type>，因为 <purpose/audience basis>。请确认；如果不准确，请告诉我更希望它作为哪种形式。`

If two types remain plausible, recommend one and name only the closest
alternative, including the structural consequence. Ask only what is needed to
distinguish them. Do not present a page sequence before confirmation unless the
user explicitly waives this gate.

Treat a direct correction as confirmation. Record the confirmed type in the
temporary intake summary and later in `framework.md`; reconfirm only if the
objective changes.

## 3. Route to the type policy

Apply this shared structural shell before the selected type policy:

- place exactly one `Cover` at S01 for every deliverable type;
- when there are at least six substantive pages, place one `Agenda` at S02 and
  at least one `Section divider` before the relevant major chapter;
- allow Agenda or divider pages in shorter decks when they materially improve
  navigation, but do not add them as decoration.

After confirmation, read [storyline-and-content.md](storyline-and-content.md) and exactly one primary type policy:

| Confirmed primary type | Type policy |
|---|---|
| `Proposal` | [storyline-type-proposal.md](storyline-type-proposal.md) |
| `Sharing deck` | [storyline-type-sharing-deck.md](storyline-type-sharing-deck.md) |
| `Training` | [storyline-type-training.md](storyline-type-training.md) |
| `Interpretation` | [storyline-type-interpretation.md](storyline-type-interpretation.md) |
| `Other: <specific form>` | [storyline-type-other.md](storyline-type-other.md) |

Each type policy owns these sections:

1. `Audience outcome`: activation condition and required intake context;
2. `Storyline logic`: the type-specific audience journey and sequencing rules;
3. optional type-only context or variants;
4. `Safeguards`: failure modes and unsupported behaviors to prevent;
5. `Completion checks`: conditions the proposed Storyline must satisfy.

Do not duplicate type-specific sequence, inputs, safeguards, or completion
checks in this router or `storyline-and-content.md`. To add a primary type,
create a policy with this contract, add its route above, and extend the
`Deliverable type` schema and validator. Keep `SKILL.md` linked to this router.

For a hybrid, keep `Deliverable type` set to the confirmed primary type. Read
one secondary policy only when its behavior materially changes the Storyline,
and resolve conflicting audience outcomes before drafting.

## 4. Present the Storyline for approval

Briefly explain how the narrative arc serves the audience outcome, then show
the complete page sequence from S01 Cover. Use this field order for every page:

1. `Slide ID`
2. `Page title / purpose`
3. `Page type`
4. `Narrative role`
5. `Content Summary`
6. `Next connection`

For each substantive page, use normally three to
five bullets in `Content Summary` unless a deliberate single-impact page needs
only two. Each bullet must identify a
distinct planned block, claim, evidence group, example, boundary, implication,
action, or takeaway and explain its contribution. Together they must establish
the page claim and its support. Keep structural pages concise. Stay at
Storyline level: no final copy, unsupported facts, filler, or visual direction.

Use `Next connection` only between adjacent content pages. Name the claim,
evidence, question, conclusion, or implication that creates the next-page need;
never write a generic transition. Use `Not applicable` for structural or
protected pages, the last page, or any page followed by a non-content page.

Do not add `Protected status`; `Page type: Protected placeholder` is sufficient.

Use this page block unless a compact table can preserve the bullet hierarchy and all fields without ambiguity:

```markdown
### <Slide ID>｜<Page title / purpose>

- Page type: <type>
- Narrative role: <why this page exists>
- Content Summary:
  - <planned content point>
  - <planned content point>
  - <planned content point>
- Next connection: <specific content-to-content bridge | Not applicable>
```

Obtain explicit approval before creating `framework.md` or `content.md`, unless
the user waives this gate. After approval, use the shared controller workflow.
In `framework.md`, default Cover, Agenda, Section divider, and Ending to
`Deferred template` unless custom design is requested; never modify the fixed
Ending. Export only after every authored page has a confirmed SVG and every
deferred page has a known template type.
