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
unknown-widget. activeXTextDspClass is a read-only pv-label unless its
``editable`` flag is set (then pv-text-input), matching EDM's default.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Callable, Sequence

from pydmconverter.edm.edm_qt import (
    EDM_PRIMARY_CHANNEL_ORDER,
    EDM_READBACK_CHANNEL_ORDER,
    EDM_TO_QT_PROP,
    resolve_qt_class,
)
from pydmconverter.edm.parser import EDMFileParser, EDMGroup, EDMObject, block_items
from pydmconverter.edm.parser_helpers import (
    get_color_by_index,
    get_color_by_rgb,
    parse_colors_list,
    parse_edm_macros,
    rule_static_color,
    search_color_list,
    static_color_by_name,
)
from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.model import Number, ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec, SourceNode, conversion_failure
from pydmconverter.ir.transforms import screen_ref

logger = logging.getLogger(__name__)

# An EDM visibility spec: (visPv, visMin, visMax, visInvert). visMin/visMax are
# numbers (EDM atof semantics, see _vis_limit), or None when the EDM object only
# declares visPv (visible-when-nonzero).
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
_COLOR_PROPS = {"penColor", "brushColor", "foregroundColor", "backgroundColor", "onColor", "offColor"}
# EDM font string "family-weight-slant-size" -> pixel size for the IR fontSize.
_FONT_PROPS = {"fontSize"}
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


def _to_font_size(value: Any) -> Any:
    """EDM font string ("helvetica-bold-r-12.0") -> integer pixel size.

    EDM bitmap-font sizes render ~1:1 as CSS pixels. Malformed values drop the
    prop (returning None) rather than guessing a size.
    """
    if not isinstance(value, str):
        return None
    tail = value.rsplit("-", 1)[-1]
    try:
        size = float(tail)
    except ValueError:
        return None
    return max(6, round(size)) if size > 0 else None


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
    if qt_prop in _FONT_PROPS:
        return _to_font_size(value)
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

    return color_info_to_hex(color_info, color_data)


def color_info_to_hex(color_info: dict[str, Any] | None, color_data: dict[str, Any] | None) -> str | None:
    """A parsed colour entry (``{"rgb": [...]}``) -> "#rrggbb" (first state of a blinking colour)."""
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


# Classes whose registry definition maps a readback channel (readbackChannel ->
# pv-button's readbackPV). Elsewhere a second data channel has nowhere to land
# and is dropped with a warning. Menu buttons pair controlPv with an
# indicatorPv readback exactly like plain buttons (batch-2: cbxfel camera rows).
_READBACK_CLASSES = {"activebuttonclass", "activemessagebuttonclass", "activemenubuttonclass"}

# EDM alarm-severity palette (green / yellow / red / white-invalid) — what an
# alarm-sensitive EDM part shows instead of its configured static color. Used
# when no colors.list ``alarm { }`` block is available; a palette's block wins
# (see _alarm_palette).
_ALARM_RULE_CONDITIONS: list[tuple[str, str]] = [
    ("{0} == 1", "#ffff00"),
    ("{0} == 2", "#ff0000"),
    ("{0} >= 3", "#ffffff"),
]
_ALARM_RULE_DEFAULT = "#00c000"
# colors.list alarm-block key per severity condition above, in the same order.
_ALARM_SEVERITY_KEYS = ("minor", "major", "invalid")
# Marker: NO_ALARM shows the part's own static colour (alarm block "noalarm : *").
_STATIC_COLOR = "static"


def _named_color_hex(colors: dict[str, Any] | None, name: str) -> str | None:
    return color_info_to_hex(static_color_by_name(colors or {}, name), colors)


def _alarm_palette(colors: dict[str, Any] | None) -> tuple[list[tuple[str, str]], str]:
    """Severity conditions and the NO_ALARM colour for alarm rules, from the palette.

    EDM (color_pkg.cc, pvColor.cc) paints an alarm-sensitive part with the
    colors.list ``alarm { }`` block's minor/major/invalid colours. ``noalarm : *``
    means NO_ALARM keeps the part's own colour (returned as :data:`_STATIC_COLOR`),
    a named colour replaces it, and an entry the block leaves out is palette
    index 0 (EDM's specialIndex default). Without an alarm block the fixed
    green/yellow/red/white palette applies (the converter's long-standing default).
    """
    alarm = (colors or {}).get("alarm") or {}
    if not alarm:
        return list(_ALARM_RULE_CONDITIONS), _ALARM_RULE_DEFAULT
    index_zero = edm_color_to_hex("index 0", colors)

    def resolve(key: str, default: str) -> str:
        name = alarm.get(key)
        return (_named_color_hex(colors, name) if name else index_zero) or default

    conditions = [
        (expr, resolve(key, fixed)) for key, (expr, fixed) in zip(_ALARM_SEVERITY_KEYS, _ALARM_RULE_CONDITIONS)
    ]
    if alarm.get("noalarm") == "*":
        return conditions, _STATIC_COLOR
    return conditions, resolve("noalarm", _ALARM_RULE_DEFAULT)


# alarm flag -> IR target prop, per class family. Targets are IR prop names
# (RuleSpecs pass through the builder untranslated).
_DRAWING_ALARM_TARGETS = (("lineAlarm", "lineColor"), ("fillAlarm", "fillColor"))
_LABEL_ALARM_TARGETS = (("fgAlarm", "foregroundColor"), ("bgAlarm", "backgroundColor"))
_DRAWING_CLASSES = {"activerectangleclass", "activecircleclass", "activelineclass", "activearcclass"}
_LABEL_ALARM_CLASSES = {
    "activextextclass",
    "textupdateclass",
    "multilinetextupdateclass",
    "activexregtextclass",
    "regtextupdateclass",
    "activextextdspclassnoedit",
}

