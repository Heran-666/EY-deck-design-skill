---
name: ppt-master-internal
description: Internal PPT Master runtime embedded in EY Deck Design. Not a discoverable or directly invocable skill.
metadata:
  version: "4.5.0"
  copyright: "Copyright (c) 2025-2026 Hugo He"
  license: "MIT"
  official_repository: "https://github.com/hugohe3/ppt-master"
  sponsors:
    - "SPONSORS.md"
    - "SPONSORS_CN.md"
---

# PPT Master Internal Runtime

This package is not a standalone skill. Invoke it only through EY Deck Design
with a validated `ppt-master.page-svg-request.v2` request.

## Entry

1. Run `python3 scripts/attribution_guard.py` from this directory.
2. Read [`workflows/page-svg-service.md`](workflows/page-svg-service.md).
3. Validate and execute the supplied request exactly as that service defines.

Do not expose this package as `$ppt-master`, route direct user requests here, or
initialize any top-level PPT Master workflow. The separately installed global
PPT Master skill remains the only user-visible `$ppt-master`.
