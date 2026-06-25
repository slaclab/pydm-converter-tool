"""EDM front-end adapter: EDMFileParser -> SourceNode tree -> ScreenIR.

Reuses the EDM parser and its semantics (macro normalization already happens in
the parser), then normalizes each EDM object into the Qt vocabulary the shared
:class:`~pydmconverter.ir.builder.IRBuilder` consumes. Group nesting is flattened
to absolute geometry (EDM child coordinates are already absolute), matching the
absolute-canvas model — visible-container nodes (frame/group-box) are a later phase.

Scope (Phase 1): P0 widgets, structural conversion. Rules (visPv), calc/Fox
formulas, and colours are deferred to later phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydmconverter.edm.converter_helpers import parse_edm_macros
from pydmconverter.edm.edm_qt import EDM_TO_QT_PROP, resolve_qt_class
from pydmconverter.edm.parser import EDMFileParser, EDMGroup, EDMObject
from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec, SourceNode

# An EDM visibility spec: (visPv, visMin, visMax, visInvert). visMin/visMax are
# None when the EDM object only declares visPv (visible-when-nonzero).
VisTuple = tuple[str, "float | None", "float | None", bool]

# Qt props that need value coercion before the builder maps them.
_CHANNEL_PROPS = {"channel"}
_MACRO_PROPS = {"macros"}
_TEXT_PROPS = {"text"}
# pressValue/releaseValue are deliberately absent: the registry types them as
# number-or-string, and EDM authors write enum-name values ("Open") as often as
# numerics, so they pass through as the original string rather than being coerced.
_NUMERIC_PROPS = {"precision", "userMinimum", "userMaximum", "numBits", "shift"}
_BOOL_PROPS = {"showUnits", "alarmSensitiveContent", "alarmSensitiveBorder", "showValueLabel"}


def _to_number(value: Any) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def _to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def _to_text(value: Any) -> Any:
    if isinstance(value, list):
        return normalize_macro_syntax("\n".join(str(item) for item in value))
    return normalize_macro_syntax(value)


def _to_channel(value: Any) -> Any:
    if isinstance(value, list):
        value = value[0] if value else ""
    return normalize_macro_syntax(value)


def _to_macros(value: Any) -> dict[str, str]:
    items = value if isinstance(value, list) else [value]
    merged: dict[str, str] = {}
    for item in items:
        if isinstance(item, str):
            for key, macro_value in parse_edm_macros(item).items():
                merged[key] = normalize_macro_syntax(macro_value)
    return merged


def _coerce(qt_prop: str, value: Any) -> Any:
    if qt_prop in _CHANNEL_PROPS:
        return _to_channel(value)
    if qt_prop in _MACRO_PROPS:
        return _to_macros(value)
    if qt_prop in _TEXT_PROPS:
        return _to_text(value)
    if qt_prop in _NUMERIC_PROPS:
        return _to_number(value)
    if qt_prop in _BOOL_PROPS:
        return _to_bool(value)
    return normalize_macro_syntax(value) if isinstance(value, str) else value


def _object_to_source(obj: EDMObject) -> SourceNode:
    qt_class = resolve_qt_class(obj.name.lower(), obj.properties)
    qt_props: dict[str, Any] = {}
    if qt_class is not None:
        for edm_attr, value in obj.properties.items():
            qt_prop = EDM_TO_QT_PROP.get(edm_attr)
            if qt_prop is None:
                continue
            qt_props[qt_prop] = _coerce(qt_prop, value)
    return SourceNode(
        qt_class=qt_class,
        qt_props=qt_props,
        geometry=(obj.x, obj.y, obj.width, obj.height),
        raw_class=obj.name,
        raw_props=dict(obj.properties),
    )


def _vis_tuple(properties: dict[str, Any]) -> VisTuple | None:
    """Extract an EDM visibility tuple ``(visPv, visMin, visMax, visInvert)``, or None."""
    vis_pv = properties.get("visPv")
    if not vis_pv:
        return None
    if isinstance(vis_pv, list):
        vis_pv = vis_pv[0] if vis_pv else ""
    vis_pv = normalize_macro_syntax(str(vis_pv))
    invert = bool(properties.get("visInvert", False))
    vis_min = properties.get("visMin")
    vis_max = properties.get("visMax")
    if vis_min is not None and vis_max is not None:
        return (vis_pv, vis_min, vis_max, invert)
    return (vis_pv, None, None, invert)


def _visibility_rule_spec(vis_tuples: list[VisTuple]) -> RuleSpec:
    """Combine EDM visibility tuples (own + inherited group vis) into one ``visible`` rule.

    EDM is visible when, for every tuple, ``visMin <= value < visMax`` (or ``value != 0``
    when no range), with ``visInvert`` flipping that tuple. Multiple tuples AND together
    (PyDM semantics). The single condition is true exactly when the widget is visible.
    """
    pv_index: dict[str, int] = {}
    pvs: list[tuple[str, bool]] = []
    parts: list[str] = []
    for vis_pv, vis_min, vis_max, invert in vis_tuples:
        if vis_pv not in pv_index:
            pv_index[vis_pv] = len(pvs)
            pvs.append((vis_pv, True))
        index = pv_index[vis_pv]
        if vis_min is not None and vis_max is not None:
            base = f"({{{index}}} >= {float(vis_min)}) and ({{{index}}} < {float(vis_max)})"
        else:
            base = f"{{{index}}} != 0"
        parts.append(f"not ({base})" if invert else base)
    return RuleSpec(
        target_property="visible",
        name="Visibility",
        pvs=pvs,
        conditions=[(" and ".join(parts), True)],
        default=False,
    )


def edm_group_to_source_nodes(group: EDMGroup, inherited_vis: tuple[VisTuple, ...] = ()) -> list[SourceNode]:
    """Flatten an EDM group tree into a flat list of widget SourceNodes.

    EDM groups are organizational and their children carry absolute coordinates, so
    groups dissolve into their widgets (z-order preserved). A group's ``visPv`` is
    inherited by every descendant as a visibility rule. When visible-container widgets
    land (frame/group-box), groups with chrome can become container nodes.
    """
    nodes: list[SourceNode] = []
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            group_vis = _vis_tuple(obj.properties)
            child_vis = inherited_vis + ((group_vis,) if group_vis else ())
            nodes.extend(edm_group_to_source_nodes(obj, child_vis))
        elif isinstance(obj, EDMObject):
            node = _object_to_source(obj)
            own_vis = _vis_tuple(obj.properties)
            all_vis = list(inherited_vis) + ([own_vis] if own_vis else [])
            if all_vis:
                node.rules = [_visibility_rule_spec(all_vis)]
            nodes.append(node)
    return nodes


def edm_file_to_ir(input_path: str | Path, *, registry: RegistryClient | None = None) -> ScreenIR:
    """Parse an ``.edl`` file and build its Screen IR."""
    path = Path(input_path)
    parser = EDMFileParser(str(path), str(path.with_suffix(".ui")))
    top_level = edm_group_to_source_nodes(parser.ui)
    builder = IRBuilder(registry or VendoredRegistry())
    return builder.build_screen(
        screen_id=path.stem,
        title=path.stem,
        source_type="edl-converter",
        size=(parser.ui.width, parser.ui.height),
        top_level=top_level,
    )