# A trailing EPICS field ref (".RBV", ".PLOK") — severity is record-level, so it
# is stripped before appending .SEVR.
_FIELD_SUFFIX_RE = re.compile(r"\.[A-Z][A-Z0-9]*$")


def _severity_channel(pv: str) -> str:
    """The CA channel carrying the alarm severity of ``pv``'s record."""
    if pv.endswith(".SEVR"):
        return pv
    return _FIELD_SUFFIX_RE.sub("", pv) + ".SEVR"


# IR colour target -> the Qt prop holding the part's resolved static colour.
_TARGET_STATIC_QT_PROP = {
    "lineColor": "penColor",
    "fillColor": "brushColor",
    "foregroundColor": "foregroundColor",
    "backgroundColor": "backgroundColor",
    "onColor": "onColor",
    "offColor": "offColor",
}


def _alarm_rules(
    obj: EDMObject, colors: dict[str, Any] | None = None, qt_props: dict[str, Any] | None = None
) -> list[RuleSpec]:
    """EDM alarmPv + alarm flags -> alarm-color RuleSpecs (EDM severity palette).

    EDM semantics: an alarm-sensitive part tracks the alarm severity of
    ``alarmPv``: MINOR/MAJOR/INVALID paint the palette's alarm colours, and
    NO_ALARM paints what the palette's ``noalarm`` entry says — with the SLAC
    ``noalarm : *`` that is the part's own static colour (taken from
    ``qt_props``). Without a palette alarm block NO_ALARM is green (see
    :func:`_alarm_palette`). Flags select what tracks: lineAlarm/fillAlarm on
    drawing classes, fgAlarm/bgAlarm on label classes. alarmPv without any flag
    (or a flag without alarmPv) does nothing, matching EDM.
    """
    alarm_pv = obj.properties.get("alarmPv")
    if isinstance(alarm_pv, list):
        alarm_pv = alarm_pv[0] if alarm_pv else ""
    if not alarm_pv:
        return []
    alarm_pv = normalize_macro_syntax(str(alarm_pv))
    name_lower = obj.name.lower()
    if name_lower in _DRAWING_CLASSES:
        targets = _DRAWING_ALARM_TARGETS
    elif name_lower in _LABEL_ALARM_CLASSES:
        targets = _LABEL_ALARM_TARGETS
    else:
        return []
    conditions, no_alarm = _alarm_palette(colors)
    rules: list[RuleSpec] = []
    for flag, target in targets:
        if obj.properties.get(flag):
            default = no_alarm
            if default == _STATIC_COLOR:
                # The part's own colour; one that did not resolve leaves the
                # fixed green rather than a rule with no NO_ALARM colour.
                default = (qt_props or {}).get(_TARGET_STATIC_QT_PROP[target]) or _ALARM_RULE_DEFAULT
            rules.append(
                RuleSpec(
                    target_property=target,
                    name=f"Alarm color ({target})",
                    pvs=[(_severity_channel(alarm_pv), True)],
                    conditions=list(conditions),
                    default=default,
                )
            )
    return rules


# ── colors.list rule colours ──────────────────────────────────────────────────
#
# A rule colour index is dynamic: EDM calls colorInfoClass::evalRule(index, v)
# with a PV value v and paints the first condition's colour that holds (else
# the rule's static colour = its first result colour). Which PV supplies v is
# per class (EDM baselib/pvFactory sources, the evalRule call sites):
#   rectangle/circle/arc/line, xText, xRegText: alarmPv (line/fill, fg/bg)
#   xTextDsp(:noedit): colorPv (fg and bg)
#   Textupdate/RegTextupdate: fg from colorPv, else the controlPv; the fill
#     colour's helper is never fed a value, so it is evalRule(index, 0) — static
#   Button/MessageButton: colorPv (on, off, fg); MenuButton/UpDown/Ramp: colorPv (bg, fg)
#   relatedDisplay: colorPv (fg, bg)
# Everything else never evaluates rules and shows the static colour.
_RULE_COLOR_DRIVERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    **{
        name: (("alarmPv",), ("lineColor", "fillColor"))
        for name in ("activerectangleclass", "activecircleclass", "activearcclass", "activelineclass")
    },
    "activextextclass": (("alarmPv",), ("fgColor", "bgColor")),
    "activexregtextclass": (("alarmPv",), ("fgColor", "bgColor")),
    "activextextdspclass": (("colorPv",), ("fgColor", "bgColor")),
    "activextextdspclassnoedit": (("colorPv",), ("fgColor", "bgColor")),
    "textupdateclass": (("colorPv", "controlPv"), ("fgColor",)),
    "regtextupdateclass": (("colorPv", "controlPv"), ("fgColor",)),
    "activebuttonclass": (("colorPv",), ("onColor", "offColor", "fgColor")),
    "activemessagebuttonclass": (("colorPv",), ("onColor", "offColor", "fgColor")),
    "activemenubuttonclass": (("colorPv",), ("bgColor", "fgColor")),
    "activeupdownbuttonclass": (("colorPv",), ("bgColor", "fgColor")),
    "activerampbuttonclass": (("colorPv",), ("bgColor", "fgColor")),
    "relateddisplayclass": (("colorPv",), ("fgColor", "bgColor")),
}
# Colour attrs EDM evaluates at a fixed value of 0 (a ColorHelper nobody feeds).
_RULE_COLOR_AT_ZERO: dict[str, tuple[str, ...]] = {
    "textupdateclass": ("bgColor",),
    "regtextupdateclass": ("bgColor",),
}
_REGISTRY: VendoredRegistry | None = None


