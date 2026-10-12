"""activeSymbolClass scaling to its saved size. Without ``useOriginalSize`` EDM
(symbol.cc createFromFile) scales the symbol file's states to the w/h saved in
the display, per axis about the symbol's top-left corner, before any rotation
or flip; a resize that would leave an object under 2 pixels is refused."""

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.edm.parser import EDMFileParser
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
ORIENTATIONS = ["rotateCW", "rotateCCW", "FlipH", "FlipV"]
UNDERFLOW = "EDM symbol resize underflow; drawn at the symbol file's size"

_HEADER = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 200
h 100
endScreenProperties
"""


def _object(cls, x, y, w, h, extra=""):
    return f"""object {cls}
beginObjectProperties
major 4
minor 0
release 0
x {x}
y {y}
w {w}
h {h}
{extra}endObjectProperties
"""


def _group(x, y, w, h, *children):
    return f"""object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y {y}
w {w}
h {h}

beginGroup

{"".join(children)}
endGroup

endObjectProperties
"""


def _line(x0, y0, x1, y1):
    points = f"numPoints 2\nxPoints {{\n  0 {x0}\n  1 {x1}\n}}\nyPoints {{\n  0 {y0}\n  1 {y1}\n}}\n"
    return _object("activeLineClass", min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), points)


def _symbol(file="sym", x=20, y=20, w=80, h=60, num_states=1, orientation=None, extra=""):
    extra += f'file "{file}"\nnumStates {num_states}\nnumPvs 1\ncontrolPvs {{\n  0 "SYM:STATE"\n}}\n'
    extra += "minValues {\n" + "".join(f"  {i} {i}\n" for i in range(num_states)) + "}\n"
    extra += "maxValues {\n" + "".join(f"  {i} {i + 1}\n" for i in range(num_states)) + "}\n"
    if orientation:
        extra += f'orientation "{orientation}"\n'
    return _object("activeSymbolClass", x, y, w, h, extra)


# One 40x20 state drawn at (100, 100) in the symbol file: a nested group (a
# rectangle and a diagonal line), an arc and a text. Saved at 80x60 the symbol
# is 2x as wide and 3x as high.
_SYMBOL_FILE = _HEADER + _group(
    100,
    100,
    40,
    20,
    _group(
        110,
        102,
        10,
        10,
        _object("activeRectangleClass", 110, 102, 10, 10, "lineWidth 3\n"),
        _line(110, 102, 120, 112),
    ),
    _object("activeArcClass", 100, 100, 20, 20, "startAngle 0\ntotalAngle 90\n"),
    _object("activeXTextClass", 120, 105, 20, 10, 'font "helvetica-medium-r-12.0"\nvalue {\n  "X"\n}\n'),
)

# (x, y, w, h) per object, the line as points, the arc with its start angle.
# Scaled about (20, 20), then turned about the scaled symbol's midpoint (60, 50).
_EXPECTED = {
    None: {
        "state": (20, 20, 80, 60),
        "nested": (40, 26, 20, 30),
        "line": [(40, 26), (60, 56)],
        "arc": ((20, 20, 40, 60), "0"),
    },
    "rotateCW": {
        "state": (30, 10, 60, 80),
        "nested": (54, 30, 30, 20),
        "line": [(84, 30), (54, 50)],
        "arc": ((30, 10, 60, 40), "270"),
    },
    "rotateCCW": {
        "state": (30, 10, 60, 80),
        "nested": (36, 50, 30, 20),
        "line": [(36, 70), (66, 50)],
        "arc": ((30, 50, 60, 40), "90"),
    },
    "FlipH": {
        "state": (20, 20, 80, 60),
        "nested": (60, 26, 20, 30),
        "line": [(80, 26), (60, 56)],
        "arc": ((20, 20, 40, 60), "90"),
    },
    "FlipV": {
        "state": (20, 20, 80, 60),
        "nested": (40, 44, 20, 30),
        "line": [(40, 74), (60, 44)],
        "arc": ((20, 20, 40, 60), "270"),
    },
}


def _rect(obj):
    return (obj.x, obj.y, obj.width, obj.height)


def _points(line):
    return list(zip(map(int, line.properties["xPoints"]), map(int, line.properties["yPoints"])))


def _write(tmp_path, screen_text, **symbol_files):
    for name, text in symbol_files.items():
        (tmp_path / f"{name}.edl").write_text(text)
    screen = tmp_path / "screen.edl"
    screen.write_text(_HEADER + screen_text)
    return screen


def _parse(tmp_path, screen_text, **symbol_files):
    screen = _write(tmp_path, screen_text, **symbol_files)
    return EDMFileParser(screen, tmp_path / "screen.ui")


def test_state_is_scaled_to_the_saved_size(tmp_path):
    parser = _parse(tmp_path, _symbol(), sym=_SYMBOL_FILE)
    (symbol,) = parser.ui.objects
    assert "symbolWarnings" not in symbol.properties
    (state,) = symbol.objects
    nested, arc, text = state.objects
    rect, line = nested.objects
    expected = _EXPECTED[None]

    assert _rect(state) == expected["state"]
    assert _rect(nested) == _rect(rect) == _rect(line) == expected["nested"]
    assert _points(line) == expected["line"]
    assert (_rect(arc), arc.properties["startAngle"]) == expected["arc"]
    assert arc.properties["totalAngle"] == "90"
    # A text is only re-placed; its font, like every lineWidth, is not scaled.
    assert _rect(text) == (60, 35, 40, 30)
    assert text.properties["font"] == "helvetica-medium-r-12.0"
    assert rect.properties["lineWidth"] == "3"


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_symbol_is_scaled_then_reoriented_about_the_scaled_midpoint(tmp_path, orientation):
    parser = _parse(tmp_path, _symbol(orientation=orientation), sym=_SYMBOL_FILE)
    (state,) = parser.ui.objects[0].objects
    nested, arc, _ = state.objects
    rect, line = nested.objects
    expected = _EXPECTED[orientation]

    assert _rect(state) == expected["state"]
    assert _rect(nested) == _rect(rect) == expected["nested"]
    assert _points(line) == expected["line"]
    assert (_rect(arc), arc.properties["startAngle"]) == expected["arc"]


def test_positions_and_sizes_round_as_edm_does(tmp_path):
    """(int) (v + 0.5), not round(): 5 * 0.5 = 2.5 gives 3 (round() gives 2)."""
    symbol_file = _HEADER + _group(0, 0, 40, 40, _object("activeRectangleClass", 5, 5, 5, 5))
    parser = _parse(tmp_path, _symbol(w=20, h=30), sym=symbol_file)
    (state,) = parser.ui.objects[0].objects
    (rect,) = state.objects
    assert _rect(state) == (20, 20, 20, 30)
    # x: 20 + (int) (5 * 0.5 + 0.5) = 23, w: (int) (5 * 0.5 + 0.5) = 3;
    # y: 20 + (int) (5 * 0.75 + 0.5) = 24, h: (int) (5 * 0.75 + 0.5) = 4.
    assert _rect(rect) == (23, 24, 3, 4)


def test_line_points_stretch_with_the_rect_and_stay_inside_it(tmp_path):
    """activeLineClass::updateDimensions stretches each point from the old rect
    to the new one in float and clamps it into the new rect."""
    line = _object(
        "activeLineClass",
        0,
        0,
        30,
        30,
        "numPoints 3\nxPoints {\n  0 0\n  1 15\n  2 30\n}\nyPoints {\n  0 30\n  1 0\n  2 30\n}\n",
    )
    symbol_file = _HEADER + _group(0, 0, 30, 30, line)
    parser = _parse(tmp_path, _symbol(w=20, h=20), sym=symbol_file)
    (state,) = parser.ui.objects[0].objects
    (scaled,) = state.objects
    assert _rect(scaled) == (20, 20, 20, 20)
    # 15 * (2/3) = 10, 30 * (2/3) = 20.
    assert _points(scaled) == [(20, 40), (30, 20), (40, 40)]


def test_line_points_stretch_in_float(tmp_path):
    """11 * (13 / 22) is 6.5 in double but just under it in float, which
    activeLineClass::updateDimensions uses, so the point lands on 6, not 7."""
    line = _object(
        "activeLineClass",
        0,
        0,
        22,
        22,
        "numPoints 3\nxPoints {\n  0 0\n  1 11\n  2 22\n}\nyPoints {\n  0 0\n  1 22\n  2 0\n}\n",
    )
    symbol_file = _HEADER + _group(0, 0, 22, 22, line)
    parser = _parse(tmp_path, _symbol(w=13, h=13), sym=symbol_file)
    (scaled,) = parser.ui.objects[0].objects[0].objects
    assert _rect(scaled) == (20, 20, 13, 13)
    assert _points(scaled) == [(20, 20), (26, 33), (33, 20)]


def test_line_points_outside_the_rect_are_clamped_into_it(tmp_path):
    """activeLineClass::updateDimensions clamps every stretched point into the
    line's new rect, so a point the file puts outside the rect lands on its edge
    (the cast truncates -9.5 to -9 first)."""
    line = _object(
        "activeLineClass",
        100,
        100,
        20,
        10,
        "numPoints 3\nxPoints {\n  0 95\n  1 110\n  2 130\n}\nyPoints {\n  0 105\n  1 100\n  2 115\n}\n",
    )
    symbol_file = _HEADER + _group(100, 100, 40, 20, line)
    parser = _parse(tmp_path, _symbol(), sym=symbol_file)
    (scaled,) = parser.ui.objects[0].objects[0].objects
    assert _rect(scaled) == (20, 20, 40, 30)
    # Unclamped: (11, 35), (40, 20), (80, 65).
    assert _points(scaled) == [(20, 35), (40, 20), (60, 50)]


def test_a_nested_group_scales_its_children_by_its_own_rounded_ratio(tmp_path):
    """activeGroupClass::resizeAbs scales its children by its new width over its
    old one, both whole pixels: at 24/40 a 7-wide group becomes 4 wide, so its
    6-wide child becomes (int) (6 * 4/7 + 0.5) = 3 wide, not (int) (6 * 0.6 + 0.5) = 4."""
    symbol_file = _HEADER + _group(
        100, 100, 40, 20, _group(100, 100, 7, 20, _object("activeRectangleClass", 101, 100, 6, 20))
    )
    parser = _parse(tmp_path, _symbol(w=24, h=20), sym=symbol_file)
    (symbol,) = parser.ui.objects
    (nested,) = symbol.objects[0].objects
    (rect,) = nested.objects
    assert "symbolWarnings" not in symbol.properties
    assert _rect(nested) == (20, 20, 4, 20)
    assert _rect(rect) == (21, 20, 3, 20)


def test_a_nested_group_checks_its_children_with_its_own_rounded_ratio(tmp_path):
    """activeGroupClass::checkResizeSelectBoxAbs uses the same ratio: at 29/20 a
    2-wide group becomes 3 wide (1.5), so its 1-wide child would be
    (int) (1 * 1.5 + 0.5) = 2 wide and EDM scales; at 1.45 it would be 1 wide
    and refuse."""
    symbol_file = _HEADER + _group(
        100, 100, 20, 20, _group(100, 100, 2, 20, _object("activeRectangleClass", 100, 100, 1, 20))
    )
    parser = _parse(tmp_path, _symbol(w=29, h=20), sym=symbol_file)
    (symbol,) = parser.ui.objects
    (nested,) = symbol.objects[0].objects
    (rect,) = nested.objects
    assert "symbolWarnings" not in symbol.properties
    assert _rect(nested) == (20, 20, 3, 20)
    assert _rect(rect) == (20, 20, 2, 20)


@pytest.mark.parametrize(
    "flag, scaled",
    [("useOriginalSize\n", False), ("useOriginalSize 1\n", False), ("useOriginalSize 0\n", True), ("", True)],
)
def test_use_original_size_keeps_the_symbol_file_size(tmp_path, flag, scaled):
    parser = _parse(tmp_path, _symbol(extra=flag), sym=_SYMBOL_FILE)
    (symbol,) = parser.ui.objects
    (state,) = symbol.objects
    assert _rect(state) == ((20, 20, 80, 60) if scaled else (20, 20, 40, 20))
    assert "symbolWarnings" not in symbol.properties


def test_saved_size_equal_to_the_file_size_changes_nothing(tmp_path):
    parser = _parse(tmp_path, _symbol(w=40, h=20), sym=_SYMBOL_FILE)
    (state,) = parser.ui.objects[0].objects
    nested, arc, text = state.objects
    assert _rect(state) == (20, 20, 40, 20)
    assert _rect(nested) == (30, 22, 10, 10)
    assert _rect(text) == (40, 25, 20, 10)


def test_every_state_is_scaled_by_the_largest_read_state(tmp_path):
    """The factors are saved size over the largest of the first numStates
    states (readSymbolFile: w = maxW; h = maxH), the same for every state."""
    symbol_file = (
        _HEADER
        + _group(100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20))
        + _group(200, 100, 20, 10, _object("activeRectangleClass", 200, 100, 20, 10))
        # Past numStates: EDM doesn't read it, so it doesn't size the symbol.
        + _group(300, 100, 100, 100, _object("activeRectangleClass", 300, 100, 100, 100))
    )
    parser = _parse(tmp_path, _symbol(w=80, h=40, num_states=2), sym=symbol_file)
    states = parser.ui.objects[0].objects
    assert [_rect(state) for state in states] == [(20, 20, 80, 40), (20, 20, 40, 20)]
    assert [_rect(state.objects[0]) for state in states] == [(20, 20, 80, 40), (20, 20, 40, 20)]


def test_underflow_leaves_the_symbol_unscaled_with_a_warning(tmp_path):
    """A rectangle 2 high at half size would be 1 high: EDM posts "Symbol resize
    underflow - using original size" and keeps the symbol file's size."""
    symbol_file = _HEADER + _group(
        100,
        100,
        40,
        20,
        _object("activeRectangleClass", 100, 100, 40, 20),
        _object("activeRectangleClass", 100, 110, 40, 2),
    )
    screen = _write(tmp_path, _symbol(w=20, h=10), sym=symbol_file)
    parser = EDMFileParser(screen, tmp_path / "screen.ui")
    (symbol,) = parser.ui.objects
    (state,) = symbol.objects
    assert _rect(state) == (20, 20, 40, 20)
    assert [_rect(obj) for obj in state.objects] == [(20, 20, 40, 20), (20, 30, 40, 2)]
    assert symbol.properties["symbolWarnings"] == [UNDERFLOW]

    wire = to_wire_dict(edm_file_to_ir(screen))
    assert validate_screen_json(wire) == []
    (node,) = wire["root"]["children"]
    assert UNDERFLOW in node["warnings"]


