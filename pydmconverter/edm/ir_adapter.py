"""EDM front-end adapter: EDMFileParser -> SourceNode tree -> ScreenIR.

Reuses the EDM parser and its semantics (macro normalization already happens in
the parser), then normalizes each EDM object into the Qt vocabulary the shared
:class:`~pydmconverter.ir.builder.IRBuilder` consumes. Groups are materialized as
``group`` widget nodes (registry-resolved, no Qt analog); their children keep
absolute screen coordinates, matching the Screen IR geometry contract.

Covers structural conversion plus graphics classes (rectangle/ellipse/line/arc,
bars) and the text/button/indicator classes — activeXTextDspClass:noedit,
shellCmdClass, activeExitButtonClass, activePngClass, activeMeterClass,
activeIndicatorClass, activeRadioButtonClass, activeFreezeButtonClass,
activeRampButtonClass, activeUpdownButtonClass, mmvClass, and
multiLineTextEntryClass. Rules (visPv) are handled and colors are resolved to
static hex; calc/Fox formulas and dynamic color (colorPv/bgAlarm) are not yet
translated. Several classes carry EDM semantics with no Qt/web analog
(freeze/ramp/updown increment behaviour, shell command execution); those are
surfaced as node warnings rather than silently dropped. menuMuxClass is
deliberately unmapped (macro-muxing needs a design) and falls through to
unknown-widget.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

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
from pydmconverter.ir.model import Number, ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec, SourceNode

# An EDM visibility spec: (visPv, visMin, visMax, visInvert). visMin/visMax are
# None when the EDM object only declares visPv (visible-when-nonzero).
VisTuple = tuple[str, "float | None", "float | None", bool]

# A SourceNode geometry tuple: absolute (x, y, width, height).
Geometry = tuple[Number, Number, Number, Number]

# Qt props that need value coercion before the builder maps them.
_CHANNEL_PROPS = {"channel"}
_MACRO_PROPS = {"macros"}
_TEXT_PROPS = {"text"}
# pressValue/releaseValue are deliberately absent: the registry types them as
# number-or-string, and EDM authors write enum-name values ("Open") as often as
# numerics, so they pass through as the original string rather than being coerced.
_NUMERIC_PROPS = {"precision", "userMinimum", "userMaximum", "numBits", "shift", "penWidth", "startAngle", "spanAngle"}
_BOOL_PROPS = {"showUnits", "alarmSensitiveContent", "alarmSensitiveBorder", "showValueLabel", "brushFill"}
# Qt props holding an EDM color value ("index N" / "rgb r g b") that must be
# resolved to "#rrggbb" hex before the builder sees them. penColor/brushColor are
# consumed by the drawing widget defs (rectangle/ellipse/line/arc).
_COLOR_PROPS = {"penColor", "brushColor", "foregroundColor", "backgroundColor"}
# displayFormat carries pv-label's "format" enum value; EDM's format strings must
# be normalized to the registry's vocabulary (decimal/hex/string/exponential/default).
_FORMAT_PROPS = {"displayFormat"}
_EDM_FORMAT_TO_QT: dict[str, str] = {
    "decimal": "default",
    "float": "default",
    "gfloat": "default",
    "default": "default",
    "exponential": "exponential",
    "hex": "hex",
    "string": "string",
}


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


def _to_format(value: Any) -> str:
    """EDM format string -> pv-label's ``format`` enum. Case-insensitive; unrecognized -> "default"."""
    if isinstance(value, str):
        return _EDM_FORMAT_TO_QT.get(value.strip().lower(), "default")
    return "default"


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
    if qt_prop in _FORMAT_PROPS:
        return _to_format(value)
    return normalize_macro_syntax(value) if isinstance(value, str) else value


