# Review preferences and delegated decisions

Load this reference when the user changes review language, asks for difference
review, or delegates content/SVG decisions. Defaults remain **Chinese**, **full**,
and **manual per-page approval**. The controller still advances serially.

## Record the actual instruction

After framework initialization, use the controller-owned policy; never edit
`working/review-policy.json` by hand:

For example, when the user explicitly requests English review:

```bash
python3 <controller> set-review-policy --project-dir <dir> --language English --instruction '<exact user request>'
```

Include at least one requested setting; use only options supported by the instruction:

| Option | Effect |
|---|---|
| `--language Chinese\|English\|source` | Chat review language; `source` preserves source language |
| `--mode full\|changes` | Full page-content review or a difference view with a valid baseline |
| `--delegate-pages S02,S03 --delegate-stages content,svg` | Delegate only the listed pages and stages; both options are required together |
| `--clear-delegation` | Restore manual decisions while retaining display preferences; do not combine with a new delegation |

Omitted settings keep their existing values. Supply the actual, nonempty user
instruction, never a model-authored approval. Display preferences alone grant
no authority to approve. Before a framework exists, honor an explicit Storyline
review-language preference and carry it into this policy after initialization.
Storyline approval waivers are recorded separately under
[framework-contract.md](framework-contract.md).

## Display and source binding

Apply the effective language to Storyline and content review without changing
the deck language or source files. Storyline review remains complete by default;
the controller's `changes` mode applies to page-content review.

For `changes`, the controller requires an earlier complete source snapshot and
hash for the same page. A first review or missing/unverifiable baseline falls
back to `full`. Faithfully render or translate the emitted changes, preserving
IDs, additions, deletions, numbers, qualifiers, relationships, and source
identity. Approval always binds the **full current source hash**, never the diff
alone. Changing language or mode requires rerunning `present-review` for current
provisional content; do not reauthor the source just to change the review view.

## Approval authority

Use the decision directive's `decision_policy.mode`. For `manual`, obtain the user's
explicit decision on the current review. For `delegated`, perform the same
semantic or visual checks, then use the existing `approve-content` or
`confirm-svg` command within the recorded authorization without another wait.
Keep presenting review material under the selected display policy.

Delegation binds concrete page IDs and stages to their Storyline fields, titles,
project context, and page order. When that scope changes, the controller returns
to manual review. Only the controller's normal title synchronization after valid
content approval carries a still-current grant into the approved title. Prior
authorization persists only inside its scope;
silence, elapsed time, and permission on another page never extend it. Decision
receipts retain the authorization provenance. Delegation does not bypass
source/SVG hashes, validation, protected content, or export postflight.
