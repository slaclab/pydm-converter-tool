from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURE = Path(__file__).parent / "fixtures" / "basic_widgets.edl"


def _convert():
    return edm_file_to_ir(FIXTURE)


def test_screen_metadata():
    screen = _convert()
    assert screen.id == "basic_widgets"
    assert screen.metadata.source.type == "edl-converter"
    assert (screen.metadata.size.width, screen.metadata.size.height) == (400, 300)
    assert screen.root.type == "absolute-canvas"


def test_widget_types_in_order():
    children = _convert().root.children
    assert [c.type for c in children] == ["text-label", "pv-text-input", "pv-button", "rectangle"]


def test_static_text_maps_to_text_label():
    """activeXTextClass with no PV -> text-label, value list joined into text.

    ``fgColor rgb 0 0 0`` resolves without a palette (rgb form needs no colors.list).
    """
    label = _convert().root.children[0]
    assert label.type == "text-label"
    assert label.props == {"text": "Label ${PREFIX}", "foregroundColor": "#000000", "fontSize": 12}
    assert label.geometry.model_dump() == {"x": 10, "y": 20, "width": 120, "height": 18}


def test_text_input_channel_becomes_pv():
    text_input = _convert().root.children[1]
    assert text_input.type == "pv-text-input"
    assert text_input.props == {"pv": "${PREFIX}:SETPOINT"}


def test_button_maps_label_and_press_value():
    button = _convert().root.children[2]
    assert button.type == "pv-button"
    assert button.props["pv"] == "${PREFIX}:GO"
    assert button.props["label"] == "Go"
    assert button.props["pressValue"] == "1"


def test_rectangle_maps_with_line_color():
    """basic_widgets's rect has only ``lineColor rgb 0 0 0`` (Rectangle is a supported graphics class)."""
    rectangle = _convert().root.children[3]
    assert rectangle.type == "rectangle"
    assert rectangle.props == {"lineColor": "#000000"}
    assert rectangle.geometry.model_dump() == {"x": 200, "y": 20, "width": 100, "height": 50}


def test_macros_collected():
    screen = _convert()
    assert [(m.name, m.default) for m in screen.macros] == [("PREFIX", "")]


def test_output_validates_against_schema():
    assert validate_screen_json(to_wire_dict(_convert())) == []


def test_conversion_is_deterministic():
    """Same input -> byte-identical IR (D3 round-trip stability across runs)."""
    assert to_json(edm_file_to_ir(FIXTURE)) == to_json(edm_file_to_ir(FIXTURE))
