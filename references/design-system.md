# EY page design principles

This reference supplies only the basic design intent passed with locked page content through EY's bundled Page SVG Authoring contract. The bounded authoring action owns the actual SVG concept, composition, construction, fitting, assets, and normal quality checks. Do not expand this into a wireframe, coordinate plan, construction manual, or compatibility specification.

## Canvas and visual language

- Use the `ppt169` SVG canvas: `1280 × 720`.
- Default background: black `#000000`; primary text: white `#FFFFFF`.
- EY yellow `#FFE600` is the strongest emphasis; pale yellow `#FFFACC` is secondary; gray `#D9D9D9`/`#A6A6A6` supports hierarchy.
- Use blue `#188CE5` only for a real comparison or contrast, never as a generic decorative accent.
- Prefer Microsoft YaHei for Chinese and Calibri for English unless the user supplies another system.
- Maintain readable hierarchy; do not shrink principal content merely to force a crowded page.

Use this complete typography scale for every visible text run. Author with the
listed SVG `font-size` value; the exporter converts it to the required PPTX
point size. Do not use intermediate or ad hoc sizes.

| Text role | PPTX | SVG `font-size` | Choice rule |
|---|---:|---:|---|
| Display title | 40 pt | `53.3333` | Cover and Section divider titles only, when bound to those bundled Layouts |
| Title | 24 pt | `32` | Page title |
| Subtitle | 18 pt | `24` | Subtitle or title-supporting statement |
| Body heading | 12 or 14 pt | `16` or `18.6667` | Use 14 pt for higher importance or lower density; 12 pt for denser or secondary headings |
| Body content | 8 or 10 pt | `10.6667` or `13.3333` | Default to 10 pt. Use 8 pt only for genuinely dense content after composition and container sizing have been optimized |
| Other information | 6 pt | `8` | Notes, sources, annotations, and other tertiary information |

Both permitted body-heading sizes and both permitted body-content sizes may
appear on one page when importance differs. Choose only by information density
and importance. A framed text block must fit its container: do not leave a
large unused right or lower zone around short 8 pt copy. Prefer, in order:

1. use 10 pt body copy;
2. right-size or recompose the container;
3. reopen content when the approved argument is materially incomplete;
4. add only a semantic device that explains a relationship, sequence,
   comparison, evidence status, or takeaway.

Never add decorative filler or invent copy. The Stage 1 preflight rejects a
normal Content-page 8 pt text block with four or fewer rendered lines unless
the block carries an explicit `data-density-justification="dense-table"` or
`data-density-justification="compact-matrix"` on itself or an ancestor. Use
either exception only when 10 pt cannot fit after the composition and
container have been optimized. If approved content still does not fit, revise
the composition or reopen the content decision; never create another size or
shrink principal content below its role.

Except for this fixed typography scale, these remain directional principles,
not SVG implementation rules. The bounded authoring action decides exact
geometry, wrapping, grouping, spacing, and visual treatment.

## Visual Direction

Consume the approved semantic `Visual Direction（Build-only）` defined by [output-contract.md](output-contract.md). Preserve its attention priority and meaning without turning it into a card/grid/panel, named composition, coordinate plan, asset list, or wireframe. Retain room for two independent solutions.

## Page and asset principles

- Only the single opening Cover may optionally use a dark, text-free ImageGen background. Agenda and Section divider pages do not use ImageGen. Other pages use generated imagery only when it materially helps comprehension.
- Keep tables and charts editable, simple, and evidence-backed. Do not invent missing labels, values, units, dates, caveats, or sources.
- Preserve approved copy, data, sources, emphasis, semantic relationships, and brand constraints.

## Mode-aware design intent

For a `Simplified` page, produce one confident complete A solution. Do not lower composition, copy, typography, preview, or export quality because the page has one candidate.

For a `Standard` page, produce two complete interpretations from the same locked packet:

- A: one confident complete solution.
- B: a materially distinct complete solution, not an optimization, critique, or repair of A.

Both preserve the same approved meaning and canvas. B should report its material differences in terminal JSON; identical A/B bytes or insufficient difference evidence are advisory and do not block comparison or user selection. In either mode, the controller owns the manifest, presentation, user decision, revisions, and handoff. See [authoring-modes.md](authoring-modes.md).
