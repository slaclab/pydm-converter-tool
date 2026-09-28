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