def edm_color_to_hex(value: Any, color_data: dict[str, Any] | None) -> str | None:
    """Resolve an EDM color value ("index 14" / "rgb 65535 0 0") to "#rrggbb", or None.

    ``color_data`` is the parsed ``colors.list`` palette (see :func:`parse_colors_list`);
    it may be ``None``/empty when no palette was found, in which case an "index N" value
    cannot be resolved. Blinking colors carry six components (two RGB states); only the
    first state is used. Components are treated as 16-bit when any reaches 256 (the
    smallest value that cannot be an 8-bit intensity), scaled by ``255/(max_val - 1)``;
    values below 256 are already 8-bit and pass through unscaled.
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

    if max(red, green, blue) >= 256:
        # 256 is the smallest value that cannot be an 8-bit intensity, so any
        # component at or above it is 16-bit; without a palette-declared max,
        # assume the EDM-native 0x10000 rather than clamping everything to 255.
        max_val = (color_data or {}).get("max") or 65536
        scale = 255 / (max_val - 1)
        red = min(255, max(0, int(red * scale)))
        green = min(255, max(0, int(green * scale)))
        blue = min(255, max(0, int(blue * scale)))

    return f"#{red:02x}{green:02x}{blue:02x}"


# Per-class fixup: keyed by lowercased EDM class name. Runs after the generic
# prop loop (and color/dynamic-flag handling) in ``_object_to_source``. May
# mutate ``qt_props``/``warnings`` in place and may return a geometry override
# (bbox derived from raw properties) to replace the object's header geometry.
_CLASS_FIXUPS: dict[str, Callable[[EDMObject, dict[str, Any], list[str]], Geometry | None]] = {}


def _as_number(value: float) -> Any:
    """``float`` -> ``int`` when integral, else the float unchanged."""
    return int(value) if value.is_integer() else value


def _apply_shared_drawing_fixup(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> None:
    """Fixup shared by all drawing classes (rectangle/circle/arc/line)."""
    if obj.properties.get("invisible"):
        # The defs map opacity->opacity; EDM invisible objects must not render.
        qt_props["opacity"] = 100
    if qt_props.get("penWidth") == 0:
        # X11 width-0 means thinnest visible line; width 0 in the builder renders nothing.
        qt_props["penWidth"] = 1
    alarm_flags = [flag for flag in ("lineAlarm", "fillAlarm") if obj.properties.get(flag)]
    if alarm_flags:
        flags = ", ".join(alarm_flags)
        warnings.append(f"EDM alarm-driven colors ({flags}) are not supported; static colors emitted")


def _parse_line_points(obj: EDMObject) -> list[tuple[float, float]] | None:
    """Parse ``xPoints``/``yPoints`` into ``[(x, y), ...]``, or ``None`` if malformed."""
    x_points = obj.properties.get("xPoints")
    y_points = obj.properties.get("yPoints")
    if not isinstance(x_points, list) or not isinstance(y_points, list):
        return None
    if len(x_points) != len(y_points) or len(x_points) < 2:
        return None
    try:
        return [(float(x), float(y)) for x, y in zip(x_points, y_points)]
    except (TypeError, ValueError):
        return None


def _fixup_line(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeLineClass fixup: shared drawing logic + points/arrows/fill handling."""
    _apply_shared_drawing_fixup(obj, qt_props, warnings)

    geometry_override: Geometry | None = None
    points = _parse_line_points(obj)
    if points is None:
        warnings.append("activeLineClass points missing or malformed; keeping header geometry")
    else:
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        min_x, min_y = min(xs), min(ys)
        geometry_override = (min_x, min_y, max(xs) - min_x, max(ys) - min_y)
        qt_props["points"] = [{"x": _as_number(x - min_x), "y": _as_number(y - min_y)} for x, y in points]

    # Explicit booleans every time: the Line component defaults arrowEnd to
    # TRUE when the prop is absent, so both must always be written.
    arrows = obj.properties.get("arrows")
    qt_props["arrowStartPoint"] = arrows in ("from", "both")
    qt_props["arrowEndPoint"] = arrows in ("to", "both")

    if obj.properties.get("fill") or obj.properties.get("closePolygon"):
        # Line has no fill; brushFill arrives via the global fill->brushFill
        # rename and the line def would drop it anyway, but pop for cleanliness.
        qt_props.pop("brushFill", None)
        qt_props.pop("brushColor", None)
        warnings.append("EDM filled/closed polygon is rendered as an open polyline")

    return geometry_override