def test_a_flat_line_does_not_underflow(tmp_path):
    """activeLineClass::checkResizeSelectBoxAbs never refuses, so a horizontal
    line (h 0) scales with the rest."""
    symbol_file = _HEADER + _group(
        100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20), _line(100, 110, 140, 110)
    )
    parser = _parse(tmp_path, _symbol(w=20, h=10), sym=symbol_file)
    (symbol,) = parser.ui.objects
    rect, line = symbol.objects[0].objects
    assert "symbolWarnings" not in symbol.properties
    assert _rect(rect) == (20, 20, 20, 10)
    assert _rect(line) == (20, 25, 20, 0)
    assert _points(line) == [(20, 25), (40, 25)]


@pytest.mark.parametrize(
    "cls, w, h, scaled",
    [
        # pnglib/png.cc and giflib/gif.cc: an image refuses any resize, even a larger one.
        ("activePngClass", 80, 40, False),
        ("cfcf6c8a_dbeb_11d2_8a97_00104b8742df", 80, 40, False),
        # pvFactory/textupdate.cc: a text update or entry refuses under 10 (18 high at half size is 9).
        ("TextupdateClass", 20, 10, False),
        ("TextentryClass", 20, 10, False),
        ("TextupdateClass", 80, 40, True),
        ("activeTableClass", 20, 10, False),
        # activeGraphicClass refuses only under 2.
        ("activeRectangleClass", 20, 10, True),
    ],
)
def test_a_widget_with_its_own_minimum_size_refuses_as_edm_does(tmp_path, cls, w, h, scaled):
    """Some classes override checkResizeSelectBoxAbs; EDM then keeps the symbol
    file's size with the same "Symbol resize underflow" message."""
    symbol_file = _HEADER + _group(
        100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20), _object(cls, 100, 101, 40, 18)
    )
    parser = _parse(tmp_path, _symbol(w=w, h=h), sym=symbol_file)
    (symbol,) = parser.ui.objects
    (state,) = symbol.objects
    if scaled:
        assert _rect(state) == (20, 20, w, h)
        assert "symbolWarnings" not in symbol.properties
    else:
        assert _rect(state) == (20, 20, 40, 20)
        assert [_rect(obj) for obj in state.objects] == [(20, 20, 40, 20), (20, 21, 40, 18)]
        assert symbol.properties["symbolWarnings"] == [UNDERFLOW]


