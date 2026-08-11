#!/usr/bin/env python3
"""Environment preflight for preview rendering and EY's bundled Stage 2 export."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from preview_renderer import (
    PreviewError,
    bind_preview_runtime,
    discover_preview_runtime,
    ensure_preview_pair,
    preview_runtime_path,
)
from workflow_export import EXPORT_RUNNER
from workflow_io import sha256, text_sha256
from workflow_paths import export_root
from workflow_runtime import bind_stage2_runtime, stage2_runtime_path


def _issue(code: str, message: str, repair_scope: str = "environment") -> dict[str, str]:
    return {"code": code, "message": message, "repair_scope": repair_scope}


def preview_failure_issue(exc: Exception) -> dict[str, str]:
    detail = str(exc)
    sandbox_markers = (
        "bootstrap_check_in",
        "mach_port_rendezvous",
        "Permission denied (1100)",
    )
    if any(marker in detail for marker in sandbox_markers):
        return _issue(
            "PREVIEW_BROWSER_SANDBOX_BLOCKED",
            f"Chromium launch was blocked by the macOS sandbox. Details: {detail}",
        )
    copy_markers = (
        "visible-copy",
        "unbound visible SVG text",
        "missing required visible-copy id",
        "outside the preview canvas",
    )
    if any(marker in detail for marker in copy_markers):
        return _issue(
            "PREVIEW_VISIBLE_COPY_BLOCKED",
            f"Approved visible copy did not survive the rendered preview. Details: {detail}",
            repair_scope="source-svg",
        )
    return _issue(
        "PREVIEW_BROWSER_UNAVAILABLE",
        "Chromium headless-shell preview failed. Configure "
        f"EY_PREVIEW_CHROMIUM/EY_PREVIEW_NODE if needed. Details: {detail}",
    )


def export_runtime_binding() -> dict[str, str]:
    root = EXPORT_RUNNER.resolve().parent / "pptx_export_runtime"
    files = sorted(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    records = [
        {"path": str(path.relative_to(root)), "sha256": sha256(path)}
        for path in files
    ]
    return {
        "schema_version": "ey-deck.bundled-export-runtime.v1",
        "root": str(root),
        "runner_path": str(EXPORT_RUNNER.resolve()),
        "runner_sha256": sha256(EXPORT_RUNNER),
        "runtime_fingerprint": text_sha256(
            json.dumps(records, ensure_ascii=False, sort_keys=True)
        ),
    }


def _preview_smoke_test(runtime: dict) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="ey-deck-doctor-") as tmp:
        project = Path(tmp)
        working = project / "svg_working" / "S01"
        working.mkdir(parents=True)
        base = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
<rect width="1280" height="720" fill="COLOR"/>
<text x="80" y="120" fill="#FFFFFF" font-size="36">EY preview doctor</text>
</svg>'''
        (working / "A.svg").write_text(base.replace("COLOR", "#000000"), encoding="utf-8")
        (working / "B.svg").write_text(base.replace("COLOR", "#333333"), encoding="utf-8")
        records = ensure_preview_pair(project, "S01", ("A", "B"), runtime=runtime)
        return {
            "renderer": str(records["A"]["renderer"]),
            "renderer_version": str(records["A"]["renderer_version"]),
            "browser_version": str(records["A"].get("browser_version", "unknown")),
            "chromium_executable": str(records["A"]["chromium_executable"]),
        }


def run_doctor(
    project_dir: Path,
    bundled_python: str | Path | None = None,
    bundle_version: str | None = None,
) -> tuple[dict, list[dict[str, str]], list[str]]:
    checks: dict[str, object] = {}
    errors: list[dict[str, str]] = []
    warnings: list[str] = []

    try:
        binding = export_runtime_binding()
        if not Path(binding["runner_path"]).is_file():
            raise ValueError("EY confirmed-export runner is missing")
        checks["ey_export_runtime"] = binding
    except (OSError, ValueError) as exc:
        errors.append(_issue("EXPORT_RUNTIME_INVALID", str(exc)))

    try:
        runtime = bind_stage2_runtime(project_dir, bundled_python, bundle_version)
        checks["stage2_runtime"] = runtime
        checks["stage2_runtime_receipt"] = {
            "path": str(stage2_runtime_path(project_dir).resolve()),
            "sha256": sha256(stage2_runtime_path(project_dir)),
        }
    except (OSError, ValueError) as exc:
        errors.append(_issue("STAGE2_RUNTIME_INVALID", str(exc)))

    try:
        root = export_root(project_dir)
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, prefix=".doctor-", delete=True):
            pass
        checks["export_root"] = str(root)
    except OSError as exc:
        errors.append(_issue("EXPORT_ROOT_NOT_WRITABLE", f"export root is not writable: {exc}"))
    except ValueError as exc:
        errors.append(_issue("EXPORT_ROOT_INVALID", str(exc)))

    try:
        preview_runtime = discover_preview_runtime()
        checks["preview"] = _preview_smoke_test(preview_runtime)
        bind_preview_runtime(project_dir, preview_runtime)
        checks["preview_runtime_receipt"] = {
            "path": str(preview_runtime_path(project_dir).resolve()),
            "sha256": sha256(preview_runtime_path(project_dir)),
        }
    except (OSError, PreviewError, ValueError) as exc:
        errors.append(preview_failure_issue(exc))

    warnings.append(
        "Doctor binds EY's bundled deterministic Stage 2 runtime and preview runtime for this project."
    )
    return checks, errors, warnings
