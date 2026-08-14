# Roles and stage contracts

The controller leads workflow order and evidence. Embedded PPT Master leads
the complete visual-design and construction domain inside controller-bounded
actions. No role may silently absorb another role's decisions.

| Role | Owns | Must not own |
|---|---|---|
| User | storyline, content, A/B or revision confirmation | internal production mechanics |
| Controller | next action, state, paths, hashes, receipts, recovery | copywriting or subjective design |
| Content Lead | approved copy, data, sources, semantic Visual Direction | concrete composition or SVG geometry |
| Embedded PPT Master Design Lead | communication job, reading mode, primary claim, composition family, focal mechanism, information model, typography hierarchy, EY gesture, density, design rationale | SVG construction, copy changes, workflow state, user approval |
| Embedded PPT Master SVG Producer | faithful implementation of the persisted Design Decision in the bound template | silently redesigning the page or changing approved meaning |
| Embedded PPT Master / Independent Visual QA | one rendered candidate's hierarchy, composition fidelity, data story, and brand expression | authoring the candidate, editing while judging, or comparing A/B distinctness |
| Embedded PPT Master Export Runtime | isolated technical normalization, Master/Layout construction, conversion, package QA | reopening semantic or visual design without a reported blocking defect |

Within Stage 1, every authored candidate follows this order:

1. content lock;
2. design-context preparation;
3. persisted Design Decision by the Embedded PPT Master Design Lead;
4. SVG production by the Embedded PPT Master SVG Producer from that decision;
5. deterministic preflight;
6. independent single-candidate Visual QA;
7. mode-required user display and decision.

Embedded PPT Master is one internal subsystem with two isolated branches. Its
Stage 1 design branch leads subjective page design, page-local SVG construction,
and independent single-candidate review. Its Stage 2 runtime branch leads only
deterministic structured-template/export work and cannot silently reopen Stage
1 design. Normal execution does not invoke a separate `$ppt-master` skill.
