#!/usr/bin/env python3
"""Single machine-readable workflow authority for EY deck projects."""

from __future__ import annotations


FRAMEWORK_VERSION = "2.5"
WORKFLOW_VERSION = "3.7"
PAGE_PREFLIGHT_GATE_SCHEMA = "ey-deck.page-preflight.v1"

PAGE_STATES = {
    "Not started",
    "Content reviewing",
    "Content locked",
    "Awaiting SVG selection",
    "SVG confirmed",
    "Protected placeholder",
}

TERMINAL_STATES = {"SVG confirmed", "Protected placeholder"}

ACTION_EVENT = {
    "PRESENT_PAGE_REVIEW": "content-approved",
    "COLLECT_SVG_SELECTION": "svg-selected",
    "COLLECT_REVISION_CONFIRMATION": "svg-selected",
}
