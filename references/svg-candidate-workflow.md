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
- Every request binds the same executive-grade `design_quality` floor. A binds
  the clarity-led editorial search direction; B binds the concept-led spatial
  direction. Treat both as complete solutions, not safe-versus-experimental tiers.
- Rn binds one displayed base by path and SHA-256 plus one non-empty feedback
  file. Never rewrite an earlier candidate in place.
- A candidate is usable only when its request, SVG, and receipt hashes agree.
- A presentation receipt binds the exact one or two SVG hashes the user saw.
- Confirmation accepts only a currently displayed version and copies its exact
  bytes to `svg_output/<Slide ID>.svg`.

## PPT Master service

The request's `service_contract` is the authoritative child entrypoint. Service
composition does not limit design scope: PPT Master must perform its full
Strategist, specialist, template, Executor, and QA loop internally. It may use
chart, table, qualitative structure, imagery, icons, typography, semantic SVG,
and effects capabilities as the page requires.

Use previously confirmed SVGs and adjacent-page context to maintain deck-wide
coherence. Do not copy a previous composition merely for consistency.

Treat the first authored SVG as an internal draft. Before any candidate becomes
visible, complete the request's ordered information-design, page-composition,
art-direction, full-slide review, and source-repair gate. Reject generic card
stacks, equal-column defaults, repeated rounded rectangles, or icons/effects
that substitute for information design. Add coherent icons at semantically
appropriate positions when they improve recognition, scanning, or visual
rhythm; omit them when they have no clear communication job. Re-render and
recheck after repair.

## User interaction

Display every emitted candidate at review scale and label it with the exact
version. A structural initial review displays A alone; a content initial review
displays A/B; every revision review displays Base/Rn.
Do not recommend a winner unless the user asks. Translate natural-language
choices to the exact emitted command only when the intended displayed version
is unambiguous.

For revision, preserve the user's words in the feedback file. Do not silently
convert vague advice into a broad redesign; ask a concise question only when no
concrete executable change can be inferred.

## Recovery

- Invalid request -> regenerate it with `prepare-svg-candidates` or the owning
  revision command.
- Invalid or incomplete candidate -> repair the same requested artifact, rerun
  the service `complete` check, and record it again.
- Stale presentation -> present the current valid candidate or pair again.
- Stale confirmation -> run the emitted `reopen-svg` command; never repair the
  published file directly.
- Content change -> `reopen-content`; all downstream candidate evidence becomes
  invalid and is deleted before a fresh request.
