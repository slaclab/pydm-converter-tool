"""Tests for Phoebus rule lowering (``pydmconverter.bob.rules.lower_rule``).

Rules are built from inline ``.bob`` XML through ``parse_bob`` so the parser's
representation of values (text or serialised ``<value>`` element) is the one lowered.
"""

from __future__ import annotations

import subprocess
import sys
from xml.sax.saxutils import escape

import pytest

from pydmconverter.bob.parser import BobWidget, parse_bob
from pydmconverter.bob.rules import RuleContext, _pvstr_gateway_pvs, lower_rule, syntax_check
from pydmconverter.ir.registry import VendoredRegistry

_REGISTRY = VendoredRegistry()


def _widget(inner: str, *, wtype: str = "textupdate", name: str = "W") -> BobWidget:
    xml = f'<display><widget type="{wtype}"><name>{name}</name>{inner}</widget></display>'
    return parse_bob(xml.encode()).widgets[0]


def _rule_xml(prop: str, pvs: list[str], exps: list[tuple[str, str]], *, out_exp: bool = False, value_tag=None) -> str:
    tag = value_tag or ("expression" if out_exp else "value")
    pv_xml = "".join(f"<pv_name>{pv}</pv_name>" for pv in pvs)
    exp_xml = "".join(
        f'<exp bool_exp="{escape(cond, {chr(34): "&quot;"})}"><{tag}>{val}</{tag}></exp>' for cond, val in exps
    )
    flag = "true" if out_exp else "false"
    return f'<rules><rule name="r" prop_id="{prop}" out_exp="{flag}">{exp_xml}{pv_xml}</rule></rules>'


def _lower(widget: BobWidget, index: int = 0):
    ctx = RuleContext(registry=_REGISTRY)
    spec = lower_rule(widget.rules[index], widget, ctx)
    return spec, ctx.warnings


# --- token table ----------------------------------------------------------------


@pytest.mark.parametrize(
    "cond, expected",
    [
        ("pv0 == 1", "{0} == 1"),
        ("pvStr0 == 1", "{0} == 1"),
        ("pvInt0 == 1", "floor({0}) == 1"),
        ("pv0 > 1 && pv1 < 2", "{0} > 1  and  {1} < 2"),
        ("pv0=3", "{0}==3"),
        ("!(pv1 > 0)", "not ({1} > 0)"),  # surrounding whitespace stripped
        ("Math.abs(pv0) > 1", "abs({0}) > 1"),
        ('pv0 == "pv1"', '{0} == "pv1"'),  # tokens inside string literals are text
    ],
)
def test_value_tokens(cond, expected):
    w = _widget(_rule_xml("visible", ["A:B", "C:D"], [(cond, "false")]))
    spec, warnings = _lower(w)
    assert spec is not None, warnings
    assert spec.conditions == [(expected, False)]
    assert spec.pvs == [("A:B", True), ("C:D", True)]
    assert spec.target_property == "visible"


def test_pvsev_binds_severity_channel():
    w = _widget(_rule_xml("visible", ["A:B.RBV"], [("pvSev0 >= 2", "false")]))
    spec, _ = _lower(w)
    assert spec.pvs == [("A:B.RBV", True), ("A:B.SEVR", True)]
    assert spec.conditions == [("{1} >= 2", False)]


def test_pvlegacysev_ladder_and_shared_severity_binding():
    w = _widget(_rule_xml("visible", ["A:B", "C:D"], [("pvLegacySev1 == 1 || pvSev1 == 2", "false")]))
    spec, _ = _lower(w)
    assert spec.pvs == [("A:B", True), ("C:D", True), ("C:D.SEVR", True)]
    ladder = "(2 if {2}==1 else (1 if {2}==2 else (-1 if {2}>=3 else 0)))"
    assert spec.conditions == [(f"{ladder} == 1  or  {{2}} == 2", False)]


def test_untriggered_pv_keeps_trigger_flag_and_macro_syntax():
    xml = (
        '<rules><rule name="r" prop_id="visible" out_exp="false">'
        '<exp bool_exp="pv0 == 1"><value>false</value></exp>'
        '<pv_name trig="false">$(P):X</pv_name></rule></rules>'
    )
    spec, _ = _lower(_widget(xml))
    assert spec.pvs == [("${P}:X", False)]


def test_out_of_range_pv_token_drops_rule():
    w = _widget(_rule_xml("visible", ["A:B"], [("pv3 == 1", "false")]))
    spec, warnings = _lower(w)
    assert spec is None
    assert any(m.startswith("W: ") and "pv3" in m for m in warnings)


# --- macros and the syntax check -------------------------------------------------


