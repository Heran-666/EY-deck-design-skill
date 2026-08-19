# SVG candidate workflow

## Lifecycle

```text
Content locked -> author A -> present -> confirm or revise -> SVG confirmed
```

The controller owns requests, hashes, decisions, state, and publication. PPT
Master owns design and technical completion. The user owns feedback and
confirmation.

## Candidate rules

- Deferred templates skip this workflow. Authored pages start with one A only.
- One hash-bound page context carries approved content, page logic, execution
  anchors, bounded consistency references, and the self-contained prototype.
- A request carries identity, artifact path, context binding, and, for Rn, the
  base SVG binding and exact feedback.
- Never overwrite a prior version. Present only the current version.
- `record` accepts only the exact request and artifact hashes returned by PPT
  Master's complete validation.
- Confirmation copies the current valid candidate to
  `svg_output/<Slide ID>.svg` and binds one artifact hash.

## Authoring

Follow the bound `service_contract`. Preserve approved meaning and page logic;
PPT Master may optimize expression. Use consistency references for coherence,
not composition copying. Keep build-only fields invisible.

Before presentation, complete information design, composition, art-direction
refinement, direct source-SVG review, repair, and recheck. Do not use a browser
renderer for candidate QA.

## Recovery

- Invalid request: regenerate it through the owning controller command.
- Invalid candidate: repair the requested artifact and run `record` again.
- On re-entry before a decision, present the current version again.
- Content change: use `reopen-content`.
- Visual restart without content change: use `reopen-svg`.
