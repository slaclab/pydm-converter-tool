"""activeSymbolClass ``orientation`` (rotateCW, rotateCCW, FlipH, FlipV) when a
state group holds nested groups and symbols. EDM (symbol.cc createFromFile)
rotates or flips everything in each state about the symbol's midpoint; a group
transforms its own rect and then its children about the same point
(group.cc), and a nested symbol's rotate()/flip() is a no-op."""

import pytest

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.edm.parser import EDMFileParser, EDMGroup
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

ORIENTATIONS = ["rotateCW", "rotateCCW", "FlipH", "FlipV"]

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


def _symbol(file="sym", orientation=None, x=20, y=20, w=40, h=20):
    extra = f'file "{file}"\nnumStates 1\nnumPvs 1\ncontrolPvs {{\n  0 "SYM:STATE"\n}}\n'
    extra += "minValues {\n  0 0\n}\nmaxValues {\n  0 1\n}\n"
    if orientation:
        extra += f'orientation "{orientation}"\n'
    return _object("activeSymbolClass", x, y, w, h, extra)


# One 40x20 state drawn at (100, 100) in the symbol file, holding an off-centre
# nested group (a rectangle and a diagonal line) and an arc in its top-left corner.
_SYMBOL_FILE = _HEADER + _group(
    100,
    100,
    40,
    20,
    _group(110, 102, 10, 10, _object("activeRectangleClass", 110, 102, 10, 10), _line(110, 102, 120, 112)),
    _object("activeArcClass", 100, 100, 20, 20, "startAngle 0\ntotalAngle 90\n"),
)

# Placed at (20, 20) the state's content moves by (-80, -80); EDM then turns it
# about the symbol's midpoint (40, 30). (x, y, w, h) per object, line as points.
_EXPECTED = {
    None: {
        "state": (20, 20, 40, 20),
        "nested": (30, 22, 10, 10),
        "line": [(30, 22), (40, 32)],
        "arc": ((20, 20, 20, 20), "0"),
    },
    "rotateCW": {
        "state": (30, 10, 20, 40),
        "nested": (38, 20, 10, 10),
        "line": [(48, 20), (38, 30)],
        "arc": ((30, 10, 20, 20), "270"),
    },
    "rotateCCW": {
        "state": (30, 10, 20, 40),
        "nested": (32, 30, 10, 10),
        "line": [(32, 40), (42, 30)],
        "arc": ((30, 30, 20, 20), "90"),
    },
    "FlipH": {
        "state": (20, 20, 40, 20),
        "nested": (40, 22, 10, 10),
        "line": [(50, 22), (40, 32)],
        # activeArcClass::flip changes only the start angle, never the rect.
        "arc": ((20, 20, 20, 20), "90"),
    },
    "FlipV": {
        "state": (20, 20, 40, 20),
        "nested": (30, 28, 10, 10),
        "line": [(30, 38), (40, 28)],
        "arc": ((20, 20, 20, 20), "270"),
    },
}


def _rect(obj):
    return (obj.x, obj.y, obj.width, obj.height)


def _parse(tmp_path, screen_text, **symbol_files):
    for name, text in symbol_files.items():
        (tmp_path / f"{name}.edl").write_text(text)
    screen = tmp_path / "screen.edl"
    screen.write_text(_HEADER + screen_text)
    return screen, EDMFileParser(screen, tmp_path / "screen.ui")


