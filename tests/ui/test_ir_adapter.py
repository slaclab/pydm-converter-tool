from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ui.ir_adapter import ui_file_to_ir

FIXTURE = Path(__file__).parent / "fixtures" / "basic_widgets.ui"
EDM_FIXTURE = Path(__file__).parents[1] / "edm" / "fixtures" / "basic_widgets.edl"


def _convert():
    return ui_file_to_ir(FIXTURE)


def test_screen_metadata():
    screen = _convert()
    assert screen.id == "basic_widgets"
    assert screen.metadata.title == "basic_widgets"  # from windowTitle
    assert screen.metadata.source.type == "ui-converter"
    assert (screen.metadata.size.width, screen.metadata.size.height) == (400, 300)


def test_widget_types_in_order():
    children = _convert().root.children
    assert [c.type for c in children] == ["text-label", "pv-text-input", "pv-button", "unknown-widget"]


def test_qlabel_to_text_label():
    label = _convert().root.children[0]
    assert label.type == "text-label"
    assert label.props == {"text": "Label ${PREFIX}"}


def test_channel_protocol_stripped():
    text_input = _convert().root.children[1]
    assert text_input.props == {"pv": "${PREFIX}:SETPOINT"}  # ca:// dropped by stripProtocol


def test_button_props():
    button = _convert().root.children[2]
    assert button.props["pv"] == "${PREFIX}:GO"
    assert button.props["label"] == "Go"
    assert button.props["pressValue"] == "1"


def test_unknown_pydm_class():
    unknown = _convert().root.children[3]
    assert unknown.type == "unknown-widget"
    assert unknown.props["originalClass"] == "PyDMMysteryGauge"
    assert unknown.warnings == ["No registry entry for PyDMMysteryGauge; rendering placeholder"]


def test_macros_collected():
    assert [(m.name, m.default) for m in _convert().macros] == [("PREFIX", "")]


def test_validates_and_deterministic():
    screen = _convert()
    assert validate_screen_json(to_wire_dict(screen)) == []
    assert to_json(ui_file_to_ir(FIXTURE)) == to_json(screen)


def test_layout_child_without_rect_warns(tmp_path):
    """A widget in a Qt layout (no geometry rect) is kept with a warning (D4 trust-and-warn)."""
    ui = """<?xml version="1.0"?>
    <ui version="4.0"><widget class="QWidget" name="screen">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
      <layout class="QVBoxLayout"><item>
        <widget class="QLabel" name="lbl"><property name="text"><string>hi</string></property></widget>
      </item></layout>
    </widget></ui>"""
    path = tmp_path / "layout.ui"
    path.write_text(ui, encoding="utf-8")
    label = ui_file_to_ir(path).root.children[0]
    assert label.type == "text-label"
    assert label.geometry.model_dump() == {"x": 0, "y": 0, "width": 0, "height": 0}
    assert label.warnings and "no geometry rect" in label.warnings[0]


def _structure(screen):
    return [
        (c.type, c.props.get("pv") or c.props.get("text"), tuple(c.geometry.model_dump().values()))
        for c in screen.root.children
    ]


def test_cross_input_equivalence_with_edm():
    """Milestone: the same screen as .edl and .ui yields structurally-equal IR.

    Scoped to the first 3 children (label/input/button): the 4th diverges by
    design — ``basic_widgets.ui``'s ``PyDMMysteryGauge`` is a fixture-only unknown class
    (see test_unknown_pydm_class), while ``basic_widgets.edl``'s activeRectangleClass
    maps to a supported "rectangle" node (see test_rectangle_maps_with_line_color
    in tests/edm/test_ir_adapter.py).
    """
    assert _structure(ui_file_to_ir(FIXTURE))[:3] == _structure(edm_file_to_ir(EDM_FIXTURE))[:3]


def test_scalar_number_parsing_is_tolerant():
    """A <number> is an int, but a float-formatted or junk value degrades rather than raising."""
    import xml.etree.ElementTree as ET

    from pydmconverter.ui.ir_adapter import _SKIP, _scalar_property

    def prop(tag: str, text: str) -> ET.Element:
        el = ET.Element("property")
        ET.SubElement(el, tag).text = text
        return el

    assert _scalar_property(prop("number", "8")) == 8
    assert _scalar_property(prop("number", "8.0")) == 8.0  # float-formatted number, not a crash
    assert _scalar_property(prop("number", "")) == 0
    assert _scalar_property(prop("number", "nope")) is _SKIP
    assert _scalar_property(prop("double", "1.5")) == 1.5
    assert _scalar_property(prop("double", "nope")) is _SKIP
