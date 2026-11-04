"""Phoebus Display Builder (``.bob``) -> Screen IR orchestrator.

:func:`bob_file_to_ir` wires the ``.bob`` front-end modules together, mirroring
``pydmconverter/edm/ir_adapter.py``:

1. :func:`~pydmconverter.bob.parser.parse_bob` the file and construct the
   :class:`~pydmconverter.ir.builder.IRBuilder` *before* lowering, so formulas interned
   here are numbered ahead of any ``calc://`` hoisting in the builder.
2. File-wide census: the ``loc://`` writer census (sole-writer check of the loc-formula
   matcher) and the hidden local-PV declarers, which become the first root children.
3. Per widget, in document order: the class/prop/defaults/size tables of
   :mod:`~pydmconverter.bob.bob_qt` with value coercion, group geometry, formula PVs,
   rules, the two tier-0 script matchers (alarm boilerplate, then loc-formula), actions
   and the ``meta.comment`` carry-over.
4. Readers of every loc-formula target (widget channels, rule PVs, trace channels) are
   retargeted to ``formula://<name>``; a formula nobody reads warns.
5. ``build_screen`` with the display ``<macros>`` as ``macro_defaults``.

Nothing raises on unmapped input: every problem is a warning on the node of the widget
it concerns.
"""

from __future__ import annotations

import dataclasses
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydmconverter.bob.actions import ActionContext, action_button_label, lower_actions
from pydmconverter.bob.bob_qt import (
    BOB_DEFAULTS,
    BOOL_BUTTON_MODE,
    DISPLAY_BACKGROUND_DEFAULT,
    DISPLAY_DEFAULT_SIZE,
    READBACK_COPY,
    TABS_WARNING,
    TRANSPARENT_BG_RULE_TYPES,
    default_size,
    qt_class_for,
    qt_prop_for,
    rule_coercion,
)
from pydmconverter.bob.coercion import (
    BUILTIN_NAMED_COLORS,
    RGBA,
    alignment,
    color_name_of,
    font_size,
    load_color_def,
    points,
)
from pydmconverter.colors import ColorContext, named_color
from pydmconverter.pairing import NamedColor, pair_text_colors
from pydmconverter.bob.formula_pv import lower_formula_pv
from pydmconverter.bob.gates import FILE_REFERENCE_WARNING, file_reference
from pydmconverter.bob.groups import child_geometry, group_node
from pydmconverter.bob.local_pv import local_pv_key, plan_declarers, rewrite_local_pv
from pydmconverter.bob.meta import build_meta
from pydmconverter.bob.navtabs import NAVTABS_WARNING, navtab_buttons
from pydmconverter.bob.parser import BobDisplay, BobRule, BobWidget, parse_bob, prop_text
from pydmconverter.bob.rules import RuleContext, coerce_value, is_true, lower_rule
from pydmconverter.bob.scripts import ScriptFileContext, build_writer_census, match_alarm_boilerplate, match_loc_formula
from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec, SourceNode
from pydmconverter.ir.transforms import screen_ref
from pydmconverter.scheme import SchemeResult

__all__ = ["SOURCE_TYPE", "bob_file_to_ir"]

SOURCE_TYPE = "bob-converter"
NO_READER_WARNING = "{widget}: formula {name} has no reader ({pv})"
RULE_FORMULA_WARNING = "{widget}: rule {rule!r} needs the script runtime (tier 2): formula binding {pv}"
NO_DEFAULT_WARNING = "{widget}: rule {rule!r} not lowered: its target has no static value"
TRACE_FORMULA_WARNING = "{widget}: trace {trace!r} needs the script runtime (tier 2): formula binding {pv}"

