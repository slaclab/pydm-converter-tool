"""Rule-expression helpers for the Phoebus ``.bob`` front-end.

Phoebus rule conditions (``<exp bool_exp="...">``) are written in JavaScript-flavoured
syntax. Phoebus itself converts them to Python before execution with
``RuleToScript.javascriptToPythonLogic``; :func:`js_to_python` is a faithful port of that
routine so converted rules evaluate exactly as they do in Phoebus.

:func:`lower_rule` then turns a whole ``<rule>`` into an IR :class:`RuleSpec`: the
Phoebus PV tokens (``pv0``, ``pvStr0``, ``pvInt0``, ``pvSev0``, ``pvLegacySev0``) become
positional ``{N}`` bindings, the rule target is resolved to a registry prop, arm values
are coerced per target kind, and the widget's static value becomes the rule default.
Anything that cannot be lowered is a warning on :class:`RuleContext`, never an error.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from pydmconverter.bob.bob_qt import (
    BOB_DEFAULTS,
    RULE_DIRECT_TARGETS,
    RULE_TARGET_UNSUPPORTED_WARNING,
    TRANSPARENT_BG_RULE_TYPES,
    TRANSPARENT_BG_RULE_WARNING,
    default_size,
    qt_class_for,
    qt_prop_for,
    rule_coercion,
)
from pydmconverter.bob.coercion import RGBA, coerce, color_from_element
from pydmconverter.bob.gates import FILE_REFERENCE_WARNING, expression_allowed, file_reference
from pydmconverter.colors import ColorContext
from pydmconverter.bob.parser import BobRule, BobWidget
from pydmconverter.edm.ir_adapter import _severity_channel
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec

__all__ = ["RuleContext", "coerce_value", "is_true", "js_to_python", "lower_rule", "resolve_target", "syntax_check"]


def js_to_python(expr: str) -> str:
    """Convert a JavaScript-style Phoebus rule expression to Python logic.

    Port of Phoebus ``RuleToScript.javascriptToPythonLogic``. Outside string literals:

    - ``true``/``false`` become ``True``/``False``;
    - ``&&``/``||`` become `` and ``/`` or `` and a lone ``!`` becomes `` not ``
      (padded with spaces, as Phoebus does);
    - a single ``=`` (not part of ``==``, ``!=``, ``<=``, ``>=``) becomes ``==``;
    - the ``Math.`` prefix is removed (``Math.abs(x)`` -> ``abs(x)``).

    Text inside single- or double-quoted literals (honouring backslash-escaped quotes)
    is copied untouched. An unmatched quote makes the whole input come back unchanged,
    matching Phoebus.
    """
    text = expr
    length = len(text)
    out: list[str] = []
    i = 0
    while i < length:
        ch = text[i]
        if ch in ('"', "'") and (i == 0 or text[i - 1] != "\\"):
            # Copy the quoted literal verbatim, skipping escaped closing quotes.
            out.append(ch)
            i += 1
            while i < length and (text[i] != ch or text[i - 1] == "\\"):
                out.append(text[i])
                i += 1
            if i >= length:
                return text  # unmatched quote
            out.append(text[i])
            i += 1
        elif text.startswith("true", i):
            out.append("True")
            i += 4
        elif text.startswith("false", i):
            out.append("False")
            i += 5
        elif text.startswith("&&", i):
            out.append(" and ")
            i += 2
        elif text.startswith("||", i):
            out.append(" or ")
            i += 2
        elif text.startswith("!=", i):
            out.append("!=")
            i += 2
        elif ch == "!":
            out.append(" not ")
            i += 1
        elif text.startswith("==", i):
            out.append("==")
            i += 2
        elif ch == "=" and i > 0 and text[i - 1] not in "<>":
            out.append("==")
            i += 1
        elif text.startswith("Math.", i):
            i += 5
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Token table. Phoebus exposes each rule PV to the condition under five names;
# pvSev/pvLegacySev read the alarm severity, bound here to ``<pv>.SEVR``.
# --------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\bpv(Str|Int|Sev|LegacySev)?(\d+)\b")
_STRING_LITERAL_RE = re.compile(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')")
_LEGACY_SEV_LADDER = "(2 if {k}==1 else (1 if {k}==2 else (-1 if {k}>=3 else 0)))"

# Rule targets whose values name a file (each goes through gates.file_reference).
_FILE_RULE_TARGETS = frozenset({"file", "on_image", "off_image"})

# pvStrN == "text" / "text" == pvStrN (either quote style): the code before or after a
# literal that _STRING_LITERAL_RE has already cut out, so no pattern scans quoted text.
_PVSTR_BEFORE_LITERAL_RE = re.compile(r"\bpvStr(\d+)\s*(?:==|!=)\s*$")
_PVSTR_AFTER_LITERAL_RE = re.compile(r"^\s*(?:==|!=)\s*pvStr(\d+)\b")
PVSTR_GATEWAY_WARNING = (
    "{widget}: rule compares PV text; the Formula Engine delivers enum PVs as indices, verify {pv} is a string record"
)
UNSUPPORTED_EXPRESSION_WARNING = "{widget}: unsupported rule expression: {expression}"

_LITERAL_RE = re.compile(r"^(?:true|false|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|\"[^\"]*\"|'[^']*')$")


def syntax_check(condition: str, binding_count: int | None = None) -> bool:
    """Whether a lowered condition passes :func:`~pydmconverter.bob.gates.expression_allowed`.

    The gate formula PVs and lowered formula scripts pass too: the Formula Engine's
    expression subset over ``{N}`` bindings, with no macro anywhere.
    """
    return expression_allowed(condition, binding_count)


@dataclass
class RuleContext:
    """Per-file lowering state: registry, named colours, the collected warnings and the scheme colour context.

    ``color`` is the document's :class:`~pydmconverter.colors.ColorContext` when a
    scheme is in force (named colours may then become roles); ``None`` keeps literal hex.
    """

    registry: RegistryClient | None = None
    named_colors: dict[str, RGBA] | None = None
    warnings: list[str] = field(default_factory=list)
    color: ColorContext | None = None

    def warn(self, message: str) -> None:
        """Record a conversion warning."""
        self.warnings.append(message)

    def syntax_check(self, condition: str) -> bool:
        """Return whether ``condition`` passes :func:`syntax_check` (an override may narrow it further)."""
        return syntax_check(condition)

    def resolve_registry(self) -> RegistryClient:
        """Return the registry, defaulting to the vendored snapshot."""
        if self.registry is None:
            self.registry = VendoredRegistry()
        return self.registry


def _outside_literals(text: str, fn) -> str:
    """Apply ``fn`` to the parts of ``text`` that are not string literals."""
    parts = _STRING_LITERAL_RE.split(text)
    return "".join(part if i % 2 else fn(part) for i, part in enumerate(parts))


def _rewrite_condition(
    condition: str, pvs: list[tuple[str, bool]], sev_slots: dict[int, int], base_count: int
) -> tuple[str, int | None]:
    """Token-table rewrite; returns (text, first out-of-range pv index or None)."""
    bad: list[int] = []

    def token(m: re.Match) -> str:
        kind, n = m.group(1), int(m.group(2))
        if n >= base_count:
            bad.append(n)
            return m.group(0)
        if kind in (None, "Str"):
            return f"{{{n}}}"
        if kind == "Int":
            return f"floor({{{n}}})"
        if n not in sev_slots:
            sev_slots[n] = len(pvs)
            pvs.append((_severity_channel(pvs[n][0]), True))
        k = f"{{{sev_slots[n]}}}"
        return k if kind == "Sev" else _LEGACY_SEV_LADDER.format(k=k)

    text = _outside_literals(condition, lambda part: _TOKEN_RE.sub(token, part))
    return text, (bad[0] if bad else None)


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _pvstr_comparisons(condition: str) -> list[tuple[int, str]]:
    """``(N, literal body)`` for each ``pvStrN ==/!= "text"`` or ``"text" ==/!= pvStrN``.

    Literals are cut out by the linear ``_STRING_LITERAL_RE``; a condition with an
    unmatched quote has no well-defined literals and yields nothing.
    """
    parts = _STRING_LITERAL_RE.split(condition)
    code = parts[0::2]
    if any('"' in part or "'" in part for part in code):
        return []
    found: list[tuple[int, str]] = []
    used_after = False  # the pvStr after the previous literal is taken
    for i in range(1, len(parts), 2):
        literal = parts[i][1:-1]
        before = None if used_after else _PVSTR_BEFORE_LITERAL_RE.search(parts[i - 1])
        if before is not None:
            found.append((int(before.group(1)), literal))
            used_after = False
            continue
        after = _PVSTR_AFTER_LITERAL_RE.match(parts[i + 1])
        used_after = after is not None
        if after is not None:
            found.append((int(after.group(1)), literal))
    return found


def _pvstr_gateway_pvs(condition: str, pvs: list[tuple[str, bool]]) -> list[str]:
    """PVs whose ``pvStrN`` is compared with a non-numeric string on a non-``loc://`` PV."""
    found: list[str] = []
    for index, literal in _pvstr_comparisons(condition):
        if index >= len(pvs) or _is_number(literal):
            continue
        pv = pvs[index][0]
        if not pv.startswith("loc://") and pv not in found:
            found.append(pv)
    return found