def _fixup_arc(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeArcClass fixup: shared drawing logic + angle defaults/fillMode."""
    _apply_shared_drawing_fixup(obj, qt_props, warnings)

    if "startAngle" not in qt_props:
        qt_props["startAngle"] = 0
    if "spanAngle" not in qt_props:
        # EDM draws the full ellipse when totalAngle is omitted (corpus-derived: absent ~70%).
        qt_props["spanAngle"] = 360

    if obj.properties.get("fillMode") and obj.properties.get("fill"):
        warnings.append(f"EDM arc fillMode '{obj.properties['fillMode']}' approximated by plain fill")

    return None


_BAR_UNMAPPED_PROPS = (
    "indicatorColor",
    "indicatorColour",
    "origin",
    "showScale",
    "scaleFormat",
    "scalePrecision",
    "label",
    "maxPv",
    "minPv",
)


def _fixup_bar(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeBarClass/activeSlacBarClass/activeVsBarClass fixup."""
    if obj.name.lower() == "activevsbarclass" and "orientation" not in qt_props:
        qt_props["orientation"] = "vertical"

    present = [name for name in _BAR_UNMAPPED_PROPS if name in obj.properties]
    if present:
        warnings.append(f"EDM bar props not mapped: {', '.join(present)}")

    return None


# Matches a leading "<int> " prefix that remove_prepended_index leaves in place
# when the multi-line block's indices are non-sequential.
_LEADING_INDEX_RE = re.compile(r"^\d+\s+")


def _strip_leading_index(value: str) -> str:
    return _LEADING_INDEX_RE.sub("", value, count=1)


def _as_str_list(value: Any) -> list[str]:
    """Normalize a brace-block prop value to a list of strings (a bare str -> [str])."""
    if isinstance(value, list):
        return [_strip_leading_index(str(item)) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _fixup_shell_cmd(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """shellCmdClass fixup: command/commandLabel brace blocks -> qt_props["actions"].

    (buttonLabel -> text -> label is already handled globally.)
    """
    commands = _as_str_list(obj.properties.get("command"))
    if not commands:
        return None
    labels = _as_str_list(obj.properties.get("commandLabel"))

    actions: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        action: dict[str, Any] = {"type": "shell_command", "command": normalize_macro_syntax(command)}
        if index < len(labels):
            action["label"] = normalize_macro_syntax(labels[index])
        actions.append(action)

    qt_props["actions"] = actions
    warnings.append("EDM shell commands carried as actions; the web runtime does not execute shell commands")
    return None


def _fixup_exit_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeExitButtonClass fixup: always closes the display."""
    qt_props["actions"] = [{"type": "close_display"}]
    if obj.properties.get("exitProgram"):
        warnings.append("EDM exitProgram semantics reduced to close_display")
    return None


def _fixup_freeze_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeFreezeButtonClass fixup: no PV in the corpus (freeze targets the local display)."""
    warnings.append("EDM freeze-button semantics (display update freeze) are not preserved")
    return None


def _fixup_ramp_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeRampButtonClass fixup: rampRate/finalValuePv semantics have no Qt analog."""
    warnings.append("EDM ramp-button semantics (rampRate/finalValuePv) are not preserved")
    return None


def _fixup_updown_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeUpdownButtonClass fixup: coarseValue/fineValue increment semantics have no Qt analog."""
    warnings.append("EDM up/down increment semantics (coarseValue/fineValue) are not preserved")
    return None


def _fixup_mmv(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """mmvClass fixup: derive orientation from orientStr (the NUMERIC orientation prop is unreliable)."""
    orient_str = str(obj.properties.get("orientStr", "")).lower()
    if orient_str.startswith("horiz"):
        qt_props["orientation"] = "horizontal"
    elif orient_str.startswith("vert"):
        qt_props["orientation"] = "vertical"
    else:
        qt_props.pop("orientation", None)

    if obj.properties.get("ctrl2Pv"):
        warnings.append("mmvClass second control PV (ctrl2Pv) dropped")
    return None


def _fixup_multiline_text_entry(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """multiLineTextEntryClass fixup: rendered as a single-line pv-text-input."""
    warnings.append("EDM multi-line text entry rendered as a single-line text input")
    return None


def _fixup_meter(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeMeterClass fixup: warn when labelType isn't the literal-text default.

    (readPv->channel, scaleMin/scaleMax->userMinimum/userMaximum, label->text are
    global renames already.)
    """
    label_type = obj.properties.get("labelType")
    if label_type not in (None, "", "literal"):
        warnings.append(f"EDM meter labelType '{label_type}' not supported; label emitted as literal text")
    return None


_CLASS_FIXUPS.update(
    {
        "activerectangleclass": _apply_shared_drawing_fixup,
        "activecircleclass": _apply_shared_drawing_fixup,
        "activelineclass": _fixup_line,
        "activearcclass": _fixup_arc,
        "activebarclass": _fixup_bar,
        "activeslacbarclass": _fixup_bar,
        "activevsbarclass": _fixup_bar,
        # text / buttons / indicators
        "shellcmdclass": _fixup_shell_cmd,
        "activeexitbuttonclass": _fixup_exit_button,
        "activefreezebuttonclass": _fixup_freeze_button,
        "activerampbuttonclass": _fixup_ramp_button,
        "activeupdownbuttonclass": _fixup_updown_button,
        "mmvclass": _fixup_mmv,
        "multilinetextentryclass": _fixup_multiline_text_entry,
        "activemeterclass": _fixup_meter,
        "activeindicatorclass": _fixup_bar,
        # activepngclass, activeradiobuttonclass: no fixup needed; global renames suffice.
    }
)


def _object_to_source(obj: EDMObject, colors: dict[str, Any] | None = None) -> SourceNode:
    qt_class = resolve_qt_class(obj.name.lower(), obj.properties)
    qt_props: dict[str, Any] = {}
    warnings: list[str] = []
    geometry: Geometry = (obj.x, obj.y, obj.width, obj.height)
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
                    warnings.append(f"EDM color '{value}' for {edm_attr} could not be resolved; prop dropped")
                    continue
                qt_props[qt_prop] = hex_color
                continue
            qt_props[qt_prop] = _coerce(qt_prop, value)
        for flag in ("colorPv", "bgAlarm"):
            if obj.properties.get(flag):
                warnings.append(f"EDM dynamic color ({flag}) is not supported; static colors emitted")
        fixup = _CLASS_FIXUPS.get(obj.name.lower())
        if fixup is not None:
            override = fixup(obj, qt_props, warnings)
            if override is not None:
                geometry = override
    return SourceNode(
        qt_class=qt_class,
        qt_props=qt_props,
        geometry=geometry,
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


def edm_group_to_source_nodes(group: EDMGroup, *, colors: dict[str, Any] | None = None) -> list[SourceNode]:
    """Materialize an EDM group tree into a list of widget SourceNodes.

    EDM groups are materialized as ``group`` widget nodes (the registry's ``group``
    definition, resolved via ``registry_id`` rather than a Qt class — EDM groups have
    no Qt analog). Children keep ABSOLUTE screen coordinates: that is the Screen IR
    geometry contract (verified in the Screen Builder: ``importScreenJSON`` copies
    ``node.geometry`` verbatim and ``WidgetOverlay`` subtracts the parent origin at
    render time). A group's ``visPv`` becomes a ``visible`` rule on the group node
    itself and hides the whole subtree — no inheritance onto individual descendants.

    ``colors`` is the parsed ``colors.list`` palette (see :func:`edm_file_to_ir`), used
    to resolve "index N" color props to hex.
    """
    nodes: list[SourceNode] = []
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            group_node = SourceNode(
                qt_class=None,
                registry_id="group",
                qt_props={"layoutMode": "absolute"},
                geometry=(obj.x, obj.y, obj.width, obj.height),
                raw_class="activeGroupClass",
                raw_props=dict(obj.properties),
                children=edm_group_to_source_nodes(obj, colors=colors),
            )
            group_vis = _vis_tuple(obj.properties)
            if group_vis is not None:
                group_node.rules = [_visibility_rule_spec([group_vis])]
            nodes.append(group_node)
        elif isinstance(obj, EDMObject):
            node = _object_to_source(obj, colors)
            own_vis = _vis_tuple(obj.properties)
            if own_vis is not None:
                node.rules = [_visibility_rule_spec([own_vis])]
            nodes.append(node)
    return nodes


def edm_file_to_ir(
    input_path: str | Path, *, registry: RegistryClient | None = None, color_list_path: str | Path | None = None
) -> ScreenIR:
    """Parse an ``.edl`` file and build its Screen IR.

    ``color_list_path`` points at an EDM ``colors.list`` palette used to resolve
    "index N" color props. When omitted, the palette is located via (in order) the
    ``EDMCOLORFILE`` env var, ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``;
    an explicit ``color_list_path`` wins over all of those. If no palette is found,
    "index N" colors cannot be resolved and are dropped with a node warning ("rgb ..."
    colors resolve without a palette).
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
