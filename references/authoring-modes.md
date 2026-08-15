# Page authoring modes

Use this reference to choose, initialize, interpret, change, or migrate page-level authoring modes.

## Selection and initialization

After confirming the deliverable type and before drafting the Storyline, ask once:

`这次希望采用简化版还是标准版制作流程？简化版每页生成一个方案供确认；标准版的封面、目录和分隔页生成一个方案，其余内容页生成 A/B 两个方案供选择。`

Record the answer as project-level `Requested authoring mode`. Materialize the effective `Authoring mode` on every Storyline page when creating `framework.md`:

| Requested mode | Page type | Effective `Authoring mode` |
|---|---|---|
| `Simplified` | every normal page | `Simplified` |
| `Standard` | `Cover`, `Agenda`, `Section divider` | `Simplified` |
| `Standard` | every other normal page | `Standard` |
| either | `Protected placeholder` | `Not applicable` |

Use exact `Page type` values. Do not infer structural pages from titles. Only
`Cover`, `Agenda`, `Section divider`, and `Protected placeholder` have special
mode behavior; any other precise non-empty page type is valid and is treated as
a normal content page unless the user explicitly changes its page mode.

Apply this mapping to every deliverable type. Cover, Agenda, and Section divider
pages always generate only A, regardless of the requested project mode. Agenda
binds the dedicated Agenda Layout; each numbered card contains exactly one
agenda-item label and no secondary supporting detail.

Use project mode only to initialize new pages. Treat each page's effective `Authoring mode` as the runtime authority for generation, display, decision evidence, recovery, and mode-specific audit rules.

## Mode-specific first decision

For `Simplified`:

1. Ask Embedded PPT Master to design, author, and internally review only version `A`.
2. Accept A through the controller's locked-copy and artifact boundary.
3. Show the preview without exposing an unnecessary option label.
4. Require explicit user confirmation of A or a targeted revision request.

For `Standard`:

1. Ask Embedded PPT Master to produce complete A and B candidates from the same locked packet.
2. Let PPT Master perform design, SVG construction, visual QA, and internal repair for each.
3. Accept both through the same controller interface boundary.
4. Show A and B together at equal scale.
5. Require explicit selection of A or B, or a targeted revision request.

Different A/B composition families remain useful creative guidance only.
Identical candidates or weak difference evidence are non-blocking advisories.

Set the page to `Awaiting SVG decision` after its required initial presentation. On confirmation or selection, copy the confirmed version to the canonical SVG, record the page mode and presentation evidence in the SVG decision receipt, and set `Confirmed version`.

Process pages strictly by Slide ID. The controller never groups later pages with
the first unfinished page. Show and confirm the current page in its effective
mode before advancing.

## Shared revision and QA rules

For either active mode, generate every targeted revision from its controller-bound Base. Show Base and Rn together at equal scale. Allow the user to retain that displayed Base, confirm that displayed Rn, or request another targeted revision based on Rn. Accept no version outside the current request-bound pair, and reuse the unchanged hash-bound acceptance, preview, and paired-presentation evidence when the Base is retained. Do not treat a revision comparison as a second creative option.

Keep the common quality baseline identical across modes: exact visible copy, data-copy bindings, typography scale, canvas and visibility, clipping and overlap, self-containment, rendered preview integrity, canonical hashes, confirmed export compatibility, PPTX package validity, and terminal-result integrity. Skip only B generation, A/B difference evidence, and A/B comparison for `Simplified` pages.

## Changes, insertion, and migration

Allow a page mode change before SVG authoring begins. If candidate, preview, decision, revision, or canonical evidence already exists, require a design reopen and archive the affected evidence before changing the mode.

Initialize an inserted page from `Requested authoring mode` plus its exact `Page type`. Preserve page modes during reorder. Recompute only when the page type changes or the user explicitly changes the page mode.

For legacy projects, default `Requested authoring mode` to `Standard`. Preserve completed pages as `Standard` when needed to retain their existing A/B decision evidence; initialize unfinished structural pages as `Simplified`, other unfinished pages as `Standard`, and protected pages as `Not applicable`.