def coerce_value(kind: str, value: Any, ctx: RuleContext, widget: str) -> Any:
    """Coerce a rule arm or static prop value (text or element) to ``kind``."""
    local: list[str] = []
    if isinstance(value, ET.Element):
        if kind == "color":
            result = color_from_element(value, ctx.named_colors, local, ctx.color)
        else:
            result = coerce(kind, value.text or "", ctx.named_colors, local, ctx=ctx.color)
    elif isinstance(value, str) and value.lstrip().startswith("<"):
        try:
            element = ET.fromstring(value)
        except ET.ParseError:
            element = None
        if element is not None:
            return coerce_value(kind, element, ctx, widget)
        result = coerce(kind, value, ctx.named_colors, local, ctx=ctx.color)
    elif isinstance(value, str):
        result = coerce(kind, value, ctx.named_colors, local, ctx=ctx.color)
    else:
        result = value  # already a Python value (defaults table)
    for message in local:
        ctx.warn(f"{widget}: {message}")
    return result


def _static_value(widget: BobWidget, prop: str) -> Any:
    """The widget's own value of ``prop``, else the per-type default, else ``None``."""
    if prop in widget.props:
        return widget.props[prop]
    defaults = BOB_DEFAULTS.get(widget.type, {})
    if prop in defaults:
        return defaults[prop]
    if prop == "visible":
        return True
    if prop in ("width", "height"):
        return default_size(widget.type)[0 if prop == "width" else 1]
    return None


