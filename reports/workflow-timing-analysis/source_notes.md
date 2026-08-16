# Workflow timing analysis — source notes

## Decision frame

- Question: where the six-page AI Summit deck workflow spends execution time, and which changes can reduce it without adding user-visible workflow complexity or changing embedded PPT Master design.
- Audience: workflow and deck-production stakeholders.
- Source: `WORKFLOW_BUGS.md`, supplied by the user.
- Human review and approval waiting time is excluded by the source document.

## Timing interpretation

- Plain and `~` values are treated as the stated approximate duration.
- `<0.1s` is modeled as a 0–0.1 second range with a 0.05 second midpoint.
- Compound entries such as `0.1s + <0.1s edit` are summed component-wise.
- Total observed execution time is therefore 122.6–123.1 seconds, midpoint 122.85 seconds.

## Reconciliation checks

- Page/phase midpoint totals: 8.00 + 4.60 + 29.65 + 19.80 + 24.40 + 23.50 + 9.70 + 3.20 = 122.85 seconds.
- Activity midpoint totals: 67.60 + 31.10 + 9.90 + 3.20 + 3.00 + 2.30 + 1.80 + 1.55 + 1.30 + 0.60 + 0.50 = 122.85 seconds.
- Rendering/visual QA and research/source access total 98.70 seconds, or 80.34% of the midpoint total.
- Revision QA time caused by user-requested redesigns is retained as normal work, not classified as removable waste.

## Savings model

The savings figures are scenario estimates, not measured benchmarks.

- Stable preview defaults: 18–25 seconds. Basis: eliminate repeated Chromium cache/paint investigation and known mixed-`tspan` rollback loops while retaining one final full-slide render.
- Batched source retrieval: 8–12 seconds. Basis: submit independent official-source searches/fetches concurrently and use one bounded retry policy; source-quality requirements remain unchanged.
- Master/reference memoization: 1–2 seconds. Basis: reuse unchanged authoring references and prototype inspection keyed by template/prototype hash.
- Controller/service coalescing: 1–2 seconds. Basis: combine adjacent existing reads/validations without adding a workflow state or approval gate.
- Single-primary-candidate default: additional 8–14 seconds after allowing for overlap with preview stabilization. This is optional because it reduces choice breadth; A/B remains available when the page is conceptually ambiguous or the user asks for alternatives.

Core scenario excludes the candidate-strategy change: 28–41 seconds saved, leaving about 82–95 seconds (23–33% reduction). The streamlined-candidate scenario saves 36–55 seconds, leaving about 68–87 seconds (29–45% reduction).

## PPT Master protection boundary

- Do not remove or rewrite Master/Layout/placeholder metadata in confirmed SVGs.
- Any flat projection or normalization is temporary and used only for preview/export adapters.
- Cache entries must be invalidated by template/prototype hash.
- Keep one final full-slide render plus the existing PPTX postflight and SVG-text/PPTX-text parity audit.
- The `y=650` safe-area issue is a separate design concern and is not used as a timing optimization.

## Chart map

- Section: time concentration.
- Question: which activity families dominate machine execution time?
- Form: horizontal bar comparison.
- Fields: activity, midpoint seconds, low/high estimate, share, row count.
- Takeaway: rendering/visual QA and research/source access dominate the workflow.
- Palette: single-root yellow with neutral text; no redundant series legend.

## Report structure mapping

- Title: dedicated title block.
- Executive Summary: dedicated block immediately after title.
- Key findings: activity concentration chart and page/phase table.
- Recommended next steps: prioritized optimization narrative and estimate table.
- Further questions: validation plan section.
- Caveats and assumptions: final section.

## Validation assessment

Share with caveats. Arithmetic and category reconciliation pass, and recommendations preserve required Master protections. Savings remain directional because the source contains approximate wall-clock values from one six-page deck and does not expose per-render counts or repeated-run variance.