def _mapped_color_target(qt_class: str | None, qt_prop: str) -> str | None:
    """The IR prop ``qt_prop`` lands on for ``qt_class`` (vendored registry), or None when dropped."""
    global _REGISTRY
    if qt_class is None:
        return None
    if _REGISTRY is None:
        _REGISTRY = VendoredRegistry()
    definition = _REGISTRY.by_qt_class(qt_class)
    spec = definition.qt_prop_map.get(qt_prop) if definition else None
    return spec.get("to") if spec else None


def _color_rule(colors: dict[str, Any] | None, value: Any) -> tuple[int, dict[str, Any]] | None:
    """``(index, rule)`` when ``value`` ("index N") names a colors.list rule colour."""
    if not isinstance(value, str):
        return None
    match = re.match(r"index\s+(\d+)\s*$", value.strip())
    if not match:
        return None
    index = int(match.group(1))
    if index in (colors or {}).get("static", {}):
        return None
    rule = (colors or {}).get("rules", {}).get(index)
    return (index, rule) if rule else None


def _format_rule_number(value: float) -> str:
    return str(_as_number(float(value)))


def _condition_expression(condition: dict[str, Any], token: str) -> str | None:
    """One parsed rule condition -> a rule expression on ``token`` ("{0}"); None for ``default``."""
    if condition.get("default"):
        return None
    terms = [f"{token} {op} {_format_rule_number(value)}" for op, value in condition["terms"]]
    if len(terms) == 1:
        return terms[0]
    joiner = " and " if condition.get("connector") == "&&" else " or "
    return joiner.join(f"({term})" for term in terms)


def _evaluate_condition(condition: dict[str, Any], value: float) -> bool:
    if condition.get("default"):
        return True
    ops = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
    }
    results = [ops[op](value, arg) for op, arg in condition["terms"]]
    if len(results) == 1:
        return results[0]
    return (results[0] and results[1]) if condition.get("connector") == "&&" else (results[0] or results[1])


def _rule_ladder(
    colors: dict[str, Any] | None, index: int, rule: dict[str, Any], token: str, notes: list[str]
) -> tuple[list[tuple[str, str]], str | None]:
    """A colors.list rule -> ordered ``(expression, hex)`` conditions and its no-match hex.

    First true condition wins (EDM evalRule and the IR rule contract agree);
    ``&&``/``||`` joins fold into the next condition; a ``default`` ends the
    ladder (later conditions are unreachable) and repeated expressions are
    dropped. Blinking result colours render their first (steady) state, noted.
    """
    static = rule_static_color(colors or {}, index)
    default = color_info_to_hex(static, colors)
    conditions: list[tuple[str, str]] = []
    seen: set[str] = set()
    pending: tuple[str, str] | None = None  # (expression, join operator) awaiting the next condition

    def colour(name: str) -> str | None:
        entry = static_color_by_name(colors or {}, name)
        if entry is not None and len(entry.get("rgb") or ()) >= 6:
            notes.append(f"EDM blinking colour '{name}' in colour rule '{rule.get('name')}' rendered steady")
        return color_info_to_hex(entry, colors)

    if static is not None and len(static.get("rgb") or ()) >= 6:
        notes.append(f"EDM blinking colour '{static.get('name')}' in colour rule '{rule.get('name')}' rendered steady")
    for condition in rule.get("conditions", ()):
        expression = _condition_expression(condition, token)
        if pending is not None:
            pending_expr, join = pending
            if expression is None:
                expression = pending_expr
            else:
                expression = f"({expression}) {'and' if join == '&&' else 'or'} ({pending_expr})"
            pending = None
        if condition.get("join"):
            if expression is not None:
                pending = (expression, condition["join"])
            continue
        hex_color = colour(condition["color"])
        if hex_color is None:
            continue  # an unknown colour name: EDM refuses the palette; keep the rest
        if expression is None:  # "default": always true, nothing after it can apply
            default = hex_color
            break
        if expression in seen:
            continue
        seen.add(expression)
        conditions.append((expression, hex_color))
    return conditions, default


def _rule_color_at(colors: dict[str, Any] | None, index: int, rule: dict[str, Any], value: float) -> str | None:
    """EDM evalRule(index, value) as hex: the first condition holding at ``value``."""
    pending: tuple[bool, str] | None = None
    for condition in rule.get("conditions", ()):
        result = _evaluate_condition(condition, value)
        if pending is not None:
            held, join = pending
            result = (result and held) if join == "&&" else (result or held)
            pending = None
        if condition.get("join"):
            pending = (result, condition["join"])
            continue
        if result:
            hex_color = _named_color_hex(colors, condition["color"])
            if hex_color is not None:
                return hex_color
    return color_info_to_hex(rule_static_color(colors or {}, index), colors)


def _driver_channel(obj: EDMObject, attrs: tuple[str, ...]) -> str | None:
    for attr in attrs:
        value = obj.properties.get(attr)
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, str) and value.strip():
            return _to_channel(value)
    return None