# Phoebus props consumed structurally below, never through the generic prop table.
_STRUCTURAL_PROPS = frozenset(
    {
        "x",
        "y",
        "width",
        "height",
        "pv_name",
        "transparent",
        "horizontal_alignment",
        "vertical_alignment",
        "points",
        "file",
        "macros",
        "mode",
        "on_image",
        "off_image",
        "traces",
        "y_axes",
        "font",
        "format",
        "horizontal",
        "text",
        "arrows",
    }
)
# (widget type, prop) pairs the prop table leaves unmapped because another module reads
# them: ``groups.group_style`` consumes a group's ``style``; ``_xyplot`` consumes an
# xyplot's ``x_axis`` and ``show_legend``. Not recorded as dropped.
_BOB_CONSUMED = frozenset({("group", "style"), ("xyplot", "x_axis"), ("xyplot", "show_legend")})
# Phoebus trace ``point_type`` -> xy-plot curve ``symbol``.
_XY_SYMBOL = {0: "none", 1: "square", 2: "circle", 3: "diamond", 4: "x", 5: "triangle"}
# Phoebus trace ``line_style`` -> Qt::PenStyle (1 solid, 2 dash, 3 dot, 4 dashdot, 5 dashdotdot).
_XY_PEN_STYLE = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
# Phoebus's default trace name ``$(traces[N].y_pv)``: a property path no macro regex expands.
_XY_TRACE_REF = re.compile(r"\$\(traces\[(\d+)\]\.(x_pv|y_pv|name)\)")
_SHAPE_TYPES = frozenset({"rectangle", "ellipse", "polygon"})
_BUTTON_TYPES = frozenset({"action_button", "bool_button"})
_POINT_TYPES = frozenset({"polygon", "polyline"})
_PRECISION_TYPES = frozenset({"textupdate", "textentry"})
# Kinds for props the rule-target table does not name.
_EXTRA_KINDS = {"show_units": "bool", "numBits": "number", "startBit": "number"}
# Phoebus FormatOption ordinal (or name) -> pv-label ``format`` vocabulary.
_FORMAT = {
    "0": "default",
    "1": "default",
    "2": "exponential",
    "3": "exponential",
    "4": "hex",
    "5": "default",
    "6": "string",
    "10": "binary",
    "DEFAULT": "default",
    "DECIMAL": "default",
    "EXPONENTIAL": "exponential",
    "ENGINEERING": "exponential",
    "HEXADECIMAL": "hex",
    "COMPACT": "default",
    "STRING": "string",
    "BINARY": "binary",
}
# Named colour Phoebus paints a colour prop with when the widget has no value of its own.
_RULE_COLOR_FALLBACK = {"background_color": "Background", "foreground_color": "Text"}
# RGBA of :data:`DISPLAY_BACKGROUND_DEFAULT`, the display background Phoebus paints when none is set.
_DISPLAY_BACKGROUND_RGB: RGBA = (255, 255, 255, 255)
# Phoebus polyline ``<arrows>``: 0 NONE, 1 FROM, 2 TO, 3 BOTH.
_ARROW_START = frozenset({1, 3})
_ARROW_END = frozenset({2, 3})

Geometry = tuple[Any, Any, Any, Any]


# --------------------------------------------------------------------------
# Lowering state
# --------------------------------------------------------------------------
@dataclass
class _FormulaCtx:
    """The context :func:`lower_formula_pv` needs: the builder and a warning sink."""

    builder: IRBuilder
    warnings: list[str]

    def warn(self, message: str) -> None:
        """Record a conversion warning."""
        self.warnings.append(message)


@dataclass
class _Target:
    """A loc-formula interned from a script, awaiting its readers."""

    name: str
    pv: str
    widget: str
    node: SourceNode
    readers: int = 0


@dataclass
class _File:
    """File-wide lowering state shared by every widget."""

    builder: IRBuilder
    registry: RegistryClient
    named: dict[str, RGBA] | None
    script_ctx: ScriptFileContext
    base_dir: Path | None
    confine_file_refs: bool
    declarer_warnings: dict[str, list[str]] = field(default_factory=dict)
    targets: dict[str, _Target] = field(default_factory=dict)
    color: ColorContext | None = None
    # id(node) -> {qt prop: (source colour name, RGBA, Phoebus prop)} for the pairing pass.
    named_props: dict[int, dict[str, NamedColor]] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _number(value: object, default: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        number = float(value)
    except ValueError:
        return default
    return int(number) if number.is_integer() else number


def _int(value: object, default: int) -> int:
    number = _number(value, default)
    return int(number) if isinstance(number, (int, float)) else default


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(messages))


def _raw_props(widget: BobWidget) -> dict[str, Any]:
    """Widget props as JSON-safe values for an ``unknown-widget`` ``originalProps``."""
    out: dict[str, Any] = {"name": widget.name}
    for key, value in widget.props.items():
        out[key] = ET.tostring(value, encoding="unicode").strip() if isinstance(value, ET.Element) else value
    return out


