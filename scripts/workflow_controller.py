#!/usr/bin/env python3
"""Stable public façade for the EY deck workflow authority.

The workflow remains a single authority through this entrypoint. Domain state,
directives, evidence, audits, transitions, and CLI dispatch live in cohesive
modules so importing or executing this file preserves the established contract.
"""

from __future__ import annotations

from pathlib import Path

# Re-export the established Python surface for callers and tests that imported
# helpers from workflow_controller before the implementation was decomposed.
from framework_lib import PageEntry, h2_section, line_fields, page_entries, replace_field
from preview_renderer import (  # noqa: F401
    PreviewError,
    ensure_preview_pair,
    ensure_preview_single,
    preview_paths,
    preview_runtime_errors,
    preview_runtime_path,
)
from svg_boundary import (  # noqa: F401
    candidate_errors,
    protected_candidate_errors,
    svg_canvas,
    svg_error,
)
from validate_deck_blueprint import (  # noqa: F401
    validate as validate_blueprint,
    validate_collection as validate_blueprint_collection,
)
from validate_framework import validate as validate_framework  # noqa: F401
from validate_terminal_result import validate_terminal_result  # noqa: F401
from workflow_audit import *  # noqa: F401,F403
from workflow_authoring import *  # noqa: F401,F403
from workflow_content import *  # noqa: F401,F403
from workflow_directives import *  # noqa: F401,F403
from workflow_doctor import export_runtime_binding, preview_failure_issue, run_doctor  # noqa: F401
from workflow_design import *  # noqa: F401,F403
from workflow_export import *  # noqa: F401,F403
from workflow_handoff import *  # noqa: F401,F403
from workflow_io import *  # noqa: F401,F403
from workflow_paths import *  # noqa: F401,F403
from workflow_preview_evidence import *  # noqa: F401,F403
from workflow_protected import *  # noqa: F401,F403
from workflow_runtime import *  # noqa: F401,F403
from workflow_spec import *  # noqa: F401,F403
from workflow_state import *  # noqa: F401,F403
from workflow_transitions import *  # noqa: F401,F403


def main() -> int:
    """Run the stable controller CLI from its canonical public path."""
    from workflow_cli import main as run_cli

    return run_cli(Path(__file__).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
