---
description: Internal confirmed-SVG roster to editable PPTX service used only through the EY adapter.
---

# SVG Deck to Editable PPTX Service

Accept only a hash-bound `ppt-master.svg-deck-pptx-request.v1` packet from
`ey-deck-design`. The parent owns page order, confirmed SVG identity, output
filename, lifecycle state, and receipts. This service owns final SVG technical
validation, native DrawingML conversion, package postflight, and conversion
trace production.

## Contract

1. Read only the request's ordered confirmed SVG roster from `svg_output/`.
2. Run the lockless final SVG quality gate in Quick Generate mode.
3. Reject high-confidence fragmented-paragraph warnings. Do not repair a
   confirmed SVG during export; return upstream to reopen that page.
4. Export with editable native DrawingML, flat structure, no speaker notes,
   an explicit `preserve` text-flow policy, and a conversion trace.
5. Require a passing package postflight report.
6. Verify every traced native SVG text carrier has exactly one corresponding
   PowerPoint text box on the same slide.

Never re-enter page design, rewrite copy, change page order, select another SVG
candidate, or mutate the confirmed SVG set inside this service.