def _size(widget: BobWidget) -> tuple[Any, Any]:
    """(width, height): authored, else the points' bounding box (shapes), else the table."""
    default_w, default_h = default_size(widget.type)
    if widget.type in _POINT_TYPES:
        pts = points(widget.props.get("points"))
        if pts:
            default_w = max(x for x, _y in pts)
            default_h = max(y for _x, y in pts)
    return _number(widget.props.get("width"), default_w), _number(widget.props.get("height"), default_h)


def _geometry(widget: BobWidget, parent: BobWidget | None, origin: tuple[Any, Any]) -> Geometry:
    """Absolute geometry of ``widget``; ``origin`` is the parent's absolute origin."""
    width, height = _size(widget)
    if parent is not None and parent.type == "group":
        x, y, _w, _h = child_geometry(parent, widget, origin=(origin[0], origin[1]))
        return (x, y, width, height)
    return (
        origin[0] + _number(widget.props.get("x"), 0),
        origin[1] + _number(widget.props.get("y"), 0),
        width,
        height,
    )


def _default_value(key: str, value: Any) -> Any:
    """A ``BOB_DEFAULTS`` value as the adapter lowers it.

    A colour default that names a Phoebus widget colour becomes the element
    ``<key><color name="..."/></key>``, so it resolves like an authored named colour
    (``color.def``, scheme role) and a parity note names the prop it colours.
    """
    if rule_coercion(key) == "color" and isinstance(value, str) and not value.startswith("#"):
        element = ET.Element(key)
        ET.SubElement(element, "color", name=value)
        return element
    return value


def _effective_props(widget: BobWidget) -> dict[str, Any]:
    """Authored props overlaid on the per-type defaults (defaults only where absent)."""
    props: dict[str, Any] = dict(widget.props)
    for key, value in BOB_DEFAULTS.get(widget.type, {}).items():
        if key not in props:
            props[key] = _default_value(key, value)
    return props


