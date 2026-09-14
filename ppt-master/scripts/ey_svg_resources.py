"""EY-only resource closure and pre-review inlining; never authors composition."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from resource_paths import svg_image_payload_error


SVG_NS = "http://www.w3.org/2000/svg"
HREF_KEYS = ("href", "{http://www.w3.org/1999/xlink}href")


def resource_errors(root: ET.Element, raw_bytes: bytes | None = None) -> list[str]:
    """Require geometry for uses and recursively packaged image resources."""
    error = svg_image_payload_error(
        raw_bytes if raw_bytes is not None else ET.tostring(root), allow_use=False,
    )
    return [f"SVG resource is not self-contained: {error}"] if error else []


def inline_resources(path: Path, icons_dir: Path) -> dict[str, int]:
    """Inline exact local inputs atomically, keeping picture bytes unchanged."""
    original = path.read_bytes()
    if b"<!DOCTYPE" in original.upper() or b"<?xml-stylesheet" in original.lower():
        raise ValueError("SVG resource declarations must be resolved before inlining")
    root = ET.fromstring(original)
    counts = {"icons": 0, "local_uses": 0, "images": 0}
    if any(e.tag.rsplit("}", 1)[-1] == "use" for e in root.iter()):
        from svg_to_pptx.use_expander import expand_local_use_references, expand_use_data_icons

        counts["icons"] = expand_use_data_icons(root, icons_dir, full_viewbox=True)
        counts["local_uses"] = expand_local_use_references(root, include_definitions=True)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "image":
            continue
        hrefs = [element.get(key).strip() for key in HREF_KEYS if element.get(key)]
        if not hrefs or len(set(hrefs)) > 1:
            raise ValueError("SVG image resource has missing or conflicting hrefs")
        href = hrefs[0]
        if href.lower().startswith("data:"):
            continue
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("SVG image resource must be an exact local file or data URI")
        image = Path(unquote(parsed.path))
        if not image.is_absolute():
            image = path.parent / image
        payload = image.read_bytes()
        from svg_finalize.embed_images import get_mime_type

        mime_type = get_mime_type(str(image), payload)
        if mime_type not in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}:
            raise ValueError(f"Unsupported SVG image resource type: {mime_type}")
        uri = f"data:{mime_type};base64," + base64.b64encode(payload).decode("ascii")
        for key in HREF_KEYS:
            if element.get(key) is not None:
                element.set(key, uri)
        counts["images"] += 1
    errors = resource_errors(root, original if not any(counts.values()) else None)
    if errors:
        raise ValueError(" | ".join(errors))
    if not any(counts.values()):
        return counts
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.stem}-resources-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(ET.tostring(root, encoding="utf-8"))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return counts
