from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURE = Path(__file__).parent / "fixtures" / "p0_min.edl"


def _convert():
    return edm_file_to_ir(FIXTURE)


def test_screen_metadata():
    screen = _convert()
    assert screen.id == "p0_min"
    assert screen.metadata.source.type == "edl-converter"
    assert (screen.metadata.size.width, screen.metadata.size.height) == (400, 300)
    assert screen.root.type == "absolute-canvas"


def test_p0_widget_types_in_order():
    children = _convert().root.children
    assert [c.type for c in children] == ["text-label", "pv-text-input", "pv-button", "unknown-widget"]


def test_static_text_maps_to_text_label():
    """activeXTextClass with no PV -> text-label, value list joined into text."""
    label = _convert().root.children[0]
    assert label.type == "text-label"
    assert label.props == {"text": "Label ${PREFIX}"}
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


def test_unsupported_class_becomes_unknown_widget():
    unknown = _convert().root.children[3]
    assert unknown.type == "unknown-widget"
    assert unknown.props["originalClass"] == "activeRectangleClass"
    assert unknown.props["originalProps"] == {"lineColor": "rgb 0 0 0"}
    assert unknown.warnings == ["No registry entry for activeRectangleClass; rendering placeholder"]


def test_macros_collected():
    screen = _convert()
    assert [(m.name, m.default) for m in screen.macros] == [("PREFIX", "")]


def test_output_validates_against_schema():
    assert validate_screen_json(to_wire_dict(_convert())) == []


def test_conversion_is_deterministic():
    """Same input -> byte-identical IR (D3 round-trip stability across runs)."""
    assert to_json(edm_file_to_ir(FIXTURE)) == to_json(edm_file_to_ir(FIXTURE))
