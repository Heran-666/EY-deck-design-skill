#!/usr/bin/env python3
"""Test-only executable that emulates the bundled dependency probe."""

from __future__ import annotations

import json
import os
import sys


if len(sys.argv) >= 3 and sys.argv[1] == "-c" and "import json, platform, PIL, lxml, pptx" in sys.argv[2]:
    print(json.dumps({
        "python_version": "3.test",
        "imports": {"PIL": "test", "lxml": "test", "pptx": "test"},
    }))
else:
    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
