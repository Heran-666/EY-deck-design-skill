#!/usr/bin/env python3
"""Project-local path policy for the EY deck workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Resolve workflow paths without leaking directory policy into services."""

    root: Path

    @property
    def framework(self) -> Path:
        return self.root / "framework.md"

    @property
    def content(self) -> Path:
        return self.root / "content.md"

    @property
    def working(self) -> Path:
        return self.root / "working"

    @property
    def provisional(self) -> Path:
        return self.working / "provisional-content.md"

    @property
    def content_review(self) -> Path:
        return self.working / "receipts" / "content-review.json"

    @property
    def svg_output(self) -> Path:
        return self.root / "svg_output"

    def svg_dir(self, slide_id: str) -> Path:
        return self.root / "svg_working" / slide_id

    def candidate(self, slide_id: str, version: str) -> Path:
        return self.svg_dir(slide_id) / f"{version}.svg"

    def packet(self, slide_id: str, version: str) -> Path:
        return self.working / "packets" / slide_id / f"{version}.json"

    def page_context(self, slide_id: str) -> Path:
        return self.working / "packets" / slide_id / "context.json"

    def template_prototype(self, slide_id: str) -> Path:
        return self.working / "template-prototypes" / slide_id / "prototype.svg"

    def candidate_receipt(self, slide_id: str, version: str) -> Path:
        return self.working / "receipts" / "svg" / slide_id / f"{version}.json"

    def presentation_receipt(self, slide_id: str) -> Path:
        return self.working / "receipts" / "svg" / slide_id / "presentation.json"

    def decision_receipt(self, slide_id: str) -> Path:
        return self.working / "receipts" / "svg" / slide_id / "decision.json"

    def revision_request(self, slide_id: str) -> Path:
        return self.working / "revision-requests" / f"{slide_id}.md"

    @property
    def pptx_request(self) -> Path:
        return self.working / "packets" / "pptx" / "export.json"

    @property
    def pptx_template_dir(self) -> Path:
        return self.working / "packets" / "pptx" / "templates"

    def pptx_template(self, slide_id: str) -> Path:
        return self.pptx_template_dir / f"{slide_id}.svg"

    @property
    def pptx_receipt(self) -> Path:
        return self.working / "receipts" / "pptx" / "export.json"

    @property
    def pptx_text_audit(self) -> Path:
        return self.working / "receipts" / "pptx" / "text-frames.json"

    @property
    def pptx_text_failure(self) -> Path:
        return self.working / "receipts" / "pptx" / "text-failure.json"

    @property
    def svg_quality_report(self) -> Path:
        return self.root / "validation" / "svg_quality_report.json"

    def pptx_output(self, filename: str) -> Path:
        return self.root / filename

    def pptx_postflight_report(self, filename: str) -> Path:
        return self.root / "validation" / f"{Path(filename).stem}.report.json"

    def pptx_conversion_trace(self, filename: str) -> Path:
        return self.root / "validation" / f"{Path(filename).stem}.trace.json"