def _color_rules(
    obj: EDMObject,
    qt_class: str | None,
    qt_props: dict[str, Any],
    colors: dict[str, Any] | None,
    alarm_rules: list[RuleSpec],
    warnings: list[str],
) -> list[RuleSpec]:
    """colors.list rule colours on ``obj`` -> value-driven colour RuleSpecs.

    The static prop already holds the rule's static colour (its first result
    colour, get_color_by_index). A rule is added when the class feeds the
    colour a PV value (see _RULE_COLOR_DRIVERS) and the widget carries the
    prop; a colour EDM evaluates at 0 is replaced by that fixed result. When an
    alarm rule already drives the same prop (alarmPv + lineAlarm/fillAlarm/
    fgAlarm/bgAlarm) and the palette keeps the own colour at NO_ALARM, the two
    merge into one rule: severity colours first, then the value ladder (EDM
    pvColor.cc: alarm colours override, NO_ALARM shows the evaluated rule
    colour). A palette with a named NO_ALARM colour never shows the rule while
    alarm-sensitive, so the alarm rule stands alone.
    """
    name = obj.name.lower()
    drivers, driven_attrs = _RULE_COLOR_DRIVERS.get(name, ((), ()))
    at_zero = _RULE_COLOR_AT_ZERO.get(name, ())
    rules: list[RuleSpec] = []
    notes: list[str] = []
    for edm_attr, value in obj.properties.items():
        qt_prop = EDM_TO_QT_PROP.get(edm_attr)
        if qt_prop not in _COLOR_PROPS or qt_prop not in qt_props:
            continue
        found = _color_rule(colors, value)
        if found is None:
            continue
        index, rule = found
        if edm_attr in at_zero:
            fixed = _rule_color_at(colors, index, rule, 0.0)
            if fixed is not None:
                qt_props[qt_prop] = fixed
            continue
        channel = _driver_channel(obj, drivers) if edm_attr in driven_attrs else None
        # No channel: EDM shows the static colour. No target: the widget drops
        # this colour prop altogether (the static colour too).
        target = _mapped_color_target(qt_class, qt_prop) if channel else None
        if target is None:
            continue
        merged = next((r for r in alarm_rules if r.target_property == target), None)
        if merged is not None and _alarm_palette(colors)[1] != _STATIC_COLOR:
            continue  # a named NO_ALARM colour hides the rule colour while alarm-sensitive
        conditions, default = _rule_ladder(colors, index, rule, "{1}" if merged else "{0}", notes)
        if default is None:
            continue
        if merged is not None:
            merged.pvs = [*merged.pvs, (channel, True)]
            merged.conditions = [*merged.conditions, *conditions]
            merged.default = default
            merged.name = f"Alarm and color rule {rule.get('name')} ({target})"
            continue
        rules.append(
            RuleSpec(
                target_property=target,
                name=f"Color rule {rule.get('name')} ({target})",
                pvs=[(channel, True)],
                conditions=conditions,
                default=default,
            )
        )
    warnings.extend(dict.fromkeys(notes))
    return rules


