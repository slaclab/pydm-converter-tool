from pathlib import Path

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
    assert rule.conditions[0].expression == "{0} != 0"
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
