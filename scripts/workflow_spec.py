#!/usr/bin/env python3
"""Small machine-readable contract for the EY content workflow."""

from __future__ import annotations


FRAMEWORK_VERSION = "3.1"
WORKFLOW_VERSION = "7.0"
READABLE_WORKFLOW_VERSIONS = {"6.0", WORKFLOW_VERSION}

PAGE_STATES = {
    "Not started",
    "Content locked",
    "SVG confirmed",
    "Protected placeholder",
}

LEGACY_TRANSIENT_PAGE_STATES = {
    "Content reviewing",
    "Awaiting SVG decision",
}

READABLE_PAGE_STATES = PAGE_STATES | LEGACY_TRANSIENT_PAGE_STATES

TERMINAL_PAGE_STATES = {"SVG confirmed", "Protected placeholder"}

STRUCTURAL_PAGE_TYPES = frozenset(
    {
        "cover",
        "agenda",
        "section divider",
        "divider",
        "ending",
        "closing",
        "closing page",
        "protected placeholder",
    }
)


def normalize_page_type(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def is_substantive_page_type(value: str) -> bool:
    return normalize_page_type(value) not in STRUCTURAL_PAGE_TYPES
