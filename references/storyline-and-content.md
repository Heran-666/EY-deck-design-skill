# Storyline and content design

This file defines the shared reasoning standard. Use the confirmed
`storyline-type-*.md` policy for type-specific sequence and safeguards.

## Chat review language

At Storyline confirmation and content confirmation, present all review material
in Chinese in chat, whether the deck is requested in Chinese or English.
Translate English material before displaying it; keep Chinese material in
Chinese. This applies to the initial review, revised reviews, and resumed
confirmation stages.

For Storyline, translate the context, thesis, chapter and page titles, claims,
Content Summary units, Next connection, and Reading mode × Page rhythm design
directions. For content, use the complete `present-review` marked source and
translate the full page, including Page logic, headings, block details, Child
logic, emphasis intent, tables and chart descriptions, notes, and source
explanations. Translate field labels for readability; retain schema keys and
enum values alongside Chinese explanations when needed for traceability.

Preserve page/block IDs, all numbers, units, dates, URLs, source identities,
relationships, qualifiers, conditions, and caveats. Keep proper names and
technical identifiers traceable; add Chinese explanations where useful. Review
translation must neither summarize nor omit content, add claims, strengthen
certainty, or substitute a file link. An English original alone does not satisfy
this gate. For example, `The pilot may reduce rework by 15% if controls are met`
becomes `在满足控制要求的情况下，试点可能将返工减少 15%。`

The Chinese text is a chat review view of the source. Keep the requested deck
language in `Language`, audience-facing Storyline fields used for deck output
(including deferred Cover text), and provisional/canonical on-slide content.
Do not overwrite them with the review translation. Explicit approval of the
faithful Chinese review approves the corresponding source meaning. If feedback
changes that meaning, update the source and present its complete Chinese review
again; use `present-review` again for content so the binding is current.

## Storyline

Define the audience, starting point, desired change, and thesis. Separate source
facts, interpretation, and recommendations. Every page must advance the
audience journey.

Apply the structural shell from `deliverable-types.md`; keep structural pages
concise.

Before presenting the page sequence, choose one deck-level `Reading mode`:

- `text`: reader-led; each page must stand alone with complete explanation;
- `balanced`: claim and supporting evidence share the page;
- `presentation`: projection-first; one dominant visual expression carries the claim.

Assign every page one `Page rhythm`: `anchor` for structural pages, `dense` for
information-heavy explanation or evidence, or `breathing` for a low-density
impact beat. Substantive pages must use `dense` or `breathing`. Do not infer
rhythm from the number of blocks alone; consider text volume, evidence
complexity, reading distance, and the page's audience move.

For Storyline review, show one visual design direction for each
`Reading mode × Page rhythm` pair. Synthesize it directly from the two axes:
the Reading mode states where complete meaning is carried; the Page rhythm
states the page's density, pacing, and focal burden. Name both effects in one
plain-language sentence. For example, `balanced × dense` keeps the claim and
its evidence on the page while using compact grouping and strong hierarchy for
complex relationships. The direction is an execution bias, not a stored
parameter or layout prescription; do not add coordinates, fixed columns, named
page templates, or element maps.

For Storyline review:

- Give each substantive page one main claim and normally three to five distinct
  `Content Summary` units that provide its explanation, evidence, example,
  boundary, implication, or action.
- Use `Next connection` only between adjacent content pages; name what creates
  the next-page need. Otherwise use `Not applicable`.
- Merge or challenge pages that lack a distinct audience move.

## Page argument

Before writing blocks, resolve these fields for every substantive page:

- `Page objective`: role in the Storyline
- `Audience move`: intended change in understanding or decision posture
- `Reasoning pattern`: the semantic pattern, such as progression, comparison,
  cause/effect, problem/solution, hierarchy, or convergence
- `Argument chain`: how every top-level block supports the page claim
- `Relationship constraints`: relationships that must not be misread
- `Argument priority`: the semantic order in which the argument should land

Record them in `Page logic（Build-only）` and approve them with the content
outline. Wording is preferred, not verbatim; facts, data, claims, relationships,
qualifiers, caveats, and sources remain authoritative. Exclude visual direction,
layout proposals, and coordinates.

Use one claim plus normally three to five planned content blocks, or an
equivalently complete table, chart, process, or other semantic form. Use fewer
blocks only for a deliberate single-impact page. Do not add repetition or
unsupported detail to simulate depth.

## Semantic structure

IDs encode meaning, not layout:

- progression, convergence, comparison, parallel expansion, cause/effect,
  problem/solution, and input/activity/output may use level-one peers;
- hierarchical decomposition uses a meaningful parent with at least two
  children.

Record page-level relationships once in `Argument chain` and `Relationship
constraints`; record parent-child relationships once in `Child logic`. Put
detail in children, collapse single-child structures, and normally stop at
three levels.

## Content form

Every leaf must be understandable on its own and support its heading. Choose
the form that matches the evidence:

- table: exact multi-field comparison, mapping, ownership, or lookup;
- chart: magnitude, distribution, trend, variance, or relationship;
- process/timeline: sequence, stages, dependencies, or cadence;
- responsibility boundary: ownership and control;
- deliverable anatomy/evidence package: document structure and proof purpose;
- rich text: when prose is clearest.

Combine forms only when each has a distinct role. Tables need complete visible
cells and notes. Charts need exact categories, series, values, units, periods,
definitions, caveats, and sources. Never convert qualitative claims into
invented quantitative evidence.

## Evidence and review

For each evidence object, state what it proves, its owner, validity or review
point, and whether it is required, illustrative, user-provided, externally
sourced, or pending. Do not present hypotheses, examples, interpretations, or
recommendations as established fact. Protect unverified client or EY evidence
with placeholders.

Before approval, verify that the page advances the audience outcome; claim and
evidence agree; every block is substantive; tables and charts are buildable;
and every claim is verified, labeled, or protected.
