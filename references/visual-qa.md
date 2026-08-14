# Independent Visual QA

Use this contract only when the controller emits `REVIEW_VISUAL_QA`. Inspect
the supplied PNG at full-slide scale, then verify it against the candidate's
persisted Design Decision. This is a separate review pass: do not edit the SVG
while judging it.

This role belongs to Embedded PPT Master's design branch but remains
independent from its Design Lead and SVG Producer. Membership in the same
subsystem never authorizes self-approval or cross-candidate comparison.

Review only the named candidate:

- `composition_fidelity`: the rendered page realizes the committed visual thesis and feels intentionally composed;
- `focal_hierarchy`: the primary claim is unmistakable, with a clear second and supporting read;
- `data_story`: charts, diagrams, metrics, or tables truthfully reveal the approved relationship and remain legible;
- `brand_expression`: EY gesture, typography, contrast, imagery, and negative space feel controlled rather than decorative.

Do not compare A with B. Do not judge whether their composition families or
focal mechanisms differ. A/B distinction remains a non-blocking authoring
advisory outside this QA receipt.

Return exactly one object:

```json
{
  "status": "PASS",
  "route": "independent-visual-qa",
  "scope": "single-candidate-only",
  "composition_fidelity": "PASS",
  "focal_hierarchy": "PASS",
  "data_story": "PASS",
  "brand_expression": "PASS",
  "issue_codes": []
}
```

Use `BLOCKED` for status and the affected dimensions when a visible defect
must be repaired before user display. Supply only matching single-candidate
issue codes: `composition-fidelity`, `focal-hierarchy`, `data-story`, or
`brand-expression`. Do not submit free-text issues; the controller generates a
fixed single-candidate repair statement from each code. Cross-candidate, A/B,
or Base/Revision comparisons have no accepted field in this contract. The
controller binds the receipt to the candidate SVG, preview, Design Decision,
and their hashes.
