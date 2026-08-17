---
description: Internal ordered SVG/template roster to editable PPTX service used only through the EY adapter.
---

# SVG Deck to Editable PPTX Service

Accept only a hash-bound `ppt-master.svg-deck-pptx-request.v2` packet from
`ey-deck-design`. The parent owns page order, confirmed SVG and deferred-template
snapshot identity, output filename, lifecycle state, and receipts. This service
owns final SVG technical validation, native DrawingML conversion, package
postflight, and conversion trace production.

## Contract

1. Read only the request's ordered, hash-bound mixed slide roster. Accept
   confirmed authored SVGs and export-time structural template snapshots.
2. Run the lockless final SVG quality gate in Quick Generate mode.
3. Reject high-confidence fragmented-paragraph warnings. Do not repair a
   source during export; return upstream to reopen an authored page or repair a
   bundled structural template.
4. Export with editable native DrawingML, flat structure, no speaker notes,
   an explicit `reflow` text-flow policy, and a conversion trace. Positional
   rows used to lay out one paragraph must become automatic wrapping, not hard
   line breaks in the editable string.
5. Require a passing package postflight report.
6. Assign stable bridge-only ids to anonymous source text carriers. Require
   source carrier count = conversion text-event count = PowerPoint text box
   count on every slide.
7. Map each carrier id through the conversion trace to one PowerPoint shape and
   compare its OOXML character order, literal spaces, and semantic paragraphs.
   Reject synthetic hard line breaks. A failure returns the authored page to
   SVG reconfirmation; repair a deferred template upstream.

Never re-enter page design, rewrite copy, change page order, select another SVG
candidate, or mutate the ordered source set inside this service.
