import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURE = Path(__file__).parent / "fixtures" / "visibility.edl"


def _convert():
    return edm_file_to_ir(FIXTURE)


def test_group_visibility_rule_on_group_node():
    """A group's visPv becomes a visible rule on the group node itself, not its children."""
    group = _convert().root.children[0]
    assert group.type == "group"
    assert len(group.rules) == 1
    rule = group.rules[0]
    assert rule.id == "r-001"
    assert rule.target_property == "visible"
    assert [pv.name for pv in rule.pvs] == ["${PREFIX}:ENABLE"]
    # No visMin/visMax: EDM reads both as 0, the empty range [0, 0).
    assert rule.conditions[0].expression == "({0} >= 0.0) and ({0} < 0.0)"
    assert rule.conditions[0].value is True
    assert rule.default is False

    label = group.children[0]
    assert label.type == "text-label"
    assert label.rules == []


def test_own_inverted_range_visibility():
    """visMin/visMax form a range; visInvert wraps it in not(...)."""
    rule = _convert().root.children[1].rules[0]
    assert rule.id == "r-002"
    assert [pv.name for pv in rule.pvs] == ["${PREFIX}:MODE"]
    assert rule.conditions[0].expression == "not (({0} >= 1.0) and ({0} < 3.0))"
    assert rule.default is False


def test_rule_pvs_contribute_macros():
    """Macros referenced only inside a rule PV are still declared."""
    assert [m.name for m in _convert().macros] == ["PREFIX"]


def test_output_validates():
    assert validate_screen_json(to_wire_dict(_convert())) == []


def test_widgets_without_visibility_have_no_rules():
    from pathlib import Path as _Path

    plain = edm_file_to_ir(_Path(__file__).parent / "fixtures" / "basic_widgets.edl")
    assert all(not child.rules for child in plain.root.children)


# --- visMin/visMax are strings in EDM, evaluated with atof() -------------------

_SCREEN = """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 200
h 200
endScreenProperties
"""


def _vis_object(vis_min: str, vis_max: str, *, invert: bool = False) -> str:
    return f"""
object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 14
visPv "$(P):VIS"
{"visInvert" if invert else ""}
visMin "{vis_min}"
visMax "{vis_max}"
endObjectProperties
"""


def _convert_text(tmp_path, body: str):
    path = tmp_path / "vis.edl"
    path.write_text(_SCREEN + body, encoding="utf-8")
    return edm_file_to_ir(path)


def test_edm_atof_prefix_semantics():
    from pydmconverter.edm.ir_adapter import _edm_atof

    assert _edm_atof("3") == 3.0
    assert _edm_atof("1`") == 1.0  # numeric prefix wins, trailing junk ignored
    assert _edm_atof("0x80000000") == 2147483648.0  # glibc strtod reads hex
    assert _edm_atof("-0x10") == -16.0
    assert _edm_atof(" 2.5e1abc") == 25.0
    assert _edm_atof("MAJOR") == 0.0
    assert _edm_atof("KLYS:LI20:21:BVLT.LOW") == 0.0
    assert _edm_atof("") == 0.0


def test_hex_vis_limits_evaluate_like_edm(tmp_path):
    """Hex limits: float() used to crash the screen."""
    node = _convert_text(tmp_path, _vis_object("0x80000000", "0x80008001")).root.children[0]
    [rule] = [r for r in node.rules if r.target_property == "visible"]
    assert rule.conditions[0].expression == "({0} >= 2147483648.0) and ({0} < 2147516417.0)"
    assert any("evaluated as 2147483648" in w for w in node.warnings)


def test_non_numeric_literal_vis_limit_is_zero(tmp_path):
    """A literal non-number ("MAJOR") is atof() -> 0 in EDM, with a warning."""
    node = _convert_text(tmp_path, _vis_object("MAJOR", "2")).root.children[0]
    [rule] = [r for r in node.rules if r.target_property == "visible"]
    assert rule.conditions[0].expression == "({0} >= 0.0) and ({0} < 2.0)"
    assert any("visMin 'MAJOR' is not a plain number; evaluated as 0" in w for w in node.warnings)


