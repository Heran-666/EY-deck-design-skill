#!/usr/bin/env python3
"""Hash-bound browser PNG previews for EY single, A/B, and Rn messages."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
import zlib
from pathlib import Path
from xml.etree import ElementTree

from workflow_io import now as _now, read_json, sha256 as _sha256, write_json as _atomic_json
from workflow_copy_contract import copy_contract_errors, visible_copy_errors


RECEIPT_SCHEMA = "ey-deck.preview-binding.v3"
RUNTIME_SCHEMA = "ey-deck.preview-runtime.v2"
RENDERER_NAME = "ey-deck-playwright-chromium"
NODE_SCRIPT = Path(__file__).resolve().parent / "render_svg_preview.js"
RUNTIME_ENV_KEYS = (
    "EY_PREVIEW_RENDERER",
    "EY_PREVIEW_NODE",
    "EY_PREVIEW_NODE_PATH",
    "EY_PREVIEW_CHROMIUM",
    "NODE_PATH",
)


class PreviewError(ValueError):
    """A preview is stale, unreadable, or could not be rendered."""


def _read_json(path: Path) -> dict:
    try:
        payload = read_json(path)
    except ValueError as exc:
        raise PreviewError(f"invalid preview receipt {path}: {exc}") from exc
    return payload


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:px)?\s*", value)
    return float(match.group(1)) if match else None


def svg_canvas_pixels(path: Path) -> tuple[int, int]:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise PreviewError(f"cannot read SVG canvas {path}: {exc}") from exc
    view_box = root.get("viewBox")
    width: float | None = None
    height: float | None = None
    if view_box:
        parts = [item for item in re.split(r"[\s,]+", view_box.strip()) if item]
        if len(parts) != 4:
            raise PreviewError(f"invalid SVG viewBox in {path}: {view_box}")
        try:
            width, height = float(parts[2]), float(parts[3])
        except ValueError as exc:
            raise PreviewError(f"non-numeric SVG viewBox in {path}: {view_box}") from exc
    if width is None or height is None:
        width, height = _number(root.get("width")), _number(root.get("height"))
    if width is None or height is None or width <= 0 or height <= 0:
        raise PreviewError(f"SVG has no positive pixel canvas: {path}")
    rounded = round(width), round(height)
    if abs(width - rounded[0]) > 1e-6 or abs(height - rounded[1]) > 1e-6:
        raise PreviewError(f"SVG preview canvas must use integer pixels: {path} ({width}x{height})")
    return rounded


def png_dimensions(path: Path) -> tuple[int, int]:
    """Validate PNG chunks and compressed data, then return IHDR dimensions."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise PreviewError(f"cannot read preview PNG {path}: {exc}") from exc
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PreviewError(f"preview is not a PNG: {path}")
    offset = 8
    dimensions: tuple[int, int] | None = None
    idat = bytearray()
    saw_iend = False
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise PreviewError(f"truncated PNG chunk in {path}")
        data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length : end])[0]
        actual_crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise PreviewError(f"PNG checksum failed in {path}")
        if chunk_type == b"IHDR":
            if length != 13 or dimensions is not None:
                raise PreviewError(f"invalid PNG header in {path}")
            width, height = struct.unpack(">II", data[:8])
            dimensions = width, height
        elif chunk_type == b"IDAT":
            idat.extend(data)
        elif chunk_type == b"IEND":
            saw_iend = True
            break
        offset = end
    if dimensions is None or not saw_iend or not idat:
        raise PreviewError(f"incomplete PNG structure: {path}")
    try:
        if not zlib.decompress(bytes(idat)):
            raise zlib.error("empty image data")
    except zlib.error as exc:
        raise PreviewError(f"PNG image data is unreadable in {path}: {exc}") from exc
    if dimensions[0] <= 0 or dimensions[1] <= 0:
        raise PreviewError(f"PNG has invalid dimensions: {path}")
    return dimensions


def preview_dir(project_dir: Path, slide_id: str) -> Path:
    return project_dir / "svg_working" / slide_id / "preview"


def preview_runtime_path(project_dir: Path) -> Path:
    return project_dir / "working" / "receipts" / "preview-runtime.json"


