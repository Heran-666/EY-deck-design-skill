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

### On-slide content
- Title: <exact copy>
- Subtitle: <optional exact copy>
- Core insight: <optional exact copy>

#### S03-B1｜<parent or peer title>
- Child logic（Build-only）: <only for a genuine parent>

##### S03-B1.1｜<child title>
- Detail: <exact visible copy; optional only when heading is complete>
- Emphasis:
  - “<exact visible substring>”｜<关键重点 | 次级重点 | 对比重点 | 普通加粗>

#### S03-B2｜<table block title>
- Table purpose（Build-only）: <required lookup/comparison>

| <exact header> | <exact header> |
|---|---|
| <exact row label> | <exact cell> |

- Table note: <optional exact copy>

#### S03-B3｜<chart block title>
- Chart purpose（Build-only）: <relationship and intended conclusion>
- Unit: <exact visible unit>
- Period: <optional exact period>

| Category | <exact series name> |
|---|---:|
| <exact category> | <exact value> |

- Chart note: <optional exact copy or caveat>

### Sources
- On-slide source: <exact footer or None>
- Source details: <provenance and supported IDs; or No external sources>
````

The page heading contains only the Slide ID. `Title` is the sole exact page
title and is synchronized to `framework.md` after approval. Page type and
template come from `framework.md`, not `content.md`.

Do not add Visual Direction, design briefs, wireframes, coordinates,
measurements, element maps, zones, named compositions, or layouts. Content
forms describe approved information, not composition. Protected pages remain in
`framework.md` and optional `protected_input/`; workflow 7.0 excludes them from
the authored SVG/PPTX roster.

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
charts, or descriptions. Do not number labels in content; PPT Master may derive
visible numbering from block order.

## Visible-content rules

- Every audience-facing character is final. SVG authoring may wrap but may not
  add, remove, shorten, or rewrite it without reopening content.
- Build-only fields stay invisible. PPT Master must reproduce headings, Title,
  Subtitle, Core insight, Detail, table/chart cells, Unit, Period, visible notes,
  and On-slide source.
- `Emphasis` quotes an exact visible substring from the same block. Use only
  `关键重点`, `次级重点`, `对比重点`, or `普通加粗`; use `对比重点` only for an explicit
  approved contrast. Emphasis is a required semantic priority, not a complete
  style map.
- Keep titles on one line and within 36 Chinese-width characters; resolve
  crowding during content review.

## Sources and validation

`On-slide source` is exact footer copy or `None`. `Source details` records
authoritative provenance and supported IDs. Identify user/internal material and
never invent URLs, dates, licenses, or approval status. Do not record
construction-only visual assets here.

Use controller `present-review` for the normal validation and review gate.
`scripts/validate_deck_blueprint.py` is the direct diagnostic for schema, IDs,
duplicates, emphasis targets, page types, and cross-page rules. Human review
owns meaning, evidence quality, hierarchy, and buildability.