# --------------------------------------------------------------------------
# Per-widget lowering
# --------------------------------------------------------------------------
class _WidgetLowering:
    """Lowers one :class:`BobWidget` (without its children) into a :class:`SourceNode`."""

    def __init__(self, widget: BobWidget, state: _File, geometry: Geometry) -> None:
        self.widget = widget
        self.state = state
        self.geometry = geometry
        self.name = widget.name
        self.warnings: list[str] = []
        self.rule_ctx = RuleContext(
            registry=state.registry, named_colors=state.named, warnings=self.warnings, color=state.color
        )
        self.action_ctx = ActionContext(warnings=self.warnings)
        self.formula_ctx = _FormulaCtx(builder=state.builder, warnings=self.warnings)
        self.declined: list[str] = []
        self.qt_props: dict[str, Any] = {}
        self.dropped_props: list[str] = []
        self.rules: list[RuleSpec] = []
        self.targets: list[tuple[str, str, str]] = []  # (key, formula name, target pv)
        self.unknown = False
        self._script_actions: list[dict] = []
        self.named_props: dict[str, NamedColor] = {}

    # -- helpers ------------------------------------------------------------
    def warn(self, message: str) -> None:
        """Record a conversion warning."""
        self.warnings.append(message)

    def coerce(self, kind: str, value: Any) -> Any:
        """Coerce a raw ``.bob`` value to the IR type named by ``kind``."""
        return coerce_value(kind, value, self.rule_ctx, self.name)

    def channel(self, text: str) -> str | None:
        """A PV prop value: formula PVs interned, local PVs rewritten, macros normalised."""
        raw = text.strip()
        if not raw:
            return None
        if raw.startswith("="):
            return lower_formula_pv(raw, self.formula_ctx, widget=self.name)
        return normalize_macro_syntax(rewrite_local_pv(raw, self.warn, widget=self.name))

    # -- entry ----------------------------------------------------------------
    def lower(self) -> SourceNode:
        """Lower this widget (and its children) to a ``SourceNode``."""
        widget = self.widget
        mapped = qt_class_for(widget.type)
        registry_id: str | None
        qt_class: str | None
        if widget.type == "group":
            qt_class, registry_id, group_props = group_node(widget)
            self.qt_props.update(group_props)
            if registry_id == "group":
                self.qt_props["layoutMode"] = "absolute"
        elif widget.type == "navtabs":
            # A frameless group holding one open-display button per tab (navtabs.py).
            qt_class, registry_id = None, "group"
            self.qt_props["layoutMode"] = "absolute"
            self.warn(NAVTABS_WARNING.format(widget=self.name))
        elif mapped is not None:
            qt_class, registry_id = mapped
        else:
            qt_class, registry_id = None, None
            self.unknown = True
            if widget.type == "tabs":
                self.warn(TABS_WARNING.format(widget=self.name))

        for message in self.state.declarer_warnings.pop(self.name, []):
            self.warn(message)

        if not self.unknown and widget.type != "navtabs":
            self._props()
        self._rules(registry_id)
        unlowered_scripts = self._scripts(registry_id)
        actions = lower_actions(widget, self.action_ctx) + self._script_actions
        if widget.type == "action_button":
            self.qt_props["text"] = action_button_label(widget)
            self.qt_props["actions"] = actions
        elif actions:
            self.qt_props["actions"] = actions

        meta = build_meta(
            widget,
            unlowered_scripts,
            self.action_ctx.carried,
            self.declined,
            base_dir=self.state.base_dir,
            confine_file_refs=self.state.confine_file_refs,
            warn=self.warn,
        )
        if self.unknown:
            qt_class, registry_id = None, None
        return SourceNode(
            qt_class=qt_class,
            qt_props=self.qt_props,
            registry_id=registry_id,
            geometry=self.geometry,
            rules=self.rules,
            raw_class=widget.type,
            raw_props=_raw_props(widget) if self.unknown else {},
            warnings=self.warnings,
            meta=meta,
            dropped_props=self.dropped_props,
        )

    # -- props ----------------------------------------------------------------
    def _props(self) -> None:
        widget = self.widget
        wtype = widget.type
        props = _effective_props(widget)

        for prop, value in props.items():
            if prop in _STRUCTURAL_PROPS:
                continue
            qt_prop = qt_prop_for(wtype, prop)
            if qt_prop is None:
                if (wtype, prop) not in _BOB_CONSUMED:
                    self.dropped_props.append(prop)
                continue
            kind = _EXTRA_KINDS.get(prop) or rule_coercion(prop)
            coerced = self.coerce(kind, value)
            if coerced is not None:
                self.qt_props[qt_prop] = coerced
                if kind == "color":
                    named = color_name_of(value, self.state.named, self.state.color)
                    if named is not None:
                        self.named_props[qt_prop] = (*named, prop)

        self._pv(props)
        self._text(props)
        self._font(props)
        self._alignment(props)
        self._transparent(props)
        self._format(props)
        self._precision()
        if wtype in _POINT_TYPES:
            self._points(props)
        if "horizontal" in props and qt_prop_for(wtype, "horizontal"):
            self.qt_props["orientation"] = "horizontal" if self.coerce("bool", props["horizontal"]) else "vertical"
        if wtype == "bool_button":
            self._bool_button(props)
        elif wtype == "embedded":
            self._embedded(props)
        elif wtype == "picture":
            self._file_prop(props, "file", "filename")
        elif wtype == "xyplot":
            self._xyplot(props)

    def _pv(self, props: dict[str, Any]) -> None:
        qt_prop = qt_prop_for(self.widget.type, "pv_name")
        text = prop_text(props.get("pv_name"))
        if qt_prop is None or not text.strip():
            return
        channel = self.channel(text)
        if channel is None:
            # A declined formula PV: the registry schemas require a pv, so the node
            # becomes an unknown-widget and the text is carried in meta.comment.
            self.declined.append(text)
            self.unknown = True
            return
        self.qt_props[qt_prop] = channel
        copy = READBACK_COPY.get(self.widget.type)
        if copy is not None and copy[0] == qt_prop:
            self.qt_props[copy[1]] = channel

    def _text(self, props: dict[str, Any]) -> None:
        if self.widget.type == "action_button" or "text" not in props:
            return
        qt_prop = qt_prop_for(self.widget.type, "text")
        if qt_prop is not None:
            self.qt_props[qt_prop] = self.coerce("str", prop_text(props["text"]))

    def _font(self, props: dict[str, Any]) -> None:
        size = font_size(props.get("font"))
        if size is not None:
            self.qt_props["fontSize"] = size

    def _alignment(self, props: dict[str, Any]) -> None:
        if "horizontal_alignment" not in props and "vertical_alignment" not in props:
            return
        horizontal = prop_text(props.get("horizontal_alignment")) or "0"
        vertical = prop_text(props.get("vertical_alignment")) or None
        self.qt_props["alignment"] = alignment(horizontal, vertical)

    def _transparent(self, props: dict[str, Any]) -> None:
        wtype = self.widget.type
        if wtype in _SHAPE_TYPES:
            self.qt_props["brushFill"] = not is_true(props.get("transparent"), self.rule_ctx, self.name)
        elif wtype in TRANSPARENT_BG_RULE_TYPES and is_true(props.get("transparent"), self.rule_ctx, self.name):
            self.qt_props.pop("backgroundColor", None)
        elif wtype in _BUTTON_TYPES and is_true(props.get("transparent"), self.rule_ctx, self.name):
            # Ruling 7: no painted chrome; label and press/release handlers stay.
            self.qt_props["flat"] = True

    def _format(self, props: dict[str, Any]) -> None:
        if "format" not in props or qt_prop_for(self.widget.type, "format") is None:
            return
        self.qt_props["displayFormat"] = _FORMAT.get(prop_text(props["format"]).strip().upper(), "default")

    def _precision(self) -> None:
        """Phoebus ``precision`` -1 means "use the PV"; 0 and up is the widget's own.

        An own precision is written with ``precisionFromPV: false``, since an IR
        ``precision`` alone means the PV's precision wins."""
        if self.widget.type not in _PRECISION_TYPES or "precision" not in self.qt_props:
            return
        value = self.qt_props["precision"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return
        if value >= 0:
            self.qt_props["precisionFromPV"] = False
        else:
            del self.qt_props["precision"]

    def _points(self, props: dict[str, Any]) -> None:
        pts = points(props.get("points"))
        self.qt_props["points"] = [{"x": x, "y": y} for x, y in pts]
        if self.widget.type == "polygon":
            self.qt_props["closePolygon"] = True
        else:
            arrows = _int(props.get("arrows"), 0)
            self.qt_props["arrowStartPoint"] = arrows in _ARROW_START
            self.qt_props["arrowEndPoint"] = arrows in _ARROW_END

    def _bool_button(self, props: dict[str, Any]) -> None:
        mode = _int(props.get("mode"), 0)
        self.qt_props.update(BOOL_BUTTON_MODE.get(mode, BOOL_BUTTON_MODE[0]))
        for prop, qt_prop in (("on_image", "onImage"), ("off_image", "offImage")):
            self._file_prop(props, prop, qt_prop)

    def _file_prop(self, props: dict[str, Any], prop: str, qt_prop: str) -> None:
        """Set ``qt_prop`` from the file named by ``prop`` when it is a file path; else warn."""
        raw = prop_text(props.get(prop)).strip()
        if not raw:
            return
        file = file_reference(raw)
        if file is None:
            self.warn(FILE_REFERENCE_WARNING.format(widget=self.name, what=prop, reference=raw))
        else:
            self.qt_props[qt_prop] = file

    def _embedded(self, props: dict[str, Any]) -> None:
        self._file_prop(props, "file", "filename")
        if self.widget.macros:
            self.qt_props["macros"] = {k: normalize_macro_syntax(v) for k, v in self.widget.macros.items()}

    def _xyplot(self, props: dict[str, Any]) -> None:
        traces = props.get("traces")
        trace_list = traces.findall("trace") if isinstance(traces, ET.Element) else []
        curves: list[dict[str, Any]] = []
        for index, trace in enumerate(trace_list):
            curve = self._curve(trace, index, trace_list)
            if curve is not None:
                curves.append(curve)
        self.qt_props["curves"] = curves
        x_axis = props.get("x_axis")
        self.qt_props["xAxis"] = self._axis(x_axis if isinstance(x_axis, ET.Element) else None, "x", "X")
        axes = props.get("y_axes")
        y_axis_list = axes.findall("y_axis") if isinstance(axes, ET.Element) else []
        self.qt_props["yAxes"] = [self._axis(axis, f"y{i}", "Y") for i, axis in enumerate(y_axis_list)] or [
            self._axis(None, "y0", "Y")
        ]
        legend = props.get("show_legend")
        # Phoebus shows the legend by default and its writer omits the default value.
        self.qt_props["showLegend"] = is_true(legend, self.rule_ctx, self.name) if legend is not None else True

    def _axis(self, axis: ET.Element | None, name: str, default_label: str) -> dict[str, Any]:
        """One Phoebus axis -> an xy-plot axis; absent fields take Phoebus's defaults."""

        def flag(tag: str, default: bool) -> bool:
            element = axis.find(tag) if axis is not None else None
            return is_true(element, self.rule_ctx, self.name) if element is not None else default

        title = axis.find("title") if axis is not None else None
        label = default_label if title is None else normalize_macro_syntax((title.text or "").strip())
        return {
            "name": name,
            "label": label,
            "minRange": _number(axis.findtext("minimum") if axis is not None else None, 0),
            "maxRange": _number(axis.findtext("maximum") if axis is not None else None, 100),
            "autoRange": flag("autoscale", False),
            "logMode": flag("log_scale", False),
            "grid": flag("show_grid", False),
            "visible": flag("visible", True),
        }

    def _curve(self, trace: ET.Element, index: int, traces: list[ET.Element] | None = None) -> dict[str, Any] | None:
        name = self._trace_name(trace, traces or [trace])
        curve: dict[str, Any] = {"name": name}
        for tag, key in (("x_pv", "x_channel"), ("y_pv", "y_channel")):
            text = (trace.findtext(tag) or "").strip()
            if not text:
                continue
            channel = self.channel(text)
            if channel is None:
                self.declined.append(text)
                self.warn(TRACE_FORMULA_WARNING.format(widget=self.name, trace=name or f"trace {index}", pv=text))
                return None
            curve[key] = channel
        color = trace.find("color")
        if color is not None and color.find("color") is not None:
            color = color.find("color")  # <color><color red=.../></color>
        if color is not None:
            hexed = self.coerce("color", color)
            if hexed is not None:
                curve["color"] = hexed
        curve["lineWidth"] = _number(trace.findtext("line_width"), 1)
        curve["lineStyle"] = _XY_PEN_STYLE.get(_int(trace.findtext("line_style"), 0), 1)
        curve["symbol"] = _XY_SYMBOL.get(_int(trace.findtext("point_type"), 0), "none")
        curve["symbolSize"] = _number(trace.findtext("point_size"), 10)
        curve["traceType"] = "none" if _int(trace.findtext("trace_type"), 1) == 0 else "line"
        curve["yAxisName"] = f"y{_int(trace.findtext('axis'), 0)}"
        return curve

    @staticmethod
    def _trace_name(trace: ET.Element, traces: list[ET.Element]) -> str:
        """The legend name: ``<name>``, else ``y_pv``; ``$(traces[N].field)`` resolves to trace N's field."""

        def text(element: ET.Element, tag: str) -> str:
            return normalize_macro_syntax((element.findtext(tag) or "").strip())

        element = trace.find("name")
        if element is None:
            return text(trace, "y_pv")
        name = normalize_macro_syntax((element.text or "").strip())
        match = _XY_TRACE_REF.fullmatch(name)
        if match is None or int(match.group(1)) >= len(traces):
            return name
        target, field_name = traces[int(match.group(1))], match.group(2)
        if field_name == "name" and target.find("name") is None:
            return text(target, "y_pv")
        return text(target, field_name)

    # -- rules ----------------------------------------------------------------
    def _rule_pvs(self, rule: BobRule) -> list[tuple[str, bool]] | None:
        """The rule's PVs with formulas interned; ``None`` (warned) if one is declined."""
        pvs: list[tuple[str, bool]] = []
        for pv, trigger in rule.pvs:
            text = pv.strip()
            if text.startswith("="):
                ref = lower_formula_pv(text, self.formula_ctx, widget=self.name)
                if ref is None:
                    self.declined.append(text)
                    self.warn(RULE_FORMULA_WARNING.format(widget=self.name, rule=rule.name, pv=text))
                    return None
                pvs.append((ref, trigger))
            elif text.startswith("loc://"):
                # Readers stay short-form; initializers live in the declarers.
                pvs.append((local_pv_key(text), trigger))
            else:
                pvs.append((pv, trigger))
        return pvs

    def _lower_rule(self, rule: BobRule, registry_id: str | None) -> RuleSpec | None:
        """Lower ``rule`` with its colour arms slotted on the rule's property (``Grid`` as fill vs line)."""
        color = self.rule_ctx.color
        if color is None:
            return lower_rule(rule, self.widget, self.rule_ctx, registry_id=registry_id)
        self.rule_ctx.color = color.with_slot(rule.prop_id)
        try:
            return lower_rule(rule, self.widget, self.rule_ctx, registry_id=registry_id)
        finally:
            self.rule_ctx.color = color

    def _rules(self, registry_id: str | None) -> None:
        for rule in self.widget.rules:
            pvs = self._rule_pvs(rule)
            if pvs is None:
                continue
            spec = self._lower_rule(dataclasses.replace(rule, pvs=pvs), registry_id)
            if spec is None:
                continue
            if spec.default is None:
                # The IR requires a rule default; a colour with no static value and no
                # table default is Phoebus's named widget colour for that prop.
                fallback = _RULE_COLOR_FALLBACK.get(rule.prop_id)
                if fallback is None:
                    self.warn(NO_DEFAULT_WARNING.format(widget=self.name, rule=rule.name))
                    continue
                table = self.state.named or BUILTIN_NAMED_COLORS
                spec.default = named_color(fallback, table[fallback], rule.prop_id, self.state.color)
            self.rules.append(spec)

    # -- scripts --------------------------------------------------------------
    def _scripts(self, registry_id: str | None) -> list:
        unlowered = []
        script_ctx = self.state.script_ctx
        for script in self.widget.scripts:
            before = len(self.warnings)
            spec = match_alarm_boilerplate(script, self.widget, self.rule_ctx, registry_id=registry_id)
            if spec is not None:
                self.rules.append(spec)
                continue
            if len(self.warnings) > before:
                unlowered.append(script)  # boilerplate, but skipped with a warning
                continue
            mark = len(script_ctx.warnings)
            candidate = match_loc_formula(script, self.widget, script_ctx)
            self.warnings.extend(script_ctx.warnings[mark:])
            del script_ctx.warnings[mark:]
            if candidate is None:
                unlowered.append(script)
                continue
            self._script_actions.extend(candidate.actions)
            if candidate.expression is not None and candidate.target_key is not None:
                name = self.state.builder.formulas.intern(candidate.expression, candidate.bindings)
                self.targets.append((candidate.target_key, name, candidate.target_pv or candidate.target_key))
        return unlowered


# --------------------------------------------------------------------------
# Tree walk
# --------------------------------------------------------------------------
def _lower_tree(
    widgets: list[BobWidget], state: _File, parent: BobWidget | None, origin: tuple[Any, Any]
) -> list[SourceNode]:
    nodes: list[SourceNode] = []
    for widget in widgets:
        geometry = _geometry(widget, parent, origin)
        lowering = _WidgetLowering(widget, state, geometry)
        node = lowering.lower()
        if lowering.named_props:
            state.named_props[id(node)] = lowering.named_props
        for key, name, pv in lowering.targets:
            state.targets.setdefault(key, _Target(name=name, pv=pv, widget=widget.name, node=node))
        if widget.type == "navtabs":
            node.children = navtab_buttons(widget, (geometry[0], geometry[1]), node.warnings.append)
        else:
            node.children = _lower_tree(widget.children, state, widget, (geometry[0], geometry[1]))
        nodes.append(node)
    return nodes


def _retarget_value(value: Any, targets: dict[str, _Target]) -> Any:
    if isinstance(value, str) and value.strip().startswith("loc://"):
        target = targets.get(local_pv_key(value))
        if target is not None:
            target.readers += 1
            return f"formula://{target.name}"
    return value


def _retarget(nodes: list[SourceNode], targets: dict[str, _Target]) -> None:
    """Point every reader of a loc-formula target at its ``formula://`` formula."""
    for node in nodes:
        props = node.qt_props
        for key in ("channel", "readbackChannel"):
            if key in props:
                props[key] = _retarget_value(props[key], targets)
        for curve in props.get("curves", []) if isinstance(props.get("curves"), list) else []:
            for key in ("x_channel", "y_channel"):
                if key in curve:
                    curve[key] = _retarget_value(curve[key], targets)
        for rule in node.rules:
            rule.pvs = [(_retarget_value(pv, targets), trigger) for pv, trigger in rule.pvs]
        _retarget(node.children, targets)


def _screen_size(display: BobDisplay) -> tuple[Any, Any]:
    default_w, default_h = DISPLAY_DEFAULT_SIZE
    return _number(display.props.get("width"), default_w), _number(display.props.get("height"), default_h)


def _macro_defaults(display: BobDisplay) -> dict[str, str] | None:
    defaults: dict[str, str] = {}
    for name, value in display.macros.items():
        text = normalize_macro_syntax(value)
        if text.strip().lower().endswith((".bob", ".opi")):
            text = screen_ref(text)
        defaults[name] = text
    return defaults or None


def _display_to_ir(
    display: BobDisplay,
    *,
    screen_id: str,
    registry: RegistryClient | None,
    color_def_path: str | Path | None,
    scheme: SchemeResult | None = None,
    confine_file_refs: bool = False,
) -> ScreenIR:
    registry = registry or VendoredRegistry()
    builder = IRBuilder(registry)
    file_warnings: list[str] = []
    named = load_color_def(color_def_path, file_warnings) if color_def_path else None
    color = None if scheme is None else ColorContext.from_scheme(scheme, named or dict(BUILTIN_NAMED_COLORS))

    declarer_warnings: list[str] = []
    declarers = plan_declarers(display.widgets, registry, warn=declarer_warnings.append)
    state = _File(
        builder=builder,
        registry=registry,
        named=named,
        script_ctx=ScriptFileContext(writers=build_writer_census(display.widgets)),
        base_dir=display.path.parent if display.path is not None else None,
        confine_file_refs=confine_file_refs,
        color=color,
    )
    for message in declarer_warnings:
        widget = message.split(": ", 1)[0]
        state.declarer_warnings.setdefault(widget, []).append(message)

    nodes = _lower_tree(display.widgets, state, None, (0, 0))
    _retarget(nodes, state.targets)
    for target in state.targets.values():
        if target.readers == 0:
            target.node.warnings.append(NO_READER_WARNING.format(widget=target.widget, name=target.name, pv=target.pv))
    background = None
    bg = display.props.get("background_color")
    if isinstance(bg, ET.Element):
        background = coerce_value(
            "color", bg, RuleContext(named_colors=named, warnings=file_warnings, color=color), "display"
        )
    elif color is not None:
        # An undeclared display background is the scheme's Display_Background when its
        # light value is Phoebus's white; otherwise the literal white, with a parity note.
        background = named_color("Display_Background", _DISPLAY_BACKGROUND_RGB, "background_color", color)
    # Text and the ground under it become roles together or stay literal together.
    background = pair_text_colors(
        nodes,
        background or DISPLAY_BACKGROUND_DEFAULT,
        color,
        lambda node, prop: state.named_props.get(id(node), {}).get(prop),
    )
    # Scheme parity notes are aggregated over the whole document and lead the file warnings.
    if color is not None:
        file_warnings[:0] = color.parity_notes()
    # File-level problems (color.def parse errors, the display background) have no
    # widget of their own; they land on the first widget node so none is lost.
    if file_warnings and nodes:
        nodes[0].warnings[:0] = file_warnings
    _finalise_warnings(nodes)
    return builder.build_screen(
        screen_id=screen_id,
        title=screen_id,
        source_type=SOURCE_TYPE,
        size=_screen_size(display),
        top_level=declarers + nodes,
        background=background or DISPLAY_BACKGROUND_DEFAULT,
        macro_defaults=_macro_defaults(display),
    )


def _finalise_warnings(nodes: list[SourceNode]) -> None:
    for node in nodes:
        node.warnings = _dedupe(node.warnings)
        _finalise_warnings(node.children)


def bob_file_to_ir(
    path: str | Path,
    *,
    registry: RegistryClient | None = None,
    color_def_path: str | Path | None = None,
    scheme: SchemeResult | None = None,
    confine_file_refs: bool = False,
) -> ScreenIR:
    """Parse a Phoebus ``.bob`` file and build its Screen IR.

    ``color_def_path`` names a Phoebus ``color.def`` whose entries overlay the built-in
    named colours (``<color name="...">``). With a flattened colour ``scheme``, named
    colours the scheme imports become roles under the parity rule
    (:func:`~pydmconverter.colors.named_color`); ``None`` keeps today's literal hex. ``registry`` defaults to the vendored
    widget registry. The screen id and title are the file stem. Raises
    :class:`~pydmconverter.bob.parser.BobParseError` on malformed XML; every other
    problem becomes a warning on the node it concerns. ``confine_file_refs`` is for
    untrusted input: a script or execute-action file is read only when it resolves inside
    the file's directory, and every one refused is a warning on its node.
    """
    source = Path(path)
    display = parse_bob(source, confine_file_refs=confine_file_refs)
    return _display_to_ir(
        display,
        screen_id=source.stem,
        registry=registry,
        color_def_path=color_def_path,
        scheme=scheme,
        confine_file_refs=confine_file_refs,
    )
