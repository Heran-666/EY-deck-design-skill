# EY typography and integrity policy

This reference supplies EY visual and typography policy to Embedded PPT Master Stage 1. PPT Master owns concept, composition, SVG construction, rendered visual QA, and internal repair. Do not expand content-facing Visual Direction into a wireframe, coordinate plan, or construction manual.

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
owns typography-role assignment, geometry, wrapping, grouping, spacing, color,
imagery, and visual treatment.

## Visual Direction

Consume the approved semantic `Visual Direction（Build-only）` defined by
[output-contract.md](output-contract.md). Preserve its meaning without treating
it as a prescribed layout or implementation plan.

## Visual language and color economy

Default authored content pages to black, white, neutral greys, and EY yellow.
Use at most one additional accent hue on a page, and only when it carries an
explicit, audience-relevant category, state, threshold, or comparison meaning.
Never assign a different color to every peer merely to separate adjacent
content. Labels, position, scale, grouping, line treatment, and whitespace must
carry the structure first; color may reinforce that structure but must not
invent it. Fixed Cover, Divider, Agenda, Ending, and inherited template artwork
remain exempt from this authored-content palette rule.

Treat content IDs as argument semantics, never as a container inventory. Do not
default each block to an equal card, rounded panel, arrow, pill, column, or
identically weighted module. Avoid nested panels and repeated decorative
containers when one page-scale structure can express the relationship. Merge,
stagger, subordinate, or spatially integrate blocks when that improves the
approved meaning and reading task.

Use one dominant composition per page. For evidence–system–outcome or
input–mechanism–result arguments, keep evidence visually subordinate, make the
mechanism or system the main explanatory object, and give the outcome a clear
focal role. Express integration or convergence with one coherent shared
structure or path rather than a row of separately colored peer arrows. Use
proportion, asymmetry, rhythm, whitespace, typography, and precise geometry to
create visual sophistication while preserving native editability.

Choose the clearest truthful editable information model. Simplicity applies to
the semantic model and audience reading task, not to visual ambition,
composition quality, or craft. Native-PPTX compatibility does not justify a
generic dashboard, equal-card grid, or mechanically literal block-to-shape
mapping.

## Integrity boundary

Preserve approved copy, data, sources, emphasis, semantic relationships, fixed
template atoms, and export compatibility. Do not invent missing factual labels,
values, units, dates, caveats, or sources. These integrity requirements do not
prescribe composition, color, imagery, information visualization, or layout.

## Mode-aware design intent

For a `Simplified` page, produce one confident complete A solution. Do not lower composition, copy, typography, preview, or export quality because the page has one candidate.

For a `Standard` page, produce two complete interpretations from the same locked packet:

- A: one confident complete solution.
- B: another complete solution from the same locked content, not a repair of A.

Both preserve the same approved meaning and canvas. B may use any complete
visual approach and may report material differences; identical A/B bytes or
insufficient difference evidence do not block production, comparison, or user
selection. In either mode, the controller owns the
manifest, presentation, user decision, revisions, and handoff. See
[authoring-modes.md](authoring-modes.md).