def test_symbol_inside_a_symbol_is_not_scaled(tmp_path):
    inner_file = _HEADER + _group(0, 0, 10, 10, _object("activeRectangleClass", 0, 0, 10, 10))
    outer_file = _HEADER + _group(100, 100, 40, 20, _symbol(file="inner", x=100, y=102, w=10, h=10))
    parser = _parse(tmp_path, _symbol(file="outer"), outer=outer_file, inner=inner_file)
    (symbol,) = parser.ui.objects
    (state,) = symbol.objects
    assert _rect(state) == (20, 20, 40, 20)
    assert symbol.properties["symbolWarnings"] == [
        "EDM symbol holds a symbol, which the converter does not scale; drawn at the symbol file's size"
    ]


@pytest.mark.parametrize("num_states, scaled", [(1, True), (2, False)])
def test_a_read_state_that_is_not_a_group_skips_scaling(tmp_path, num_states, scaled):
    """readSymbolFile fails when one of the first numStates objects is not a
    group, and EDM then doesn't scale; an object after them doesn't matter."""
    symbol_file = (
        _HEADER
        + _group(100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20))
        + _object("activeRectangleClass", 0, 0, 5, 5)
    )
    parser = _parse(tmp_path, _symbol(num_states=num_states), sym=symbol_file)
    state = parser.ui.objects[0].objects[0]
    assert _rect(state) == ((20, 20, 80, 60) if scaled else (20, 20, 40, 20))


