"""Which PV each EDM tag is, per class (edm_qt.EDM_CHANNEL_ROLES).

A widget's channel is its class's data PV, whatever order the file lists the
tags in: a readback, a colour-rule PV or a null PV never takes its place.

Sources: baselib/x_text_dsp_obj.cc, x_text_obj.cc, button.cc, menu_button.cc,
message_button.cc, slider.cc, choiceButton/choice_button.cc,
pvFactory/textupdate.cc and edmlib/pvColor.cc.
"""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.edm_qt import channel_roles
from pydmconverter.edm.ir_adapter import _apply_channel_attrs, _object_to_source, edm_file_to_ir
from pydmconverter.edm.parser import EDMObject
from pydmconverter.edm.parser_helpers import parse_colors_list
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
SCREEN = FIXTURES / "channel_roles.edl"
COLORS = FIXTURES / "colors.list"

# The fixture's objects, one per row, by their y.
TEXT_COLOR, CHOICE, BUTTON, MENU, SLIDER = 10, 40, 80, 120, 160
NULL_DEFAULT, NULL_EQ_0, NULL_DISABLED, STATIC_TEXT = 210, 240, 270, 300
MESSAGE, RELATED, TEXTUPDATE, RECTANGLE, READBACK_ONLY = 330, 370, 410, 440, 470
# The rectangle's .ui widget reaches past its rect by its 1 px pen.
RECTANGLE_UI = RECTANGLE - 1


@pytest.fixture
def ui(tmp_path, caplog):
    """The converted .ui's widgets by row, with the conversion's warnings in caplog."""
    output = tmp_path / "screen.ui"
    with caplog.at_level(logging.WARNING):
        convert(str(SCREEN), str(output))
    rows = {}
    for widget in ET.parse(output).getroot().find(".//widget[@name='centralwidget']").findall("widget"):
        rows.setdefault(int(widget.find("property[@name='geometry']/rect/y").text), []).append(widget)
    return rows


@pytest.fixture(scope="module")
def ir():
    """The Screen IR's nodes by row."""
    wire = to_wire_dict(edm_file_to_ir(SCREEN, color_list_path=COLORS))
    assert validate_screen_json(wire) == []
    return {node["geometry"]["y"]: node for node in wire["root"]["children"]}


def _prop(widget, name):
    element = widget.find(f"property[@name='{name}']")
    return None if element is None else element[0].text


def _rule_channels(widget, rule_property):
    rules = json.loads(_prop(widget, "rules") or "[]")
    return [channel["channel"] for rule in rules if rule["property"] == rule_property for channel in rule["channels"]]


# ── .ui ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "row, widget_class, channel",
    [
        pytest.param(TEXT_COLOR, "PyDMLabel", "DEMO:VALUE", id="text control + colorPv"),
        pytest.param(CHOICE, "PyDMEnumButton", "DEMO:SETPOINT", id="choice button + indicatorPv"),
        pytest.param(MENU, "PyDMPushButton", "DEMO:MENU_SET", id="menu button + indicatorPv"),
        pytest.param(SLIDER, "PyDMSlider", "DEMO:SLIDER_SET", id="slider + indicatorPv"),
        pytest.param(NULL_DEFAULT, "PyDMLabel", "DEMO:NULL_CTL", id="text control + nullPv"),
        pytest.param(STATIC_TEXT, "PyDMLabel", "DEMO:STATUS", id="static text + alarmPv"),
        pytest.param(MESSAGE, "PyDMPushButton", "DEMO:MSG", id="message button + colorPv"),
        pytest.param(RELATED, "PyDMRelatedDisplayButton", None, id="related display + colorPv"),
        pytest.param(TEXTUPDATE, "PyDMLabel", "DEMO:TU_VALUE", id="text update + colorPv"),
        pytest.param(RECTANGLE_UI, "PyDMDrawingRectangle", "DEMO:RECT_STAT", id="rectangle + alarmPv"),
        pytest.param(READBACK_ONLY, "PyDMPushButton", "DEMO:IND_ONLY", id="button with only indicatorPv"),
    ],
)
def test_ui_channel_is_the_data_pv(ui, row, widget_class, channel):
    (widget,) = ui[row]
    assert widget.get("class") == widget_class
    assert _prop(widget, "channel") == channel


