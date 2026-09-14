"""Explicit review preferences and page-scoped authorization evidence."""

from __future__ import annotations

import difflib
import json
import re

from framework_lib import h2_section, line_fields, page_entries
from workflow_io import now, read_json, text_sha256, write_json
from workflow_paths import ProjectPaths


POLICY_SCHEMA = "ey-deck.review-policy.v1"
DEFAULT_PREFERENCES = {"language": "Chinese", "mode": "full"}
CONTENT_REVIEW_DISPLAY_MODE = "full-chinese-review"
_FULL_REVIEW_INSTRUCTION = (
    "Show the complete marked review in {language}, including all prose, headings, labels, "
    "Page logic, blocks, tables, chart descriptions, notes, emphasis and sources. Translate faithfully "
    "where needed; preserve IDs, schema keys/enums, numbers, units, dates, URLs, source identities, "
    "relationships, qualifiers and caveats. Keep translated labels and identifiers traceable. "
    "Do not summarize, omit any section or block, or substitute a file link. Review language does "
    "not change the deck Language or provisional/canonical content. Bind the decision to the full "
    "current source; if feedback changes meaning, update the source and run present-review again."
)
CONTENT_REVIEW_INSTRUCTION = _FULL_REVIEW_INSTRUCTION.format(language="Chinese")


def load_policy(paths: ProjectPaths) -> dict:
    if not paths.review_policy.is_file():
        return {"schema": POLICY_SCHEMA, **DEFAULT_PREFERENCES, "delegation": None}
    policy = read_json(paths.review_policy)
    if (policy.get("schema") != POLICY_SCHEMA
            or policy.get("language") not in {"Chinese", "English", "source"}
            or policy.get("mode") not in {"full", "changes"}):
        raise ValueError("invalid review policy")
    grant = policy.get("delegation")
    if grant is not None and (
        not isinstance(grant, dict)
        or not isinstance(grant.get("instruction"), str)
        or not grant["instruction"].strip()
        or not isinstance(grant.get("scopes"), dict)
        or not grant["scopes"]
        or not isinstance(grant.get("stages"), list)
        or not grant["stages"]
        or any(stage not in {"content", "svg"} for stage in grant["stages"])
    ):
        raise ValueError("invalid review delegation")
    return policy


def review_preferences(paths: ProjectPaths) -> dict:
    policy = load_policy(paths)
    return {key: policy[key] for key in DEFAULT_PREFERENCES}


def delegation_scope(text: str, slide_id: str) -> str:
    pages = page_entries(text)
    page = next((page for page in pages if page.slide_id == slide_id), None)
    if page is None:
        raise ValueError(f"unknown delegation page: {slide_id}")
    # Progress fields do not change scope. Titles do, except for the explicit
    # controller-owned synchronization after a valid content approval below.
    scope = {
        "project": line_fields(h2_section(text, "Project context")),
        "order": [page.slide_id for page in pages],
        "page": {key: value for key, value in page.fields.items()
                 if key not in {"Status", "Confirmed decisions", "Open items"}},
        "slide_id": slide_id,
        "title": page.title,
    }
    return text_sha256(json.dumps(scope, ensure_ascii=False, sort_keys=True))


def sync_approved_title(paths: ProjectPaths, before: str, after: str, slide_id: str) -> None:
    """Carry an unchanged grant through the controller's approved-title update."""
    policy = load_policy(paths)
    grant = policy.get("delegation")
    if grant and grant["scopes"].get(slide_id) == delegation_scope(before, slide_id):
        grant["scopes"][slide_id] = delegation_scope(after, slide_id)
        write_json(paths.review_policy, policy)