@pytest.mark.parametrize(
    "cond",
    [
        "${COLOR_CODE} == 0",
        "$(COLOR_CODE) == 0",
        "${M} > 0",  # M = __import__('os').system('x') or 1 would run as code
        "pv0 == '${M}'",  # M = x' or __import__('os').system('x') or 'x would close the literal
    ],
)
def test_macro_condition_is_not_lowered(cond):
    w = _widget(_rule_xml("visible", ["A"], [(cond, "false")]))
    spec, warnings = _lower(w)
    assert spec is None
    assert len(warnings) == 1 and "condition not lowered" in warnings[0]


@pytest.mark.parametrize(
    "cond, ok",
    [
        ("{0} == 1", True),
        ("${COLOR_CODE} == 0", False),
        ("floor({1}) > 2 and {0} != 'x'", True),
        ("(2 if {2}==1 else (1 if {2}==2 else (-1 if {2}>=3 else 0))) == 1", True),
        ("{0} ==", False),
        ("{0} === 1", False),
        ("abs({0} - 1) < 1e-3", True),
        ("__import__('os').system('true')", False),
        ("{0}.__class__", False),
        ("{0}[0] == 1", False),
        ("max({0}, 1) > 2", False),
        ("abs == 1", False),
        ("abs({0}, key=1) > 0", False),
        ("x == 1", False),  # a name that is no binding
        ("${M}(1) == 0", False),  # a macro as a callee
        ("[c for c in ()] == []", False),
        ("(lambda: 1)() == 1", False),
        ("{0} in (1, 2)", False),
        ("b'x' == {0}", False),
    ],
)
def test_syntax_check(cond, ok):
    assert syntax_check(cond) is ok
    assert RuleContext().syntax_check(cond) is ok


def test_syntax_check_bounds_the_bindings():
    assert syntax_check("{0} == {1}", 2)
    assert not syntax_check("{0} == {2}", 2)


class _PermissiveContext(RuleContext):
    def syntax_check(self, condition: str) -> bool:
        return True


@pytest.mark.parametrize(
    "cond",
    [
        "__import__('os').system('touch /tmp/x') == 0",
        "pv0.__class__ == 1",
        "Math.max(pv0, 1) > 2",
        "open('/etc/passwd') == 1",
    ],
)
def test_injected_condition_is_not_lowered(cond):
    w = _widget(_rule_xml("visible", ["A"], [(cond, "false")]))
    for ctx in (RuleContext(registry=_REGISTRY), _PermissiveContext(registry=_REGISTRY)):
        assert lower_rule(w.rules[0], w, ctx) is None
        assert len(ctx.warnings) == 1 and "condition not lowered" in ctx.warnings[0]


