"""Phoebus ``navtabs`` (Navigation Tabs) -> a row of open-display buttons.

A navtabs widget shows one button per ``<tab>`` and embeds the selected tab's display
below or beside them, with the widget's macros joined by that tab's own ``<macros>``
(``NavigationTabsWidget.getEffectiveMacros``). The IR has no navigation-tabs widget, so
each tab becomes a ``regular-button`` that opens its tab's display with exactly that
tab's file and macros; the embedded body is not built (the node warns).

Layout follows ``NavigationTabsWidget``: ``direction`` 0 HORIZONTAL / 1 VERTICAL
(default VERTICAL), ``tab_width`` 100, ``tab_height`` 30 and ``tab_spacing`` 2 by default,
buttons from the widget's top-left corner.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from pydmconverter.bob.gates import FILE_REFERENCE_WARNING, file_reference
from pydmconverter.bob.parser import BobWidget, prop_text
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.source import SourceNode
from pydmconverter.ir.transforms import screen_ref

__all__ = ["NAVTABS_WARNING", "navtab_buttons"]

NAVTABS_WARNING = (
    "{widget}: navigation tabs converted to open-display buttons, one per tab with its own macros; "
    "the selected tab's display is not embedded"
)
_DEFAULT_TAB_SIZE = (100, 30)
_DEFAULT_SPACING = 2
_HORIZONTAL = {"0", "HORIZONTAL"}

Geometry = tuple[Any, Any, Any, Any]


def _int(value: object, default: int) -> int:
    try:
        return int(float(prop_text(value).strip()))
    except ValueError:
        return default


def _tab_macros(tab: ET.Element) -> dict[str, str]:
    macros = tab.find("macros")
    if macros is None:
        return {}
    return {m.tag: (m.text or "").strip() for m in macros if m.tag != "include_parent_macros"}


def navtab_buttons(widget: BobWidget, origin: tuple[Any, Any], warn) -> list[SourceNode]:
    """One ``regular-button`` source node per ``<tab>`` of ``widget``, at absolute ``origin``.

    A tab's action macros are the widget's ``<macros>`` overlaid by the tab's own. A tab
    with no ``<file>`` gets a button without an action and a warning through ``warn``.
    """
    tabs = widget.props.get("tabs")
    elements = list(tabs.findall("tab")) if isinstance(tabs, ET.Element) else []
    width = _int(widget.props.get("tab_width"), _DEFAULT_TAB_SIZE[0])
    height = _int(widget.props.get("tab_height"), _DEFAULT_TAB_SIZE[1])
    spacing = _int(widget.props.get("tab_spacing"), _DEFAULT_SPACING)
    horizontal = prop_text(widget.props.get("direction")).strip().upper() in _HORIZONTAL
    buttons: list[SourceNode] = []
    for index, tab in enumerate(elements):
        name = (tab.findtext("name") or "").strip() or f"Tab {index + 1}"
        raw = (tab.findtext("file") or "").strip()
        file = file_reference(raw) if raw else ""
        if file is None:
            warn(FILE_REFERENCE_WARNING.format(widget=widget.name, what=f"navigation tab {name!r}", reference=raw))
        offset = index * ((width if horizontal else height) + spacing)
        x = origin[0] + (offset if horizontal else 0)
        y = origin[1] + (0 if horizontal else offset)
        actions: list[dict] = []
        if file:
            action: dict[str, Any] = {
                "type": "open_display",
                "file": screen_ref(file),
                "target": "tab",
            }
            macros = {**widget.macros, **_tab_macros(tab)}
            if macros:
                action["macros"] = {key: normalize_macro_syntax(value) for key, value in macros.items()}
            actions.append(action)
        elif file is not None:
            warn(f"{widget.name}: navigation tab {name!r} has no file")
        props: dict[str, Any] = {"text": normalize_macro_syntax(name)}
        if actions:
            props["actions"] = actions
        buttons.append(
            SourceNode(
                qt_class="QPushButton",
                qt_props=props,
                registry_id="regular-button",
                geometry=(x, y, width, height),
                raw_class="navtabs",
            )
        )
    return buttons
