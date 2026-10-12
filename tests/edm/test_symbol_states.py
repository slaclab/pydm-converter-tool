"""Iteration-3 WS3 regressions: activeSymbolClass state groups become
complementary visibility rules over the symbol channel (instead of every
state rendering stacked), and the symbol file resolves beside the display."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
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


# --- .ui target ------------------------------------------------------------


def _ui_rules(ui_path):
    """Each drawing widget's Visible rules, keyed by class."""
    rules = {}
    for widget in ET.parse(ui_path).getroot().iter("widget"):
        cls = widget.get("class")
        if cls not in ("PyDMDrawingRectangle", "PyDMDrawingEllipse"):
            continue
        prop = widget.find("property[@name='rules']/string")
        rules[cls] = [r for r in json.loads(prop.text) if r["property"] == "Visible"]
    return rules


def test_ui_symbol_states_switch_on_the_symbol_channel(tmp_path, monkeypatch):
    """Each state's widgets show only while the channel is in the state's range,
    as in EDM (min <= value < max), instead of every state drawing stacked."""
    monkeypatch.chdir(tmp_path)
    convert(str(FIXTURES / "symbol_two_state.edl"), str(tmp_path / "symbol.ui"))
    rules = _ui_rules(tmp_path / "symbol.ui")
    for cls, (low, high) in (("PyDMDrawingRectangle", (0.0, 1.0)), ("PyDMDrawingEllipse", (1.0, 2.0))):
        (rule,) = rules[cls]
        assert [c["channel"] for c in rule["channels"]][0] == "${dev}:MOTOR_STATE"
        assert f"float(ch[0]) >= {low} and float(ch[0]) < {high}" in rule["expression"]


# The symbol on a local variable, plus a text control reading the same variable. PyDM
# sends a rule that joins a loc:// variable its first value before reporting it
# connected, and rules skip that value, so a variable only rules read shows its first
# state only after a write. A real control PV delivers its value after connecting,
# which the text control's channel reproduces here. (No SLAC symbol uses a LOC\\
# control PV.)
SYMBOL_ON_LOC = (FIXTURES / "symbol_two_state.edl").read_text().replace(
    '"$(dev):MOTOR_STATE"', '"LOC\\\\symbolState=i:1"'
) + (
    "\nobject activeXTextDspClass\nbeginObjectProperties\nmajor 4\nminor 7\nrelease 0\n"
    'x 100\ny 60\nw 60\nh 20\ncontrolPv "LOC\\\\symbolState"\nendObjectProperties\n'
)


def test_ui_symbol_shows_the_state_its_variable_selects(tmp_path, monkeypatch, qtbot):
    """Loaded in PyDM, only the state the variable selects is visible, and writing the
    variable switches states."""
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.display import load_file
    from pydm.widgets.drawing import PyDMDrawingEllipse, PyDMDrawingRectangle

    assert "symbolState=i:1" in SYMBOL_ON_LOC
    monkeypatch.chdir(tmp_path)
    (tmp_path / "symbol_states.edl").write_text((FIXTURES / "symbol_states.edl").read_text())
    (tmp_path / "symbol.edl").write_text(SYMBOL_ON_LOC)
    convert(str(tmp_path / "symbol.edl"), str(tmp_path / "symbol.ui"))

    screen = load_file(str(tmp_path / "symbol.ui"), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (state0,) = screen.findChildren(PyDMDrawingRectangle)
    (state1,) = screen.findChildren(PyDMDrawingEllipse)

    # The variable starts at 1: state 1 shows once the channel connects, state 0 stays hidden.
    qtbot.waitUntil(lambda: state1.isVisible() and not state0.isVisible(), timeout=3000)
    plugin_for_address("loc://x").connections["symbolState"].put_value(0)
    qtbot.waitUntil(lambda: state0.isVisible() and not state1.isVisible(), timeout=3000)


def _symbol_with_ranges(ranges):
    """symbol_two_state.edl with one [min, max) range per state."""
    text = (FIXTURES / "symbol_two_state.edl").read_text()
    head, rest = text.split("numStates 2\n", 1)
    _, tail = rest.split("controlPvs {", 1)
    blocks = "".join(
        f"{key} {{\n" + "".join(f"  {i} {limits[column]}\n" for i, limits in enumerate(ranges)) + "}\n"
        for column, key in ((0, "minValues"), (1, "maxValues"))
    )
    return f"{head}numStates {len(ranges)}\n{blocks}controlPvs {{{tail}"


def _shows(rules, value):
    """Whether a widget's Visible rule holds while its channels all read value."""
    (rule,) = rules
    return eval(rule["expression"], {}, {"ch": [value] * len(rule["channels"])})


@pytest.mark.parametrize(
    "ranges",
    [
        [(0, 1), (1, 2)],
        # State 0 only ever shows as the fallback, as in lcls/pps_dog_main.edl.
        [(1, 1), (0, 1)],
        # Three states but two groups: EDM still matches state 2 and draws nothing.
        [(0, 1), (1, 2), (2, 3)],
    ],
)
def test_ui_symbol_shows_state_0_when_no_state_holds_the_value(tmp_path, monkeypatch, ranges):
    """EDM draws the first state whose range holds the value, and state 0 when none
    does (symbol.cc executeDeferred), so state 0 also shows outside the other ranges."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "symbol_states.edl").write_text((FIXTURES / "symbol_states.edl").read_text())
    (tmp_path / "symbol.edl").write_text(_symbol_with_ranges(ranges))
    convert(str(tmp_path / "symbol.edl"), str(tmp_path / "symbol.ui"))
    rules = _ui_rules(tmp_path / "symbol.ui")

    widgets = ["PyDMDrawingRectangle", "PyDMDrawingEllipse"]  # states 0 and 1
    for value in (-1, 0, 0.5, 1, 1.5, 2, 2.5, 3, 7):
        edm_state = next((i for i, (low, high) in enumerate(ranges) if low <= value < high), 0)
        assert [cls for cls in widgets if _shows(rules[cls], value)] == widgets[edm_state : edm_state + 1], value


def test_ui_symbol_shows_state_0_for_a_value_in_no_range(tmp_path, monkeypatch, qtbot):
    """Loaded in PyDM, a value in no state's range shows state 0, as in EDM."""
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.display import load_file
    from pydm.widgets.drawing import PyDMDrawingEllipse, PyDMDrawingRectangle

    monkeypatch.chdir(tmp_path)
    (tmp_path / "symbol_states.edl").write_text((FIXTURES / "symbol_states.edl").read_text())
    (tmp_path / "symbol.edl").write_text(SYMBOL_ON_LOC.replace("symbolState=i:1", "symbolState=i:5"))
    convert(str(tmp_path / "symbol.edl"), str(tmp_path / "symbol.ui"))

    screen = load_file(str(tmp_path / "symbol.ui"), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (state0,) = screen.findChildren(PyDMDrawingRectangle)
    (state1,) = screen.findChildren(PyDMDrawingEllipse)
    variable = plugin_for_address("loc://x").connections["symbolState"]

    # 5 is past both ranges ([0, 1) and [1, 2)): state 0 shows.
    qtbot.waitUntil(lambda: state0.isVisible() and not state1.isVisible(), timeout=3000)
    variable.put_value(1)
    qtbot.waitUntil(lambda: state1.isVisible() and not state0.isVisible(), timeout=3000)
    variable.put_value(7)
    qtbot.waitUntil(lambda: state0.isVisible() and not state1.isVisible(), timeout=3000)
