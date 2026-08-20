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

## Purpose

Use for EY proposals, executive sharing, training, interpretations, and
client-facing reports. The template supplies authentic identity and editable
native structure; it does not prescribe page-local composition, information
models, or density. PPT Master retains design judgment within the fixed
identity and structure below.

## Identity

| Role | Value | Use |
|---|---|---|
| EY yellow | `#FFE600` | Identity accent and decisive emphasis |
| Black | `#000000` | Main background and maximum contrast |
| White | `#FFFFFF` | Primary dark-page text and negative space |
| Neutral gray | `#D9D9D9` | Secondary copy, dividers, metadata |
| Pale yellow | `#FFF4B3` | Restrained supporting emphasis |
| Balancing blue | `#188CE5` (`rgb(24, 140, 229)`) | Balance the dominant EY yellow; express comparison or contrast relationships |

Use balancing blue selectively so EY yellow remains the primary accent. Add
other hues only to encode a meaningful category, state, threshold, or
comparison.

| Text | Font stack |
|---|---|
| Latin | `Calibri, sans-serif` |
| Chinese | `Microsoft YaHei, sans-serif` |

PPT Master determines hierarchy, scale, wrapping, and density while preserving
approved wording.

## Fixed and adaptive boundaries

- Preserve the authentic EY mark and Cover lockup as fixed atoms.
- Cover retains its gradient frame and EY tagline.
- Agenda, Divider, and Content share the EY Dark Master and fixed mark.
- Ending is a fixed full-slide image: do not reflow, restyle, translate, clean,
  or overlay it.
- Open composite regions are technical carriers, not composition boxes.
  Content may use the complete 1280×720 canvas. Placeholder bounds do not
  impose a safe area, footer reserve, `y=650` cap, or EY-logo overlap gate.
- Preserve Master/Layout identity and literal fixed atoms.

## Page roster

| File | Master | Layout | Picker name | Fixed character | Editable content |
|---|---|---|---|---|---|
| `cover.svg` | EY Cover | cover | EY Cover | Gradient, mark/lockup, tagline | Project type, title, subtitle |
| `agenda.svg` | EY Dark | agenda | EY Agenda | Dark canvas, mark, glow | Title, blank agenda region |
| `divider.svg` | EY Dark | divider | EY Section Divider | Dark transition, glow, mark | Section label, title |
| `content.svg` | EY Dark | content | EY Content | Black canvas, mark | Title, subtitle, composite region |
| `ending.svg` | EY Dark | ending | EY Ending | Exact closing page | None |

## Assets

| File | Use |
|---|---|
| `cover-gradient.png` | Cover gradient |
| `divider-glow.png` | Divider glow |
| `ending-background.png` | Ending background source |
| `ending-slide.png` | Exact user-approved `收尾页.pptx` slide; preserve unchanged |

## Authoring overrides

- Agenda has no protected item layout. PPT Master owns ordering treatment,
  grouping, numbering, typography, geometry, and canvas use. Only its
  Master/Layout, fixed mark, glow, and title's semantic role are fixed.
- Content uses a full-slide proxy slot; its stored bounds are metadata only.
- Cover and Divider text slots retain their declared roles and bounds.
- Ending has no slots and remains literal.