def preview_paths(project_dir: Path, slide_id: str, version: str) -> tuple[Path, Path]:
    root = preview_dir(project_dir, slide_id)
    source = source_path(project_dir, slide_id, version)
    source_token = _sha256(source)[:16] if source.is_file() else "missing"
    return root / f"{version}-{source_token}.png", root / f"{version}.json"


def source_path(project_dir: Path, slide_id: str, version: str) -> Path:
    if not re.fullmatch(r"(?:A|B|R[1-9]\d*)", version):
        raise PreviewError(f"unsupported SVG preview version: {version}")
    return project_dir / "svg_working" / slide_id / f"{version}.svg"


def _node_runtime() -> tuple[list[str], dict[str, str]]:
    override = os.environ.get("EY_PREVIEW_RENDERER")
    if override:
        renderer = Path(override).expanduser().resolve()
        if not renderer.is_file():
            raise PreviewError(f"EY_PREVIEW_RENDERER does not exist: {renderer}")
        command = [sys.executable, str(renderer)] if renderer.suffix == ".py" else [str(renderer)]
        return command, os.environ.copy()

    candidates = [
        os.environ.get("EY_PREVIEW_NODE"),
        str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"),
        shutil.which("node"),
    ]
    node = next((Path(item).resolve() for item in candidates if item and Path(item).is_file()), None)
    if node is None:
        raise PreviewError("Node.js runtime for Playwright was not found; set EY_PREVIEW_NODE")
    env = os.environ.copy()
    if os.environ.get("EY_PREVIEW_NODE_PATH"):
        env["NODE_PATH"] = os.environ["EY_PREVIEW_NODE_PATH"]
    elif "NODE_PATH" not in env:
        bundled = node.parent.parent / "node_modules"
        if bundled.is_dir():
            env["NODE_PATH"] = str(bundled)
    return [str(node), str(NODE_SCRIPT)], env


def _renderer_identity(command: list[str], env: dict[str, str]) -> dict[str, str]:
    result = subprocess.run(
        [*command, "--version"], text=True, capture_output=True, check=False, env=env
    )
    if result.returncode != 0:
        raise PreviewError(
            "preview renderer is unavailable: "
            + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
        )
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise PreviewError(f"preview renderer returned invalid version data: {result.stdout!r}") from exc
    executable = Path(str(payload.get("chromium_executable", ""))).expanduser()
    if (
        payload.get("renderer") != RENDERER_NAME
        or not payload.get("renderer_version")
        or not executable.is_absolute()
        or not executable.is_file()
    ):
        raise PreviewError(f"unsupported preview renderer identity: {payload}")
    return {
        "renderer": str(payload["renderer"]),
        "renderer_version": str(payload["renderer_version"]),
        "chromium_executable": str(executable.resolve()),
    }


