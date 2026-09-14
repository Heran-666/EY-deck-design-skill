"""Regression coverage for the native export's shared marker preflight."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if not sys.path or sys.path[0] != str(SCRIPTS_DIR):
    sys.path.insert(0, str(SCRIPTS_DIR))

from svg_to_pptx.pptx_package import cli  # noqa: E402


class PreflightComplete(Exception):
    """Stop after actual CLI preflight, before any export artifact is written."""


class ReleaseGraphicsScanTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.sources = self.project / 'svg_final'
        self.sources.mkdir()

    def svg(self, name: str, body: str) -> Path:
        path = self.sources / name
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            + body + '</svg>',
            encoding='utf-8',
        )
        return path

    def cli_args(self) -> list[str]:
        # Diagnostic input avoids unrelated release-report setup; it executes
        # the same default marker preflight without enabling native objects.
        return [str(self.project), '-s', 'final', '--primary-language', 'en']

    def test_cli_default_marker_preflight_parses_each_source_once(self) -> None:
        paths = [
            self.svg('01_first.svg', '<g id="plain" data-pptx-fallback-kind="placeholder"/>'),
            self.svg('02_second.svg', '<g id="native" data-pptx-fallback-kind="placeholder" data-pptx-replace-with="chart"/>'),
        ]
        original_bytes = [path.read_bytes() for path in paths]
        stderr = io.StringIO()
        with (
            patch.object(cli.ET, 'parse', wraps=ET.parse) as parse,
            patch.object(cli, 'datetime') as clock,
            redirect_stdout(io.StringIO()),
            redirect_stderr(stderr),
        ):
            clock.now.side_effect = PreflightComplete
            with self.assertRaises(PreflightComplete):
                cli.main(self.cli_args())
        self.assertEqual(len(paths), parse.call_count)
        self.assertEqual(paths, [Path(call.args[0]) for call in parse.call_args_list])
        output = stderr.getvalue()
        self.assertLess(output.index('01_first.svg: plain'), output.index('02_second.svg: native'))
        self.assertIn('plain (placeholder fallback)', output)
        self.assertIn('native (active native Chart/Table replacement)', output)
        self.assertEqual(original_bytes, [path.read_bytes() for path in paths])
        self.assertFalse((self.project / 'exports').exists())

    def test_cli_blocks_before_placeholder_warning_or_native_checks(self) -> None:
        self.svg('01_mixed.svg', '''
          <metadata id="ignored" data-pptx-fallback-kind="invalid"/>
          <g id="bad-first" data-pptx-fallback-kind="invalid"/>
          <g id="placeholder" data-pptx-fallback-kind="placeholder"/>
          <g data-name="bad-second" data-pptx-replace-with="invalid"/>
        ''')
        stderr = io.StringIO()
        with (
            patch.object(cli, 'datetime') as clock,
            patch.object(cli, '_native_object_projection_findings') as projection,
            patch.object(cli, '_native_object_fallbacks') as fallback,
            redirect_stdout(io.StringIO()),
            redirect_stderr(stderr),
        ):
            self.assertEqual(1, cli.main(self.cli_args()))
        clock.now.assert_not_called()
        projection.assert_not_called()
        fallback.assert_not_called()
        output = stderr.getvalue()
        self.assertIn("bad-first (invalid-status: unsupported data-pptx-fallback-kind value: 'invalid')", output)
        self.assertIn("bad-second (invalid-status: unsupported data-pptx-replace-with value: 'invalid')", output)
        self.assertLess(output.index('bad-first'), output.index('bad-second'))
        self.assertNotIn('ignored', output)
        self.assertNotIn('Warning: reconstruction-only', output)
        self.assertFalse((self.project / 'exports').exists())

    def test_findings_preserve_input_order_and_skip_unreadable_xml(self) -> None:
        first = self.svg('02_first.svg', '''
          <metadata id="ignored" data-pptx-fallback-kind="invalid"/>
          <g id="active" data-pptx-fallback-kind="placeholder" data-pptx-replace-with="table"/>
          <g data-name="named" data-pptx-fallback-kind="placeholder"/>
          <g data-pptx-fallback-kind="placeholder"/>
          <g id="invalid" data-pptx-fallback-kind="placeholder" data-pptx-replace-with="unsupported"/>
        ''')
        malformed = self.sources / 'malformed.svg'
        malformed.write_text('<svg>', encoding='utf-8')
        missing = self.sources / 'missing.svg'
        last = self.svg('01_last.svg', '''
          <g id="legacy" data-pptx-visual-status="placeholder" data-pptx-route-status="reconstruction-only"/>
        ''')
        paths = [first, malformed, missing, last]
        before = {p: p.read_bytes() for p in paths if p.exists()}
        with patch.object(cli.ET, 'parse', wraps=ET.parse) as parse:
            blocked, diagnostics = cli._release_graphics_findings(paths)
        self.assertEqual(len(paths), parse.call_count)
        self.assertEqual([
            ('02_first.svg', 'invalid', "invalid-status: unsupported data-pptx-replace-with value: 'unsupported'"),
        ], blocked)
        self.assertEqual([
            ('02_first.svg', 'active', True),
            ('02_first.svg', 'named', False),
            ('02_first.svg', '<unnamed>', False),
            ('01_last.svg', 'legacy', False),
        ], diagnostics)
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == '__main__':
    unittest.main()
