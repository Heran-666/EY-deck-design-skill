# EY build-spec contract

## File boundary

Replace `working/provisional-content.md` with exactly the controller-listed
active pages; never append. Include the compact build-profile header for the
first approved page only; later provisional pages reuse the canonical header.
After approval, the controller promotes those sections unchanged to canonical
`content.md`. Store project memory in
`framework.md` and workflow evidence in receipts. Keep analysis and design
alternatives out of both files.

Use stable slide IDs (`S01`) and content IDs (`S03-B1`). Use decimal children
only under a meaningful parent with at least two children, and normally stop at
three levels. IDs express semantic hierarchy, never layout.

Begin the first provisional file and the canonical file with:

```markdown
# Presentation Build Specification

## Deck build profile（Build-only）
- Language: <Chinese | English>
```

Exclude template identity, visual decisions, Storyline tables, analysis
registers, review logs, open questions, and assumptions.

## Page schema

````markdown
## S03

### Page logic（Build-only）
- Page objective: <why this page exists>
- Audience move: <audience state before → after>
- Reasoning pattern: <semantic argument pattern>
- Argument chain: <name every top-level block and explain its role in the claim>
- Relationship constraints: <relationships that must not be misread; or None>
- Argument priority: <semantic order in which the argument should land>

### On-slide content
- Title: <preferred page title>
- Subtitle: <optional preferred wording>
- Core insight: <approved claim or takeaway>

#### S03-B1｜<parent or peer title>
- Child logic（Build-only）: <only for a genuine parent>

##### S03-B1.1｜<child title>
- Detail: <substantive point with preferred wording; optional when heading is complete>
- Emphasis:
  - “<substring expressing the priority>”｜<关键重点 | 次级重点 | 对比重点 | 普通加粗>

#### S03-B2｜<table block title>
- Table purpose（Build-only）: <required lookup/comparison>

| <preferred header> | <preferred header> |
|---|---|
| <row label> | <approved value or text> |

- Table note: <optional note or caveat>

#### S03-B3｜<chart block title>
- Chart purpose（Build-only）: <relationship and intended conclusion>
- Unit: <approved unit>
- Period: <optional approved period>

| Category | <approved series name> |
|---|---:|
| <approved category> | <approved value> |

- Chart note: <optional note or caveat>

### Sources
- On-slide source: <approved source footer or None>
- Source details: <provenance and supported IDs; or No external sources>
````

The page heading contains only the Slide ID. `Title` is preferred wording; after
approval, the controller synchronizes it to `framework.md`. PPT Master may
optimize the visible title without changing meaning. Page type and template
come only from `framework.md`.

Every substantive page requires `Page logic（Build-only）`. `Argument chain`
must name every top-level block and reference only IDs on that page. These
fields guide information design but remain invisible. Structural and protected
pages omit Page logic.

Do not add Visual Direction, design briefs, wireframes, coordinates,
measurements, element maps, zones, named compositions, or layouts. Content
describes approved information, not composition. Do not create sections for
`Deferred template` pages; they remain in `framework.md` until export.
Protected pages remain in `framework.md` and optional `protected_input/` and
are excluded from the authored SVG/PPTX roster.

Use tables for exact multi-field inspection and charts for approved
quantitative relationships. Do not show one dataset in both forms unless each
has a separate approved purpose.

## Agenda exception

When an Agenda is explicitly authored rather than deferred, include only
`Title` and sequential top-level block headings:

```markdown
### On-slide content
- Title: 目录

#### S02-B1｜战略背景与目标

#### S02-B2｜核心方法与路径
```

Do not add Subtitle, Core insight, Detail, Child logic, Emphasis, tables,
charts, descriptions, or Page logic. Do not number labels; PPT Master may
derive visible numbering from block order.

## Content adaptation

- Apply PPT Master's `content vs expression` rule: wording is preferred, not
  verbatim, and concise connective copy may add no new claim.
- Keep build-only fields invisible; use them as guidance, never on-slide text.
- Use `Emphasis` only for semantic priority: `关键重点`, `次级重点`, `对比重点`, or
  `普通加粗`. Reserve `对比重点` for an approved contrast. PPT Master may apply
  the emphasis to equivalent optimized wording.

## Sources and validation

`On-slide source` is approved footer content or `None`. `Source details` records
authoritative provenance and supported IDs. Identify user or internal material;
never invent URLs, dates, licenses, or approval status. Exclude construction-only
visual assets.

Use controller `present-review` for the normal validation and review gate. Use
`scripts/validate_deck_blueprint.py` only for direct diagnosis of schema, IDs,
duplicates, emphasis targets, page types, and cross-page rules. Human review
decides meaning, evidence quality, hierarchy, and buildability.