def test_macro_vis_limits_drop_rule_with_warning(tmp_path):
    """PVs named in visMin/visMax ("$(device):...:BVLT.LOW").

    The value depends on the caller's macros, so no rule is emitted — the screen
    converts instead of aborting, and the node says why.
    """
    ir = _convert_text(tmp_path, _vis_object("$(device):BVLT.LOW", "$(device):BVLT.HIGH", invert=True))
    node = ir.root.children[0]
    assert node.type == "rectangle"
    assert [r for r in node.rules if r.target_property == "visible"] == []
    assert any("visMin '${device}:BVLT.LOW' depends on a macro" in w for w in node.warnings)
    assert validate_screen_json(to_wire_dict(ir)) == []


def test_group_macro_vis_limit_warns_on_group_node(tmp_path):
    """A group's unevaluable visMin lands as a warning on the group node, not a crash."""
    body = """
object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 50
h 50
beginGroup

object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 14
endObjectProperties

endGroup

visPv "$(P):VIS"
visMin "$(LO)"
visMax "5"
endObjectProperties
"""
    group = _convert_text(tmp_path, body).root.children[0]
    assert group.type == "group"
    assert group.rules == []
    assert any("visMin '${LO}' depends on a macro" in w for w in group.warnings)


# --- A missing visMin or visMax is 0 (EDM's atof() of an empty string) --------

_RECTANGLE = """
object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 14
{vis}
endObjectProperties
"""

_GROUP = """
object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 50
h 50
beginGroup
{rectangle}
endGroup

{vis}
endObjectProperties
"""

# The values a live EDM was checked at, and the ones the object showed at.
_VALUES = (1, 0, 5, -1, 0.5)
MISSING_LIMITS = [
    pytest.param([], set(), id="no-limits"),
    pytest.param(["visInvert"], set(_VALUES), id="no-limits-inverted"),
    pytest.param(['visMin "1"'], set(), id="only-visMin"),
    pytest.param(['visMin "1"', "visInvert"], set(_VALUES), id="only-visMin-inverted"),
    pytest.param(['visMax "1"'], {0, 0.5}, id="only-visMax"),
    pytest.param(['visMax "1"', "visInvert"], {1, 5, -1}, id="only-visMax-inverted"),
]


def _vis_screen(vis_lines, *, group):
    vis = "\n".join(['visPv "DEMO:SHOW"', *vis_lines])
    if group:
        return _SCREEN + _GROUP.format(rectangle=_RECTANGLE.format(vis=""), vis=vis)
    return _SCREEN + _RECTANGLE.format(vis=vis)


@pytest.mark.parametrize("group", [False, True], ids=["object", "group"])
@pytest.mark.parametrize(("vis_lines", "shown"), MISSING_LIMITS)
def test_ir_missing_vis_limit_is_zero(tmp_path, vis_lines, shown, group):
    path = tmp_path / "vis.edl"
    path.write_text(_vis_screen(vis_lines, group=group), encoding="utf-8")
    node = edm_file_to_ir(path).root.children[0]
    [rule] = node.rules
    assert rule.target_property == "visible"
    assert [pv.name for pv in rule.pvs] == ["DEMO:SHOW"]
    [condition] = rule.conditions
    assert condition.value is True and rule.default is False
    assert {value for value in _VALUES if eval(condition.expression.replace("{0}", repr(float(value))))} == shown
    assert not [w for w in node.warnings if "visMin" in w or "visMax" in w]


@pytest.mark.parametrize("group", [False, True], ids=["object", "group"])
@pytest.mark.parametrize(("vis_lines", "shown"), MISSING_LIMITS)
def test_ui_missing_vis_limit_is_zero(tmp_path, vis_lines, shown, group):
    source = tmp_path / "vis.edl"
    source.write_text(_vis_screen(vis_lines, group=group), encoding="utf-8")
    convert(str(source), str(tmp_path / "vis.ui"))
    [rectangle] = [w for w in ET.parse(tmp_path / "vis.ui").iter("widget") if w.get("class") == "PyDMDrawingRectangle"]
    [rule] = json.loads(rectangle.find("property[@name='rules']/string").text)
    assert rule["property"] == "Visible"
    assert [channel["channel"] for channel in rule["channels"]] == ["DEMO:SHOW"]
    assert {value for value in _VALUES if eval(rule["expression"], {"ch": [value], "float": float})} == shown
