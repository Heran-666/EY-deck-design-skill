#!/usr/bin/env python3
"""Enforce the bundled-Python boundary for Confirmed SVG Export."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path


REQUIRED_IMPORTS = {
    "PIL": "Pillow",
    "lxml.etree": "lxml",
    "pptx": "python-pptx",
}


def contains_local_dependencies(value: str) -> bool:
    return ".python-deps" in Path(value).parts


def same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return left.resolve() == right.resolve()


def validate(project_dir: Path, expected_python: Path) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    project = project_dir.resolve()
    expected = expected_python.resolve()
    running = Path(sys.executable).resolve()

    if not project.is_dir():
        errors.append(f"confirmed export project is missing: {project}")
    if not expected.is_file():
        errors.append(f"bundled Python is missing: {expected}")
    elif not same_file(running, expected):
        errors.append(f"running Python does not match bundled Python: {running} != {expected}")
    try:
        running.relative_to(project)
    except ValueError:
        pass
    else:
        errors.append("Python executable must be outside the isolated export project")

    if project.is_dir():
        local_dirs = sorted(path for path in project.rglob(".python-deps") if path.is_dir())
        errors.extend(f"forbidden project-local dependency directory: {path}" for path in local_dirs)

    active_local_paths = sorted({
        value for value in sys.path if value and contains_local_dependencies(value)
    })
    errors.extend(f"forbidden .python-deps entry in sys.path: {value}" for value in active_local_paths)
    pythonpath = os.environ.get("PYTHONPATH", "")
    active_pythonpath = sorted({
        value
        for value in pythonpath.split(os.pathsep)
        if value and contains_local_dependencies(value)
    })
    errors.extend(f"forbidden .python-deps entry in PYTHONPATH: {value}" for value in active_pythonpath)

    missing: list[str] = []
    for module_name, package_name in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)
    if missing:
        errors.append("bundled Python is missing required packages: " + ", ".join(missing))

    return errors, {
        "python_executable": str(running),
        "project_dir": str(project),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--expected-python", type=Path, required=True)
    args = parser.parse_args()

    errors, context = validate(args.project_dir, args.expected_python)
    payload = {
        "schema": "ppt-master.confirmed-export-runtime.v1",
        "status": "BLOCKED" if errors else "PASS",
        **context,
    }
    if errors:
        payload["errors"] = errors
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