def test_ui_button_and_its_off_variant_write_and_key_on_the_control_pv(ui):
    """EDM's button label follows the controlPv, so the on/off variants switch on it."""
    on, off = ui[BUTTON]
    for widget in (on, off):
        assert _prop(widget, "channel") == "DEMO:BTN_SET"
        assert _rule_channels(widget, "Visible") == ["DEMO:BTN_SET"]
    assert {_prop(on, "text"), _prop(off, "text")} == {"On", "Off"}


def test_ui_choice_button_hides_while_its_control_pv_is_disconnected(ui):
    (choice,) = ui[CHOICE]
    assert _rule_channels(choice, "Visible") == ["DEMO:SETPOINT"]


def test_ui_static_text_with_alarm_pv_keeps_its_text(ui):
    (label,) = ui[STATIC_TEXT]
    assert _prop(label, "text") == "Status"
    assert _prop(label, "displayLabelText") == "true"


def test_ui_drawing_with_alarm_pv_is_not_a_label(ui):
    (rectangle,) = ui[RECTANGLE_UI]
    assert _prop(rectangle, "displayLabelText") is None


def test_ui_text_controls_with_null_pv_show_their_control_pv(ui):
    for row, channel in ((NULL_EQ_0, "DEMO:NULL0_CTL"), (NULL_DISABLED, "DEMO:NULLOFF_CTL")):
        (label,) = ui[row]
        assert _prop(label, "channel") == channel


def test_ui_warns_about_each_pv_it_drops(ui, caplog):
    messages = "\n".join(record.getMessage() for record in caplog.get_records("setup"))
    for dropped in (
        "indicatorPv DEMO:READBACK is a readback",
        "indicatorPv DEMO:BTN_RBV is a readback",
        "indicatorPv DEMO:MENU_RBV is a readback",
        "indicatorPv DEMO:SLIDER_RBV is a readback",
        "colorPv DEMO:COLOR picks rule colours",
        "colorPv DEMO:MSG_COLOR picks rule colours",
        "colorPv DEMO:RD_COLOR picks rule colours",
        "colorPv DEMO:TU_COLOR picks rule colours",
        "nullPv DEMO:NULL_REF switches the text to nullColor (nullEqCtl)",
        "nullPv DEMO:NULL0_REF switches the text to nullColor (nullEq0)",
        "DEMO:RD_WRITE",
        "indicatorPv DEMO:IND_ONLY is its only PV",
    ):
        assert dropped in messages
    # Disabled null detection never compares, so nothing is lost.
    assert "DEMO:NULLOFF_REF" not in messages
    # A static text's and a drawing's alarm PV is their channel.
    assert "DEMO:STATUS" not in messages
    assert "DEMO:RECT_STAT" not in messages


# ── Screen IR ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "row, node_type, pv, readback",
    [
        pytest.param(TEXT_COLOR, "pv-label", "DEMO:VALUE", None, id="text control + colorPv"),
        pytest.param(CHOICE, "pv-radio-group", "DEMO:SETPOINT", None, id="choice button + indicatorPv"),
        pytest.param(BUTTON, "pv-button", "DEMO:BTN_SET", "DEMO:BTN_RBV", id="button + indicatorPv"),
        pytest.param(MENU, "pv-button", "DEMO:MENU_SET", "DEMO:MENU_RBV", id="menu button + indicatorPv"),
        pytest.param(SLIDER, "pv-slider", "DEMO:SLIDER_SET", None, id="slider + indicatorPv"),
        pytest.param(NULL_DEFAULT, "pv-label", "DEMO:NULL_CTL", None, id="text control + nullPv"),
        pytest.param(STATIC_TEXT, "text-label", None, None, id="static text + alarmPv"),
        pytest.param(MESSAGE, "pv-button", "DEMO:MSG", None, id="message button + colorPv"),
        pytest.param(RELATED, "related-display-button", None, None, id="related display + colorPv"),
        pytest.param(TEXTUPDATE, "pv-label", "DEMO:TU_VALUE", None, id="text update + colorPv"),
        pytest.param(READBACK_ONLY, "pv-button", "DEMO:IND_ONLY", "DEMO:IND_ONLY", id="button with only indicatorPv"),
    ],
)
def test_ir_pv_is_the_data_pv(ir, row, node_type, pv, readback):
    node = ir[row]
    assert node["type"] == node_type
    assert node["props"].get("pv") == pv
    assert node["props"].get("readbackPV") == readback


