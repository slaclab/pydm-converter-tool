"""EDM's menu button is an enum selector (#233).

It shows its PV's state and pops up the controlPv's states; choosing one writes
it to the controlPv. With an indicatorPv it shows that PV's state instead, in
inconsistentColor while the two differ (menu_button.cc). Both targets make it an
enum combo box on the controlPv, which has no readback: the indicatorPv is
dropped loudly, as a choice button's is.
"""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydm.widgets import PyDMEnumComboBox as QtEnumComboBox
from qtpy import uic

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import _object_to_source, edm_file_to_ir
from pydmconverter.edm.parser import EDMObject
from pydmconverter.edm.parser_helpers import parse_colors_list
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.registry import VendoredRegistry
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
SCREEN = FIXTURES / "menu_button.edl"
COLORS = FIXTURES / "colors.list"

# The fixture's menu buttons, one per row, by their y.
PLAIN, READBACK, GATED, SAME = 20, 60, 100, 140
CONTROL_PVS = {PLAIN: "DEMO:MODE", READBACK: "DEMO:MODE_SET", GATED: "DEMO:GATED", SAME: "DEMO:SAME"}
# fgColor index 25 and bgColor index 14 in the fixture's palette.
BLUE, YELLOW = "rgba(0, 0, 255, 255)", "rgba(255, 255, 0, 255)"
COLOURS_DROPPED = [
    "EDM fgColor dropped (the widget has no foregroundColor)",
    "EDM bgColor dropped (the widget has no backgroundColor)",
]


@pytest.fixture
def ui_path(tmp_path, caplog):
    """The converted .ui, with the conversion's warnings in caplog."""
    output = tmp_path / "menu_button.ui"
    with caplog.at_level(logging.WARNING):
        convert(str(SCREEN), str(output), color_list_file=str(COLORS))
    return output


@pytest.fixture
def ui(ui_path):
    """The converted .ui's widgets by row."""
    widgets = ET.parse(ui_path).getroot().find(".//widget[@name='centralwidget']").findall("widget")
    return {int(widget.find("property[@name='geometry']/rect/y").text): widget for widget in widgets}


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


@pytest.mark.parametrize("row", CONTROL_PVS)
def test_ui_menu_button_is_an_enum_combo_box_on_its_control_pv(ui, row):
    widget = ui[row]
    assert widget.get("class") == "PyDMEnumComboBox"
    assert _prop(widget, "channel") == CONTROL_PVS[row]
    # The combo box shows the state; the push button's "Menu" label is gone.
    assert _prop(widget, "text") is None


def test_ui_menu_button_keeps_its_colours(ui):
    """A QComboBox takes colours from a style sheet, which needs a border for its background."""
    style = _prop(ui[PLAIN], "styleSheet")
    assert f"background-color: {YELLOW}" in style
    assert f"color: {BLUE}" in style
    assert "border: 1px solid black" in style


def test_ui_menu_button_hides_only_by_its_vis_pv(ui):
    assert _rule_channels(ui[GATED], "Visible") == ["DEMO:SHOW"]
    assert _rule_channels(ui[PLAIN], "Visible") == []


def test_ui_menu_button_drops_its_readback_loudly(ui, caplog):
    messages = "\n".join(record.getMessage() for record in caplog.get_records("setup"))
    assert "indicatorPv DEMO:MODE_RBV is a readback, which PyDM widgets lack" in messages
    # An indicatorPv naming the controlPv loses nothing.
    assert "DEMO:SAME" not in messages


def test_ui_menu_buttons_load_in_pydm(ui_path, qtbot):
    window = uic.loadUi(str(ui_path))
    qtbot.addWidget(window)
    menus = sorted(window.findChildren(QtEnumComboBox), key=lambda menu: menu.y())
    assert [menu.channel for menu in menus] == list(CONTROL_PVS.values())


# ── Screen IR ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", CONTROL_PVS)
def test_ir_menu_button_is_an_enum_combo_box_on_its_control_pv(ir, row):
    node = ir[row]
    assert node["type"] == "pv-enum-combobox"
    assert node["props"]["pv"] == CONTROL_PVS[row]
    assert node["props"]["fontSize"] == 12
    assert "readbackPV" not in node["props"]


@pytest.mark.parametrize(
    "row, warnings",
    [
        pytest.param(PLAIN, COLOURS_DROPPED, id="colours"),
        pytest.param(
            READBACK,
            ["EDM indicatorPv readback dropped (controlPv kept as the channel)", *COLOURS_DROPPED],
            id="readback and colours",
        ),
        pytest.param(SAME, None, id="indicatorPv is the controlPv"),
    ],
)
def test_ir_menu_button_drops_what_the_combo_box_lacks_loudly(ir, row, warnings):
    assert ir[row].get("warnings") == warnings


def test_ir_menu_button_text_alarm_and_visibility(ir):
    node = ir[GATED]
    assert node["props"]["alarmSensitive"] is True  # fgAlarm
    (rule,) = node["rules"]
    assert rule["targetProperty"] == "visible"
    assert [pv["name"] for pv in rule["pvs"]] == ["DEMO:SHOW"]


