# EY build-spec contract

## Contents

1. Boundary and IDs
2. Deck build profile
3. Page schema
4. Content rules
5. Sources
6. Validation

## 1. Boundary and IDs

Replace the entire `working/provisional-content.md` with exactly the active pages listed by the controller, in order, using the same lean build-spec schema; never append to a previous review batch. After explicit approval, the controller promotes those exact sections into the single canonical `content.md` and removes the handled provisional file; do not rewrite them during promotion. `content.md` owns approved visible copy, data, page-local sources, and emphasis. Keep project memory in `framework.md`, workflow evidence in receipts, and analysis, design directions, or rejected alternatives out of both files.

Use stable slide IDs (`S01`, `S02`) and content IDs (`S03-B1`, `S03-B2`). Use decimal children only under a meaningful parent with at least two children and keep normal hierarchy to three levels. IDs express semantic hierarchy, not visual placement, reading sequence, or card count.

## 2. Deck build profile

Begin both provisional and canonical files with only the deck language:

```markdown
# Presentation Build Specification

## Deck build profile（Build-only）
- Language: <Chinese | English>
```

Template identity and visual decisions belong to the bundled PPT Master page
service and its explicit workspace. Do not copy them into `content.md`. Do not add a
Storyline table, intake-analysis register, coverage matrix, review log, open
questions, or assumptions register.

## 3. Page schema

Use this structure for each locked page:

````markdown
## S03｜<exact audience-facing title>

### On-slide content
- Title: <exact copy>
- Subtitle: <optional exact copy>
- Core insight: <optional exact copy>

#### S03-B1｜<parent or peer title>
- Child logic（Build-only）: <only for a genuine parent>

##### S03-B1.1｜<child title>
- Detail: <exact visible copy; omit only when the heading is complete>
- Emphasis:
  - “<exact substring>”｜<关键重点 | 次级重点 | 对比重点 | 普通加粗>

#### S03-B2｜<table block title>
- Table purpose（Build-only）: <what exact multi-field lookup or comparison the table must support>

| <exact header> | <exact header> |
|---|---|
| <exact row label> | <exact cell content> |

- Table note: <optional exact copy>

#### S03-B3｜<chart block title>
- Chart purpose（Build-only）: <the relationship and audience-facing conclusion the chart must make visible>
- Unit: <exact visible unit>
- Period: <optional exact period>

| Category | <exact series name> |
|---|---:|
| <exact category> | <exact value> |

- Chart note: <optional exact copy or caveat>

### Sources
- On-slide source: <exact footer or None>
- Source details: <organization, title, date, URL or local path, access date, and supported IDs; or No external sources>
````

The page heading after `## <Slide ID>｜` must equal the exact `Title:` field. The
PPT Master request adapter obtains Page type from the matching `framework.md`
entry and selects the required template independently of `content.md`.

Do not add a Visual Direction, design brief, wireframe, coordinates,
measurements, element table, spatial zones, named composition, or specific
layout. Text, table, and chart blocks are approved content forms, not page
composition instructions. Protected pages live in `framework.md` and optional
`protected_input/`; do not add them to provisional or canonical `content.md`.
Workflow 6.0 does not process protected inputs into the confirmed SVG list.

Choose a table block only when the audience must inspect exact values across
multiple fields. Choose a chart block when approved values support a trend,
ranking, gap, part-to-whole, range, threshold, or another quantitative
relationship that should be understood visually. Do not duplicate the same
complete dataset as both a table and a chart on one page unless each has a
separate approved argumentative role.

`Agenda` is the one page-type-specific exception to the general content forms.
Its `On-slide content` contains `Title` only, followed by one or more sequential
top-level blocks whose headings are the exact directory labels:

```markdown
### On-slide content
- Title: 目录

#### S02-B1｜战略背景与目标

#### S02-B2｜核心方法与路径
```

Do not add `Subtitle`, `Core insight`, `Detail`, Child logic, Emphasis,
table/chart content, description, or supporting detail to an Agenda item. Do
not prefix the label with a number. During SVG authoring, bundled PPT Master may
render zero-padded visible numbering (`01`, `02`, ...) from the approved block
order without changing the approved labels. Invalid Agenda fields fail
provisional-content validation before page authoring.

## 4. Content rules

Treat every on-slide sentence and visible character as final. Page authoring may
wrap text but must not add, remove, shorten, or rewrite approved wording without
reopening the page in conversation.

Each PPT Master request carries the exact approved page section and its SHA-256.
Candidate validation checks that hash against the current page in `content.md`.
Workflow 6.0 does not create a separate visible-copy manifest or copy-ID graph;
bundled PPT Master remains responsible for reproducing all audience-facing
headings, Title, Subtitle, Core insight, Detail, table/chart cells, Unit, Period,
visible notes, and On-slide source while excluding Build-only instructions from
the visible SVG.

Use Emphasis to mark semantic priorities that the content author explicitly
requires to stand out. Quote an exact target substring from visible text in the
same content block: its heading, Detail, table cells, Unit, Period, or visible
table/chart note. Build-only fields and neighboring blocks are not valid
targets. Emphasis is not an exhaustive visual-style manifest: PPT Master may
create visual hierarchy among other existing text according to composition and
information hierarchy, but must not add or rewrite audience-facing copy. Icons,
shapes, color fields, dividers, and other non-text visual elements are not
limited by Emphasis annotations. Use only `关键重点`, `次级重点`, `对比重点`, and
`普通加粗`. Use `对比重点` only when the approved on-slide content itself makes
an explicit comparison or contrast; otherwise use yellow, pale yellow, or white
emphasis.

Keep titles on one line and within 36 Chinese-width characters. Shorten crowded
titles during content review; bundled PPT Master owns later typography and page
composition.

## 5. Sources

Keep factual sourcing with the page that uses it. `On-slide source` is exact visible footer copy or `None`. `Source details` records authoritative provenance needed to verify or rebuild the page. Do not create a separate complete source register or record construction-only visual assets selected during page authoring.

For user-provided or internal material, state that status and the supported IDs. Never invent a URL, publication date, license, or approval status.

## 6. Validation

Use controller `present-review` as the normal validation-and-presentation gate.
For direct diagnostics, run `scripts/validate_deck_blueprint.py` with
`--content`, `--framework`, and repeatable `--page` options. It checks schema,
IDs, duplicate fields, emphasis targets, page types, and cross-page rules. Human
review remains responsible for semantic sufficiency: approved wording, evidence
quality, complete table/chart inputs, correct hierarchy, and faithful meaning.
Do not use character-count heuristics as a substitute for that review.
