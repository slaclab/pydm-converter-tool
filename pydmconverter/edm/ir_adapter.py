"""EDM front-end adapter: EDMFileParser -> SourceNode tree -> ScreenIR.

Reuses the EDM parser and its semantics (macro normalization already happens in
the parser), then normalizes each EDM object into the Qt vocabulary the shared
:class:`~pydmconverter.ir.builder.IRBuilder` consumes. Group nesting is flattened
to absolute geometry (EDM child coordinates are already absolute), matching the
absolute-canvas model — visible-container nodes (frame/group-box) are a later phase.

Scope (Phase 1): P0 widgets, structural conversion. Rules (visPv) are handled;
colours are resolved to static hex; calc/Fox formulas and dynamic colour (colorPv/
bgAlarm) are deferred to later phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydmconverter.edm.edm_qt import EDM_TO_QT_PROP, resolve_qt_class
from pydmconverter.edm.parser import EDMFileParser, EDMGroup, EDMObject
from pydmconverter.edm.parser_helpers import (
    get_color_by_index,
    get_color_by_rgb,
    parse_colors_list,
    parse_edm_macros,
    search_color_list,
)
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
# Qt props holding an EDM colour value ("index N" / "rgb r g b") that must be
# resolved to "#rrggbb" hex before the builder sees them. penColor/brushColor are
# consumed by drawing widget defs a later phase wires up; included now so their
# resolution is already in place when those widgets land.
_COLOR_PROPS = {"penColor", "brushColor", "foregroundColor", "backgroundColor"}


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


def edm_color_to_hex(value: Any, color_data: dict[str, Any] | None) -> str | None:
    """Resolve an EDM colour value ("index 14" / "rgb 65535 0 0") to "#rrggbb", or None.

    ``color_data`` is the parsed ``colors.list`` palette (see :func:`parse_colors_list`);
    it may be ``None``/empty when no palette was found, in which case an "index N" value
    cannot be resolved. Blinking colours carry six components (two RGB states); only the
    first state is used. Scaling matches :func:`parser_helpers.convert_color_property_to_qcolor`:
    components are 16-bit when any exceeds 256, scaled by ``255/(max_val - 1)``.
    Returns ``None`` on any failure — callers drop the prop rather than emit a default.
    """
    if not isinstance(value, str) or not value:
        return None

    if value.startswith("rgb"):
        try:
            color_info = get_color_by_rgb(value)
        except ValueError:
            return None
    elif value.startswith("index"):
        color_info = get_color_by_index(color_data or {}, value)
    else:
        return None

    if not color_info:
        return None

    rgb = color_info.get("rgb")
    if not rgb or len(rgb) < 3:
        return None
    red, green, blue = rgb[:3]

    if max(red, green, blue) > 256:
        # Components above 256 are 16-bit; without a palette-declared max,
        # assume the EDM-native 0x10000 rather than clamping everything to 255.
        max_val = (color_data or {}).get("max") or 65536
        scale = 255 / (max_val - 1)
        red = min(255, max(0, int(red * scale)))
        green = min(255, max(0, int(green * scale)))
        blue = min(255, max(0, int(blue * scale)))

    return f"#{red:02x}{green:02x}{blue:02x}"


def _object_to_source(obj: EDMObject, colors: dict[str, Any] | None = None) -> SourceNode:
    qt_class = resolve_qt_class(obj.name.lower(), obj.properties)
    qt_props: dict[str, Any] = {}
    warnings: list[str] = []
    if qt_class is not None:
        use_display_bg = bool(obj.properties.get("useDisplayBg"))
        for edm_attr, value in obj.properties.items():
            qt_prop = EDM_TO_QT_PROP.get(edm_attr)
            if qt_prop is None:
                continue
            if qt_prop in _COLOR_PROPS:
                if qt_prop == "backgroundColor" and use_display_bg:
                    # EDM writes bgColor even when the object uses the display
                    # background; emitting it would paint a spurious background.
                    continue
                hex_color = edm_color_to_hex(value, colors)
                if hex_color is None:
                    warnings.append(f"EDM colour '{value}' for {edm_attr} could not be resolved; prop dropped")
                    continue
                qt_props[qt_prop] = hex_color
                continue
            qt_props[qt_prop] = _coerce(qt_prop, value)
        for flag in ("colorPv", "bgAlarm"):
            if obj.properties.get(flag):
                warnings.append(f"EDM dynamic colour ({flag}) is not supported; static colours emitted")
    return SourceNode(
        qt_class=qt_class,
        qt_props=qt_props,
        geometry=(obj.x, obj.y, obj.width, obj.height),
        raw_class=obj.name,
        raw_props=dict(obj.properties),
        warnings=warnings,
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


def edm_group_to_source_nodes(
    group: EDMGroup, inherited_vis: tuple[VisTuple, ...] = (), *, colors: dict[str, Any] | None = None
) -> list[SourceNode]:
    """Flatten an EDM group tree into a flat list of widget SourceNodes.

    EDM groups are organizational and their children carry absolute coordinates, so
    groups dissolve into their widgets (z-order preserved). A group's ``visPv`` is
    inherited by every descendant as a visibility rule. When visible-container widgets
    land (frame/group-box), groups with chrome can become container nodes.

    ``colors`` is the parsed ``colors.list`` palette (see :func:`edm_file_to_ir`), used
    to resolve "index N" colour props to hex.
    """
    nodes: list[SourceNode] = []
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            group_vis = _vis_tuple(obj.properties)
            child_vis = inherited_vis + ((group_vis,) if group_vis else ())
            nodes.extend(edm_group_to_source_nodes(obj, child_vis, colors=colors))
        elif isinstance(obj, EDMObject):
            node = _object_to_source(obj, colors)
            own_vis = _vis_tuple(obj.properties)
            all_vis = list(inherited_vis) + ([own_vis] if own_vis else [])
            if all_vis:
                node.rules = [_visibility_rule_spec(all_vis)]
            nodes.append(node)
    return nodes


def edm_file_to_ir(
    input_path: str | Path, *, registry: RegistryClient | None = None, color_list_path: str | Path | None = None
) -> ScreenIR:
    """Parse an ``.edl`` file and build its Screen IR.

    ``color_list_path`` points at an EDM ``colors.list`` palette used to resolve
    "index N" colour props. When omitted, the palette is located via (in order) the
    ``EDMCOLORFILE`` env var, ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``;
    an explicit ``color_list_path`` wins over all of those. If no palette is found,
    "index N" colours cannot be resolved and are dropped with a node warning ("rgb ..."
    colours resolve without a palette).
    """
    path = Path(input_path)
    parser = EDMFileParser(str(path), str(path.with_suffix(".ui")))
    colors_path = search_color_list(str(color_list_path) if color_list_path else None)
    colors = parse_colors_list(colors_path)
    top_level = edm_group_to_source_nodes(parser.ui, colors=colors)
    builder = IRBuilder(registry or VendoredRegistry())
    return builder.build_screen(
        screen_id=path.stem,
        title=path.stem,
        source_type="edl-converter",
        size=(parser.ui.width, parser.ui.height),
        top_level=top_level,
    )
