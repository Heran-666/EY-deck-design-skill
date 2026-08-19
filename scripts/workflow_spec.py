#!/usr/bin/env python3
"""Small machine-readable contract for the EY content workflow."""

from __future__ import annotations


FRAMEWORK_VERSION = "3.2"
WORKFLOW_VERSION = "8.1"
READABLE_FRAMEWORK_VERSIONS = {"3.1", FRAMEWORK_VERSION}
READABLE_WORKFLOW_VERSIONS = {"6.0", "7.0", "8.0", WORKFLOW_VERSION}

READING_MODES = frozenset({"text", "balanced", "presentation"})
PAGE_RHYTHMS = frozenset({"anchor", "dense", "breathing"})
DEFAULT_READING_MODE = "balanced"
DEFAULT_SUBSTANTIVE_PAGE_RHYTHM = "dense"
DEFAULT_STRUCTURAL_PAGE_RHYTHM = "anchor"

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


def reading_mode(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in READING_MODES else DEFAULT_READING_MODE


def page_rhythm(value: str, page_type: str) -> str:
    normalized = value.strip().lower()
    if is_substantive_page_type(page_type):
        return normalized if normalized in {"dense", "breathing"} else DEFAULT_SUBSTANTIVE_PAGE_RHYTHM
    return DEFAULT_STRUCTURAL_PAGE_RHYTHM
