"""Iteration-3 WS3 regressions: activeSymbolClass state groups become
complementary visibility rules over the symbol channel (instead of every
state rendering stacked), and the symbol file resolves beside the display."""

from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir

FIXTURES = Path(__file__).parent / "fixtures"


def _symbol_groups():
    screen = edm_file_to_ir(FIXTURES / "symbol_two_state.edl")
    container = screen.root.children[0]
    assert container.type == "group"
    states = [child for child in container.children if child.type == "group"]
    return states


def test_two_state_symbol_emits_complementary_visibility_rules():
    states = _symbol_groups()
    assert len(states) == 2

    seen = []
    for state in states:
        vis_rules = [r for r in state.rules if r.target_property == "visible"]
        assert len(vis_rules) == 1
        rule = vis_rules[0]
        assert rule.pvs[0].name == "${dev}:MOTOR_STATE"
        assert rule.default is False
        seen.append(rule.conditions[0].expression)

    # State 0 visible in [0, 1), state 1 in [1, 2) — complementary ranges.
    assert "({0} >= 0.0) and ({0} < 1.0)" in seen[0]
    assert "({0} >= 1.0) and ({0} < 2.0)" in seen[1]


def test_symbol_state_children_render_real_widgets():
    states = _symbol_groups()
    child_types = [child.type for state in states for child in state.children]
    assert child_types == ["rectangle", "ellipse"]
