"""Tests for the remaining colour emitters routed through the parity rule.

Alarm colours, the rule colour fallback, rule arms and defaults, the Phoebus-named
widget defaults (``BOB_DEFAULTS``) and the undeclared display background all go
through :func:`~pydmconverter.colors.named_color`: a scheme role when the role's
light value equals the hex the converter writes today, else that hex with a
``parity:`` note, unless the text pairing (:mod:`pydmconverter.pairing`) makes a default
text the role of the ground it sits on. Defaults with no Phoebus name stay literal. Panels and schemes are
synthetic, except the last tests, which use the vendored ``canopy-default`` scheme.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS
from pydmconverter.colors import ColorContext
from pydmconverter.bob.parser import BobScript, BobWidget, parse_bob
from pydmconverter.bob.rules import RuleContext, lower_rule
from pydmconverter.bob.scripts import match_alarm_boilerplate
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.registry import VendoredRegistry
from pydmconverter.react import convert_bytes
from pydmconverter.scheme import SchemeResult, load_scheme

_REGISTRY = VendoredRegistry()

# Synthetic scheme. Equal to Phoebus's built-ins: OK, MINOR, Text, Background,
# Read_Background, Display_Background. Overridden: MAJOR, INVALID, DISCONNECTED.
# On/Off exist as roles but the LED and bool_button defaults have no Phoebus name.
_ROLES = {
    "OK": "#00ff00",
    "MINOR": "#ff8000",
    "MAJOR": "#da1e28",
    "INVALID": "#ff00ff",
    "DISCONNECTED": "#6f6f6f",
    "Text": "#000000",
    "Background": "#ffffff",
    "Read_Background": "#f0f0f0",
    "Display_Background": "#ffffff",
    "On": "#00ff00",
    "Off": "#3c643c",
}


def _scheme(**overrides: str) -> SchemeResult:
    roles = {**_ROLES, **overrides}
    names = list(roles)
    flat = {"roles": names, "light": [roles[r] for r in names], "dark": ["#101010"] * len(names)}
    return SchemeResult(flat=flat, imports={"phoebus": {n: n for n in names}}, meta={})


def _ctx(scheme: SchemeResult | None = None) -> ColorContext:
    return ColorContext.from_scheme(scheme or _scheme(), dict(BUILTIN_NAMED_COLORS))


def _role(role: str, fallback: str) -> dict:
    return {"$role": role, "fallback": fallback}


def _bob_ir(data: bytes, **kwargs):
    """Convert ``.bob`` bytes through the public bytes entry point."""
    return convert_bytes(data, kind="bob", **kwargs)


def _panel(body: str, background: str = "") -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0"><name>t</name>{background}{body}</display>'
    ).encode()


def _wire(panel: bytes, scheme: SchemeResult | None = None, **kwargs) -> dict:
    return to_wire_dict(_bob_ir(panel, scheme=scheme, **kwargs))


def _children(wire: dict) -> list[dict]:
    return wire["root"]["children"]


def _parity(node: dict) -> list[str]:
    return [w for w in node.get("warnings", []) if w.startswith("parity: ")]


_LABEL = '<widget type="label" version="2.0.0"><name>L</name><text>a</text></widget>'
_TEXTUPDATE = '<widget type="textupdate" version="2.0.0"><name>T</name><pv_name>sim://x</pv_name></widget>'
_LED = '<widget type="led" version="2.0.0"><name>D</name><pv_name>sim://y</pv_name></widget>'
_BOOL = '<widget type="bool_button" version="2.0.0"><name>B</name><pv_name>sim://z</pv_name></widget>'
_RECT = '<widget type="rectangle" version="2.0.0"><name>R</name></widget>'


# --------------------------------------------------------------------------
# Alarm boilerplate colours
# --------------------------------------------------------------------------
_ALARM_SCRIPT = """from org.csstudio.display.builder.runtime.script import PVUtil
from org.csstudio.display.builder.model.persist import WidgetColorService
sevr = PVUtil.getSeverity(pvs[0])
cn = ( 'OK', 'MINOR', 'MAJOR', 'INVALID', 'DISCONNECTED' )[sevr]
widget.setPropertyValue('background_color', WidgetColorService.getColor(cn))"""


def _alarm(ctx: RuleContext):
    script = BobScript(name="", file="EmbeddedPy", text=_ALARM_SCRIPT, pvs=[("A:B", True)])
    widget = BobWidget(type="rectangle", name="R1", props={}, scripts=[script])
    return match_alarm_boilerplate(script, widget, ctx)


def test_alarm_colours_become_roles_under_parity():
    color = _ctx()
    ctx = RuleContext(registry=_REGISTRY, color=color)
    spec = _alarm(ctx)
    assert spec is not None, ctx.warnings
    assert spec.default == _role("OK", "#00ff00")
    values = [value for _cond, value in spec.conditions]
    assert values == [_role("MINOR", "#ff8000"), "#ff0000", _role("INVALID", "#ff00ff")]
    notes = color.parity_notes()
    assert len(notes) == 1
    assert "'MAJOR'" in notes[0] and "#ff0000" in notes[0] and "#da1e28" in notes[0]
    assert "background_color" in notes[0]


def test_alarm_colours_without_scheme_stay_literal():
    spec = _alarm(RuleContext(registry=_REGISTRY))
    assert spec.default == "#00ff00"
    assert [value for _cond, value in spec.conditions] == ["#ff8000", "#ff0000", "#ff00ff"]


def test_alarm_colours_follow_color_def_then_scheme():
    # A color.def table moves OK off the role's light value: literal plus a note.
    named = dict(BUILTIN_NAMED_COLORS, OK=(1, 2, 3, 255))
    color = ColorContext.from_scheme(_scheme(), named)
    spec = _alarm(RuleContext(registry=_REGISTRY, named_colors=named, color=color))
    assert spec.default == "#010203"
    assert any("'OK'" in note for note in color.parity_notes())


# --------------------------------------------------------------------------
# Rule arms, rule defaults and the rule colour fallback
# --------------------------------------------------------------------------
def _rule_widget(inner: str, *, wtype: str = "textupdate") -> BobWidget:
    xml = f'<display><widget type="{wtype}"><name>W</name>{inner}</widget></display>'
    return parse_bob(xml.encode()).widgets[0]


def _rule(prop: str, value_xml: str) -> str:
    return (
        f'<rules><rule name="r" prop_id="{prop}" out_exp="false">'
        f'<exp bool_exp="pv0 == 1"><value>{value_xml}</value></exp><pv_name>X:Y</pv_name></rule></rules>'
    )


def test_rule_arm_named_colour_becomes_role():
    widget = _rule_widget(_rule("foreground_color", '<color name="MINOR" red="255" green="128" blue="0"/>'))
    spec = lower_rule(widget.rules[0], widget, RuleContext(registry=_REGISTRY, color=_ctx()))
    assert spec.conditions[0][1] == _role("MINOR", "#ff8000")


def test_textupdate_foreground_rule_default_is_the_text_role():
    # No authored foreground colour: the default comes from BOB_DEFAULTS (Text).
    widget = _rule_widget(_rule("foreground_color", '<color red="255" green="0" blue="0"/>'))
    color = _ctx()
    spec = lower_rule(widget.rules[0], widget, RuleContext(registry=_REGISTRY, color=color))
    assert spec.conditions[0][1] == "#ff0000"
    assert spec.default == _role("Text", "#000000")
    # ... and equals what the static Text default lowers to on the same widget.
    wire = _wire(_panel(_TEXTUPDATE), _scheme())
    assert _children(wire)[0]["props"]["foregroundColor"] == spec.default


def test_textupdate_foreground_rule_default_without_scheme_is_black():
    widget = _rule_widget(_rule("foreground_color", '<color red="255" green="0" blue="0"/>'))
    spec = lower_rule(widget.rules[0], widget, RuleContext(registry=_REGISTRY))
    assert spec.default == "#000000"


def test_rule_colour_fallback_becomes_background_role():
    # A label background rule: no authored value and no table default -> Phoebus Background.
    body = (
        '<widget type="label" version="2.0.0"><name>L</name><text>a</text><transparent>false</transparent>'
        + _rule("background_color", '<color name="MAJOR" red="255" green="0" blue="0"/>')
        + "</widget>"
    )
    rule = _children(_wire(_panel(body), _scheme()))[0]["rules"][0]
    assert rule["default"] == _role("Background", "#ffffff")
    assert rule["conditions"][0]["value"] == "#ff0000"  # MAJOR is overridden: literal


def test_rule_colour_fallback_overridden_keeps_literal_and_notes():
    body = (
        '<widget type="label" version="2.0.0"><name>L</name><text>a</text><transparent>false</transparent>'
        + _rule("background_color", '<color red="1" green="2" blue="3"/>')
        + "</widget>"
    )
    node = _children(_wire(_panel(body), _scheme(Background="#eeeeee")))[0]
    assert node["rules"][0]["default"] == "#ffffff"
    notes = _parity(node)
    assert len(notes) == 1 and "'Background'" in notes[0] and "#eeeeee" in notes[0]


# --------------------------------------------------------------------------
# Phoebus-named widget defaults; unnamed defaults stay literal
# --------------------------------------------------------------------------
def test_label_and_textupdate_defaults_become_roles():
    label, textupdate = _children(_wire(_panel(_LABEL + _TEXTUPDATE), _scheme()))
    assert label["props"]["foregroundColor"] == _role("Text", "#000000")
    assert textupdate["props"]["foregroundColor"] == _role("Text", "#000000")
    assert textupdate["props"]["backgroundColor"] == _role("Read_Background", "#f0f0f0")


def test_label_and_textupdate_defaults_without_scheme_are_todays_hex():
    label, textupdate = _children(_wire(_panel(_LABEL + _TEXTUPDATE)))
    assert label["props"]["foregroundColor"] == "#000000"
    assert textupdate["props"]["foregroundColor"] == "#000000"
    assert textupdate["props"]["backgroundColor"] == "#f0f0f0"


def test_defaults_follow_color_def_without_scheme(tmp_path: Path):
    color_def = tmp_path / "color.def"
    color_def.write_text("Text = 10, 20, 30\nRead_Background = 200, 201, 202\n", encoding="utf-8")
    label, textupdate = _children(_wire(_panel(_LABEL + _TEXTUPDATE), color_def_path=color_def))
    assert label["props"]["foregroundColor"] == "#0a141e"
    assert textupdate["props"]["foregroundColor"] == "#0a141e"
    assert textupdate["props"]["backgroundColor"] == "#c8c9ca"


def test_overridden_default_role_keeps_literal_with_prop_slot_note():
    label, _textupdate = _children(_wire(_panel(_LABEL + _TEXTUPDATE), _scheme(Text="#161616")))
    assert label["props"]["foregroundColor"] == "#000000"
    notes = _parity(label)
    assert len(notes) == 1
    assert "'Text'" in notes[0] and "2 uses" in notes[0] and "foreground_color" in notes[0]


def test_led_and_bool_button_on_off_stay_literal():
    led, button = _children(_wire(_panel(_LED + _BOOL), _scheme()))
    assert (led["props"]["onColor"], led["props"]["offColor"]) == ("#00ff00", "#3c643c")
    on_off = {k: v for k, v in button["props"].items() if k in ("onColor", "offColor")}
    assert all(isinstance(v, str) for v in on_off.values())


def test_shape_fill_and_line_defaults_stay_literal():
    (rect,) = _children(_wire(_panel(_RECT), _scheme()))
    colors = [v for k, v in rect["props"].items() if k.lower().endswith("color")]
    assert colors and all(isinstance(v, str) and v.startswith("#") for v in colors)


# --------------------------------------------------------------------------
# Undeclared display background
# --------------------------------------------------------------------------
def test_undeclared_display_background_becomes_role():
    wire = _wire(_panel(_LABEL), _scheme())
    assert wire["root"]["props"]["backgroundColor"] == _role("Display_Background", "#ffffff")


def test_undeclared_display_background_without_scheme_is_white():
    wire = _wire(_panel(_LABEL))
    assert wire["root"]["props"]["backgroundColor"] == "#ffffff"
    assert to_json(_bob_ir(_panel(_LABEL))) == to_json(_bob_ir(_panel(_LABEL), scheme=None))


def test_undeclared_display_background_overridden_stays_literal_with_note():
    wire = _wire(_panel(_LABEL), _scheme(Display_Background="#eeeeee"))
    assert wire["root"]["props"]["backgroundColor"] == "#ffffff"
    notes = _parity(_children(wire)[0])
    assert len(notes) == 1
    assert "'Display_Background'" in notes[0] and "#eeeeee" in notes[0] and "background_color" in notes[0]


@pytest.mark.parametrize("body", [_LABEL, _TEXTUPDATE + _LED])
def test_undeclared_display_background_with_vendored_canopy_default(body):
    wire = _wire(_panel(body), load_scheme(None))
    assert wire["root"]["props"]["backgroundColor"] == {"$role": "Display_Background", "fallback": "#ffffff"}


def test_vendored_canopy_default_label_default_pairs_with_the_display_background():
    # canopy-default's Text light (#161616) is not Phoebus black, so parity alone would keep
    # black text on the Display_Background role (unreadable in the dark theme). Pairing makes
    # the text the Text role and drops the parity note for it.
    (label,) = _children(_wire(_panel(_LABEL), load_scheme(None)))
    assert label["props"]["foregroundColor"] == _role("Text", "#000000")
    assert not any("'Text'" in note for note in _parity(label))
    assert any(w.startswith("pair: color 'Text'") for w in label.get("warnings", []))
