#!/usr/bin/env python3
"""Small machine-readable contract for the EY content workflow."""

from __future__ import annotations


FRAMEWORK_VERSION = "3.1"
WORKFLOW_VERSION = "6.0"
READABLE_WORKFLOW_VERSIONS = {WORKFLOW_VERSION}

PAGE_STATES = {
    "Not started",
    "Content reviewing",
    "Content locked",
    "Awaiting SVG decision",
    "SVG confirmed",
    "Protected placeholder",
}

TERMINAL_PAGE_STATES = {"SVG confirmed", "Protected placeholder"}