def discover_preview_runtime() -> dict:
    command, env = _node_runtime()
    identity = _renderer_identity(command, env)
    payload = {
        "schema_version": RUNTIME_SCHEMA,
        "command": command,
        "environment": {
            key: env[key]
            for key in RUNTIME_ENV_KEYS
            if key in env and env[key]
        },
        **identity,
        "created_at": _now(),
    }
    payload["runtime_fingerprint"] = hashlib.sha256(
        json.dumps(
            {key: payload[key] for key in ("schema_version", "command", "environment", "renderer", "renderer_version", "chromium_executable")},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return payload


def _runtime_command_env(runtime: dict) -> tuple[list[str], dict[str, str]]:
    command = runtime.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
        raise PreviewError("preview runtime command is missing")
    executable = Path(command[0]).expanduser()
    if not executable.is_absolute() or not executable.is_file():
        raise PreviewError(f"preview runtime executable is missing: {executable}")
    for item in command[1:]:
        candidate = Path(item).expanduser()
        if candidate.is_absolute() and candidate.suffix in {".js", ".py"} and not candidate.is_file():
            raise PreviewError(f"preview runtime script is missing: {candidate}")
    stored_env = runtime.get("environment")
    if not isinstance(stored_env, dict) or any(
        key not in RUNTIME_ENV_KEYS or not isinstance(value, str)
        for key, value in stored_env.items()
    ):
        raise PreviewError("preview runtime environment is invalid")
    env = os.environ.copy()
    for key in RUNTIME_ENV_KEYS:
        env.pop(key, None)
    env.update(stored_env)
    return command, env


def preview_runtime_errors(runtime: dict, *, verify_identity: bool = True) -> list[str]:
    errors: list[str] = []
    if runtime.get("schema_version") != RUNTIME_SCHEMA:
        errors.append("preview runtime has the wrong schema version")
    try:
        command, env = _runtime_command_env(runtime)
    except PreviewError as exc:
        errors.append(str(exc))
        return errors
    executable = Path(str(runtime.get("chromium_executable", ""))).expanduser()
    if not executable.is_absolute() or not executable.is_file():
        errors.append(f"preview Chromium executable is missing: {executable}")
    expected_fingerprint = hashlib.sha256(
        json.dumps(
            {key: runtime.get(key) for key in ("schema_version", "command", "environment", "renderer", "renderer_version", "chromium_executable")},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if runtime.get("runtime_fingerprint") != expected_fingerprint:
        errors.append("preview runtime fingerprint is stale")
    if verify_identity and not errors:
        try:
            identity = _renderer_identity(command, env)
        except PreviewError as exc:
            errors.append(str(exc))
        else:
            for key, value in identity.items():
                if runtime.get(key) != value:
                    errors.append(f"preview runtime {key} changed")
    return errors


def bind_preview_runtime(project_dir: Path, runtime: dict | None = None) -> dict:
    payload = runtime or discover_preview_runtime()
    errors = preview_runtime_errors(payload)
    if errors:
        raise PreviewError("; ".join(errors))
    _atomic_json(preview_runtime_path(project_dir), payload)
    return payload


def current_preview_runtime(project_dir: Path) -> dict:
    path = preview_runtime_path(project_dir)
    if path.is_file():
        runtime = _read_json(path)
        errors = preview_runtime_errors(runtime)
        if not errors:
            return runtime
    return bind_preview_runtime(project_dir)


def renderer_identity(runtime: dict | None = None) -> dict[str, str]:
    if runtime is None:
        runtime = discover_preview_runtime()
    command, env = _runtime_command_env(runtime)
    return _renderer_identity(command, env)


def _preview_html(source: Path, width: int, height: int) -> Path:
    svg_text = source.read_text(encoding="utf-8")
    html = f'''<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'">
<style>html,body{{margin:0;padding:0;width:{width}px;height:{height}px;overflow:hidden;background:#0E1116}}#stage{{width:{width}px;height:{height}px;overflow:hidden}}#stage>svg{{display:block;width:{width}px!important;height:{height}px!important}}</style>
</head><body><div id="stage">{svg_text}</div></body></html>'''
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".html", dir=source.parent, delete=False
    ) as handle:
        handle.write(html)
        return Path(handle.name)


def preview_receipt_errors(
    project_dir: Path,
    slide_id: str,
    version: str,
    identity: dict[str, str] | None = None,
    copy_contract: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    source = source_path(project_dir, slide_id, version)
    png, receipt_file = preview_paths(project_dir, slide_id, version)
    if not source.is_file():
        return [f"missing source SVG: {source}"]
    if not png.is_file():
        errors.append(f"missing preview PNG: {png}")
    if not receipt_file.is_file():
        errors.append(f"missing preview receipt: {receipt_file}")
    if errors:
        return errors
    try:
        receipt = _read_json(receipt_file)
        expected_dimensions = svg_canvas_pixels(source)
        actual_dimensions = png_dimensions(png)
    except PreviewError as exc:
        return [str(exc)]
    expected_source = str(source.relative_to(project_dir))
    expected_png = str(png.relative_to(project_dir))
    expected = {
        "schema_version": RECEIPT_SCHEMA,
        "slide_id": slide_id,
        "version": version,
        "source_svg": expected_source,
        "source_svg_sha256": _sha256(source),
        "preview_png": expected_png,
        "preview_png_sha256": _sha256(png),
        "width": expected_dimensions[0],
        "height": expected_dimensions[1],
    }
    if copy_contract is not None:
        expected.update({
            "visible_copy_contract_sha256": copy_contract.get("contract_sha256"),
            "visible_copy_status": "PASS",
        })
    for key, value in expected.items():
        if receipt.get(key) != value:
            errors.append(f"{slide_id} {version} preview receipt {key} is stale")
    if actual_dimensions != expected_dimensions:
        errors.append(
            f"{slide_id} {version} preview dimensions {actual_dimensions[0]}x{actual_dimensions[1]} "
            f"do not match SVG canvas {expected_dimensions[0]}x{expected_dimensions[1]}"
        )
    executable = Path(str(receipt.get("chromium_executable", ""))).expanduser()
    if (
        receipt.get("renderer") != RENDERER_NAME
        or not receipt.get("renderer_version")
        or not executable.is_absolute()
        or not executable.is_file()
    ):
        errors.append(f"{slide_id} {version} preview renderer binding is missing")
    if identity:
        for key in ("renderer", "renderer_version", "chromium_executable"):
            if receipt.get(key) != identity.get(key):
                errors.append(f"{slide_id} {version} preview {key} changed")
    if not isinstance(receipt.get("created_at"), str) or not receipt.get("created_at"):
        errors.append(f"{slide_id} {version} preview created_at is missing")
    return errors


def _render(
    project_dir: Path,
    slide_id: str,
    versions: list[str],
    dimensions: dict[str, tuple[int, int]],
    runtime: dict,
    copy_contract: dict | None = None,
) -> tuple[dict[str, dict], dict[str, str]]:
    root = preview_dir(project_dir, slide_id)
    root.mkdir(parents=True, exist_ok=True)
    command, env = _runtime_command_env(runtime)
    html_files: list[Path] = []
    temporary_pngs: dict[str, Path] = {}
    source_hashes: dict[str, str] = {}
    request_file: Path | None = None
    try:
        items = []
        for version in versions:
            source = source_path(project_dir, slide_id, version)
            width, height = dimensions[version]
            source_hashes[version] = _sha256(source)
            html_file = _preview_html(source, width, height)
            html_files.append(html_file)
            temporary_png = root / f".{version}-{uuid.uuid4().hex}.png"
            temporary_pngs[version] = temporary_png
            items.append({
                "version": version,
                "html_path": str(html_file),
                "output_path": str(temporary_png),
                "width": width,
                "height": height,
                "copy_contract": copy_contract,
            })
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", dir=root, delete=False) as handle:
            json.dump({"items": items}, handle)
            request_file = Path(handle.name)
        result = subprocess.run(
            [*command, "--request", str(request_file)],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise PreviewError(f"Chromium preview rendering failed for {slide_id} {'/'.join(versions)}: {detail}")
        try:
            summary = json.loads(result.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise PreviewError(f"preview renderer returned invalid output: {result.stdout!r}") from exc
        records = summary.get("records")
        if not isinstance(records, list):
            raise PreviewError("preview renderer returned no records")
        returned = {str(item.get("version")): item for item in records if isinstance(item, dict)}
        for version in versions:
            item = returned.get(version)
            if not item or item.get("ok") is not True:
                raise PreviewError(f"preview renderer failed for {slide_id} {version}: {(item or {}).get('error', 'missing record')}")
            if not temporary_pngs[version].is_file():
                raise PreviewError(f"preview renderer produced no PNG for {slide_id} {version}")
            if png_dimensions(temporary_pngs[version]) != dimensions[version]:
                raise PreviewError(f"preview renderer produced the wrong size for {slide_id} {version}")
            if _sha256(source_path(project_dir, slide_id, version)) != source_hashes[version]:
                raise PreviewError(f"source SVG changed during preview rendering: {slide_id} {version}")
        identity = {
            "renderer": str(summary.get("renderer", "")),
            "renderer_version": str(summary.get("renderer_version", "")),
            "browser_version": str(summary.get("browser_version", "unknown")),
            "chromium_executable": str(summary.get("chromium_executable", "")),
        }
        executable = Path(identity["chromium_executable"]).expanduser()
        if (
            identity["renderer"] != RENDERER_NAME
            or not identity["renderer_version"]
            or not executable.is_absolute()
            or not executable.is_file()
        ):
            raise PreviewError(f"preview renderer identity is invalid: {identity}")
        identity["chromium_executable"] = str(executable.resolve())
        output: dict[str, dict] = {}
        for version in versions:
            source = source_path(project_dir, slide_id, version)
            png, receipt_file = preview_paths(project_dir, slide_id, version)
            temporary_pngs[version].replace(png)
            width, height = dimensions[version]
            receipt = {
                "schema_version": RECEIPT_SCHEMA,
                "slide_id": slide_id,
                "version": version,
                "source_svg": str(source.relative_to(project_dir)),
                "source_svg_sha256": source_hashes[version],
                "preview_png": str(png.relative_to(project_dir)),
                "preview_png_sha256": _sha256(png),
                "renderer": identity["renderer"],
                "renderer_version": identity["renderer_version"],
                "browser_version": identity["browser_version"],
                "chromium_executable": identity["chromium_executable"],
                "width": width,
                "height": height,
                "created_at": _now(),
            }
            visible_copy = returned[version].get("visible_copy")
            if copy_contract is not None:
                receipt.update({
                    "visible_copy_contract_sha256": copy_contract["contract_sha256"],
                    "visible_copy_status": "PASS",
                    "visible_copy_evidence": visible_copy,
                })
            _atomic_json(receipt_file, receipt)
            output[version] = receipt
        return output, identity
    finally:
        for path in html_files:
            path.unlink(missing_ok=True)
        if request_file:
            request_file.unlink(missing_ok=True)
        for path in temporary_pngs.values():
            path.unlink(missing_ok=True)


def ensure_previews(
    project_dir: Path,
    slide_id: str,
    versions: tuple[str, ...],
    runtime: dict | None = None,
    copy_contract: dict | None = None,
    prevalidated_source_hashes: dict[str, str] | None = None,
) -> dict[str, dict]:
    if not versions or len(set(versions)) != len(versions):
        raise PreviewError("preview rendering requires one or more distinct versions")
    dimensions = {
        version: svg_canvas_pixels(source_path(project_dir, slide_id, version))
        for version in versions
    }
    if len(versions) > 1 and any(
        dimensions[version] != dimensions[versions[0]] for version in versions[1:]
    ):
        raise PreviewError(
            f"{slide_id} {'/'.join(versions)} preview canvases differ"
        )
    if copy_contract is not None:
        contract_problems = copy_contract_errors(copy_contract)
        if contract_problems:
            raise PreviewError("; ".join(contract_problems))
        for version in versions:
            source = source_path(project_dir, slide_id, version)
            if (
                prevalidated_source_hashes is not None
                and prevalidated_source_hashes.get(version) == _sha256(source)
            ):
                continue
            problems = visible_copy_errors(
                source, copy_contract
            )
            if problems:
                raise PreviewError("; ".join(problems))
    runtime = runtime or current_preview_runtime(project_dir)
    identity = renderer_identity(runtime)
    stale = [
        version
        for version in versions
        if preview_receipt_errors(
            project_dir, slide_id, version, identity, copy_contract=copy_contract
        )
    ]
    if stale:
        _render(
            project_dir,
            slide_id,
            stale,
            dimensions,
            runtime,
            copy_contract=copy_contract,
        )
    records: dict[str, dict] = {}
    problems: list[str] = []
    for version in versions:
        problems.extend(
            preview_receipt_errors(
                project_dir,
                slide_id,
                version,
                identity,
                copy_contract=copy_contract,
            )
        )
        _, receipt_file = preview_paths(project_dir, slide_id, version)
        if receipt_file.is_file():
            records[version] = _read_json(receipt_file)
    if problems:
        raise PreviewError("; ".join(problems))
    dimensions_seen = {
        (records[version]["width"], records[version]["height"]) for version in versions
    }
    if len(dimensions_seen) != 1:
        raise PreviewError(f"{slide_id} rendered previews are not equal-scale")
    return records


def ensure_preview_single(
    project_dir: Path,
    slide_id: str,
    version: str,
    runtime: dict | None = None,
    copy_contract: dict | None = None,
    prevalidated_source_hash: str | None = None,
) -> dict[str, dict]:
    return ensure_previews(
        project_dir,
        slide_id,
        (version,),
        runtime=runtime,
        copy_contract=copy_contract,
        prevalidated_source_hashes=(
            {version: prevalidated_source_hash} if prevalidated_source_hash else None
        ),
    )


def ensure_preview_pair(
    project_dir: Path,
    slide_id: str,
    versions: tuple[str, str],
    runtime: dict | None = None,
    copy_contract: dict | None = None,
    prevalidated_source_hashes: dict[str, str] | None = None,
) -> dict[str, dict]:
    if len(versions) != 2 or versions[0] == versions[1]:
        raise PreviewError("preview comparison requires two distinct versions")
    return ensure_previews(
        project_dir,
        slide_id,
        versions,
        runtime=runtime,
        copy_contract=copy_contract,
        prevalidated_source_hashes=prevalidated_source_hashes,
    )
