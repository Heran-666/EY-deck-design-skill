# EY build-spec contract

## Contents

1. Boundary and IDs
2. Deck build profile
3. Page schema
4. Content rules
5. Semantic Visual Direction
6. Sources
7. Validation

## 1. Boundary and IDs

Replace the entire `working/provisional-content.md` with exactly the active pages listed by the controller, in order, using the same lean build-spec schema; never append to a previous review batch. After explicit approval, the controller promotes those exact sections into the single canonical `content.md` and removes the handled provisional file; do not rewrite them during promotion. `content.md` owns approved visible copy, data, page-local sources, and semantic Visual Directions. Keep project memory in `framework.md`, workflow evidence in receipts, and analysis or rejected alternatives out of both files.

Use stable slide IDs (`S01`, `S02`) and content IDs (`S03-B1`, `S03-B2`). Use decimal children only under a meaningful parent with at least two children and keep normal hierarchy to three levels. IDs express semantic hierarchy, not visual placement, reading sequence, or card count.

## 2. Deck build profile

Begin both provisional and canonical files with only the deck language. Project-specific design and asset exceptions remain owned by `framework.md` and are injected separately by the controller:

```markdown
# Presentation Build Specification

## Deck build profile（Build-only）
- Language: <Chinese | English>
```

The fixed canvas and project exceptions remain in `framework.md`; basic EY palette, hierarchy, editability, and ImageGen principles remain in the design reference; display/decision evidence remains in controller receipts. Do not copy them into `content.md`. Do not add a Storyline table, intake-analysis register, coverage matrix, review log, open questions, or assumptions register.

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
- Table purpose（Build-only）: <what the comparison must communicate>

| <exact header> | <exact header> |
|---|---|
| <exact row label> | <exact cell content> |

- Table note: <optional exact copy>

#### S03-B3｜<chart block title>
- Chart purpose（Build-only）: <what the chart must communicate>
- Unit: <exact visible unit>
- Period: <optional exact period>

| Category | <exact series name> |
|---|---:|
| <exact category> | <exact value> |

- Chart note: <optional exact copy or caveat>

### Visual Direction（Build-only）
- Page type: <Cover | Agenda | Section divider | Standard content | Methodology | Approach | Table-led | Chart-led | Deliverable | Case | other precise type>
- Visual focus: <the claim, value, or content ID that should receive first attention>
- Information hierarchy: <primary and supporting information plus intended reading order, without layout>
- Relationship to preserve: <semantic relationship among the approved content>
- Fixed constraints: <approved content, evidence, emphasis, brand, or page-specific non-negotiables>
- Avoid: <page-specific meaning, emphasis, or comprehension failures; no visual solution>

### Sources
- On-slide source: <exact footer or None>
- Source details: <organization, title, date, URL or local path, access date, and supported IDs; or No external sources>
````

The page heading after `## <Slide ID>｜` must equal the exact `Title:` field. `Visual Direction Page type` must equal the matching `framework.md` Page type; the controller enforces both identities before content lock.

Do not add a wireframe, coordinates, measurements, element table, spatial zones, named composition, or specific layout. Text, table, and chart blocks are content forms; combine them only when each has a distinct argumentative role. Protected pages live only in `framework.md` and `svg_output/`; do not add them to provisional or canonical `content.md`.

## 4. Content rules

Treat every on-slide sentence and visible character as final. Page authoring may wrap text but must not add, remove, shorten, or rewrite approved wording without reopening the page in conversation.

The controller derives a machine-enforced visible-copy manifest from the
approved page. It includes audience-facing headings, Title, Subtitle, Core
insight, Detail, table/chart cells, Unit, Period, visible notes, and On-slide
source. It excludes Child logic, table/chart purpose, Visual Direction, Source
details, and emphasis annotations because those fields are Build-only. Page
authoring binds the resulting IDs; do not invent IDs manually in `content.md`.

Annotate emphasis by quoting the exact target substring. Use only `关键重点`, `次级重点`, `对比重点`, and `普通加粗`. Use `对比重点` only when the page's `Relationship to preserve` states an explicit comparison or contrast; otherwise use yellow, pale yellow, or white emphasis.

Keep titles on one line and within 36 Chinese-width characters. Shorten crowded titles; the page-authoring action assigns text roles and chooses only from the fixed typography scale in `design-system.md`.

## 5. Semantic Visual Direction

Use only the five Visual Direction decisions plus `Page type`. State what dominates, the semantic reading order/relationship, confirmed constraints, and comprehension failures to avoid.

Do not name or sketch a composition, layout family, geometry, position, shape, card/grid/panel structure, timeline, funnel, matrix, or other concrete design solution. Do not include coordinates, dimensions, font sizes, asset links, or construction instructions. The bounded page-authoring action owns composition and typography-role assignment within the fixed scale. Keep the Visual Direction open enough for one complete `Simplified` solution or two independent `Standard` A/B solutions under [authoring-modes.md](authoring-modes.md).

Judge prescriptions by context. An isolated analytical term such as “matrix,” “timeline,” “row,” or “column” may describe approved subject matter and is not by itself a layout instruction. Block it only when the field tells the page author to construct or arrange that visual solution.

## 6. Sources

Keep factual sourcing with the page that uses it. `On-slide source` is exact visible footer copy or `None`. `Source details` records authoritative provenance needed to verify or rebuild the page. Do not create a separate complete source register or record construction-only visual assets selected during page authoring.

For user-provided or internal material, state that status and the supported IDs. Never invent a URL, publication date, license, or approval status.

## 7. Validation

Use controller `present-review` as the normal validation-and-presentation gate. Keep `validate-review` only as an optional editing diagnostic. The lower-level validator also accepts `--content`, `--framework`, and repeatable `--page` options for schema, IDs, duplicate fields, Visual Direction boundaries, emphasis targets, page types, and cross-page rules. Human review remains responsible for semantic sufficiency: approved wording, evidence quality, complete table/chart inputs, correct hierarchy, and faithful meaning. Do not use character-count heuristics as a substitute for that review.