def _apply_channel_attrs(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> None:
    """Route the object's data-channel attrs: primary -> ``channel``, readback ->
    ``readbackChannel`` (registry maps it only where a readback exists, i.e.
    pv-button). Anything else is dropped loudly — silently keeping the last
    attr parsed is how buttons ended up writing to their readback PV.
    """
    primary = next((attr for attr in EDM_PRIMARY_CHANNEL_ORDER if obj.properties.get(attr)), None)
    if primary is None:
        return
    qt_props["channel"] = _to_channel(obj.properties[primary])
    readback = next(
        (attr for attr in EDM_READBACK_CHANNEL_ORDER if attr != primary and obj.properties.get(attr)),
        None,
    )
    if readback is not None:
        if obj.name.lower() in _READBACK_CLASSES:
            qt_props["readbackChannel"] = _to_channel(obj.properties[readback])
        else:
            warnings.append(f"EDM {readback} readback dropped ({primary} kept as the channel)")
    for attr in EDM_PRIMARY_CHANNEL_ORDER:
        if attr not in (primary, readback) and obj.properties.get(attr):
            warnings.append(f"EDM {attr} dropped ({primary} kept as the channel)")


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
    if alarm_flags and not obj.properties.get("alarmPv"):
        # With an alarmPv these flags become alarm-color rules (_alarm_rules);
        # without one EDM ignores them, but say so rather than vanish them.
        flags = ", ".join(alarm_flags)
        warnings.append(f"EDM alarm flags ({flags}) without alarmPv; static colors emitted")


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
    """activeLineClass fixup: shared drawing logic + points/arrows/fill handling.

    A closed or filled line resolves to the polygon widget (resolve_qt_class),
    which consumes the same points plus brushFill/brushColor and a ``closed``
    flag; an open line stays a polyline (no fill props).
    """
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
        qt_props["closePolygon"] = True

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


def _as_str_list(value: Any) -> list[str]:
    """Normalize a brace-block prop value to a list of strings (a bare str -> [str])."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _by_index(value: Any) -> dict[int, str]:
    return dict(block_items(value))


def _fixup_shell_cmd(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """shellCmdClass fixup: command/commandLabel brace blocks -> qt_props["actions"].

    (buttonLabel -> text -> label is already handled globally.)
    """
    commands = block_items(obj.properties.get("command"))
    if not commands:
        return None
    labels = _by_index(obj.properties.get("commandLabel"))

    actions: list[dict[str, Any]] = []
    for index, command in commands:
        action: dict[str, Any] = {"type": "shell_command", "command": normalize_macro_syntax(command)}
        if index in labels:
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


def _fixup_state_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeMessageButtonClass/activeButtonClass fixup: EDM buttons label via
    onLabel/offLabel (buttonLabel is rare on these classes); the visible resting
    label is offLabel. With a readback channel the web button switches
    onLabel/offLabel live (isOn from readbackPV); without one distinct labels
    cannot switch — keep the resting label and say so.
    """
    off_label = obj.properties.get("offLabel")
    on_label = obj.properties.get("onLabel")
    if not qt_props.get("text"):
        label = off_label or on_label
        if label:
            qt_props["text"] = normalize_macro_syntax(str(label))
    if obj.name.lower() == "activebuttonclass":
        # EDM's Button is a toggle unless buttonType says otherwise; the web
        # button defaults to momentary push, so the default must be written.
        qt_props.setdefault("buttonType", "toggle")
    if on_label and off_label and on_label != off_label and "readbackChannel" not in qt_props:
        warnings.append("EDM on/off button labels differ; resting (off) label kept (no readback channel)")
    return None


def _fixup_xy_graph(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """xyGraphClass fixup: EDM trace lists -> the registry's PyDM-style curves.

    Each EDM yPv becomes one curve JSON string ({"y_channel": ...}); the registry
    transform parses them. A parallel xPv entry rides along as ``x_channel``
    (waveform-vs-waveform traces; the plot renders time-series when absent).
    """
    y_pvs = [(index, pv) for index, pv in block_items(obj.properties.get("yPv")) if pv]
    x_pvs = _by_index(obj.properties.get("xPv"))  # trace i plots yPv[i] against xPv[i]
    curves = []
    for number, (index, pv) in enumerate(y_pvs, start=1):
        curve: dict[str, Any] = {"y_channel": normalize_macro_syntax(pv), "name": f"trace {number}"}
        if x_pvs.get(index):
            curve["x_channel"] = normalize_macro_syntax(x_pvs[index])
        curves.append(json.dumps(curve))
    if curves:
        qt_props["curves"] = curves
    title = obj.properties.get("graphTitle")
    if title:
        qt_props["title"] = normalize_macro_syntax(str(title))
    return None


def _pip_menu_refs(obj: EDMObject) -> list[tuple[int, str]]:
    """displaySource=menu pip: ``(EDM index, screen ref)`` per ``displayFileName``
    entry (same normalization the ``screenRef`` transform applies — rule values
    bypass ``qtPropMap`` transforms, so the adapter must pre-normalize). The
    filePv value selects entry ``index``."""
    refs: list[tuple[int, str]] = []
    for index, name in block_items(obj.properties.get("displayFileName")):
        normalized = normalize_macro_syntax(name)
        ref = screen_ref(normalized)
        if isinstance(ref, str) and ref.strip():
            refs.append((index, ref))
    return refs


def _fixup_pip(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activePipClass fixup by displaySource:

    - "file" (default): the macro-bearing ``file`` template is already mapped
      (file -> filename -> screenRef keeps ``${VAR}`` refs for view-time
      resolution) — nothing to do.
    - "menu": ``filePv`` selects among ``displayFileName`` entries; emit the
      first entry as the static file and let ``_pip_rules`` switch it live.
    - "stringPv": the file name is the PV's string value; no rule-conditions
      analog, surfaced as a warning instead of dropping the node silently.
    """
    source = str(obj.properties.get("displaySource", "file") or "file").strip().lower()
    if source in ("", "file"):
        return None
    if source == "menu":
        names = [name for _, name in sorted(block_items(obj.properties.get("displayFileName"))) if name.strip()]
        if names and obj.properties.get("filePv"):
            # Raw first entry: the builder's screenRef transform normalizes it.
            qt_props["filename"] = normalize_macro_syntax(names[0])
            if len(_as_str_list(obj.properties.get("symbols"))) > 1:
                warnings.append("EDM menu pip per-entry symbols are merged; macros do not switch with the file")
        else:
            warnings.append("EDM menu pip without filePv/displayFileName; no file emitted")
    elif source == "stringpv":
        warnings.append("EDM stringPv-driven embedded file is not translated; no file emitted")
    else:
        warnings.append(f"EDM pip displaySource '{source}' is not translated; no file emitted")
    return None


def _pip_rules(obj: EDMObject) -> list[RuleSpec]:
    """displaySource=menu pip -> a ``file`` rule keyed on the filePv's value."""
    if obj.name.lower() != "activepipclass":
        return []
    source = str(obj.properties.get("displaySource", "file") or "file").strip().lower()
    file_pv = obj.properties.get("filePv")
    if source != "menu" or not file_pv:
        return []
    refs = sorted(_pip_menu_refs(obj))
    if not refs:
        return []
    if isinstance(file_pv, list):
        file_pv = file_pv[0] if file_pv else ""
    file_pv = normalize_macro_syntax(str(file_pv))
    return [
        RuleSpec(
            target_property="file",
            name="Embedded file (menu)",
            pvs=[(file_pv, True)],
            conditions=[(f"{{0}} == {index}", ref) for index, ref in refs],
            default=refs[0][1],
        )
    ]


def _fixup_related_display(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """relatedDisplayClass fixup: one target, with that target's own symbols.

    EDM keeps ``displayFileName``/``symbols``/``menuLabel`` as parallel arrays
    indexed by display number (related_display.cc): ``symbols[i]`` are the
    macros for ``displayFileName[i]``, and a file may skip indices
    (``symbols { 2 "P=X" }``). The IR button carries one target, so it takes the
    lowest-numbered non-empty display and only that display's symbols (merging
    every entry's symbols handed the first target the last entry's macros).
    """
    files = {index: name for index, name in block_items(obj.properties.get("displayFileName")) if name.strip()}
    if not files:
        return None
    first = min(files)
    qt_props["filenames"] = [normalize_macro_syntax(files[first])]
    symbols = _by_index(obj.properties.get("symbols")).get(first)
    macros = _to_macros(symbols) if symbols else {}
    if macros:
        qt_props["macros"] = macros
    else:
        qt_props.pop("macros", None)
    if len(files) > 1:
        warnings.append(f"EDM related display offers {len(files)} displays; only the first is carried")
    return None


def _fixup_choice_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeChoiceButtonClass fixup: EDM lays the states out to fill the rect —
    wide boxes read horizontally, tall boxes vertically."""
    qt_props["orientation"] = "horizontal" if obj.width >= obj.height else "vertical"
    return None


def _fixup_menu_button(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeMenuButtonClass fixup: the button face shows the CURRENT choice
    (EDM renders the enum string of its PV), so the web button uses pvState
    labeling; without an explicit indicatorPv the control channel doubles as
    the state source.
    """
    qt_props["labelType"] = "pvState"
    if "readbackChannel" not in qt_props and qt_props.get("channel"):
        qt_props["readbackChannel"] = qt_props["channel"]
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


def _fixup_text_control(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """activeXTextDspClass(:noedit) fixup.

    Alarm border (x_text_dsp_obj.cc): ``useAlarmBorder`` only acts together with
    ``fgAlarm``; then the text keeps its static colour (drawn with
    ``fgColor.pixelIndex()``) and a 2 px border in the alarm colour appears while
    the PV is in alarm. Alone it does nothing.
    """
    if obj.properties.get("useAlarmBorder") and obj.properties.get("fgAlarm"):
        qt_props["alarmSensitiveBorder"] = True
        qt_props.pop("alarmSensitiveContent", None)
    # Precision: the PV's PREC when limitsFromDb is set or no precision is
    # written (efPrecision null), else the widget's own precision.
    if obj.properties.get("limitsFromDb") or "precision" not in obj.properties:
        _precision_from_pv(obj, qt_props)
    else:
        _widget_precision(obj, qt_props)
    return None


# TextupdateClass displayMode -> pv-label format (engineering notation has no
# exact analog; exponential is the closest).
_TEXTUPDATE_MODE_FORMAT = {"decimal": "default", "hex": "hex", "exp": "exponential", "engineer": "exponential"}


def _fixup_textupdate(obj: EDMObject, qt_props: dict[str, Any], warnings: list[str]) -> Geometry | None:
    """TextupdateClass/RegTextupdateClass fixup.

    Alarm border (textupdate.cc redraw_text): with ``lineAlarm`` the border is
    drawn in the alarm colour only while the PV is in alarm (width at least 1);
    the text colour is governed by ``fgAlarm`` independently.

    Display mode and precision (textupdate.cc get_current_values): "default"
    (absent) prints the PV's own string, i.e. the PV's PREC; decimal/exp/engineer
    format with the widget's ``precision`` (0 when absent); hex ignores precision.
    """
    if obj.properties.get("lineAlarm"):
        qt_props["alarmSensitiveBorder"] = True
    if not obj.properties.get("fill"):
        # redraw_text fills the background only when "fill" is set; otherwise the
        # display shows through.
        qt_props.pop("backgroundColor", None)
    mode = str(obj.properties.get("displayMode", "default") or "default").strip().lower()
    if mode in _TEXTUPDATE_MODE_FORMAT:
        qt_props["displayFormat"] = _TEXTUPDATE_MODE_FORMAT[mode]
    if mode == "engineer":
        warnings.append("EDM engineering display mode approximated by exponential format")
    if mode in ("decimal", "exp", "engineer"):
        _widget_precision(obj, qt_props)
    elif mode == "hex":
        qt_props.pop("precision", None)
    else:
        _precision_from_pv(obj, qt_props)
    return None


def _edm_int(value: Any) -> int:
    """EDM's integer read of a tag value (strtol semantics): the leading integer, else 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else 0


def _widget_precision(obj: EDMObject, qt_props: dict[str, Any]) -> None:
    """The widget's own ``precision`` (0 when absent), not the PV's."""
    qt_props["precision"] = max(0, _edm_int(obj.properties.get("precision", 0)))
    qt_props["precisionFromPV"] = False


def _precision_from_pv(obj: EDMObject, qt_props: dict[str, Any]) -> None:
    """The PV's PREC: drop the widget's number (it would override ``fromPV``); say
    ``fromPV`` explicitly only when the file wrote a precision EDM ignores."""
    qt_props.pop("precision", None)
    if "precision" in obj.properties:
        qt_props["precisionFromPV"] = True
    else:
        qt_props.pop("precisionFromPV", None)


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
        "activemessagebuttonclass": _fixup_state_button,
        "activebuttonclass": _fixup_state_button,
        "activechoicebuttonclass": _fixup_choice_button,
        "activemenubuttonclass": _fixup_menu_button,
        "xygraphclass": _fixup_xy_graph,
        "activepipclass": _fixup_pip,
        "relateddisplayclass": _fixup_related_display,
        "activextextdspclass": _fixup_text_control,
        "activextextdspclassnoedit": _fixup_text_control,
        "textupdateclass": _fixup_textupdate,
        "regtextupdateclass": _fixup_textupdate,
        # activepngclass, activeradiobuttonclass: no fixup needed; global renames suffice.
    }
)


def _object_to_source(obj: EDMObject, colors: dict[str, Any] | None = None) -> SourceNode:
    qt_class = resolve_qt_class(obj.name.lower(), obj.properties)
    qt_props: dict[str, Any] = {}
    warnings: list[str] = []
    rules: list[RuleSpec] = []
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
            coerced = _coerce(qt_prop, value)
            if qt_prop in _FONT_PROPS and coerced is None:
                continue  # malformed font string: no size beats a wrong size
            qt_props[qt_prop] = coerced
        _apply_channel_attrs(obj, qt_props, warnings)
        alarm_rules = _alarm_rules(obj, colors, qt_props)
        if any(rule.target_property == "foregroundColor" for rule in alarm_rules):
            # The alarm rule replaces own-PV alarm sensitivity (EDM: alarmPv
            # overrides the widget's own channel as the alarm source).
            qt_props.pop("alarmSensitiveContent", None)
        # colorPv only ever feeds colors.list rule colours (evalRule is a no-op on
        # a static index), so _color_rules covers it: no separate warning.
        rules = alarm_rules + _color_rules(obj, qt_class, qt_props, colors, alarm_rules, warnings) + _pip_rules(obj)
        if obj.properties.get("bgAlarm") and not any(rule.target_property == "backgroundColor" for rule in rules):
            warnings.append("EDM dynamic color (bgAlarm) is not supported; static colors emitted")
        fixup = _CLASS_FIXUPS.get(obj.name.lower())
        if fixup is not None:
            override = fixup(obj, qt_props, warnings)
            if override is not None:
                geometry = override
    return SourceNode(
        qt_class=qt_class,
        qt_props=qt_props,
        geometry=geometry,
        rules=rules,
        raw_class=obj.name,
        raw_props=dict(obj.properties),
        warnings=warnings,
    )


def _symbol_state_vis(group: EDMGroup) -> VisTuple | None:
    """Per-state visibility for an exploded activeSymbolClass state group.

    The parser explodes a symbol into one child EDMGroup per state, stamping the
    state range (``symbolMin``/``symbolMax``) on the group and the symbol channel
    (``symbolChannel``) on its leaf objects. Without a rule every state renders
    stacked; with one, exactly the state whose range holds the channel's value
    shows — EDM symbol semantics (min <= value < max).
    """
    props = getattr(group, "properties", None) or {}
    if "symbolMin" not in props or "symbolMax" not in props:
        return None
    channel = None
    for sub_object in group.objects:
        sub_props = getattr(sub_object, "properties", None) or {}
        if sub_props.get("symbolChannel"):
            channel = sub_props["symbolChannel"]
            break
    if not channel:
        return None
    try:
        vis_min = float(props["symbolMin"])
        vis_max = float(props["symbolMax"])
    except (TypeError, ValueError):
        return None
    channel = normalize_macro_syntax(str(channel))
    return (channel, vis_min, vis_max, False)


# The leading number C's strtod() accepts (what EDM's atof() reads): hex first,
# since the decimal pattern would otherwise stop at the "0" of "0x...".
_HEX_PREFIX_RE = re.compile(r"[+-]?0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?\d+)?")
_DEC_PREFIX_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_SPECIAL_PREFIX_RE = re.compile(r"[+-]?(?:inf(?:inity)?|nan)", re.IGNORECASE)


def _edm_atof(text: str) -> float:
    """C ``atof()`` semantics: the longest numeric prefix (decimal, hex, inf/nan), else 0.0."""
    text = text.lstrip()
    hex_match = _HEX_PREFIX_RE.match(text)
    if hex_match:
        token = hex_match.group(0)
        sign = -1.0 if token.startswith("-") else 1.0
        return sign * float.fromhex(token.lstrip("+-"))
    match = _DEC_PREFIX_RE.match(text) or _SPECIAL_PREFIX_RE.match(text)
    return float(match.group(0)) if match else 0.0


def _vis_limit(attr: str, value: Any, warnings: list[str]) -> float | None:
    """One EDM ``visMin``/``visMax`` string -> the number EDM compares against.

    EDM stores both as strings and evaluates them with ``atof()`` after macro
    substitution, so a non-numeric value (a PV name, "MAJOR") counts as 0 and a
    numeric prefix ("1`", "0x80") counts as that number. A value that *starts*
    with a macro depends on the caller's substitution and cannot be evaluated at
    convert time: ``None`` (the caller drops that visibility rule).
    """
    if isinstance(value, bool):
        text = ""  # a bare "visMin" line (no value) parses as True
    elif isinstance(value, (int, float)):
        return float(value)
    else:
        text = str(value) if value is not None else ""
    if text.lstrip().startswith(("${", "$(")):
        warnings.append(
            f"EDM {attr} '{text}' depends on a macro and cannot be evaluated at convert time; "
            "visibility rule dropped (widget always shown)"
        )
        return None
    number = _edm_atof(text)
    if not math.isfinite(number):
        warnings.append(f"EDM {attr} '{text}' is not a finite number; visibility rule dropped (widget always shown)")
        return None
    try:
        exact = float(text)
    except ValueError:
        exact = None
    if exact != number:
        warnings.append(
            f"EDM {attr} '{text}' is not a plain number; evaluated as {_as_number(number)} (EDM atof semantics)"
        )
    return number


def _vis_tuple(properties: dict[str, Any], warnings: list[str] | None = None) -> VisTuple | None:
    """Extract an EDM visibility tuple ``(visPv, visMin, visMax, visInvert)``, or None.

    visMin/visMax are converted with EDM's ``atof()`` semantics (see
    :func:`_vis_limit`); notes about non-numeric limits go to ``warnings``. A limit
    that cannot be evaluated drops the tuple (no rule) rather than aborting.
    """
    if warnings is None:
        warnings = []
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
        low = _vis_limit("visMin", vis_min, warnings)
        high = _vis_limit("visMax", vis_max, warnings) if low is not None else None
        if low is None or high is None:
            return None
        return (vis_pv, low, high, invert)
    return (vis_pv, None, None, invert)


def _visibility_rule_spec(vis_tuples: list[VisTuple]) -> RuleSpec:
    """Combine EDM visibility tuples (own + inherited group vis) into one ``visible`` rule.

    EDM is visible when, for every tuple, ``visMin <= value < visMax`` (or ``value != 0``
    when no range; the limits are already numbers, see :func:`_vis_limit`), with
    ``visInvert`` flipping that tuple. Multiple tuples AND together
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
    group: EDMGroup, *, colors: dict[str, Any] | None = None, skip_classes: frozenset[str] = frozenset()
) -> list[SourceNode]:
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

    Errors are isolated per object: an object whose conversion raises becomes an
    ``unknown-widget`` placeholder carrying the failure as its warning, and a group
    whose visibility cannot be converted keeps its children with a warning, so one
    bad object never aborts the screen.
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
                children=edm_group_to_source_nodes(obj, colors=colors, skip_classes=skip_classes),
            )
            missing_symbol = obj.properties.get("symbolFileNotFound")
            if missing_symbol:
                group_node.warnings.append(
                    f"EDM symbol file '{missing_symbol}' not found beside the display, on the search paths or "
                    "on EDMDATAFILES; symbol not rendered"
                )
            group_node.warnings.extend(obj.properties.get("symbolWarnings") or ())
            try:
                vis_tuples: list[VisTuple] = []
                symbol_vis = _symbol_state_vis(obj)
                if symbol_vis is not None:
                    vis_tuples.append(symbol_vis)
                group_vis = _vis_tuple(obj.properties, group_node.warnings)
                if group_vis is not None:
                    vis_tuples.append(group_vis)
                if vis_tuples:
                    group_node.rules = [_visibility_rule_spec(vis_tuples)]
            except Exception as exc:  # noqa: BLE001 - keep the group and its children
                logger.warning("EDM group visibility failed to convert", exc_info=True)
                group_node.warnings.append(f"EDM group visibility not converted ({type(exc).__name__}: {exc})")
            nodes.append(group_node)
        elif isinstance(obj, EDMObject):
            if obj.name.lower() in skip_classes:
                continue
            try:
                node = _object_to_source(obj, colors)
                own_vis = _vis_tuple(obj.properties, node.warnings)
                if own_vis is not None:
                    # Append: the node may already carry alarm-color rules.
                    node.rules.append(_visibility_rule_spec([own_vis]))
            except Exception as exc:  # noqa: BLE001 - one bad object must not abort the screen
                logger.warning("EDM %s failed to convert; emitting a placeholder", obj.name, exc_info=True)
                node = SourceNode(
                    qt_class=None,
                    geometry=(obj.x, obj.y, obj.width, obj.height),
                    raw_class=obj.name,
                    raw_props=dict(obj.properties),
                    placeholder_reason=conversion_failure(obj.name, exc),
                )
            nodes.append(node)
    return nodes


def edm_file_to_ir(
    input_path: str | Path,
    *,
    registry: RegistryClient | None = None,
    color_list_path: str | Path | None = None,
    calc_list_path: str | Path | None = None,
    site: str | None = None,
    search_paths: Sequence[str | Path] | None = None,
) -> ScreenIR:
    """Parse an ``.edl`` file and build its Screen IR.

    ``color_list_path`` points at an EDM ``colors.list`` palette used to resolve
    "index N" color props. When omitted, the palette is located via (in order) the
    ``EDMCOLORFILE`` env var, ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``;
    an explicit ``color_list_path`` wins over all of those. If no palette is found,
    "index N" colors cannot be resolved and are dropped with a node warning ("rgb ..."
    colors resolve without a palette).

    ``calc_list_path`` points at an EDM ``calc.list`` used to resolve named
    ``CALC\\`` PVs; when omitted the parser searches beside the input file, then
    ``$EDMFILES/calc.list``, then beside ``$EDMCOLORFILE``. Unresolvable named
    calcs stay as warnings. ``site`` applies site skip rules (same vocabulary as
    the PyDM target, e.g. ``"slac"`` drops exit buttons).

    ``search_paths`` are extra directories, searched after the file's own directory
    and before ``EDMDATAFILES``, for activeSymbolClass symbol files and (after the
    file's own directory) for ``calc.list``. A symbol file that cannot be found
    leaves an empty group with a node warning.
    """
    from pydmconverter.sites import get_skip_widgets

    path = Path(input_path)
    parser = EDMFileParser(
        str(path),
        str(path.with_suffix(".ui")),
        calc_list_file=str(calc_list_path) if calc_list_path else None,
        calc_reuse_short=False,
        search_paths=search_paths,
    )
    colors_path = search_color_list(str(color_list_path) if color_list_path else None)
    colors = parse_colors_list(colors_path)
    skip_classes = frozenset(get_skip_widgets(site))
    top_level = edm_group_to_source_nodes(parser.ui, colors=colors, skip_classes=skip_classes)
    builder = IRBuilder(registry or VendoredRegistry())
    # Screen background: the parser resolves bgColor to an (r, g, b, a) tuple.
    background: str | None = None
    bg = getattr(parser.ui, "properties", {}).get("bgColor") if getattr(parser.ui, "properties", None) else None
    if hasattr(bg, "r") and hasattr(bg, "g") and hasattr(bg, "b"):
        background = "#{:02x}{:02x}{:02x}".format(int(bg.r), int(bg.g), int(bg.b))
    elif isinstance(bg, (tuple, list)) and len(bg) >= 3:
        background = "#{:02x}{:02x}{:02x}".format(int(bg[0]), int(bg[1]), int(bg[2]))
    # The EDM window is exactly the declared w x h (objects outside it are clipped,
    # hidden ones parked off-screen on purpose), so the canvas does not grow to fit.
    # Only a dimension the file does not declare is sized from the content.
    missing = parser.missing_screen_size
    screen_warnings: list[str] = []
    if missing:
        keys = "/".join(dim[0] for dim in missing)
        screen_warnings.append(f"EDM screen {keys} missing or not an integer; sized from the content extent")
    return builder.build_screen(
        screen_id=path.stem,
        title=path.stem,
        source_type="edl-converter",
        size=(
            None if "width" in missing else parser.ui.width,
            None if "height" in missing else parser.ui.height,
        ),
        top_level=top_level,
        background=background,
        grow_to_fit=False,
        warnings=screen_warnings,
    )
