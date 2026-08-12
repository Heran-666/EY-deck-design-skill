from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
import sys

sys.path.insert(0, str(SCRIPTS))

from preview_renderer import ensure_preview_pair, png_dimensions  # noqa: E402
from workflow_copy_contract import visible_copy_contract  # noqa: E402


@unittest.skipUnless(
    os.environ.get("EY_RUN_BROWSER_PREVIEW_TESTS") == "1",
    "set EY_RUN_BROWSER_PREVIEW_TESTS=1 for the local Chromium smoke test",
)
class RealPreviewRendererTests(unittest.TestCase):
    def test_copy_gate_ignores_pretty_print_tspan_indentation(self) -> None:
        section = """## S01｜转向“持续 / hello world

### On-slide content
- Title: 转向“持续 / hello world
"""
        contract = visible_copy_contract(section, "S01")
        compact = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
<rect width="1280" height="720" fill="#000000"/>
<text data-copy-id="S01-title" x="80" y="100" fill="#FFFFFF" font-size="36"><tspan>转向</tspan><tspan>“持续 / hello</tspan> <tspan>world</tspan></text>
</svg>'''
        formatted = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
<rect width="1280" height="720" fill="#000000"/>
<text data-copy-id="S01-title" x="80" y="100" fill="#FFFFFF" font-size="36">
  <tspan>转向</tspan>
  <tspan>“持续 / hello</tspan> <tspan>world</tspan>
</text>
</svg>'''
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            working = project / "svg_working" / "S01"
            working.mkdir(parents=True)
            (working / "A.svg").write_text(compact, encoding="utf-8")
            (working / "B.svg").write_text(formatted, encoding="utf-8")
            records = ensure_preview_pair(
                project,
                "S01",
                ("A", "B"),
                copy_contract=contract,
            )
            for version in ("A", "B"):
                self.assertEqual(records[version]["visible_copy_status"], "PASS")

    def test_playwright_chromium_renders_text_and_embedded_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            working = project / "svg_working" / "S01"
            working.mkdir(parents=True)
            image_uri = (
                "data:image/png;base64,"
                + base64.b64encode(base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                )).decode("ascii")
            )
            base = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
<rect width="1280" height="720" fill="#000000"/>
<text x="80" y="100" fill="#FFFFFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="36">浏览器预览 Browser preview</text>
<image href="{image_uri}" x="200" y="150" width="320" height="180" preserveAspectRatio="xMidYMid meet"/>
<rect x="80" y="400" width="520" height="120" fill="COLOR"/>
</svg>'''
            (working / "A.svg").write_text(base.replace("COLOR", "#333333"), encoding="utf-8")
            (working / "B.svg").write_text(base.replace("COLOR", "#FFE600"), encoding="utf-8")
            records = ensure_preview_pair(
                project,
                "S01",
                ("A", "B"),
            )
            for version in ("A", "B"):
                png = project / records[version]["preview_png"]
                self.assertEqual(png_dimensions(png), (1280, 720))
                self.assertEqual(records[version]["renderer"], "ey-deck-playwright-chromium")
                self.assertTrue(records[version]["browser_version"])
                executable = Path(records[version]["chromium_executable"])
                self.assertTrue(executable.is_file())
                self.assertIn("chrome-headless-shell", executable.name)

            previous_node = os.environ.get("EY_PREVIEW_NODE")
            os.environ["EY_PREVIEW_NODE"] = "/missing/node-after-doctor"
            try:
                (working / "B.svg").write_text(
                    base.replace("COLOR", "#188CE5"), encoding="utf-8"
                )
                rebound = ensure_preview_pair(project, "S01", ("A", "B"))
            finally:
                if previous_node is None:
                    os.environ.pop("EY_PREVIEW_NODE", None)
                else:
                    os.environ["EY_PREVIEW_NODE"] = previous_node
            self.assertEqual(rebound["B"]["chromium_executable"], records["B"]["chromium_executable"])


if __name__ == "__main__":
    unittest.main()
