# Embedded PPT Master design contract

Use this contract for every authored page after content lock. It vendors the
useful design responsibilities formerly associated with PPT Master into EY
Deck Design; it does not activate, import, or depend on a separate global
`$ppt-master` skill.

## Contents

1. Leadership boundary
2. Design sequence
3. Design kernel
4. Routed references

## Leadership boundary

The EY controller remains the only workflow authority. Embedded PPT Master
leads the complete visual-design domain inside the controller's bounded Stage
1 actions and leads deterministic technical construction in Stage 2.

| Embedded role | Owns | Must not own |
|---|---|---|
| PPT Master Design Lead | communication job, reading mode, composition family, focal mechanism, information model, typography hierarchy, imagery strategy, EY gesture, density, Design Decision | workflow order, copy changes, user approval, SVG construction |
| PPT Master SVG Producer | faithful page-local geometry and SVG construction inside the bound Layout | silently changing the Design Decision or approved meaning |
| Independent Visual QA | one rendered candidate's composition fidelity, focal hierarchy, data story, and brand expression | authoring, repair during judgment, A/B or Base/Revision comparison |
| PPT Master Export Runtime | isolated normalization, Master/Layout construction, conversion, compatibility, package QA | reopening subjective design without a controller-classified blocking defect |

The Content Lead owns audience-facing copy, approved data, sources, and the
semantic Visual Direction. EY's design system and structured-template profile
are mandatory inputs to PPT Master, not optional style suggestions.

## Design sequence

For each requested candidate, perform the following bounded sequence:

1. Read the controller-supplied design context and verify its hash, design
   module identity, policy fingerprint, approved content, adjacent-page
   context, and deck design memory.
2. Define the page's communication job and intended first, second, and
   supporting read.
3. Select one page-scale composition and the correct information-model branch.
4. Persist one candidate-specific Design Decision before any SVG construction.
5. Construct the SVG faithfully inside the bound Master/Layout prototype.
6. Run deterministic preflight, render the candidate, then conduct independent
   single-candidate Visual QA.

Never let remembered conversation state replace the persisted context,
decision, policy fingerprint, or QA receipt.

## Design kernel

### Communication job and reading mode

Make the page independently understandable and preserve the approved content
relationship. Choose the expression from the audience's task:

- `presentation`: one claim and one dominant visual expression legible at
  projection distance;
- `balanced`: a primary claim plus structured evidence, with explanation kept
  subordinate;
- `reference`: exact lookup, qualification, or multi-field detail where a
  table or denser organization is genuinely required.

The reading mode changes expression, never facts. Do not convert connected
prose into bullets merely because a template exposes list slots, and do not
turn parallel evidence into paragraphs merely to fill space.

### Page-scale composition

Treat the SVG as one canvas, not a DOM or UI component library. Establish a
dominant visual field before placing supporting elements. Use scale,
asymmetry, alignment, crop, rhythm, contrast, and negative space to create a
deliberate reading path. Prefer one coherent composition over stacked banners,
uniform columns, repeated rounded cards, pills, badges, or dashboards.

Cards remain valid only when they express a real peer grouping, comparison,
hierarchy, or capacity relationship. The Agenda Layout is the sole default
card-grid exception. A reusable Master/Layout defines inherited structure; it
does not dictate the slide-local qualitative composition inside the content
region.

### Information-model routing

Choose the branch from the approved relationship, not from visual novelty:

| Meaning to express | Design branch |
|---|---|
| qualitative sequence, hierarchy, dependency, flow, roles, or grouping | structure/composition |
| value-derived position, length, angle, area, radius, width, or color | chart/data visual |
| row-header × column-header facts requiring exact lookup | table |
| sourced or generated scene that materially improves comprehension | image and argument |
| one short conclusion supported by limited evidence | claim and evidence |

Use the simplest truthful editable form. Numbers used only as identifiers or
labels do not create a chart. Do not imitate a table with disconnected text
boxes. Do not introduce imagery as decoration when typography or data already
carries the meaning.

### Visual hierarchy and continuity

Map every visible text item to the fixed EY typography roles before drawing.
Shorten or recompose before using a denser permitted role. Use one restrained
EY gesture as the signature device for the page and subordinate other accents.
Vary a deck motif through scale, crop, density, position, or interaction rather
than cloning the same carrier and topology across adjacent pages.

Deck memory is guidance for continuity and accidental-repetition avoidance. It
must never become a gate requiring A and B to be compositionally distinct.

## Routed references

Use these EY-adapted modules as parts of this embedded design subsystem:

- [design-direction.md](design-direction.md): persisted Design Decision schema;
- [design-system.md](design-system.md): EY brand and typography policy;
- [composition-and-data-visual-language.md](composition-and-data-visual-language.md): composition, structure, chart, table, and image repertoire;
- [page-svg-authoring.md](page-svg-authoring.md): PPT Master SVG Producer contract;
- [visual-qa.md](visual-qa.md): independent single-candidate rendered review;
- [structured-template-profile.md](structured-template-profile.md): Master/Layout inheritance boundary.

These files are bundled policy. Normal execution must not read the external
`/Users/.../.codex/skills/ppt-master` directory. Any future upstream import must
be reviewed, adapted to EY, added to the design-policy manifest, and covered by
controller and forward tests before it becomes authoritative.