@pytest.mark.parametrize("orientation", [None, *ORIENTATIONS])
def test_nested_group_is_reoriented_with_its_children(tmp_path, orientation):
    _, parser = _parse(tmp_path, _symbol(orientation=orientation), sym=_SYMBOL_FILE)
    (symbol,) = parser.ui.objects
    assert "symbolWarnings" not in symbol.properties
    (state,) = symbol.objects
    nested, arc = state.objects
    rect, line = nested.objects
    expected = _EXPECTED[orientation]

    assert isinstance(nested, EDMGroup)
    assert _rect(state) == expected["state"]
    assert _rect(nested) == _rect(rect) == expected["nested"]
    points = list(zip(map(int, line.properties["xPoints"]), map(int, line.properties["yPoints"])))
    assert points == expected["line"]
    assert (_rect(arc), arc.properties["startAngle"]) == expected["arc"]
    assert arc.properties["totalAngle"] == "90"


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_centre_ignores_groups_past_num_states(tmp_path, orientation):
    """readSymbolFile reads only the first numStates groups and sizes the symbol
    to the largest of those, so a larger group after them must not move the
    centre EDM turns the symbol about."""
    symbol_file = (
        _HEADER
        + _group(100, 100, 40, 20, _object("activeRectangleClass", 100, 100, 40, 20))
        + _group(300, 100, 80, 80, _object("activeRectangleClass", 300, 100, 80, 80))
    )
    _, parser = _parse(tmp_path, _symbol(orientation=orientation), sym=symbol_file)
    (state,) = parser.ui.objects[0].objects
    (rect,) = state.objects
    expected = _EXPECTED[orientation]["state"]
    assert _rect(state) == _rect(rect) == expected


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_reoriented_symbol_with_a_nested_group_renders(tmp_path, orientation):
    """The regression: the nested group used to raise AttributeError, which
    replaced the whole symbol with a "could not be expanded" placeholder."""
    screen, _ = _parse(tmp_path, _symbol(orientation=orientation), sym=_SYMBOL_FILE)
    wire = to_wire_dict(edm_file_to_ir(screen))
    assert validate_screen_json(wire) == []
    (symbol,) = wire["root"]["children"]
    assert not any("could not be expanded" in w for w in symbol.get("warnings", []))
    (state,) = symbol["children"]
    nested = next(child for child in state["children"] if child["type"] == "group")
    x, y, w, h = _EXPECTED[orientation]["nested"]
    assert nested["geometry"] == {"x": x, "y": y, "width": w, "height": h}
    assert [child["type"] for child in nested["children"]] == ["rectangle", "line"]


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_nested_missing_symbol_is_left_as_drawn(tmp_path, orientation):
    """A nested symbol (here a placeholder for a missing file) is only moved:
    activeSymbolClass::rotate/flip post "Symbol rotate --> No-op"."""
    symbol_file = _HEADER + _group(100, 100, 40, 20, _symbol(file="missing", x=100, y=102, w=10, h=10))
    screen, parser = _parse(tmp_path, _symbol(orientation=orientation), sym=symbol_file)
    (state,) = parser.ui.objects[0].objects
    (placeholder,) = state.objects
    assert placeholder.is_symbol
    assert _rect(placeholder) == (20, 22, 10, 10)
    assert placeholder.properties["symbolFileNotFound"] == "missing.edl"

    wire = to_wire_dict(edm_file_to_ir(screen))
    assert validate_screen_json(wire) == []
    (symbol,) = wire["root"]["children"]
    (placeholder_node,) = symbol["children"][0]["children"]
    assert placeholder_node["geometry"] == {"x": 20, "y": 22, "width": 10, "height": 10}
    warnings = placeholder_node["warnings"]
    assert any("'missing.edl' not found" in w for w in warnings)
    assert any(f"EDM ignores orientation {orientation} for a symbol inside a symbol" in w for w in warnings)
    assert not any("could not be expanded" in w for w in symbol.get("warnings", []))


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_nested_expanded_symbol_is_moved_but_not_reoriented(tmp_path, orientation):
    inner_file = _HEADER + _group(0, 0, 10, 10, _object("activeRectangleClass", 0, 0, 4, 10))
    outer_file = _HEADER + _group(100, 100, 40, 20, _symbol(file="inner", x=100, y=102, w=10, h=10))
    _, parser = _parse(tmp_path, _symbol(file="outer", orientation=orientation), outer=outer_file, inner=inner_file)
    (outer_state,) = parser.ui.objects[0].objects
    (inner_symbol,) = outer_state.objects
    assert inner_symbol.is_symbol
    (inner_state,) = inner_symbol.objects
    (rect,) = inner_state.objects
    assert _rect(inner_state) == (20, 22, 10, 10)
    assert _rect(rect) == (20, 22, 4, 10)
