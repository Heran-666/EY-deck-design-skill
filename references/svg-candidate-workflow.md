# SVG candidate workflow

## State machine

```text
Content locked
  -> EY controller writes adaptive candidate_plan
  -> structural/default page: prepare, generate, and present A
  -> verified dual-design need: prepare, generate, and present A/B
  -> confirm one displayed version, or request R1 from a displayed base
  -> present Base/R1
  -> confirm one displayed version, or request R2 from a displayed base
  -> repeat
  -> SVG confirmed
```

The controller owns transitions and receipts. PPT Master owns candidate design
and technical completion. The user owns selection, feedback, and confirmation.

## Candidate identity

- Cover, Agenda, Section divider, and Ending bind only A. Substantive pages also
  default to A. The EY controller upgrades the plan to A/B only when locked
  content exposes chart/table evidence, explicit comparison or hierarchy, a
  high-stakes selection, or `Confirmed decisions` explicitly requests alternatives.
  An explicit single-candidate decision wins over automatic triggers.
- Persist the decision as `candidate_plan` in the shared hash-bound page context.
  Do not add a user gate and do not let PPT Master change the plan.
- Every request binds the same executive-grade `design_quality` floor. When the
  plan is A/B, derive one paired search strategy from the approved content form,
  Narrative role, Audience outcome, and Storyline thesis. Bind distinct roles to
  A and B and require a material difference in communication model, information
  hierarchy, or composition/visualization. Treat both as complete solutions,
  not safe-versus-experimental tiers. For an A-only plan, bind one complete
  direction without a fictitious counterpart contract.
- Rn binds one displayed base by path and SHA-256 plus one non-empty feedback
  file. Never rewrite an earlier candidate in place.
- A candidate is usable only when its request, SVG, and receipt hashes agree.
- A presentation receipt binds the exact one or two SVG hashes the user saw.
- Confirmation accepts only a currently displayed version and copies its exact
  bytes to `svg_output/<Slide ID>.svg`.

Materialize one hash-bound page authoring context and one self-contained
template prototype per Slide ID. Put approved content, project/page context,
confirmed-page coherence inputs, candidate plan, design quality, template, and service contract
there once. Make A, B, and every Rn request contain only candidate-specific
identity, direction, artifact, base, feedback, and the page-context path/hash.

## PPT Master service

The page authoring context's `service_contract` is the authoritative child entrypoint. Service
composition does not limit design scope: PPT Master must perform its full
Strategist, specialist, template, Executor, and source-SVG completion loop internally. It may use
chart, table, qualitative structure, imagery, icons, typography, semantic SVG,
and effects capabilities as the page requires.

Use previously confirmed SVGs and adjacent-page context to maintain deck-wide
coherence. Do not copy a previous composition merely for consistency.

For Content pages, use the complete 1280×720 canvas. Placeholder bounds exist
only for native PowerPoint structure and do not define a visual safe area;
there is no `y=650` limit, reserved footer band, or EY-logo overlap QA gate.

Treat the first authored SVG as an internal draft. Before any candidate becomes
visible, complete the request's ordered information-design, page-composition,
art-direction, direct source-SVG full-slide review, and source-repair gate. Reject generic card
stacks, equal-column defaults, repeated rounded rectangles, or icons/effects
that substitute for information design. Add coherent icons at semantically
appropriate positions when they improve recognition, scanning, or visual
rhythm; omit them when they have no clear communication job. Reinspect the
source SVG after repair.

Do not invoke Chromium, Playwright, or another browser renderer to QA candidate
content or appearance. Browser output is not completion evidence and must not
block, simplify, or trigger repair of an otherwise valid source SVG.

## User interaction

Display every emitted candidate at review scale and label it with the exact
version. An A-only initial review displays A; an A/B initial review displays
both; every revision review displays Base/Rn.
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
