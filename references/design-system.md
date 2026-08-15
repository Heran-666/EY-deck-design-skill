# EY typography and color policy

This reference contains the only EY Deck Design constraints on Embedded PPT
Master's visual design: the fixed typography scale and the color policy below.
The bound template is supplied separately. Apart from those three constraints,
PPT Master owns the visual approach without EY Deck Design composition, layout,
geometry, density, hierarchy, imagery, information-visualization, style, or
editability preferences.

## Canvas and typography

- Use the `ppt169` SVG canvas: `1280 × 720`.

Use this complete typography scale for every visible text run. Author with the
listed SVG `font-size` value; the exporter converts it to the required PPTX
point size. Do not use intermediate or ad hoc sizes.

| Text role | PPTX | SVG `font-size` | Choice rule |
|---|---:|---:|---|
| Display title / hero metric | 40 pt | `53.3333` | Cover and Section divider titles; on Content pages, at most one short hero metric or focal statement inside the content region |
| Title | 24 pt | `32` | Page title |
| Subtitle | 18 pt | `24` | Subtitle or title-supporting statement |
| Body heading | 12 or 14 pt | `16` or `18.6667` | Use 14 pt for higher importance or lower density; 12 pt for denser or secondary headings |
| Body content | 8 or 10 pt | `10.6667` or `13.3333` | Default to 10 pt. Use 8 pt only for genuinely dense content after composition and container sizing have been optimized |
| Other information | 6 pt | `8` | Notes, sources, annotations, and other tertiary information |

Both permitted body-heading sizes and both permitted body-content sizes may
appear on one page. Use only the listed sizes; Embedded PPT Master otherwise
owns typography-role assignment and all other typographic treatment.

## Visual language and color economy

Default authored content pages to black, white, neutral greys, and EY yellow.
Use at most one additional accent hue on a page, and only when it carries an
explicit, audience-relevant category, state, threshold, or comparison meaning.
Never assign a different color to every peer merely to separate adjacent
content. Fixed Cover, Divider, Agenda, Ending, and inherited template artwork
remain exempt from this authored-content palette rule.