@pytest.mark.parametrize("row", [CHOICE, SLIDER])
def test_ir_readback_without_a_home_is_dropped_loudly(ir, row):
    assert ir[row]["warnings"] == ["EDM indicatorPv readback dropped (controlPv kept as the channel)"]


def test_ir_related_display_pv_list_is_dropped_loudly(ir):
    """EDM writes a related display's pv[] when it opens a display; the IR button can't."""
    assert ir[RELATED]["warnings"] == ["EDM pv dropped (the widget has no channel)"]


@pytest.mark.parametrize(
    "name, properties, dropped",
    [
        pytest.param("activeSliderClass", {"ctrl1Pv": "X:POS"}, "ctrl1Pv", id="slider + mmv tag"),
        pytest.param("activeRectangleClass", {"controlPv": "X:STRAY"}, "controlPv", id="rectangle + controlPv"),
        pytest.param(
            "activeXTextClass", {"alarmPv": "X:STAT", "controlPv": "X:STRAY"}, "controlPv", id="static text + controlPv"
        ),
    ],
)
def test_ir_data_pv_tag_on_a_class_without_one_is_dropped_loudly(name, properties, dropped):
    qt_props, warnings = {}, []
    _apply_channel_attrs(_obj(name, properties), qt_props, warnings)
    assert "channel" not in qt_props
    assert warnings == [f"EDM {dropped} dropped (the widget has no channel)"]


def test_ir_static_text_alarm_pv_drives_alarm_colours(ir):
    (rule,) = ir[STATIC_TEXT]["rules"]
    assert rule["targetProperty"] == "foregroundColor"
    assert [pv["name"] for pv in rule["pvs"]] == ["DEMO:STATUS.SEVR"]


@pytest.mark.parametrize(
    "row, control, null, expression",
    [
        pytest.param(NULL_DEFAULT, "DEMO:NULL_CTL", "DEMO:NULL_REF", "{0} == {1}", id="nullEqCtl"),
        pytest.param(NULL_EQ_0, "DEMO:NULL0_CTL", "DEMO:NULL0_REF", "{1} == 0", id="nullEq0"),
    ],
)
def test_ir_null_pv_switches_the_text_to_null_color(ir, row, control, null, expression):
    node = ir[row]
    assert node["props"]["pv"] == control
    (rule,) = node["rules"]
    assert rule["targetProperty"] == "foregroundColor"
    assert [pv["name"] for pv in rule["pvs"]] == [control, null]
    assert rule["conditions"] == [{"expression": expression, "value": "#ffff00"}]  # nullColor
    assert rule["default"] == "#0000ff"  # fgColor
    assert not node.get("warnings")


def test_ir_disabled_null_detection_does_nothing(ir):
    node = ir[NULL_DISABLED]
    assert not node.get("rules")
    assert not node.get("warnings")


# ── null colour with other colours (unit level) ──────────────────────────────

_PALETTE = """4 0 0
max=0x10000

static 14 "Yellow" { 0xffff 0xffff 0 }
static 15 "Green" { 0 0xffff 0 }
static 25 "Blue" { 0 0 0xffff }

rule 84 level {
 = 1 : "Green"
 default : "Blue"
}
"""


def _obj(name, properties):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, 60, 20
    return obj


def _palette(tmp_path):
    path = tmp_path / "colors.list"
    path.write_text(_PALETTE, encoding="utf-8")
    return parse_colors_list(str(path))


