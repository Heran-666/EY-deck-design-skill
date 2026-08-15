# SVG candidate workflow

## State machine

```text
Content locked
  -> prepare A + B requests
  -> generate and record A + B
  -> present A/B
  -> confirm either, or request R1 from a displayed base
  -> present Base/R1
  -> confirm either, or request R2 from a displayed base
  -> repeat
  -> SVG confirmed
```

The controller owns transitions and receipts. PPT Master owns candidate design
and technical completion. The user owns selection, feedback, and confirmation.

## Candidate identity

- A and B bind the same exact approved page content and template prototype.
- A and B are independent solutions; neither is the other's base.
- Rn binds one displayed base by path and SHA-256 plus one non-empty feedback
  file. Never rewrite an earlier candidate in place.
- A candidate is usable only when its request, SVG, and receipt hashes agree.
- A presentation receipt binds the exact two SVG hashes the user saw.
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

## User interaction

Display both candidates at the same scale and label them with exact versions.
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
- Stale presentation -> present the current valid pair again.
- Stale confirmation -> run the emitted `reopen-svg` command; never repair the
  published file directly.
- Content change -> `reopen-content`; all downstream candidate evidence becomes
  invalid and is deleted before a fresh request.