# ── an indicatorPv on the controlPv's LOC variable ───────────────────────────

# EDM names a LOC variable by the text before "=" (loc_pv_factory.cc), so an
# indicatorPv naming the controlPv's variable is the same PV. One declaring it
# carries a declaration the channel lacks, and that goes with it.
LOC_READBACKS = [
    pytest.param(r"LOC\\mode=e:0,Off,On", r"LOC\\mode", False, id="names-the-variable"),
    pytest.param(r"LOC\\mode", r"LOC\\mode=e:0,Off,On", True, id="declares-the-variable"),
]


def _loc_screen(tmp_path, control_pv, indicator_pv):
    path = tmp_path / "loc_menu_button.edl"
    path.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 300\nh 100\nendScreenProperties\n"
        "object activeMenuButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x 20\ny 20\nw 120\nh 22\ncontrolPv "{control_pv}"\nindicatorPv "{indicator_pv}"\nendObjectProperties\n',
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("control_pv, indicator_pv, dropped", LOC_READBACKS)
def test_ui_readback_on_the_control_variable(tmp_path, caplog, control_pv, indicator_pv, dropped):
    with caplog.at_level(logging.WARNING):
        convert(str(_loc_screen(tmp_path, control_pv, indicator_pv)), str(tmp_path / "loc_menu_button.ui"))
    assert ("is a readback, which PyDM widgets lack" in caplog.text) == dropped


@pytest.mark.parametrize("control_pv, indicator_pv, dropped", LOC_READBACKS)
def test_ir_readback_on_the_control_variable(tmp_path, control_pv, indicator_pv, dropped):
    (node,) = to_wire_dict(edm_file_to_ir(_loc_screen(tmp_path, control_pv, indicator_pv)))["root"]["children"]
    expected = ["EDM indicatorPv readback dropped (controlPv kept as the channel)"] if dropped else None
    assert node.get("warnings") == expected


# ── colours (unit level) ─────────────────────────────────────────────────────

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


def _obj(properties):
    obj = EDMObject.__new__(EDMObject)
    obj.name = "activeMenuButtonClass"
    obj.properties = {"controlPv": "X:MODE", **properties}
    obj.x, obj.y, obj.width, obj.height = 0, 0, 120, 22
    return obj


def _palette(tmp_path):
    path = tmp_path / "colors.list"
    path.write_text(_PALETTE, encoding="utf-8")
    return parse_colors_list(str(path))


class _ComboBoxWithForeground:
    """The vendored registry, with pv-enum-combobox mapping foregroundColor."""

    def __init__(self):
        self._inner = VendoredRegistry()

    def by_id(self, widget_id):
        return self._inner.by_id(widget_id)

    def by_qt_class(self, qt_class):
        definition = self._inner.by_qt_class(qt_class)
        if qt_class != "PyDMEnumComboBox":
            return definition
        prop_map = {**definition.qt_prop_map, "foregroundColor": {"to": "foregroundColor"}}
        return definition.model_copy(update={"qt_prop_map": prop_map})


def test_color_pv_goes_with_the_rule_colours_it_picks(tmp_path):
    """menu_button.cc evaluates the bg and fg rules on the colorPv's value."""
    source = _object_to_source(
        _obj({"colorPv": "X:COLOR", "fgColor": "index 84", "bgColor": "index 14"}), _palette(tmp_path)
    )
    assert source.rules == []
    assert source.warnings == [
        "EDM fgColor dropped (the widget has no foregroundColor)",
        "EDM bgColor dropped (the widget has no backgroundColor)",
        "EDM colorPv dropped (it picks only rule colours the widget has no prop for)",
    ]


def test_color_pv_with_static_colours_drops_nothing_more(tmp_path):
    """A static colour never reads the colorPv (pvColor.cc evalRule)."""
    source = _object_to_source(
        _obj({"colorPv": "X:COLOR", "fgColor": "index 25", "bgColor": "index 14"}), _palette(tmp_path)
    )
    assert source.warnings == COLOURS_DROPPED


def test_display_background_is_not_a_dropped_colour(tmp_path):
    source = _object_to_source(
        _obj({"fgColor": "index 25", "bgColor": "index 14", "useDisplayBg": True}), _palette(tmp_path)
    )
    assert source.warnings == ["EDM fgColor dropped (the widget has no foregroundColor)"]


def test_colours_the_registry_maps_are_carried(tmp_path):
    """The registry passed in decides which colours the combo box keeps. The
    colorPv still picks the kept one's rule colour."""
    source = _object_to_source(
        _obj({"colorPv": "X:COLOR", "fgColor": "index 84", "bgColor": "index 84"}),
        _palette(tmp_path),
        registry=_ComboBoxWithForeground(),
    )
    (rule,) = source.rules
    assert rule.target_property == "foregroundColor"
    assert rule.pvs == [("X:COLOR", True)]
    assert source.warnings == ["EDM bgColor dropped (the widget has no backgroundColor)"]