def resolve_target(prop: str, widget: BobWidget, ctx: RuleContext, registry_id: str | None) -> str | None:
    """Phoebus rule ``prop_id`` -> IR target prop (registry prop name), or ``None``."""
    if prop in RULE_DIRECT_TARGETS:
        return RULE_DIRECT_TARGETS[prop]
    qt_prop = qt_prop_for(widget.type, prop)
    if qt_prop is None:
        return None
    if registry_id is None:
        mapped = qt_class_for(widget.type)
        registry_id = mapped[1] if mapped else None
    definition = ctx.resolve_registry().by_id(registry_id) if registry_id else None
    entry = definition.qt_prop_map.get(qt_prop) if definition is not None else None
    if entry is None:
        return None
    return entry.get("to", qt_prop) if isinstance(entry, dict) else str(entry)


def is_true(value: Any, ctx: RuleContext, widget: str) -> bool:
    """A raw ``.bob`` flag coerced to ``bool``; an absent (``None``) flag is false."""
    return bool(coerce_value("bool", value, ctx, widget)) if value is not None else False


def lower_rule(
    rule: BobRule,
    widget: BobWidget,
    ctx: RuleContext,
    *,
    registry_id: str | None = None,
) -> RuleSpec | None:
    """Lower one Phoebus ``<rule>`` on ``widget`` to a :class:`RuleSpec`.

    Returns ``None`` (with a warning on ``ctx``) when the target is unsupported, the
    rule is a ``background_color`` rule on a transparent label/textupdate with no
    ``transparent`` rule beside it, an ``out_exp`` arm is computed, a token names a
    PV the rule does not list, or a rewritten condition fails :func:`syntax_check`.
    ``registry_id`` overrides the class-table id (e.g. a style-dependent group).
    """
    name = widget.name
    prop = rule.prop_id

    target = resolve_target(prop, widget, ctx, registry_id)
    if target is None:
        ctx.warn(RULE_TARGET_UNSUPPORTED_WARNING.format(widget=name, target=prop))
        return None

    if (
        prop == "background_color"
        and widget.type in TRANSPARENT_BG_RULE_TYPES
        and not any(other.prop_id == "transparent" for other in widget.rules)
        and is_true(_static_value(widget, "transparent"), ctx, name)
    ):
        ctx.warn(TRANSPARENT_BG_RULE_WARNING.format(widget=name))
        return None

    kind = rule_coercion(prop)
    pvs: list[tuple[str, bool]] = [(normalize_macro_syntax(pv), trig) for pv, trig in rule.pvs]
    base_count = len(pvs)
    sev_slots: dict[int, int] = {}
    conditions: list[tuple[str, Any]] = []
    gateway_text_pvs: list[str] = []

    for bool_exp, raw_value in rule.expressions:
        if rule.out_exp:
            literal = raw_value.strip()
            if not _LITERAL_RE.match(literal):
                ctx.warn(UNSUPPORTED_EXPRESSION_WARNING.format(widget=name, expression=literal))
                return None
            if literal[:1] in ("'", '"'):
                literal = literal[1:-1]
            raw_value = literal
        python = js_to_python(normalize_macro_syntax(bool_exp))
        for pv in _pvstr_gateway_pvs(python, pvs[:base_count]):
            if pv not in gateway_text_pvs:
                gateway_text_pvs.append(pv)
        text, bad = _rewrite_condition(python, pvs, sev_slots, base_count)
        text = text.strip()  # js_to_python pads a leading ``!``; the Formula Engine wants no indent
        if bad is not None:
            ctx.warn(f"{name}: rule {rule.name!r} references pv{bad} but lists {base_count} PV(s)")
            return None
        # The module check always runs: an overriding context cannot widen the subset.
        if not (syntax_check(text, len(pvs)) and ctx.syntax_check(text)):
            ctx.warn(f"{name}: rule {rule.name!r} condition not lowered: {bool_exp}")
            return None
        conditions.append((text, coerce_value(kind, raw_value, ctx, name)))

    for pv in gateway_text_pvs:
        ctx.warn(PVSTR_GATEWAY_WARNING.format(widget=name, pv=pv))

    if conditions and conditions[-1][0] == "True":
        default = conditions.pop()[1]
    else:
        static = _static_value(widget, prop)
        default = None if static is None else coerce_value(kind, static, ctx, name)

    if prop in _FILE_RULE_TARGETS:
        values = [value for _, value in conditions] + ([] if default is None else [default])
        refused = next((v for v in values if not isinstance(v, str) or file_reference(v) is None), None)
        if refused is not None:
            ctx.warn(FILE_REFERENCE_WARNING.format(widget=name, what=f"rule {rule.name!r} value", reference=refused))
            return None
        conditions = [(text, file_reference(value)) for text, value in conditions]
        default = None if default is None else file_reference(default)

    return RuleSpec(target_property=target, name=rule.name or prop, pvs=pvs, conditions=conditions, default=default)
