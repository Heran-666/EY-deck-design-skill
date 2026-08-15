# Embedded PPT Master contract

Embedded PPT Master is EY Deck Design's complete visual-production engine. EY
Deck Design supplies locked content, candidate/version requirements, template
bindings, user revision requests, confirmed-page manifests, and required output
paths. PPT Master owns every visual and technical decision inside those bounds.

## Stage 1 — design and SVG candidate

When the controller emits `RUN_PPT_MASTER_A`, `RUN_PPT_MASTER_B`, or
`RUN_PPT_MASTER_REVISION`, read the supplied packet, verify its hash, and create
only the requested candidate at `requested_artifact`.

The current Codex task performs this bounded role directly. Stage 1 has no
separate runner, subagent, or global skill and creates no outer design state.

Internally perform the complete loop without exposing intermediate design state
to the outer controller:

1. Understand the communication job, audience reading task, approved hierarchy,
   semantic Visual Direction, adjacent-page context, and project constraints.
2. Choose a coherent page-scale composition and the clearest truthful editable
   information model. Simplicity applies to the semantic model, not to visual
   ambition or compositional craft.
3. Author the SVG from the bound structured-template prototype.
4. Render and inspect the candidate at full-slide scale.
5. Repair composition, hierarchy, legibility, data expression, brand treatment,
   fit, and export-readiness until the candidate is ready for user display.

Use [design-system.md](design-system.md) for EY visual and typography policy and
[structured-template-profile.md](structured-template-profile.md) for inherited
Master/Layout atoms and placeholder boundaries.

### Design authority

Own concept, composition, information visualization, imagery, typography-role
assignment, SVG geometry, grouping, wrapping, spacing, density, and visual QA.
Internal design notes or Design Decisions may be used when helpful, but they are
not controller state, public receipts, or external approval gates.

For B, create another complete solution from the same locked packet using any
visual approach; similarity to A is never a blocker. For Rn, preserve the bound
Base and change only the user's
targeted request; PPT Master may redesign internally when that is necessary to
fulfil the request without changing approved meaning.

### Content and template boundary

Preserve every approved word, number, source, emphasis, relationship, and fixed
constraint. Never invent or rewrite content. Bind every page-authored visible
text run to exactly one packet `data-copy-id`. Do not expose Build-only text.

Use the bound prototype as the literal starting SVG. Preserve root
`data-pptx-master*` and `data-pptx-layout*` identity, every root-level fixed atom
carrying `data-pptx-layer`, and every placeholder id/type/index/bounds. Content
marked `data-copy-scope="template-fixed"` is inherited and must remain exact and
unbound to page copy IDs. Keep authored elements attached to the editable
placeholder proxy required for export; its internal geometry and footprint do
not prescribe the composition. Agenda item numbers and labels remain separately
bound editable text.

### SVG and visual-quality boundary

Write one self-contained SVG with `viewBox="0 0 1280 720"`. Use presentation
attributes or element-local style only. Do not use `<style>`, external URLs,
`@import`, `xml-stylesheet`, `foreignObject`, or runtime placeholders.

Keep every intended PowerPoint text box as one `<text>` element. Wrap with direct
`<tspan>` children using consistent absolute `y` values or positive relative
`dy` steps; use nested tspans only for inline emphasis. Apply only the typography
scale defined in `design-system.md`.

Before returning COMPLETE, inspect the rendered page for exact copy, clipping,
overlap, off-canvas content, legibility, data truthfulness, fixed-template
integrity, and native-PPTX readiness. Repair
design or implementation defects internally. Return BLOCKED only when the
candidate cannot be completed without reopening locked content, restarting the
design request, or fixing the environment.

Return exactly one terminal object:

```json
{"status":"COMPLETE","route":"embedded-ppt-master-stage1","artifact_path":"/absolute/path/to/S01/A.svg"}
```

COMPLETE permits only `status`, `route`, `artifact_path`, and optional
`material_differences`. For B, a non-empty string array is recommended when the
differences are material; omitting it remains a non-blocking advisory.

BLOCKED permits exactly `status`, `route`, `stage`, `reason`, `repair_scope`,
`resume_from`, and `slide_ids`. `stage` and `resume_from` are concise non-empty
descriptions of the failed step and deterministic continuation point;
`repair_scope` is `content`, `design`, or `environment`. Use the active Slide ID
only and do not ask the user a question inside this bounded action:

```json
{"status":"BLOCKED","route":"embedded-ppt-master-stage1","stage":"SVG rendering","reason":"The bound preview runtime is unavailable.","repair_scope":"environment","resume_from":"Render the unchanged requested candidate after the runtime is restored.","slide_ids":["S01"]}
```

The outer controller checks only the interface boundary: requested artifact,
locked-copy identity, template integrity, candidate canvas, preview evidence,
and user decision. It does not inspect or approve PPT Master's internal design
reasoning.

## Stage 2 — editable PPTX

When the controller emits `RUN_PPT_MASTER_EXPORT`, run the supplied
`runner_command` exactly once. It is bound to the confirmed SVG manifest, staged
hashes, required output path, validated Python runtime, fixed Ending prototype,
template profile when applicable, and terminal validator.

Own isolated technical normalization, text-frame topology, exact-copy proof,
Master/Layout construction, SVG-to-native-PPTX conversion, transitions and
animations, package relationships, slide count, typography, compatibility, and
final artifact QA. Never mutate upstream confirmed SVGs or reopen subjective
design without a reported blocking source defect.

All-authored decks use structured export with the bound two-Master/five-Layout
profile. A deck containing a Protected placeholder uses flat export so protected
source bytes are not reauthored. Both append the fixed Ending prototype after
the confirmed Storyline pages. That Ending is export-only and is exempt from
Storyline, content, Stage 1, and candidate approval.

Return the runner's exact terminal JSON. COMPLETE permits only `status`, `route`,
and `artifact_path`; the path must equal the manifest output path:

```json
{"status":"COMPLETE","route":"embedded-ppt-master-stage2","artifact_path":"/absolute/path/to/output.pptx"}
```

BLOCKED permits exactly `status`, `route`, `stage`, `reason`, `repair_scope`,
`resume_from`, and `slide_ids`. Use a non-empty ordered subset of manifest Slide
IDs and a `repair_scope` of `source-svg`, `user-decision`, or `environment`:

```json
{"status":"BLOCKED","route":"embedded-ppt-master-stage2","stage":"native conversion","reason":"S03 contains unsupported confirmed SVG structure.","repair_scope":"source-svg","resume_from":"Reopen S03 and replace the incompatible SVG before rebuilding the export workspace.","slide_ids":["S03"]}
```

EY Deck Design records the result, routes a BLOCKED result, or delivers the
COMPLETE PPTX; it does not duplicate Stage 2's technical QA.
