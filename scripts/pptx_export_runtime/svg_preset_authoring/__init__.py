"""Shared authored-preset SVG contract used by the confirmed export runtime."""

from .authoring import (
    AUTHORING_ATTR,
    AUTHORING_VALUE,
    authored_preset_encoding,
    render_preset_shape_fragment,
    validate_authored_preset_group,
)

__all__ = [
    "AUTHORING_ATTR",
    "AUTHORING_VALUE",
    "authored_preset_encoding",
    "render_preset_shape_fragment",
    "validate_authored_preset_group",
]
