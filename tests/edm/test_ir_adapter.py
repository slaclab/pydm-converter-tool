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


_OBJ = """
object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y {y}
w {w}
h {h}
lineColor index 14
endObjectProperties
"""


def test_edm_canvas_is_exactly_declared_size(tmp_path):
    """EDM clips to w x h: an overhanging object and one parked at y=55,000,039
    (the corpus's hidden-group idiom) no longer grow the canvas."""
    edl = tmp_path / "parked.edl"
    edl.write_text(
        "4 0 0\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 0\nx 0\ny 0\nw 200\nh 100\nendScreenProperties\n"
        + _OBJ.format(x=150, y=10, w=100, h=20)
        + _OBJ.format(x=10, y=55000039, w=20, h=20),
        encoding="utf-8",
    )
    ir = edm_file_to_ir(edl)
    assert (ir.metadata.size.width, ir.metadata.size.height) == (200, 100)
    assert ir.root.props["width"] == 200 and ir.root.props["height"] == 100
    assert len(ir.root.children) == 2
    assert ir.root.warnings == [
        "1 widget(s) lie entirely outside the 200x100 canvas; kept in the IR, clipped at runtime"
    ]
    assert validate_screen_json(to_wire_dict(ir)) == []


def test_edm_screen_height_macro_sized_from_content(tmp_path):
    """Corpus: event/evnt_header_template has ``h $(DISP_HEIGHT)``; it used to abort."""
    edl = tmp_path / "tmpl.edl"
    edl.write_text(
        "4 0 0\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 581\ny 305\nw 684\nh $(DISP_HEIGHT)\n"
        "endScreenProperties\n" + _OBJ.format(x=0, y=0, w=684, h=60),
        encoding="utf-8",
    )
    ir = edm_file_to_ir(edl)
    assert (ir.metadata.size.width, ir.metadata.size.height) == (684, 68)  # content extent + 8 px margin
    assert ir.root.warnings == ["EDM screen h missing or not an integer; sized from the content extent"]


def test_edm_fragment_without_screen_block_sized_from_content(tmp_path):
    """No beginScreenProperties at all (template fragments): both dimensions come
    from the content, as before, rather than a 0 x 0 canvas."""
    edl = tmp_path / "fragment.edl"
    edl.write_text(_OBJ.format(x=5, y=5, w=100, h=40), encoding="utf-8")
    ir = edm_file_to_ir(edl)
    assert (ir.metadata.size.width, ir.metadata.size.height) == (113, 53)
    assert ir.root.warnings == ["EDM screen w/h missing or not an integer; sized from the content extent"]
