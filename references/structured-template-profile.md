# Bundled structured template profile

EY Deck Design bundles `ey-gradient-dark-v1` as a current PPT Master structured
template profile. The controller chooses the Layout from the exact
`framework.md` Page type and binds its prototype path, prototype hash, profile
fingerprint, and placeholder-contract hash into every page-authoring packet.

| Page type | PowerPoint Master | PowerPoint Layout | Editable slots (`x y w h`, SVG px) |
|---|---|---|---|
| Cover | `EY Cover` | `EY Cover` | project type/core insight `80 280 350 20`; title `78 332 574 138`; subtitle `80 498 660 55` |
| Agenda | `EY Dark` | `EY Agenda` | title `48 50 1128 43`; composite agenda region `48 145 1152 510` |
| Section divider | `EY Dark` | `EY Section Divider` | section label `64 225 220 32`; title `64 296 716 124` |
| All other authored pages | `EY Dark` | `EY Content` | title `48 50 1128 43`; subtitle `48 93 1128 40`; composite content region `48 150 1168 500` |
| Fixed ending | `EY Dark` | `EY Ending` | none; Stage 2 appends the user-supplied full-slide design as one unchanged fixed image after all confirmed pages |

The Agenda Layout follows the supplied two-column numbered-card design. Balance
the current item count across the two columns; use four-left/three-right for
seven items. Each card contains only its number and one agenda-item label; do
not add a subtitle, description, or supporting-detail line. Agenda numbers are
not fixed Layout atoms: the visible-copy contract derives zero-padded numbers
from approved item order and page authoring exports each number and label as a
separate editable text box. The content Layout
reserves the lower band beginning at `y=650`; page-specific
content must not enter it. The template owns the background, frame, glow, EY
mark, and other fixed atoms. The EY mark is inherited fixed template content on
every authored page and must never be page-authored, rebound, moved, changed, or
deleted. Agenda, Section divider, and Content use the identical three-path EY
mark extracted from their supplied PPTX Master group, including its exact
position and proportions. The Cover template additionally owns the exact
vector-outline two-line fixed lockup `Shape the future` / `with confidence`
below its EY mark; do not retype or restyle it. The Cover Layout also owns the exact fixed tagline
`The better the question. The better the answer. The better the world works.`
at `x=51`, baseline `y=679`; it is not part of page-authored visible copy and
must not be changed or deleted. Page authoring owns only the visible content
inside the bound placeholders. The content-region placeholder uses PPT Master's
`object` proxy binding so the authored composition remains editable while the
Layout retains a single reusable content zone.

Use Display title (`53.3333` SVG px / 40 pt) only for the Cover and Section
divider title placeholders. The normal content title remains `32` SVG px / 24
pt. Other visible text uses the fixed scale in `design-system.md`.

The fixed ending page is not a Storyline page and never enters content review,
page authoring, A/B comparison, or revision. Preserve the user-supplied ending
template exactly, including all visible text, fields, spacing, background, and
brand treatment; never clean, mask, parameterize, or overlay any part of it.
Preserve its embedded full-slide PNG bytes during PPTX export; resizing or JPEG
re-encoding this fixed asset is forbidden.
Stage 2 appends its hash-bound prototype as the
final slide for both structured and flat mixed decks.

For a protected placeholder, the controller keeps the source SVG untouched and
Stage 2 uses the legacy flat structure for that mixed deck. On isolated Stage 2
working copies only, remove structured Master/Layout/layer/placeholder metadata
from every page before flat validation; retain the untouched source copy and
prove exact visible-text identity. All-authored decks
use structured export and receive two native Masters plus five reusable
Layouts. This fallback protects supplied material; it does not apply to normal
authored pages.

The profile is a structured reconstruction. Its cover frame, Agenda design,
and fixed ending page were refreshed from the user-supplied PPTX references;
it does not mutate those reference files.