def test_null_color_goes_before_a_colour_rule_on_the_text(tmp_path):
    """pvColor.cc setNull: the null colour replaces the evaluated rule colour."""
    obj = _obj(
        "activeXTextDspClassnoedit",
        {
            "controlPv": "X:VAL",
            "colorPv": "X:COLOR",
            "fgColor": "index 84",
            "nullPv": "X:NULL",
            "nullColor": "index 14",
            "nullCondition": "nullEq0",
        },
    )
    source = _object_to_source(obj, _palette(tmp_path))
    (rule,) = [rule for rule in source.rules if rule.target_property == "foregroundColor"]
    assert rule.pvs == [("X:COLOR", True), ("X:VAL", True), ("X:NULL", True)]
    assert rule.conditions[0] == ("{2} == 0", "#ffff00")
    assert rule.conditions[1:] == [("{0} == 1", "#00ff00")]
    assert rule.default == "#0000ff"


def test_null_color_is_not_drawn_with_the_alarm_border(tmp_path):
    """x_text_dsp_obj.cc draws the text in its static colour while the alarm border is on."""
    obj = _obj(
        "activeXTextDspClassnoedit",
        {
            "controlPv": "X:VAL",
            "fgColor": "index 25",
            "fgAlarm": True,
            "useAlarmBorder": True,
            "nullPv": "X:NULL",
            "nullColor": "index 14",
        },
    )
    assert _object_to_source(obj, _palette(tmp_path)).rules == []


def test_editable_text_control_drops_its_null_colour_loudly(tmp_path):
    """pv-text-input has no foreground colour to switch."""
    obj = _obj(
        "activeXTextDspClass",
        {"controlPv": "X:VAL", "editable": True, "nullPv": "X:NULL", "nullColor": "index 14"},
    )
    source = _object_to_source(obj, _palette(tmp_path))
    assert source.qt_props["channel"] == "X:VAL"
    assert source.rules == []
    assert source.warnings == ["EDM nullPv null colour dropped (no foreground colour to switch)"]


@pytest.mark.parametrize(
    "colours",
    [
        pytest.param({"nullColor": "index 14"}, id="no fgColor"),
        pytest.param({"fgColor": "index 99", "nullColor": "index 14"}, id="fgColor not in the palette"),
        pytest.param({"fgColor": "index 25", "nullColor": "index 99"}, id="nullColor not in the palette"),
    ],
)
def test_null_color_needs_both_colours(tmp_path, colours):
    """The rule's default is the static fgColor the text returns to, and the IR requires one."""
    obj = _obj("activeXTextDspClassnoedit", {"controlPv": "X:VAL", "nullPv": "X:NULL", **colours})
    source = _object_to_source(obj, _palette(tmp_path))
    assert source.rules == []
    assert "EDM nullPv null colour dropped (its nullColor or fgColor did not resolve)" in source.warnings


def test_bar_null_pv_is_an_unmapped_offset():
    source = _object_to_source(_obj("activeBarClass", {"indicatorPv": "X:VAL", "nullPv": "X:OFFSET"}))
    assert source.qt_props["channel"] == "X:VAL"
    assert source.warnings == ["EDM bar props not mapped: nullPv"]


# ── the role table ───────────────────────────────────────────────────────────


def test_button_family_readback_backs_up_a_missing_control_pv():
    roles = channel_roles("activechoicebuttonclass")
    both = {"controlPv": "X:SET", "indicatorPv": "X:RBV"}
    assert (roles.data_attr(both), roles.readback_attr(both)) == ("controlPv", "indicatorPv")
    alone = {"indicatorPv": "X:RBV"}
    assert (roles.data_attr(alone), roles.readback_attr(alone)) == ("indicatorPv", None)


def test_classes_without_a_data_pv():
    for name in ("activextextclass", "activerectangleclass", "relateddisplayclass"):
        assert channel_roles(name).data_attr({"alarmPv": "X:STAT", "colorPv": "X:C", "pv": ["X:W"]}) is None


def test_unlisted_classes_read_their_control_pv():
    assert channel_roles("byteclass").data_attr({"controlPv": "X:BITS", "colorPv": "X:C"}) == "controlPv"
