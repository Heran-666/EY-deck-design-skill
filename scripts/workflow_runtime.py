#!/usr/bin/env python3
"""Validated, project-bound runtimes for preview and isolated Stage 2 export."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from workflow_io import now, text_sha256, write_json


STAGE2_RUNTIME_SCHEMA = "ey-deck.stage2-runtime.v1"
REQUIRED_STAGE2_IMPORTS = ("PIL", "lxml", "pptx")


def stage2_runtime_path(project_dir: Path) -> Path:
    return project_dir / "working" / "receipts" / "stage2-runtime.json"


def _runtime_fingerprint(payload: dict) -> str:
    stable = {
        key: payload.get(key)
        for key in (
            "schema_version",
            "bundle_version",
            "bundled_python",
            "python_version",
            "imports",
        )
    }
    return text_sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True))


def _probe_python(python: Path) -> dict:
    code = (
        "import json, platform, PIL, lxml, pptx; "
        "print(json.dumps({'python_version': platform.python_version(), "
        "'imports': {'PIL': PIL.__version__, 'lxml': lxml.__version__, "
        "'pptx': pptx.__version__}}, sort_keys=True))"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ValueError(
            "bundled Python cannot import Pillow, lxml, and python-pptx: " + detail
        )
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"bundled Python returned invalid probe data: {result.stdout!r}") from exc
    imports = payload.get("imports")
    if (
        not isinstance(payload.get("python_version"), str)
        or not isinstance(imports, dict)
        or any(not isinstance(imports.get(name), str) or not imports.get(name) for name in REQUIRED_STAGE2_IMPORTS)
    ):
        raise ValueError(f"bundled Python probe is incomplete: {payload}")
    return payload


def discover_stage2_runtime(
    bundled_python: str | Path | None = None,
    bundle_version: str | None = None,
) -> dict:
    candidate = bundled_python or os.environ.get("EY_BUNDLED_PYTHON")
    if not candidate:
        raise ValueError(
            "Stage 2 bundled Python is unbound; call load_workspace_dependencies in the parent "
            "context, then rerun doctor with --bundled-python and --bundle-version"
        )
    python = Path(candidate).expanduser().resolve()
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"Stage 2 bundled Python is not executable: {python}")
    probe = _probe_python(python)
    payload = {
        "schema_version": STAGE2_RUNTIME_SCHEMA,
        "bundle_version": (bundle_version or os.environ.get("EY_BUNDLE_VERSION") or "unknown").strip(),
        "bundled_python": str(python),
        "python_version": probe["python_version"],
        "imports": probe["imports"],
        "validated_at": now(),
    }
    payload["runtime_fingerprint"] = _runtime_fingerprint(payload)
    return payload


def validate_stage2_runtime(payload: dict, *, reprobe: bool = True) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != STAGE2_RUNTIME_SCHEMA:
        errors.append("Stage 2 runtime has the wrong schema version")
    python = Path(str(payload.get("bundled_python", ""))).expanduser()
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK):
        errors.append(f"Stage 2 bundled Python is missing or not executable: {python}")
    imports = payload.get("imports")
    if not isinstance(imports, dict) or any(not imports.get(name) for name in REQUIRED_STAGE2_IMPORTS):
        errors.append("Stage 2 runtime is missing validated dependency versions")
    if payload.get("runtime_fingerprint") != _runtime_fingerprint(payload):
        errors.append("Stage 2 runtime fingerprint is stale")
    if not errors and reprobe:
        try:
            current = _probe_python(python)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if current.get("python_version") != payload.get("python_version"):
                errors.append("Stage 2 bundled Python version changed")
            if current.get("imports") != payload.get("imports"):
                errors.append("Stage 2 bundled dependency versions changed")
    return errors


def bind_stage2_runtime(
    project_dir: Path,
    bundled_python: str | Path | None = None,
    bundle_version: str | None = None,
) -> dict:
    payload = discover_stage2_runtime(bundled_python, bundle_version)
    write_json(stage2_runtime_path(project_dir), payload)
    return payload

