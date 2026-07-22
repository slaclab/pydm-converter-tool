"""Batch-2 regressions: EDM font sizes reach the IR, choice buttons render as
radio sets, menu buttons show their current choice, and state colors map."""

from pydmconverter.edm.edm_qt import EDM_TO_QT_CLASS
from pydmconverter.edm.ir_adapter import (
    _fixup_choice_button,
    _object_to_source,
    _to_font_size,
)
from pydmconverter.edm.parser import EDMObject


def _obj(name, properties, w=10, h=10):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, w, h
    return obj


def test_font_string_becomes_pixel_size():
    assert _to_font_size("helvetica-medium-r-12.0") == 12
    assert _to_font_size("helvetica-bold-r-14.0") == 14
    assert _to_font_size("courier-medium-r-8.0") == 8
    assert _to_font_size("garbage") is None


def test_font_flows_into_qt_props_and_malformed_is_dropped():
    node = _object_to_source(_obj("activeXTextClass", {"value": ["hi"], "font": "helvetica-bold-r-10.0"}))
    assert node.qt_props["fontSize"] == 10
    node = _object_to_source(_obj("activeXTextClass", {"value": ["hi"], "font": "weird"}))
    assert "fontSize" not in node.qt_props


def test_choice_button_is_a_radio_set_with_aspect_orientation():
    assert EDM_TO_QT_CLASS["activechoicebuttonclass"] == "PyDMEnumButton"
    qt_props = {}
    _fixup_choice_button(_obj("activeChoiceButtonClass", {}, w=150, h=20), qt_props, [])
    assert qt_props["orientation"] == "horizontal"
    qt_props = {}
    _fixup_choice_button(_obj("activeChoiceButtonClass", {}, w=68, h=150), qt_props, [])
    assert qt_props["orientation"] == "vertical"


def test_menu_button_face_shows_current_choice():
    node = _object_to_source(_obj("activeMenuButtonClass", {"controlPv": "X:MODE"}))
    assert node.qt_props["labelType"] == "pvState"
    # Without an indicatorPv the control channel doubles as the state source.
    assert node.qt_props["readbackChannel"] == "X:MODE"

    node = _object_to_source(_obj("activeMenuButtonClass", {"controlPv": "X:MODE", "indicatorPv": "X:MODE_RBV"}))
    assert node.qt_props["readbackChannel"] == "X:MODE_RBV"


def test_state_colors_resolve_to_hex():
    node = _object_to_source(
        _obj(
            "activeButtonClass",
            {
                "controlPv": "X:SW",
                "indicatorPv": "X:SW",
                "onColor": "rgb 0 65535 0",
                "offColor": "rgb 65535 65535 0",
            },
        )
    )
    assert node.qt_props["onColor"] == "#00ff00"
    assert node.qt_props["offColor"] == "#ffff00"


def test_byte_state_colors_resolve_to_hex():
    node = _object_to_source(
        _obj("ByteClass", {"controlPv": "X:BITS", "numBits": 4, "onColor": "rgb 0 0 65535", "offColor": "rgb 0 0 0"})
    )
    assert node.qt_props["onColor"] == "#0000ff"
    assert node.qt_props["offColor"] == "#000000"
