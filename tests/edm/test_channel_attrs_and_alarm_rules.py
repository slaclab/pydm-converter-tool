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
    edm_file_to_ir,
)
from pydmconverter.edm.parser import EDMObject
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json


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
    obj = _obj("activeButtonClass", {"onLabel": "Enabled", "offLabel": "Disabled", "labelType": "literal"})
    _fixup_state_button(obj, qt_props, warnings)
    assert qt_props["text"] == "Disabled"
    assert qt_props["buttonType"] == "toggle"
    assert warnings == []


def test_state_button_without_readback_still_warns_on_differing_labels():
    qt_props, warnings = {}, []
    obj = _obj("activeButtonClass", {"onLabel": "Running", "offLabel": "Stopped", "labelType": "literal"})
    _fixup_state_button(obj, qt_props, warnings)
    assert any("resting" in w for w in warnings)


def test_button_without_label_type_shows_the_control_pv_state():
    # EDM writes labelType only for "literal": absent means pvState, and the
    # onLabel/offLabel it still carries are never drawn (button.cc drawActive).
    node = _object_to_source(
        _obj("activeButtonClass", {"controlPv": "X:MODE", "onLabel": "Running", "offLabel": "Stopped"})
    )
    assert node.qt_props["labelType"] == "pvState"
    assert node.qt_props["readbackChannel"] == "X:MODE"
    assert not {"text", "onLabel", "offLabel"} & node.qt_props.keys()
    assert node.warnings == []


def test_literal_button_switches_labels_on_the_control_pv():
    node = _object_to_source(
        _obj(
            "activeButtonClass",
            {"controlPv": "X:MODE", "onLabel": "Running", "offLabel": "Stopped", "labelType": "literal"},
        )
    )
    assert "labelType" not in node.qt_props
    assert node.qt_props["readbackChannel"] == "X:MODE"
    assert (node.qt_props["text"], node.qt_props["onLabel"], node.qt_props["offLabel"]) == (
        "Stopped",
        "Running",
        "Stopped",
    )
    assert node.warnings == []


def test_button_state_follows_the_indicator_pv_when_present():
    for label_type in ({}, {"labelType": "literal"}):
        node = _object_to_source(
            _obj("activeButtonClass", {"controlPv": "X:MODE_SET", "indicatorPv": "X:MODE", **label_type})
        )
        assert node.qt_props["channel"] == "X:MODE_SET"
        assert node.qt_props["readbackChannel"] == "X:MODE"


def test_message_button_labels_stay_literal_without_readback():
    # Message buttons switch onLabel/offLabel on the press, not on a PV (message_button.cc).
    node = _object_to_source(
        _obj("activeMessageButtonClass", {"controlPv": "X:CMD", "onLabel": "Running", "offLabel": "Stopped"})
    )
    assert not {"labelType", "readbackChannel"} & node.qt_props.keys()
    assert node.qt_props["text"] == "Stopped"
    assert any("resting" in w for w in node.warnings)


def test_state_buttons_validate_against_the_schema(tmp_path):
    def button(y, *lines):
        body = "\n".join(lines)
        return (
            "object activeButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
            f"x 10\ny {y}\nw 80\nh 20\n{body}\nendObjectProperties\n"
        )

    edl = tmp_path / "buttons.edl"
    edl.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 200\nh 100\nendScreenProperties\n"
        + button(10, 'controlPv "X:MODE"', 'onLabel "On"', 'offLabel "Off"')
        + button(40, 'controlPv "X:MODE"', 'onLabel "On"', 'offLabel "Off"', 'labelType "literal"'),
        encoding="utf-8",
    )
    screen = edm_file_to_ir(edl)
    pv_state, literal = screen.root.children
    assert pv_state.props["labelType"] == "pvState"
    assert pv_state.props["readbackPV"] == "X:MODE"
    assert "label" not in pv_state.props
    assert literal.props["readbackPV"] == "X:MODE"
    assert literal.props["label"] == "Off"
    assert validate_screen_json(to_wire_dict(screen)) == []


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
