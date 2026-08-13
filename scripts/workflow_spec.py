#!/usr/bin/env python3
"""Single machine-readable workflow authority for EY deck projects."""

from __future__ import annotations


FRAMEWORK_VERSION = "2.6"
WORKFLOW_VERSION = "3.9"
READABLE_WORKFLOW_VERSIONS = {"3.8", WORKFLOW_VERSION}
PAGE_PREFLIGHT_GATE_SCHEMA = "ey-deck.page-preflight.v2"

REQUESTED_AUTHORING_MODES = {"Simplified", "Standard"}
PAGE_AUTHORING_MODES = {"Simplified", "Standard", "Not applicable"}
SIMPLIFIED_STANDARD_PAGE_TYPES = {"cover", "agenda", "section divider"}
LONG_DECK_CONTENT_THRESHOLD = 6

PAGE_STATES = {
    "Not started",
    "Content reviewing",
    "Content locked",
    "Awaiting SVG decision",
    "SVG confirmed",
    "Protected placeholder",
}

TERMINAL_STATES = {"SVG confirmed", "Protected placeholder"}

ACTION_EVENT = {
    "PRESENT_PAGE_REVIEW": "content-approved",
    "COLLECT_SVG_DECISION": "svg-confirmed",
    "COLLECT_REVISION_CONFIRMATION": "svg-confirmed",
}

MANAGED_START = "<!-- EY-DECK-DESIGN-WORKFLOW:START -->"
MANAGED_END = "<!-- EY-DECK-DESIGN-WORKFLOW:END -->"
LEGACY_MANAGED_START = "<!-- EY-PROPOSAL-WORKFLOW:START -->"
LEGACY_MANAGED_END = "<!-- EY-PROPOSAL-WORKFLOW:END -->"

EY_PAGE_AUTHORING_INSTRUCTION = (
    "Use EY Deck Design's bundled Page SVG Authoring contract. Create one complete candidate from "
    "the exact hash-bound locked page packet and its bound structured-template prototype at the supplied paths. "
    "Preserve the prototype's root Master/Layout identity, fixed atoms, and placeholder contract. "
    "Own placeholder content, concept, composition, construction, fit, and normal SVG quality; bind every page-authored visible text run to the packet's exact "
    "data-copy-id while preserving inherited template-fixed text exactly, emit only inline SVG attributes/styles with no <style> or class dependency, and "
    "do not initialize a project or enter PPTX export."
)

B_OPTION_KERNEL = (
    "B option kernel: design B independently from the same locked content, semantic Visual Direction, "
    "and EY page-authoring rules; do not optimize, critique, repair, or incrementally polish A. "
    "Use independent design judgment to produce a genuinely distinct realization while preserving all "
    "approved copy, data, sources, emphasis, semantic relationships, and fixed constraints. Compare "
    "with A only after drafting to confirm at least one material design difference and the same canvas."
)

PREPARE_AUTHORING_ACTIONS = {
    "PREPARE_SVG_A": "GENERATE_SVG_A",
    "PREPARE_SVG_B": "GENERATE_SVG_B",
    "PREPARE_SVG_REVISION": "GENERATE_SVG_REVISION",
}


def initial_authoring_mode(requested_mode: str, page_type: str) -> str:
    """Resolve the initial page mode from the project request and exact page type."""
    normalized_type = page_type.strip().lower()
    if normalized_type == "protected placeholder":
        return "Not applicable"
    if requested_mode == "Simplified" or normalized_type in SIMPLIFIED_STANDARD_PAGE_TYPES:
        return "Simplified"
    return "Standard"
