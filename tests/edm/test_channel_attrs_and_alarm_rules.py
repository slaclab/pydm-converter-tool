"""Regression tests for the iteration-3 WS1 fixes: multi-channel attr routing
(controlPv/indicatorPv split instead of last-wins funneling), alarmPv-driven
alarm-color rules, and closed/filled activeLineClass -> polygon."""

from pydmconverter.edm.edm_qt import has_pv, resolve_qt_class
from pydmconverter.edm.ir_adapter import (
    _alarm_rules,
    _apply_channel_attrs,
    _fixup_line,
    _fixup_state_button,
    _object_to_source,
    _severity_channel,
)
from pydmconverter.edm.parser import EDMObject


def _obj(name, properties, w=10, h=10):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, w, h
    return obj


# ── channel routing ──────────────────────────────────────────────────────────


def test_two_channel_button_keeps_control_as_channel_and_maps_readback():
    qt_props, warnings = {}, []
    obj = _obj(
        "activeButtonClass",
        {"controlPv": "$(dev):HSTAMODESET", "indicatorPv": "$(dev):HSTAMODE"},
    )
    _apply_channel_attrs(obj, qt_props, warnings)
    assert qt_props["channel"] == "${dev}:HSTAMODESET"
    assert qt_props["readbackChannel"] == "${dev}:HSTAMODE"
    assert warnings == []


def test_menu_button_maps_indicator_to_readback():
    qt_props, warnings = {}, []
    obj = _obj(
        "activeMenuButtonClass",
        {"controlPv": "CAMR:X:Acquire", "indicatorPv": "CAMR:X:DetectorState_RBV"},
    )
    _apply_channel_attrs(obj, qt_props, warnings)
    assert qt_props["channel"] == "CAMR:X:Acquire"
    assert qt_props["readbackChannel"] == "CAMR:X:DetectorState_RBV"
    assert warnings == []


def test_choice_button_control_wins_and_indicator_drop_is_loud():
    qt_props, warnings = {}, []
    obj = _obj(
        "activeChoiceButtonClass",
        {"controlPv": "X:SET", "indicatorPv": "X:RBV"},
    )
    _apply_channel_attrs(obj, qt_props, warnings)
    assert qt_props["channel"] == "X:SET"
    assert "readbackChannel" not in qt_props
    assert any("indicatorPv readback dropped" in w for w in warnings)


def test_alarm_pv_never_becomes_the_channel():
    qt_props, warnings = {}, []
    obj = _obj("activeRectangleClass", {"alarmPv": "X:STAT"})
    _apply_channel_attrs(obj, qt_props, warnings)
    assert "channel" not in qt_props


def test_static_label_with_alarm_pv_stays_static():
    props = {"value": ["Fault"], "alarmPv": "X:STAT", "fgAlarm": True}
    assert not has_pv(props)
    assert resolve_qt_class("activextextclass", props) == "QLabel"


# ── alarm rules ──────────────────────────────────────────────────────────────


def test_alarm_rectangle_emits_line_and_fill_rules():
    obj = _obj(
        "activeRectangleClass",
        {"alarmPv": "FBCK:FB04:LG01:A1_S", "lineAlarm": True, "fillAlarm": True, "fill": True},
    )
    rules = _alarm_rules(obj)
    assert [r.target_property for r in rules] == ["lineColor", "fillColor"]
    for rule in rules:
        assert rule.pvs == [("FBCK:FB04:LG01:A1_S.SEVR", True)]
        assert rule.default == "#00c000"
        assert ("{0} == 2", "#ff0000") in rule.conditions


def test_alarm_pv_without_flags_is_ignored_like_edm():
    obj = _obj("activeRectangleClass", {"alarmPv": "X:STAT", "fill": True})
    assert _alarm_rules(obj) == []


def test_severity_channel_strips_field_refs_and_keeps_sevr():
    assert _severity_channel("A:B") == "A:B.SEVR"
    assert _severity_channel("A:B.SEVR") == "A:B.SEVR"
    assert _severity_channel("EVR:FEE1:203:CTRL.PLOK") == "EVR:FEE1:203:CTRL.SEVR"


def test_label_fg_alarm_with_alarm_pv_becomes_rule_and_drops_alarm_sensitive():
    obj = _obj(
        "activeXTextClass",
        {"value": ["OK"], "alarmPv": "X:STAT", "fgAlarm": True},
    )
    node = _object_to_source(obj)
    assert node.qt_class == "QLabel"
    assert "alarmSensitiveContent" not in node.qt_props
    assert [r.target_property for r in node.rules] == ["foregroundColor"]


def test_visibility_rule_appends_to_alarm_rules():
    from pydmconverter.edm.ir_adapter import edm_group_to_source_nodes
    from pydmconverter.edm.parser import EDMGroup

    obj = _obj(
        "activeRectangleClass",
        {"alarmPv": "X:STAT", "lineAlarm": True, "visPv": "X:VIS", "visMin": "1", "visMax": "5"},
    )
    group = EDMGroup.__new__(EDMGroup)
    group.objects = [obj]
    group.properties = {}
    group.x = group.y = 0
    group.width = group.height = 100
    nodes = edm_group_to_source_nodes(group)
    targets = [r.target_property for r in nodes[0].rules]
    assert targets == ["lineColor", "visible"]


# ── state buttons ────────────────────────────────────────────────────────────


def test_state_button_with_readback_carries_live_labels_without_warning():
    qt_props = {"readbackChannel": "X:STATE"}
    warnings = []
    obj = _obj("activeButtonClass", {"onLabel": "Enabled", "offLabel": "Disabled"})
    _fixup_state_button(obj, qt_props, warnings)
    assert qt_props["text"] == "Disabled"
    assert qt_props["buttonType"] == "toggle"
    assert warnings == []


def test_state_button_without_readback_still_warns_on_differing_labels():
    qt_props, warnings = {}, []
    obj = _obj("activeButtonClass", {"onLabel": "Running", "offLabel": "Stopped"})
    _fixup_state_button(obj, qt_props, warnings)
    assert any("resting" in w for w in warnings)


# ── closed/filled polylines ──────────────────────────────────────────────────


def test_filled_line_resolves_to_polygon_and_keeps_fill():
    props = {
        "fill": True,
        "fillColor": "index 14",
        "xPoints": ["0", "10", "5"],
        "yPoints": ["10", "10", "0"],
    }
    assert resolve_qt_class("activelineclass", props) == "PyDMDrawingIrregularPolygon"
    qt_props, warnings = {"brushFill": True, "brushColor": "#111111"}, []
    _fixup_line(_obj("activeLineClass", props), qt_props, warnings)
    assert qt_props["closePolygon"] is True
    assert qt_props["brushFill"] is True
    assert qt_props["brushColor"] == "#111111"
    assert not any("open polyline" in w for w in warnings)


def test_open_line_stays_polyline():
    props = {"xPoints": ["0", "10"], "yPoints": ["0", "10"]}
    assert resolve_qt_class("activelineclass", props) == "PyDMDrawingPolyline"
