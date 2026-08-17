# EY build-spec contract

## File boundary

Replace `working/provisional-content.md` with exactly the controller-listed
active pages; never append. After approval, the controller promotes those exact
sections to canonical `content.md`. Keep project memory in `framework.md`,
workflow evidence in receipts, and analysis/design alternatives out of both.

Use stable slide IDs (`S01`) and content IDs (`S03-B1`). Decimal children are
allowed only under a meaningful parent with at least two children; normally
stop at three levels. IDs encode semantic hierarchy, never layout.

Begin provisional and canonical files with:

```markdown
# Presentation Build Specification

## Deck build profile（Build-only）
- Language: <Chinese | English>
```

Do not add template identity, visual decisions, Storyline tables, analysis
registers, review logs, open questions, or assumptions.

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

The page heading contains only the Slide ID. `Title` is the preferred working
title and is synchronized to `framework.md` after approval. PPT Master may
optimize the visible title without changing its meaning. Page type and template
come from `framework.md`, not `content.md`.

Every substantive page requires `Page logic（Build-only）`. Its `Argument chain`
must name every top-level block and may reference only IDs on that page. These
fields guide information design but remain invisible. Cover, Agenda, Section
divider, Ending, and protected placeholder pages must omit Page logic.

Do not add Visual Direction, design briefs, wireframes, coordinates,
measurements, element maps, zones, named compositions, or layouts. Content
forms describe approved information, not composition. Do not create sections
for `Deferred template` pages; they remain ordered in `framework.md` and are
materialized only for PPTX export. Protected pages remain in `framework.md` and
optional `protected_input/`; workflow 8.0 excludes protected pages from the
authored SVG/PPTX roster.

Use a table only for exact multi-field inspection and a chart only for approved
quantitative relationships. Do not duplicate one dataset as both unless each
form has a separate approved purpose.

## Agenda exception

Agenda contains `Title` plus sequential top-level block headings only:

```markdown
### On-slide content
- Title: 目录

#### S02-B1｜战略背景与目标

#### S02-B2｜核心方法与路径
```

Do not add Subtitle, Core insight, Detail, Child logic, Emphasis, tables,
charts, descriptions, or Page logic. Do not number labels in content; PPT
Master may derive visible numbering from block order.

## Content adaptation

- Follow PPT Master's `content vs expression` rule. Treat narrative wording as
  preferred, not verbatim; permit concise connective copy that adds no claim.
- Build-only fields stay invisible. They may guide generated wording but must
  not be copied onto the page as internal instructions.
- `Emphasis` identifies a semantic priority in the source outline. Use only
  `关键重点`, `次级重点`, `对比重点`, or `普通加粗`; use `对比重点` only for an explicit
  approved contrast. PPT Master may emphasize equivalent optimized wording.

## Sources and validation

`On-slide source` is approved footer content or `None`. `Source details` records
authoritative provenance and supported IDs. Identify user/internal material and
never invent URLs, dates, licenses, or approval status. Do not record
construction-only visual assets here.

Use controller `present-review` for the normal validation and review gate.
`scripts/validate_deck_blueprint.py` is the direct diagnostic for schema, IDs,
duplicates, emphasis targets, page types, and cross-page rules. Human review
owns meaning, evidence quality, hierarchy, and buildability.
