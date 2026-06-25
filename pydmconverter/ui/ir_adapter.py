"""Qt ``.ui`` front-end adapter: ``.ui`` XML -> SourceNode tree -> ScreenIR.

Parses a PyDM/Qt Designer ``.ui`` document with ``xml.etree`` and normalizes each
widget into a :class:`~pydmconverter.ir.source.SourceNode`. Because ``.ui`` carries
Qt/PyDM class names and Qt property names, the props pass straight to the shared
:class:`~pydmconverter.ir.builder.IRBuilder` (Beaver's ``qtPropMap`` does the rest)
— there is no per-attribute translation as on the EDM side.

Geometry (D4): a widget's absolute ``geometry`` ``<rect>`` is trusted. A widget that
has no ``<rect>`` (e.g. it sits in a Qt layout) gets a warning and ``(0,0,0,0)`` for
now — computing absolute coordinates from layout managers is a later refinement
("trust ``<rect>``, warn when computing").
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import SourceNode

_SKIP = object()


def _parse_int(text: str) -> Any:
    """``<number>`` text -> int; tolerate a float-formatted value, ``_SKIP`` if unparseable."""
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return _SKIP


def _parse_float(text: str) -> Any:
    """``<double>`` text -> float, ``_SKIP`` if unparseable."""
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return _SKIP


def _scalar_property(prop: ET.Element) -> Any:
    """Extract a scalar value from a ``<property>``; ``_SKIP`` for unsupported kinds.

    Handles the simple typed children. Complex kinds (font, sizepolicy, ...) are
    skipped — no P0 prop consumes them.
    """
    children = list(prop)
    if not children:
        return _SKIP
    el = children[0]
    text = (el.text or "").strip()
    tag = el.tag
    if tag == "string":
        return el.text or ""
    if tag == "bool":
        return text.lower() == "true"
    if tag == "number":
        return _parse_int(text)
    if tag == "double":
        return _parse_float(text)
    if tag in ("enum", "set"):
        return text
    if tag == "stringlist":
        return [c.text or "" for c in el]
    return _SKIP


def _rect(prop: ET.Element) -> tuple[int, int, int, int] | None:
    rect = prop.find("rect")
    if rect is None:
        return None

    def part(tag: str) -> int:
        el = rect.find(tag)
        return int(el.text) if el is not None and el.text else 0

    return (part("x"), part("y"), part("width"), part("height"))


def _child_widgets(elem: ET.Element) -> list[ET.Element]:
    """Immediate child ``<widget>`` elements, reaching through ``<layout><item>``."""
    found: list[ET.Element] = []
    for child in elem:
        if child.tag == "widget":
            found.append(child)
        elif child.tag == "layout":
            found.extend(_layout_widgets(child))
    return found


def _layout_widgets(layout: ET.Element) -> list[ET.Element]:
    found: list[ET.Element] = []
    for item in layout.findall("item"):
        for sub in item:
            if sub.tag == "widget":
                found.append(sub)
            elif sub.tag == "layout":
                found.extend(_layout_widgets(sub))
    return found


def _widget_to_source(widget: ET.Element) -> SourceNode:
    qt_class = widget.get("class")
    props: dict[str, Any] = {}
    geometry: tuple[int, int, int, int] | None = None
    for prop in widget.findall("property"):
        name = prop.get("name")
        if name == "geometry":
            geometry = _rect(prop)
            continue
        value = _scalar_property(prop)
        if value is not _SKIP and name:
            props[name] = value

    warnings: list[str] = []
    if geometry is None:
        warnings.append(
            f"{widget.get('name') or qt_class} has no geometry rect (likely in a Qt layout); using (0,0,0,0)"
        )
        geometry = (0, 0, 0, 0)

    return SourceNode(
        qt_class=qt_class,
        qt_props=props,
        geometry=geometry,
        raw_class=qt_class,
        raw_props=dict(props),
        children=[_widget_to_source(child) for child in _child_widgets(widget)],
        warnings=warnings,
    )


def _string_property(widget: ET.Element, name: str) -> str | None:
    for prop in widget.findall("property"):
        if prop.get("name") == name:
            el = prop.find("string")
            if el is not None:
                return el.text or ""
    return None


def parse_ui(path: str | Path) -> tuple[ET.Element, str, tuple[int, int]]:
    """Return the root ``<widget>`` element, its window title, and screen size."""
    root_widget = ET.parse(path).getroot().find("widget")
    if root_widget is None:
        raise ValueError(f"{path}: no root <widget> element in .ui file")
    title = _string_property(root_widget, "windowTitle") or root_widget.get("name") or "screen"
    size: tuple[int, int] = (0, 0)
    for prop in root_widget.findall("property"):
        if prop.get("name") == "geometry":
            rect = _rect(prop)
            if rect:
                size = (rect[2], rect[3])
            break
    return root_widget, title, size


def ui_file_to_ir(input_path: str | Path, *, registry: RegistryClient | None = None) -> ScreenIR:
    """Parse a ``.ui`` file and build its Screen IR."""
    path = Path(input_path)
    root_widget, title, size = parse_ui(path)
    top_level = [_widget_to_source(child) for child in _child_widgets(root_widget)]
    builder = IRBuilder(registry or VendoredRegistry())
    return builder.build_screen(
        screen_id=path.stem,
        title=title,
        source_type="ui-converter",
        size=size,
        top_level=top_level,
    )
