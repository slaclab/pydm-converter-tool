"""EDM text display semantics: alarm borders, precision, background fill.

Sources: baselib/x_text_dsp_obj.cc (activeXTextDspClass) and
pvFactory/textupdate.cc (TextupdateClass).
"""

from pydmconverter.edm.ir_adapter import _object_to_source
from pydmconverter.edm.parser import EDMObject
from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.registry import VendoredRegistry


def _obj(name, properties, w=60, h=20):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, w, h
    return obj


def _ir_props(obj):
    source = _object_to_source(obj)
    return IRBuilder(VendoredRegistry())._build_node(source).props


# ── alarm border ─────────────────────────────────────────────────────────────


def test_use_alarm_border_with_fg_alarm_is_a_border_not_text_colour():
    obj = _obj("activeXTextDspClassnoedit", {"controlPv": "X:VAL", "fgAlarm": True, "useAlarmBorder": True})
    props = _ir_props(obj)
    assert props["alarmBorder"] is True
    assert "alarmSensitive" not in props  # the text keeps its static colour


def test_use_alarm_border_alone_does_nothing():
    obj = _obj("activeXTextDspClass", {"controlPv": "X:VAL", "useAlarmBorder": True})
    props = _ir_props(obj)
    assert "alarmBorder" not in props


def test_fg_alarm_alone_colours_the_text():
    obj = _obj("activeXTextDspClass", {"controlPv": "X:VAL", "fgAlarm": True})
    props = _ir_props(obj)
    assert props["alarmSensitive"] is True
    assert "alarmBorder" not in props


def test_textupdate_line_alarm_is_an_alarm_border():
    obj = _obj("TextupdateClass", {"controlPv": "X:VAL", "lineAlarm": True, "lineWidth": "2", "fgAlarm": True})
    props = _ir_props(obj)
    assert props["alarmBorder"] is True
    assert props["alarmSensitive"] is True


# ── precision ────────────────────────────────────────────────────────────────


def test_text_control_without_limits_from_db_uses_its_own_precision():
    """x_text_dsp_obj.cc: precision = PV PREC only if limitsFromDb or precision is null."""
    obj = _obj("activeXTextDspClassnoedit", {"controlPv": "X:VAL", "precision": "3"})
    assert _ir_props(obj)["precision"] == 3


def test_text_control_with_limits_from_db_ignores_its_precision():
    obj = _obj("activeXTextDspClass", {"controlPv": "X:VAL", "precision": "3", "limitsFromDb": True})
    assert _ir_props(obj)["precision"] == "fromPV"


def test_text_control_without_precision_uses_the_pv():
    obj = _obj("activeXTextDspClass", {"controlPv": "X:VAL"})
    assert _ir_props(obj).get("precision", "fromPV") == "fromPV"


def test_textupdate_default_mode_prints_with_the_pv_precision():
    """textupdate.cc: dm_default falls through to pv->get_string (the PV's PREC)."""
    obj = _obj("TextupdateClass", {"controlPv": "X:VAL", "precision": "2"})
    props = _ir_props(obj)
    assert props["precision"] == "fromPV"


def test_textupdate_decimal_mode_uses_widget_precision_default_zero():
    obj = _obj("TextupdateClass", {"controlPv": "X:VAL", "displayMode": "decimal"})
    props = _ir_props(obj)
    assert props["precision"] == 0
    assert props["format"] == "default"


def test_textupdate_exp_and_hex_modes_map_to_formats():
    exp = _ir_props(_obj("TextupdateClass", {"controlPv": "X:VAL", "displayMode": "exp", "precision": "4"}))
    assert (exp["format"], exp["precision"]) == ("exponential", 4)
    hexa = _ir_props(_obj("TextupdateClass", {"controlPv": "X:VAL", "displayMode": "hex", "precision": "4"}))
    assert hexa["format"] == "hex"
    assert hexa.get("precision", "fromPV") == "fromPV"


def test_textupdate_engineer_mode_is_noted():
    source = _object_to_source(_obj("TextupdateClass", {"controlPv": "X:VAL", "displayMode": "engineer"}))
    assert any("engineering" in warning for warning in source.warnings)


# ── background fill ──────────────────────────────────────────────────────────


def test_textupdate_background_only_when_filled():
    """textupdate.cc redraw_text: XFillRectangle only if is_filled."""
    bare = _ir_props(_obj("TextupdateClass", {"controlPv": "X:VAL", "bgColor": "rgb 0 0 65535"}))
    assert "backgroundColor" not in bare
    filled = _ir_props(_obj("TextupdateClass", {"controlPv": "X:VAL", "bgColor": "rgb 0 0 65535", "fill": True}))
    assert filled["backgroundColor"] == "#0000ff"


# The SLAC alarm block shape: NO_ALARM keeps the part's own colour ("noalarm : *").
_NOALARM_STATIC = {"static": {}, "alarm": {"noalarm": "*"}}


def test_unfilled_textupdate_bg_alarm_paints_nothing():
    """Without fill redraw_text never paints the background, so bgAlarm has
    nothing to colour: no bg alarm rule (its NO_ALARM default would be the
    static bgColor, i.e. an opaque box) and no "not supported" warning."""
    obj = _obj(
        "TextupdateClass",
        {"controlPv": "X:VAL", "bgColor": "rgb 0 0 65535", "alarmPv": "X:STAT", "fgAlarm": True, "bgAlarm": True},
    )
    source = _object_to_source(obj, _NOALARM_STATIC)
    assert "backgroundColor" not in source.qt_props
    assert [rule.target_property for rule in source.rules] == ["foregroundColor"]
    assert not any("bgAlarm" in warning for warning in source.warnings)
    assert "backgroundColor" not in IRBuilder(VendoredRegistry())._build_node(source).props


def test_filled_textupdate_keeps_its_bg_alarm_rule():
    obj = _obj(
        "RegTextupdateClass",
        {"controlPv": "X:VAL", "bgColor": "rgb 0 0 65535", "fill": True, "alarmPv": "X:STAT", "bgAlarm": True},
    )
    source = _object_to_source(obj, _NOALARM_STATIC)
    assert source.qt_props["backgroundColor"] == "#0000ff"
    (rule,) = source.rules
    assert rule.target_property == "backgroundColor"
    assert rule.pvs == [("X:STAT.SEVR", True)]
    assert rule.default == "#0000ff"  # noalarm * -> the static fill colour
    assert not any("bgAlarm" in warning for warning in source.warnings)