@pytest.mark.parametrize("num_states, scaled", [(1, True), (2, False)])
def test_a_read_state_that_is_a_symbol_skips_scaling(tmp_path, num_states, scaled):
    """A symbol isn't a group either: readSymbolFile fails on one among the
    first numStates objects the same way, and EDM doesn't scale."""
    inner_file = _HEADER + _group(0, 0, 10, 10, _object("activeRectangleClass", 0, 0, 10, 10))
    symbol_file = (
        _HEADER
        + _group(100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20))
        + _symbol(file="inner", x=0, y=0, w=10, h=10)
    )
    parser = _parse(tmp_path, _symbol(num_states=num_states), sym=symbol_file, inner=inner_file)
    state = parser.ui.objects[0].objects[0]
    assert _rect(state) == ((20, 20, 80, 60) if scaled else (20, 20, 40, 20))


def test_ir_has_the_scaled_geometry(tmp_path):
    screen = _write(tmp_path, _symbol(), sym=_SYMBOL_FILE)
    wire = to_wire_dict(edm_file_to_ir(screen))
    assert validate_screen_json(wire) == []
    (symbol,) = wire["root"]["children"]
    (state,) = symbol["children"]
    assert state["geometry"] == {"x": 20, "y": 20, "width": 80, "height": 60}
    nested, arc, text = state["children"]
    assert nested["geometry"] == {"x": 40, "y": 26, "width": 20, "height": 30}
    rect, line = nested["children"]
    assert rect["geometry"] == {"x": 40, "y": 26, "width": 20, "height": 30}
    assert line["geometry"] == {"x": 40, "y": 26, "width": 20, "height": 30}
    assert line["props"]["points"] == [{"x": 0, "y": 0}, {"x": 20, "y": 30}]
    assert arc["geometry"] == {"x": 20, "y": 20, "width": 40, "height": 60}
    assert text["geometry"] == {"x": 60, "y": 35, "width": 40, "height": 30}


def test_ui_widgets_have_the_scaled_geometry(tmp_path, monkeypatch):
    """symbol_two_state.edl saved at 48x36 instead of the file's 24x24."""
    monkeypatch.chdir(tmp_path)
    shutil.copy(FIXTURES / "symbol_states.edl", tmp_path)
    text = (FIXTURES / "symbol_two_state.edl").read_text()
    assert "w 24\nh 24\n" in text and "useOriginalSize\n" in text
    source = tmp_path / "scaled.edl"
    source.write_text(text.replace("w 24\nh 24\n", "w 48\nh 36\n").replace("useOriginalSize\n", ""))
    convert(str(source), str(tmp_path / "scaled.ui"))

    root = ET.parse(tmp_path / "scaled.ui").getroot()
    geometry = {}
    for widget in root.iter("widget"):
        rect = widget.find("./property[@name='geometry']/rect")
        if rect is not None:
            geometry[widget.get("class")] = tuple(int(rect.find(k).text) for k in ("x", "y", "width", "height"))
    assert geometry["PyDMDrawingRectangle"] == (50, 60, 48, 36)
    assert geometry["PyDMDrawingEllipse"] == (50, 60, 48, 36)
