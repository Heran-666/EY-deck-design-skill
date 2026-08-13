# Page SVG authoring

Use this internal contract only when the controller emits `GENERATE_SVG_A`,
`GENERATE_SVG_B`, or `GENERATE_SVG_REVISION` with one effective page authoring
mode, one packet path/hash, and one exact artifact path. Generate only the
requested version; do not infer that B is required for a `Simplified` page.

Read the complete packet once. Preserve every approved word, number, source,
emphasis, semantic relationship, and fixed constraint. Choose the composition,
geometry, hierarchy, typography, wrapping, grouping, spacing, and visual
treatment needed to communicate the approved meaning.

Read the packet's bound structured-template prototype and use it as the literal
starting SVG. Keep the root `data-pptx-master*` and `data-pptx-layout*`
attributes, every root-level fixed atom carrying `data-pptx-layer`, and every
placeholder id/type/index/bounds unchanged. Replace carrier text inside title
and subtitle placeholders. Replace only the children of the `content-region`
proxy with the page-specific composition. Never put page content below `y=650`.
For revisions and A/B candidates, retain the same bound Layout.

For an `Agenda`, use the bound `EY Agenda` prototype as its literal base. Keep
its background, fixed atoms, title placeholder, and composite agenda-region
placeholder intact. Replace the agenda-region children with the approved
directory items using the supplied two-column numbered-card grammar. Balance
the columns; use four-left/three-right for seven items. Retain a yellow left
rule, yellow number, and exactly one white agenda-item label on each card. Do
not add a subtitle, description, or supporting-detail line. The single label
may wrap when needed but remains one agenda item. Do not retain unused sample
cards. Bind each yellow number to the packet's `<block-id>-number` item and the
white label to `<block-id>-heading`; both are page-authored editable text. Do
not mark an Agenda number `template-fixed`, leave it unbound, combine it with
the label in one text box, or renumber it independently of the packet.

Apply the complete typography scale in `design-system.md` to every visible text
run. Author with its listed SVG `font-size` values and do not invent an
intermediate size so the exported PPTX lands on the stated point sizes.
Default normal Content-page body copy to 10 pt. Before returning `COMPLETE`,
inspect every framed text block at rendered size and repair any obvious unused
right/lower zone by enlarging the type, right-sizing/recomposing the frame, or
adding a meaning-bearing visual device. Never invent words. If the approved
argument itself is insufficient, return a user-decision block so content can be
reopened. The static preflight enforces the narrow 8 pt rule from
`design-system.md`; passing that check does not replace visual judgment.

Treat the packet's machine-enforced visible-copy JSON as authoritative. Bind
every page-authored visible text run to exactly one listed item with
`data-copy-id`. Text already present in the prototype with
`data-copy-scope="template-fixed"` is inherited Layout/Master content: preserve
its text, attributes, position, and root-level atom identity exactly and do not
give it a page `data-copy-id`. Put the
attribute on one `<text>` element or one containing `<g>` and split wrapping or
emphasis only into descendants of that bound element. Do not nest bindings,
repeat an ID, expose an unbound text run, or render Build-only text. Optional
system copy may be omitted but must match exactly when used.

Keep every intended PowerPoint text box as one SVG `<text>`. For wrapped lines,
use direct `<tspan>` children with the parent x and either consistent absolute
`y` baselines or consistent positive relative `dy` steps. Use nested or
unpositioned tspans only for inline emphasis. Do not author one logical text
box as sibling `<text>` elements.

Write exactly one complete SVG at the requested path with
`viewBox="0 0 1280 720"`. Keep it self-contained. Use presentation attributes
or element-local `style="..."`; do not use `<style>`, class-dependent styling,
external URLs, `@import`, `xml-stylesheet`, `foreignObject`, or runtime asset
placeholders. An inert `class` used only as metadata is not a CSS dependency,
but prefer stable `id` and `data-*` attributes for authoring semantics.

For B on a `Standard` page, start independently from the same packet. Do not repair or polish A.
Compare only after drafting to confirm the same approved meaning and at least
one material design difference. For a revision, change only the recorded
targets from the supplied base. If the resulting revision is byte-identical to
its base, report it normally; the controller records a non-blocking advisory.

Perform one normal authoring check for exact-copy bindings, typography-scale
and content-frame fit, legibility, clipping, overlap, missing content, canvas,
self-containment, and CSS-free export readiness. Fix detected issues once, then
return exactly one terminal JSON object:

```json
{"status":"COMPLETE","route":"page-svg-authoring","artifact_path":"/absolute/path/to/S01/A.svg"}
```

B should also include a non-empty `material_differences` string array. This field
does not apply to the only A candidate of a `Simplified` page. Missing or empty
A/B difference evidence is recorded as a non-blocking advisory, not an authoring
failure. On a terminal block, return `stage`, `slide_ids`, `reason`,
`repair_scope`, and `resume_from`; do not ask the user a question inside this
bounded action.

The controller performs the deterministic static/copy/typography portion again
when it records `COMPLETE`, then binds that PASS to the artifact and copy-contract
hashes. Later page-level gates reuse that evidence while those hashes remain
unchanged. This does not replace the browser-rendered visible-copy gate or the
independent confirmed-export compatibility gate.
