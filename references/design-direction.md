# Persisted Design Decision

Use this contract only when the controller emits `PLAN_PAGE_DESIGN`. The
Embedded PPT Master Design Lead reads the exact `design_context_path`, verifies
its hash, and confirms `design_owner: embedded-ppt-master-design` before acting.
That context contains approved content, semantic Visual Direction, the design
policy manifest, durable design principles, adjacent-page context, and recent
deck design memory.

Choose one coherent visual thesis before SVG construction. Prefer one dominant
mechanism over a collection of panels. Turn approved evidence into the
simplest truthful visual form. Use scale, contrast, asymmetry, crop, alignment,
and negative space to create a deliberate reading sequence. Select one
restrained EY gesture; do not decorate every block.

Return exactly one object:

```json
{
  "status": "COMPLETE",
  "route": "ppt-master-design-lead",
  "decision": {
    "communication_job": "what the audience should understand, decide, or do on this page",
    "reading_mode": "presentation, balanced, or reference",
    "primary_claim": "the single audience takeaway",
    "composition_family": "one family from the composition reference",
    "focal_mechanism": "the element or relationship that creates the first read",
    "information_model": "structure, chart, table, image, or claim-and-evidence",
    "data_encoding": "chart, diagram, metric, table, or none, with truthful rationale",
    "typography_hierarchy": "declared EY roles for first, second, and supporting reads",
    "ey_gesture": "one named restrained EY gesture",
    "density": "low, medium, or high",
    "rationale": "why this visual structure best expresses the approved meaning",
    "avoid": ["specific failure modes for this candidate"]
  }
}
```

The decision is an implementation brief, not visible copy. Do not include
coordinates or rewrite approved content. For Standard B, deck memory may help
create a useful alternative, but similarity to A is never a blocking error.
