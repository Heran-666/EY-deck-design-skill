# SVG candidate workflow

## Lifecycle and authority

```text
Content locked -> author A -> present one SVG -> confirm or optimize -> SVG confirmed
```

The controller owns state, requests, receipts, presentation, and publication.
PPT Master owns design and technical completion. The user owns selection,
feedback, and confirmation.

## Candidate contract

- Deferred template pages never enter this workflow. A Cover, Agenda, or Section
  divider explicitly activated for custom design uses A only. Ending remains
  the approved fixed source and never enters SVG candidate design. Every
  substantive page also uses A only, regardless of content type or requests
  for alternatives. Generate no second initial option before user review.
- Persist `candidate_plan` in the hash-bound page context. PPT Master must
  follow it and may not add a gate or version.
- EY supplies one quality floor, not design direction or layout. PPT Master
  chooses the strongest single solution for A.
- Materialize one page context and one self-contained template prototype per
  Slide ID. The context holds approved content, project/page and confirmed-page
  context, candidate plan, design quality, template, and service contract.
  Candidate requests hold only identity, artifact, context path/hash, and, for
  revisions, base and feedback.
- Rn binds the one currently displayed SVG by path and SHA-256 plus non-empty
  user feedback. Never overwrite an earlier version. Present only the new Rn;
  keep prior versions as immutable history rather than concurrent options.
- A candidate is usable only when request, SVG, and receipt hashes agree.
  Presentation binds the exact displayed hashes. Confirmation accepts only a
  displayed version and copies its bytes to `svg_output/<Slide ID>.svg`.
- After re-entry or compaction, recover through the controller and reread the
  bound request and context; never reconstruct direction from chat memory.

## Authoring and QA

Enter through `service_contract` and run PPT Master's full Strategist,
specialist, template, Executor, and source-SVG completion loop. It may use
chart, table, qualitative structure, imagery, icons, typography, semantic SVG,
and effects as needed.

Use confirmed pages and adjacent-page context for coherence without copying
their compositions. Content pages may use the complete 1280×720 canvas;
placeholder bounds are PowerPoint metadata, not a safe area. There is no
`y=650` cap, reserved footer band, or EY-logo overlap gate.

Treat the first SVG as an internal draft. Complete information design,
composition, art direction, direct full-slide source-SVG review, repair, and
reinspection before presentation. Use icons only when they aid communication.
Do not use Chromium, Playwright, or another browser renderer for candidate QA.

## User interaction and recovery

- Present exactly one SVG at review scale with its exact version label. Wait for
  confirmation or concrete optimization feedback before generating anything
  else.
- Preserve revision feedback verbatim. Delete its transient file after the
  controller embeds it in the immutable request. Ask only when no executable
  change can be inferred.
- Invalid request: regenerate it through the owning prepare/revision command.
- Invalid candidate: repair the requested artifact and run `record` again.
- Stale presentation: present the current valid version(s) again.
- Stale confirmation: use the emitted `reopen-svg` command.
- Content change: use `reopen-content`; downstream candidate evidence is
  invalidated before a new cycle.
