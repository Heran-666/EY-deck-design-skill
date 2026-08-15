---
native_structure_mode: structured
template_profile: ey-gradient-dark-v1
canvas_viewbox: "0 0 1280 720"
placeholders:
  cover: [project-type, title, subtitle]
  agenda: [title, agenda-content-region]
  divider: [section-label, title]
  content: [title, subtitle, content-region]
  ending: []
---

# EY Gradient Dark template profile

This reusable profile was reconstructed from the inspected cover, divider, and
body templates supplied for EY Deck Design. It intentionally exposes two
PowerPoint Masters and five reusable Layouts.

## VI. Page Roster

### 1. Cover (`cover.svg`)

- Master: `ey-cover` / `EY Cover`
- Layout: `cover` / `EY Cover`
- Slots: optional project type or core insight, title, optional subtitle
- Fixed Layout copy: `The better the question. The better the answer. The better the world works.` at `x=51`, baseline `y=679`
- Fixed template brand: authentic EY mark with the two-line lockup `Shape the future` / `with confidence`; both are exact vector outlines reconstructed from the supplied Cover Layout group, and must never be retyped or authored as page copy

### 2. Agenda (`agenda.svg`)

- Master: `ey-dark` / `EY Dark`
- Layout: `agenda` / `EY Agenda`
- Slots: title and a composite editable directory region
- Composition: two balanced columns of rounded `#141414` cards, each with a
  yellow left rule, numbered emphasis, and exactly one agenda-item label;
  the seven-item reference uses four cards left and three right

### 3. Section divider (`divider.svg`)

- Master: `ey-dark` / `EY Dark`
- Layout: `divider` / `EY Section Divider`
- Slots: optional section label, title

### 4. Content (`content.svg`)

- Master: `ey-dark` / `EY Dark`
- Layout: `content` / `EY Content`
- Slots: title, optional subtitle, composite editable content region
- Content-region proxy: one borderless black rectangle that blends into the
  Master background. It exists only to carry the native object placeholder and
  must not be interpreted as a visible panel or composition boundary.

### 5. Ending (`ending.svg`)

- Master: `ey-dark` / `EY Dark`
- Layout: `ending` / `EY Ending`
- Treatment: the complete user-supplied ending slide is embedded as one fixed full-slide image with no cleanup, mask, parameterization, or overlay; do not reflow, restyle, translate, revise, or otherwise change it.
- Slots: none
- Fixed behavior: append this unchanged legal/brand page after every generated
  deck; do not expose it to Storyline, content, or page-authoring updates
- Export behavior: preserve the embedded full-slide PNG bytes; do not resize or
  JPEG-reencode this fixed asset

The title/subtitle/content coordinates are contract data. Page authoring may
change only placeholder content. It must retain the root Master/Layout identity,
fixed-layer atom roster, placeholder ids/types/bounds, and inherited-shape
visibility.

Agenda, Section divider, and Content each retain one identical, authentic EY
mark as fixed template content. Its canvas bounds are reconstructed from the
shared source Master group at approximately `x=1184.383`, `y=667.333`,
`w=31.817`, `h=32.667`; preserve the exact three path geometries in the
prototype files. The separate fixed Ending remains exactly as supplied, even
where its brand treatment differs from authored pages.
