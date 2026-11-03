"""Group handling for the Phoebus ``.bob`` front-end.

A Phoebus ``group`` widget places its children relative to its own origin, shifted by
an inset that depends on the group ``<style>`` (0 GROUP_BOX, 1 TITLE, 2 LINE, 3 NONE)
and on the group's ``<font>`` size (``GroupRepresentation.updateChanges``). The IR
geometry is absolute, so :func:`child_geometry` accumulates the group's origin plus
that inset; nested groups compose by passing the inner group's absolute origin back in
as ``origin``.

:func:`group_node` picks the IR target: styles 0/1 draw a titled frame and become
``group-box`` (the Phoebus group title is the widget ``<name>``), styles 2/3 become a
plain ``group``. The inset and style tables live in :mod:`pydmconverter.bob.bob_qt`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pydmconverter.bob.bob_qt import GROUP_DEFAULT_FONT_SIZE, GROUP_STYLE_TO_ID, default_size, inset
from pydmconverter.bob.coercion import font_size as _font_size
from pydmconverter.bob.parser import BobWidget

__all__ = [
    "child_geometry",
    "group_font_size",
    "group_node",
    "group_style",
]

_DEFAULT_STYLE = 0


def _number(value: ET.Element | str | None, default: int) -> int:
    """Leaf prop text -> int (truncated), ``default`` when absent or unparsable."""
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def group_style(group: BobWidget) -> int:
    """The group's ``<style>``; absent, unparsable or unknown -> 0 (GROUP_BOX)."""
    style = _number(group.props.get("style"), _DEFAULT_STYLE)
    return style if style in GROUP_STYLE_TO_ID else _DEFAULT_STYLE


def group_font_size(group: BobWidget) -> int | float:
    """Size from the group's ``<font>``, else the Phoebus default (14)."""
    size = _font_size(group.props.get("font"))
    return GROUP_DEFAULT_FONT_SIZE if size is None else size


def child_geometry(
    group: BobWidget,
    child: BobWidget,
    font_size: float | None = None,
    *,
    origin: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Absolute ``(x, y, w, h)`` of ``child`` inside ``group``.

    ``origin`` is the group's absolute origin; it defaults to the group's own
    ``x``/``y``, which is only absolute for a top-level group. ``font_size``
    overrides the group's ``<font>`` size.
    """
    if origin is None:
        origin = (_number(group.props.get("x"), 0), _number(group.props.get("y"), 0))
    size = group_font_size(group) if font_size is None else font_size
    dx, dy = inset(group_style(group), size)
    default_w, default_h = default_size(child.type)
    return (
        origin[0] + dx + _number(child.props.get("x"), 0),
        origin[1] + dy + _number(child.props.get("y"), 0),
        _number(child.props.get("width"), default_w),
        _number(child.props.get("height"), default_h),
    )


def group_node(group: BobWidget) -> tuple[str | None, str, dict]:
    """``(qt_class, registry_id, qt_props)`` for a group; styles 0/1 carry ``title``."""
    qt_class, registry_id = GROUP_STYLE_TO_ID[group_style(group)]
    props = {"title": group.name} if registry_id == "group-box" else {}
    return qt_class, registry_id, props
