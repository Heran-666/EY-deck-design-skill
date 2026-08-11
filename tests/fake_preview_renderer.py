#!/usr/bin/env python3
"""Deterministic renderer test double for workflow failure and binding tests."""

from __future__ import annotations

import argparse
import binascii
import json
import os
import struct
import sys
import zlib
from pathlib import Path


IDENTITY = {
    "renderer": "ey-deck-playwright-chromium",
    "renderer_version": "ey-deck-preview-renderer.v2/fake-test",
    "chromium_executable": str(Path(__file__).resolve()),
}


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", binascii.crc32(kind + data) & 0xFFFFFFFF
    )


def png(width: int, height: int, seed: int) -> bytes:
    color = bytes(((seed * 37) % 256, (seed * 67) % 256, (seed * 97) % 256, 255))
    scanline = b"\x00" + color * width
    raw = scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--request")
    args = parser.parse_args()
    if args.version:
        print(json.dumps(IDENTITY))
        return 0
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    fail_version = os.environ.get("EY_PREVIEW_RENDER_FAIL_VERSION")
    records = []
    for index, item in enumerate(request["items"], start=1):
        version = str(item["version"])
        if version == fail_version:
            records.append({"version": version, "ok": False, "error": "injected renderer failure"})
            continue
        output = Path(item["output_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        html_seed = binascii.crc32(Path(item["html_path"]).read_bytes()) & 0xFFFFFFFF
        output.write_bytes(png(int(item["width"]), int(item["height"]), html_seed + index))
        records.append({
            "version": version,
            "ok": True,
            "output_path": str(output),
            "width": int(item["width"]),
            "height": int(item["height"]),
        })
    print(json.dumps({
        **IDENTITY,
        "browser_version": "Fake Chromium 1",
        "records": records,
    }))
    return 4 if any(not record["ok"] for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