def set_policy(paths: ProjectPaths, text: str, *, instruction: str,
               language: str | None = None, mode: str | None = None,
               delegate_pages: str | None = None, delegate_stages: str | None = None,
               clear_delegation: bool = False) -> dict:
    if not instruction.strip():
        raise ValueError("review policy requires the exact non-empty user instruction")
    if all(value is None for value in (language, mode, delegate_pages, delegate_stages)) and not clear_delegation:
        raise ValueError("specify a review preference or delegation change")
    if (delegate_pages is None) != (delegate_stages is None):
        raise ValueError("delegation requires both pages and stages")
    if clear_delegation and delegate_pages is not None:
        raise ValueError("cannot grant and clear delegation together")
    policy = load_policy(paths)
    if language is not None:
        if language not in {"Chinese", "English", "source"}:
            raise ValueError("unsupported review language")
        policy["language"] = language
    if mode is not None:
        if mode not in {"full", "changes"}:
            raise ValueError("unsupported review mode")
        policy["mode"] = mode
    if language is not None or mode is not None:
        policy["review_instruction"] = instruction
    if delegate_pages is not None:
        pages = [value.strip() for value in delegate_pages.split(",")]
        stages = [value.strip() for value in delegate_stages.split(",")]
        if not pages or len(set(pages)) != len(pages):
            raise ValueError("delegation needs distinct page IDs")
        if not stages or len(set(stages)) != len(stages) or set(stages) - {"content", "svg"}:
            raise ValueError("delegation stages must be content and/or svg")
        known = {page.slide_id: page for page in page_entries(text)}
        for page_id in pages:
            if page_id not in known:
                raise ValueError(f"unknown delegation page: {page_id}")
            if known[page_id].fields.get("Status") in {"Deferred template", "Protected placeholder"}:
                raise ValueError(f"{page_id} has no authored review cycle to delegate")
        policy["delegation"] = {
            "instruction": instruction,
            "stages": stages,
            "scopes": {page_id: delegation_scope(text, page_id) for page_id in pages},
            "recorded_at": now(),
        }
    if clear_delegation:
        policy["delegation"] = None
        policy["revocation_instruction"] = instruction
    write_json(paths.review_policy, policy)
    return policy


def decision_policy(paths: ProjectPaths, text: str, slide_id: str, stage: str) -> dict:
    grant = load_policy(paths).get("delegation")
    if grant and stage in grant["stages"] and slide_id in grant["scopes"]:
        scope = delegation_scope(text, slide_id)
        if grant["scopes"][slide_id] == scope:
            return {
                "mode": "delegated", "instruction": grant["instruction"],
                "scope_sha256": scope,
                "authorization_sha256": text_sha256(json.dumps(grant, ensure_ascii=False, sort_keys=True)),
            }
        return {"mode": "manual", "reason": "authorized Storyline scope changed"}
    return {"mode": "manual"}


def decision_instruction(decision: dict, *, svg: bool = False) -> str:
    if decision["mode"] == "delegated":
        return ("Review the current artifact within the recorded delegation and continue through "
                "the emitted approval command without another user wait. Repair failures first; "
                "do not extend the authorized scope.")
    return ("Collect an explicit confirmation or optimization request for the displayed SVG."
            if svg else "Explicit semantic approval is required after the review is visible.")


def content_review_view(paths: ProjectPaths, slide_id: str, scope_hash: str, source: str) -> tuple[str, dict]:
    preferences = review_preferences(paths)
    language = preferences["language"]
    if language == "source":
        header = source + (paths.content.read_text(encoding="utf-8") if paths.content.is_file() else "")
        match = re.search(r"^- Language: (Chinese|English)\s*$", header, re.MULTILINE)
        if not match:
            raise ValueError("review language cannot be resolved from the deck build profile")
        language = match.group(1)
    try:
        previous = read_json(paths.content_review) if paths.content_review.is_file() else {}
    except ValueError:
        previous = {}
    baseline = previous.get("review_source")
    changes = (
        preferences["mode"] == "changes"
        and previous.get("slide_id") == slide_id
        and previous.get("review_scope_sha256") == scope_hash
        and isinstance(baseline, str)
        and text_sha256(baseline) == previous.get("provisional_sha256")
    )
    if changes:
        body = "\n".join(difflib.unified_diff(baseline.splitlines(), source.splitlines(),
                                            fromfile="previous review", tofile="current source", lineterm=""))
        body = body or "No content changes since the previous review."
        instruction = (
            f"Show every added, removed and changed passage faithfully in {language}, with enough "
            "context to assess meaning. Preserve IDs, figures, units, dates, sources and qualifiers. "
            "The unchanged content remains as previously reviewed; the decision binds the complete "
            "current source, never the diff alone. Keep the requested deck language unchanged."
        )
        display_mode = "changes-review"
    else:
        body = source.rstrip()
        instruction = _FULL_REVIEW_INSTRUCTION.format(language=language)
        display_mode = "full-chinese-review" if language == "Chinese" else "full-review"
    contract = {"display_mode": display_mode, "display_language": language, "instruction": instruction}
    if changes:
        contract["baseline_sha256"] = previous["provisional_sha256"]
    return body, contract
