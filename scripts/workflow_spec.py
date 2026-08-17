#!/usr/bin/env python3
"""Small machine-readable contract for the EY content workflow."""

from __future__ import annotations


FRAMEWORK_VERSION = "3.1"
WORKFLOW_VERSION = "8.0"
READABLE_WORKFLOW_VERSIONS = {"6.0", "7.0", WORKFLOW_VERSION}

PAGE_STATES = {
    "Not started",
    "Content locked",
    "SVG confirmed",
    "Deferred template",
    "Protected placeholder",
}

LEGACY_TRANSIENT_PAGE_STATES = {
    "Content reviewing",
    "Awaiting SVG decision",
}

READABLE_PAGE_STATES = PAGE_STATES | LEGACY_TRANSIENT_PAGE_STATES

TERMINAL_PAGE_STATES = {
    "SVG confirmed",
    "Deferred template",
    "Protected placeholder",
}

DEFERRED_TEMPLATE_PAGE_TYPES = frozenset(
    {
        "cover",
        "agenda",
        "section divider",
        "divider",
        "ending",
        "closing",
        "closing page",
    }
)

STRUCTURAL_PAGE_TYPES = frozenset(
    {*DEFERRED_TEMPLATE_PAGE_TYPES, "protected placeholder"}
)


def normalize_page_type(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def is_substantive_page_type(value: str) -> bool:
    return normalize_page_type(value) not in STRUCTURAL_PAGE_TYPES


def is_deferred_template_page_type(value: str) -> bool:
    return normalize_page_type(value) in DEFERRED_TEMPLATE_PAGE_TYPES
