---
name: ppt-master-internal
description: Internal PPT Master runtime embedded in EY Deck Design. Not a discoverable or directly invocable skill.
metadata:
  version: "6.4.0-ey.1"
  copyright: "Copyright (c) 2025-2026 Hugo He"
  license: "MIT"
  official_repository: "https://github.com/hugohe3/ppt-master"
  sponsors:
    - "SPONSORS.md"
    - "SPONSORS_CN.md"
---

# PPT Master Internal Runtime

This package is not a standalone skill. Invoke it only through EY Deck Design
with a validated `ppt-master.page-svg-request.v4` page request and its
hash-bound `ey-deck.page-authoring-context.v6`, or a hash-bound
`ppt-master.svg-deck-pptx-request.v3` export request.

Upstream design/conversion baseline: PPT Master 6.4.0 (local installation,
2026-09-14). This is a selective embedded integration, not a full standalone
6.4.0 installation. EY service contracts override generic route procedures;
see [integration notes](UPSTREAM_INTEGRATION.md).

## Entry

1. Run `python3 scripts/attribution_guard.py` from this directory.
2. Read [`workflows/page-svg-service.md`](workflows/page-svg-service.md) for a
   page request or
   [`workflows/svg-deck-pptx-service.md`](workflows/svg-deck-pptx-service.md)
   for a deck export request.
3. Validate and execute the supplied request exactly as that service defines.

Do not expose this package as `$ppt-master`, route direct user requests here, or
initialize any top-level PPT Master workflow. The separately installed global
PPT Master skill remains the only user-visible `$ppt-master`.
