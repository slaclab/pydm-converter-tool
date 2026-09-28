"""Symbol expansion runs at parse time, outside the adapter's per-object
isolation, so a malformed symbol file or symbol object must degrade to a
warning, never fail the screen (EDM symbol.cc readSymbolFile semantics where
they are clear)."""

import pytest

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.edm.parser import EDMFileParser
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

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

_RECT = """object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y 0
w 10
h 10
lineColor rgb {red} 0 0
endObjectProperties
"""


def _state(x, red=0):
    return f"""object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y 0
w 10
h 10

beginGroup

{_RECT.format(x=x, red=red)}
endGroup

endObjectProperties
"""


def _symbol(extra='numPvs 1\ncontrolPvs {\n  0 "SYM:STATE"\n}\n'):
    return (
        _HEADER
        + """
object activeSymbolClass
beginObjectProperties
major 4
minor 0
release 0
x 20
y 20
w 10
h 10
file "sym"
numStates 2
minValues {
  1 1
}
maxValues {
  0 1
  1 2
}
"""
        + extra
        + "endObjectProperties\n"
    )


def _convert(tmp_path, symbol_file_text, screen_text=None, encoding="utf-8"):
    (tmp_path / "sym.edl").write_bytes(symbol_file_text.encode(encoding))
    screen = tmp_path / "screen.edl"
    screen.write_text(screen_text or _symbol(), encoding="utf-8")
    wire = to_wire_dict(edm_file_to_ir(screen))
    assert validate_screen_json(wire) == []
    (symbol,) = wire["root"]["children"]
    return symbol


def test_non_group_top_level_object_ends_the_states(tmp_path):
    """EDM reads states until the first top-level object that is not a group."""
    symbol = _convert(tmp_path, _HEADER + _state(0) + _RECT.format(x=0, red=0) + _state(20))
    assert [child["type"] for child in symbol["children"]] == ["group"]
    assert any("state 1 should be a group" in w for w in symbol.get("warnings", []))


def test_symbol_file_without_groups_renders_nothing_with_a_warning(tmp_path):
    symbol = _convert(tmp_path, _HEADER + _RECT.format(x=0, red=0))
    assert symbol.get("children", []) == []
    assert any("state 0 should be a group" in w for w in symbol.get("warnings", []))


def test_missing_num_pvs_is_edm_default_zero_and_shows_state_one(tmp_path):
    """symbol.cc: numPvs defaults to 0; with no control PV index = 1."""
    symbol = _convert(tmp_path, _HEADER + _state(0) + _state(20, red=65535), _symbol(extra=""))
    (state,) = symbol["children"]
    assert state["children"][0]["props"]["lineColor"] == "#ff0000"  # state 1's rectangle
    assert state.get("rules", []) == []


def test_state_ranges_honour_one_based_min_values(tmp_path):
    symbol = _convert(tmp_path, _HEADER + _state(0) + _state(20))
    expressions = [state["rules"][0]["conditions"][0]["expression"] for state in symbol["children"]]
    assert expressions == ["({0} >= 0.0) and ({0} < 1.0)", "({0} >= 1.0) and ({0} < 2.0)"]


def test_symbol_file_without_screen_properties_and_latin1(tmp_path):
    text = "# caf\xe9\n" + _state(0) + _state(20)
    symbol = _convert(tmp_path, text, encoding="latin-1")
    assert len(symbol["children"]) == 2


def test_unexpected_expansion_failure_keeps_the_rect_with_a_warning(tmp_path, monkeypatch):
    def boom(self, *args, **kwargs):
        raise RuntimeError("exploded")

    monkeypatch.setattr(EDMFileParser, "resize_symbol_groups", boom)
    symbol = _convert(tmp_path, _HEADER + _state(0) + _state(20))
    assert symbol.get("children", []) == []
    assert symbol["geometry"] == {"x": 20, "y": 20, "width": 10, "height": 10}
    assert any("could not be expanded (RuntimeError: exploded)" in w for w in symbol["warnings"])


@pytest.mark.parametrize("extra", ["numPvs 1\n", 'numPvs 1\ncontrolPvs {\n  0 ""\n}\n'])
def test_num_pvs_without_a_control_pv_is_no_control(tmp_path, extra):
    symbol = _convert(tmp_path, _HEADER + _state(0) + _state(20), _symbol(extra=extra))
    assert len(symbol["children"]) == 1