def test_out_exp_literal_check_is_linear():
    """``\\d+\\.?\\d*`` once backtracked quadratically on a long run of digits."""
    code = (
        "from pydmconverter.bob.rules import _LITERAL_RE\n"
        "assert _LITERAL_RE.match('1' * 200000 + 'x') is None\n"
        "assert _LITERAL_RE.match('1' * 200000 + '.5e3')\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


def test_condition_macros_are_replaced_in_one_linear_pass():
    code = (
        "from pydmconverter.bob.rules import syntax_check\n"
        "for cond in ['${' * 200000, '$(' * 200000, '${a}$(' * 100000]:\n"
        "    syntax_check(cond)\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


def test_syntax_failure_drops_rule_with_warning():
    w = _widget(_rule_xml("visible", ["A"], [("pv0 === 1", "false")]))
    spec, warnings = _lower(w)
    assert spec is None
    assert warnings and warnings[0].startswith("W: ")


# --- default arm, static default, value coercion ---------------------------------


def test_trailing_true_arm_becomes_default():
    w = _widget(_rule_xml("visible", ["A"], [("pv0 == 1", "false"), ("true", "true")]))
    spec, _ = _lower(w)
    assert spec.conditions == [("{0} == 1", False)]
    assert spec.default is True


def test_non_trailing_true_arm_is_kept():
    w = _widget(_rule_xml("visible", ["A"], [("true", "false"), ("pv0 == 1", "true")]))
    spec, _ = _lower(w)
    assert spec.conditions == [("True", False), ("{0} == 1", True)]


def test_static_prop_value_is_default():
    inner = '<foreground_color><color red="1" green="2" blue="3"/></foreground_color>' + _rule_xml(
        "foreground_color", ["A"], [("pv0 > 0", '<color red="255" green="0" blue="0"/>')]
    )
    spec, _ = _lower(_widget(inner))
    assert spec.target_property == "foregroundColor"
    assert spec.conditions == [("{0} > 0", "#ff0000")]
    assert spec.default == "#010203"


def test_defaults_table_used_when_prop_absent():
    spec, _ = _lower(_widget(_rule_xml("foreground_color", ["A"], [("pv0 > 0", "#00ff00")])))
    assert spec.default == "#000000"  # textupdate foreground_color default
    assert spec.conditions == [("{0} > 0", "#00ff00")]


def test_visible_defaults_true_and_number_coercion():
    spec, _ = _lower(_widget(_rule_xml("visible", ["A"], [("pv0 > 0", "false")])))
    assert spec.default is True
    inner = "<x>12</x>" + _rule_xml("x", ["A"], [("pv0 > 0", "40")])
    spec, _ = _lower(_widget(inner))
    assert spec.target_property == "x"
    assert spec.conditions == [("{0} > 0", 40)]
    assert spec.default == 12


def test_text_rule_resolves_through_qt_prop_map():
    inner = "<text>idle</text>" + _rule_xml("text", ["A"], [("pv0 == 1", "$(P) busy")])
    spec, _ = _lower(_widget(inner, wtype="label"))
    assert spec.target_property == "text"
    assert spec.conditions == [("{0} == 1", "${P} busy")]
    assert spec.default == "idle"


# --- target resolution -------------------------------------------------------------


def test_unsupported_rule_target_warns():
    w = _widget(_rule_xml("tooltip", ["A"], [("pv0 == 1", "x")]))
    spec, warnings = _lower(w)
    assert spec is None
    assert warnings == ["W: unsupported rule target tooltip"]


def test_prop_absent_from_qt_prop_map_is_unsupported():
    # action_button (regular-button) has no foregroundColor in its qtPropMap
    w = _widget(_rule_xml("foreground_color", ["A"], [("pv0 == 1", "#ff0000")]), wtype="action_button")
    spec, warnings = _lower(w)
    assert spec is None
    assert warnings == ["W: unsupported rule target foreground_color"]


# --- out_exp ------------------------------------------------------------------------


def test_out_exp_literal_lowered():
    w = _widget(_rule_xml("visible", ["A"], [("pvInt0==0", "false"), ("true", "true")], out_exp=True))
    spec, warnings = _lower(w)
    assert warnings == []
    assert spec.conditions == [("floor({0})==0", False)]
    assert spec.default is True


def test_out_exp_quoted_string_literal():
    w = _widget(_rule_xml("text", ["A"], [("pv0 == 1", "'on'")], out_exp=True), wtype="label")
    spec, _ = _lower(w)
    assert spec.conditions == [("{0} == 1", "on")]


def test_out_exp_computed_expression_warns():
    w = _widget(_rule_xml("text", ["A"], [("pv0 == 1", "pvStr0 + 'x'")], out_exp=True), wtype="label")
    spec, warnings = _lower(w)
    assert spec is None
    assert len(warnings) == 1
    assert warnings[0].startswith("W: unsupported rule expression")


# --- pvStr text compare on a gateway PV ---------------------------------------------

_PVSTR_WARNING = (
    "W: rule compares PV text; the Formula Engine delivers enum PVs as indices, verify {pv} is a string record"
)


@pytest.mark.parametrize(
    "cond, pv, warned",
    [
        ('pvStr0 == "ON"', "SR:MODE", True),
        ("'ON' != pvStr0", "SR:MODE", True),
        ('pvStr0 == "3.5"', "SR:MODE", False),  # numeric literal
        ('pvStr0 == "ON"', "loc://mode", False),  # local PV holds text
        ("pvStr0 == 1", "SR:MODE", False),  # not a string compare
        ('pvStr0 == "a\\"b"', "SR:MODE", True),  # escaped quote inside the literal
        ("pvStr0=='it\\'s'", "SR:MODE", True),
    ],
)
def test_pvstr_gateway_compare_warning(cond, pv, warned):
    w = _widget(_rule_xml("visible", [pv], [(cond, "false")]))
    spec, warnings = _lower(w)
    assert spec is not None
    expected = [_PVSTR_WARNING.format(pv=pv)] if warned else []
    assert warnings == expected


def test_pvstr_warning_once_per_pv():
    w = _widget(_rule_xml("visible", ["SR:MODE"], [('pvStr0 == "A"', "false"), ('pvStr0 == "B"', "false")]))
    _, warnings = _lower(w)
    assert warnings == [_PVSTR_WARNING.format(pv="SR:MODE")]


@pytest.mark.parametrize(
    "cond, found",
    [
        ('pvStr0 == "A" && "B" != pvStr1', ["G:0", "G:1"]),
        ('"A" == pvStr0 == "B"', ["G:0"]),
        ("pvStr2 == \"pvStr0 == 'x'\"", []),  # a comparison quoted inside a literal is text
        ('pvStr0 == "A', []),  # unmatched quote: no scan
        ("pvStr0 == 'A\" && pvStr1 == \"B'", ["G:0"]),  # pvStr1 is inside the one literal
    ],
)
def test_pvstr_comparisons_read_only_code_outside_literals(cond, found):
    assert _pvstr_gateway_pvs(cond, [("G:0", True), ("G:1", True), ("loc://x", True)]) == found


def test_pvstr_scan_is_linear_on_pathological_input():
    """An unterminated literal of backslashes once backtracked exponentially (2**n steps)."""
    code = (
        "from pydmconverter.bob.rules import _pvstr_gateway_pvs\n"
        "for cond in ['pvStr0 == \"' + '\\\\' * 5000 + 'x', '\"' + '\\\\' * 5000 + 'x == pvStr0',\n"
        "             'pvStr0 == \"' + 'a' * 20000 + ' \\\\\"' * 5000]:\n"
        "    _pvstr_gateway_pvs(cond, [('G:0', True)])\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


# --- transparent-label background drop ------------------------------------------------

_BG_RULE = _rule_xml("background_color", ["A"], [("pv0 == 1", "#ff0000")])
_TRANSPARENT_WARNING = "W: background_color rule ignored on a transparent widget (Phoebus semantics)"


def test_background_rule_dropped_on_default_transparent_label():
    spec, warnings = _lower(_widget(_BG_RULE, wtype="label"))
    assert spec is None
    assert warnings == [_TRANSPARENT_WARNING]


def test_background_rule_dropped_on_explicit_transparent_textupdate():
    spec, warnings = _lower(_widget("<transparent>true</transparent>" + _BG_RULE))
    assert spec is None
    assert warnings == [_TRANSPARENT_WARNING]


def test_background_rule_kept_on_opaque_label():
    spec, warnings = _lower(_widget("<transparent>false</transparent>" + _BG_RULE, wtype="label"))
    assert spec is not None
    assert spec.target_property == "backgroundColor"
    assert warnings == []


def test_background_rule_kept_when_transparent_rule_coexists():
    xml = (
        "<rules>"
        '<rule name="bg" prop_id="background_color" out_exp="false">'
        '<exp bool_exp="pv0 == 1"><value>#ff0000</value></exp><pv_name>A</pv_name></rule>'
        '<rule name="tr" prop_id="transparent" out_exp="false">'
        '<exp bool_exp="pv0 == 1"><value>false</value></exp><pv_name>A</pv_name></rule>'
        "</rules>"
    )
    spec, warnings = _lower(_widget(xml, wtype="label"))
    assert spec is not None
    assert spec.conditions == [("{0} == 1", "#ff0000")]
    assert _TRANSPARENT_WARNING not in warnings


# --------------------------------------------------------------------------
# Scheme colour context: rule colour values may become roles
# --------------------------------------------------------------------------
def _color_ctx():
    from pydmconverter.colors import ColorContext
    from pydmconverter.scheme import SchemeResult

    flat = {"roles": ["MAJOR", "OK"], "light": ["#ff0000", "#24a148"], "dark": ["#ff0000", "#24a148"]}
    scheme = SchemeResult(flat=flat, imports={"phoebus": {"MAJOR": "MAJOR", "OK": "OK"}}, meta={})
    return ColorContext.from_scheme(scheme)


def test_rule_context_color_defaults_to_none():
    assert RuleContext().color is None
    assert RuleContext(registry=_REGISTRY).color is None


def test_rule_color_arms_become_roles_with_color_context():
    widget = _widget(
        _rule_xml(
            "foreground_color",
            ["sim://a"],
            [
                ("pv0 > 1", '<color name="MAJOR" red="255" green="0" blue="0"/>'),
                ("pv0 > 0", '<color name="OK" red="0" green="255" blue="0"/>'),
            ],
        )
    )
    color = _color_ctx()
    ctx = RuleContext(registry=_REGISTRY, color=color)
    spec = lower_rule(widget.rules[0], widget, ctx)
    values = [value for _cond, value in spec.conditions]
    # MAJOR's light equals Phoebus red; OK's (#24a148) differs from Phoebus green (#00ff00).
    assert values == [{"$role": "MAJOR", "fallback": "#ff0000"}, "#00ff00"]
    notes = color.parity_notes()
    assert len(notes) == 1 and notes[0].startswith("parity: ") and "'OK'" in notes[0]


def test_rule_color_arms_stay_literal_without_color_context():
    widget = _widget(
        _rule_xml("foreground_color", ["sim://a"], [("pv0 > 1", '<color name="MAJOR" red="255" green="0" blue="0"/>')])
    )
    spec, _warnings = _lower(widget)
    assert [value for _cond, value in spec.conditions] == ["#ff0000"]


def test_coerce_value_passes_color_context_to_text_values():
    from pydmconverter.bob.rules import coerce_value

    ctx = RuleContext(color=_color_ctx())
    assert coerce_value("color", "MAJOR", ctx, "W") == {"$role": "MAJOR", "fallback": "#ff0000"}
    assert coerce_value("color", "MAJOR", RuleContext(), "W") == "#ff0000"
