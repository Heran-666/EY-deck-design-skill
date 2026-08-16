# SVG candidate workflow

## State machine

```text
Content locked
  -> Cover / Agenda / Section divider / Ending: prepare, generate, and present A
  -> other authored pages: prepare, generate, and present A/B
  -> confirm one displayed version, or request R1 from a displayed base
  -> present Base/R1
  -> confirm one displayed version, or request R2 from a displayed base
  -> repeat
  -> SVG confirmed
```

The controller owns transitions and receipts. PPT Master owns candidate design
and technical completion. The user owns selection, feedback, and confirmation.

## Candidate identity

- Cover, Agenda, Section divider, and Ending bind only one initial candidate,
  A. Every other authored page binds independent A and B candidates to the same
  exact approved content and template prototype; neither is the other's base.
- Every request binds the same executive-grade `design_quality` floor. For each
  substantive page, derive one paired A/B search strategy from the approved
  content form, Narrative role, Audience outcome, and Storyline thesis. Bind
  distinct roles to A and B and require a material difference in communication
  model, information hierarchy, or composition/visualization. Treat both as
  complete solutions, not safe-versus-experimental tiers.
- Rn binds one displayed base by path and SHA-256 plus one non-empty feedback
  file. Never rewrite an earlier candidate in place.
- A candidate is usable only when its request, SVG, and receipt hashes agree.
- A presentation receipt binds the exact one or two SVG hashes the user saw.
- Confirmation accepts only a currently displayed version and copies its exact
  bytes to `svg_output/<Slide ID>.svg`.

Materialize one hash-bound page authoring context and one self-contained
template prototype per Slide ID. Put approved content, project/page context,
confirmed-page coherence inputs, design quality, template, and service contract
there once. Make A, B, and every Rn request contain only candidate-specific
identity, direction, artifact, base, feedback, and the page-context path/hash.

## PPT Master service

The page authoring context's `service_contract` is the authoritative child entrypoint. Service
composition does not limit design scope: PPT Master must perform its full
Strategist, specialist, template, Executor, and QA loop internally. It may use
chart, table, qualitative structure, imagery, icons, typography, semantic SVG,
and effects capabilities as the page requires.

Use previously confirmed SVGs and adjacent-page context to maintain deck-wide
coherence. Do not copy a previous composition merely for consistency.

For Content pages, use the complete 1280×720 canvas. Placeholder bounds exist
only for native PowerPoint structure and do not define a visual safe area;
there is no `y=650` limit, reserved footer band, or EY-logo overlap QA gate.

Treat the first authored SVG as an internal draft. Before any candidate becomes
visible, complete the request's ordered information-design, page-composition,
art-direction, full-slide review, and source-repair gate. Reject generic card
stacks, equal-column defaults, repeated rounded rectangles, or icons/effects
that substitute for information design. Add coherent icons at semantically
appropriate positions when they improve recognition, scanning, or visual
rhythm; omit them when they have no clear communication job. Re-render and
recheck after repair.

Treat a browser-only omission as a preview failure until a fresh, hash-keyed
HTTP render reproduces it. Do not simplify mixed-format text, remove imagery,
or reduce composition complexity solely to accommodate stale local-file paint.

## User interaction

Display every emitted candidate at review scale and label it with the exact
version. A structural initial review displays A alone; a content initial review
displays A/B; every revision review displays Base/Rn.
Do not recommend a winner unless the user asks. Translate natural-language
choices to the exact emitted command only when the intended displayed version
is unambiguous.

For revision, preserve the user's words in the emitted feedback file. After the
controller embeds them in the immutable Rn request, delete that transient file.
Do not silently
convert vague advice into a broad redesign; ask a concise question only when no
concrete executable change can be inferred.

## Recovery

- Invalid request -> regenerate it with `prepare-svg-candidates` or the owning
  revision command.
- Invalid or incomplete candidate -> repair the same requested artifact and run
  `record` again; it performs the final service `complete` check atomically.
- Stale presentation -> present the current valid candidate or pair again.
- Stale confirmation -> run the emitted `reopen-svg` command; never repair the
  published file directly.
- Content change -> `reopen-content`; all downstream candidate evidence becomes
  invalid and is deleted before a fresh request.
