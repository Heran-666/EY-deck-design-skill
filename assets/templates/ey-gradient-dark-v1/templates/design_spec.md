---
deck_id: ey-gradient-dark-v1
kind: deck
category: brand
summary: EY proposal, sharing, training, and interpretation decks that need confident executive communication with authentic EY identity and editable native structure.
keywords: [EY, proposal, sharing, training, interpretation, consulting]
primary_color: "#FFE600"
canvas_format: ppt169
canvas_width: 1280
canvas_height: 720
canvas_viewbox: "0 0 1280 720"
source_canvas_width: 1280
source_canvas_height: 720
source_viewbox: "0 0 1280 720"
replication_mode: fidelity
native_structure_mode: structured
page_count: 5
---

# EY Gradient Dark — Design Specification

## I. Template Overview

| Application context | Definition |
|---|---|
| Recurring presentation family | EY proposals, executive sharing decks, training materials, interpretations, and client-facing reports |
| Intended audiences and outcomes | Help client, leadership, stakeholder, or learner audiences understand an argument, trust its evidence, and take the intended next step |
| Delivery and reading assumptions | Supports live presentation and later independent reading; pages should preserve decisive headlines, evidence, and source context |
| Representative narrative/page roles | Cover, Agenda, Section divider, open Content, and fixed Ending; native PPT Master decides which prototypes to use, repeat, or adapt for the approved content |

The workspace supplies authentic EY identity and reusable native structure. It
does not impose a page-local composition catalog, information model, or density
target. Native PPT Master retains complete communication and visual-design
judgment within the resolved identity and structure contract.

## II. Color Scheme

| Role | Color | Application |
|---|---|---|
| EY yellow | #FFE600 | Primary identity accent and decisive emphasis |
| Black | #000000 | Main background and maximum-contrast text |
| White | #FFFFFF | Primary text on dark pages and open negative space |
| Neutral gray | #A6A6A6 | Secondary copy, dividers, and metadata |
| Pale yellow | #FFF4B3 | Restrained supporting emphasis |

Use additional hues only when they encode an audience-relevant category,
state, threshold, or comparison. Do not create decorative rainbow coding.

## III. Typography

| Role | Font stack | Application |
|---|---|---|
| Latin title and body | `EYInterstate, Arial, sans-serif` | EY-facing Latin display and body copy |
| Chinese title and body | `Microsoft YaHei, PingFang SC, Arial, sans-serif` | Chinese display and body copy |

Use the native PPT Master typography system to resolve page-specific hierarchy,
scale, wrapping, and density. Preserve literal approved wording.

## IV. Signature Design Elements

- Keep the authentic EY mark and cover lockup as fixed template atoms.
- Use dark editorial fields, confident negative space, and EY yellow as the
  principal identity accent.
- The Cover preserves the supplied gradient frame and EY tagline.
- Agenda, Divider, and Content share the EY Dark Master and authentic fixed mark.
- The complete Ending remains a fixed full-slide image and must not be reflowed,
  restyled, translated, cleaned, or overlaid.
- Open composite content regions are technical carriers, not composition boxes.
  For Content pages, compose freely across the complete 1280×720 slide; do not
  infer a bottom safety line, reserve a footer band, or treat placeholder bounds
  as visual limits. Preserve Master/Layout identity and literal fixed atoms, but
  do not run a separate overlap gate against the EY mark.

## V. Page Roster

| File | Master | Layout key | PowerPoint picker name | Visual character | Reusable slots |
|---|---|---|---|---|---|
| `cover.svg` | EY Cover | cover | EY Cover | Gradient frame, authentic EY mark/lockup, fixed tagline | Project type, title, subtitle |
| `agenda.svg` | EY Dark | agenda | EY Agenda | Dark editorial directory shell | Title and composite agenda region |
| `divider.svg` | EY Dark | divider | EY Section Divider | Dark chapter transition with controlled glow | Section label and title |
| `content.svg` | EY Dark | content | EY Content | Open black content canvas with fixed EY mark | Title, subtitle, and composite content region |
| `ending.svg` | EY Dark | ending | EY Ending | Exact supplied legal/brand closing page | None |

## VI. Assets

| File | Intended usage |
|---|---|
| `cover-gradient.png` | Cover gradient frame source |
| `divider-glow.png` | Divider glow source |
| `ending-background.png` | Ending background source |
| `ending-slide.png` | Exact fixed Ending page |

## VII. Placeholder Overrides

- Composite Agenda and Content object slots are editable authoring regions; their
  stored bounds carry native placeholder metadata and do not limit composition.
- Content uses a full-slide proxy slot. The entire 1280×720 canvas is available
  for page composition, with no special rule at `y=650` and no EY-logo overlap
  QA check.
- Cover and Divider text slots retain their declared role and bounds.
- Ending has zero slots and remains literal.
