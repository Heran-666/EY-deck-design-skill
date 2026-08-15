#!/usr/bin/env python3
"""Single machine-readable workflow authority for EY deck projects."""

from __future__ import annotations


FRAMEWORK_VERSION = "2.7"
WORKFLOW_VERSION = "4.1"
READABLE_WORKFLOW_VERSIONS = {"3.8", "3.9", "4.0", WORKFLOW_VERSION}
STAGE1_ACCEPTANCE_SCHEMA = "ey-deck.stage1-acceptance.v1"

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

PPT_MASTER_STAGE1_INSTRUCTION = (
    "Act only as EY Deck Design's embedded PPT Master Stage 1 engine. From the exact hash-bound locked page packet, "
    "design, author, render, review, and internally repair one complete SVG candidate at the requested path. "
    "Own all subjective design decisions, page composition, information visualization, SVG construction, and visual QA. "
    "Do not expose or require the outer controller to record your internal design reasoning. Preserve approved meaning, "
    "copy, data, sources, template-fixed atoms, and the bound Master/Layout contract exactly. Bind every page-authored "
    "visible text run to the packet's data-copy-id, keep the SVG self-contained and export-compatible, and return COMPLETE "
    "only after the candidate is ready for user display. Return BLOCKED only for content, design, or environment failure; "
    "do not initialize a project, change workflow state, ask the user a question, or enter Stage 2."
)

B_OPTION_KERNEL = (
    "B option guidance (advisory, never a blocking gate): start from the same locked content and semantic "
    "Visual Direction without treating A as a repair target. A different suitable composition family or focal "
    "mechanism may improve the usefulness of the choice, but similarity to A never blocks authoring, Visual QA, "
    "presentation, or confirmation. Preserve all approved copy, data, sources, emphasis, semantic relationships, "
    "fixed constraints, and the same canvas."
)

PREPARE_PPT_MASTER_ACTIONS = {
    "PREPARE_PPT_MASTER_A": "RUN_PPT_MASTER_A",
    "PREPARE_PPT_MASTER_B": "RUN_PPT_MASTER_B",
    "PREPARE_PPT_MASTER_REVISION": "RUN_PPT_MASTER_REVISION",
}


def initial_authoring_mode(requested_mode: str, page_type: str) -> str:
    """Resolve the initial page mode from the project request and exact page type."""
    normalized_type = page_type.strip().lower()
    if normalized_type == "protected placeholder":
        return "Not applicable"
    if requested_mode == "Simplified" or normalized_type in SIMPLIFIED_STANDARD_PAGE_TYPES:
        return "Simplified"
    return "Standard"
