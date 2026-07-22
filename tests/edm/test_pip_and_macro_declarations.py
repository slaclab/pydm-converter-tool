"""Iteration-3 WS4 regressions: activePipClass file handling per displaySource
(menu pips gain a filePv-keyed `file` rule) and macro declarations discovered
inside structured props (action commands, rule PVs)."""

from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir

FIXTURES = Path(__file__).parent / "fixtures"


def _convert(name):
    return edm_file_to_ir(FIXTURES / name)


def test_menu_pip_gets_static_file_and_switching_rule():
    screen = _convert("pip_menu.edl")
    pip = screen.root.children[0]
    assert pip.type == "embedded-display"
    assert pip.props["file"] == "TEMnocentroid.screen.json"
    rules = [r for r in pip.rules if r.target_property == "file"]
    assert len(rules) == 1
    rule = rules[0]
    assert rule.pvs[0].name == "${TEMLOCATION}:INAPOSITION"
    assert [(c.expression, c.value) for c in rule.conditions] == [
        ("{0} == 0", "TEMnocentroid.screen.json"),
        ("{0} == 1", "TEMcentroid.screen.json"),
    ]
    assert rule.default == "TEMnocentroid.screen.json"


def test_file_pip_keeps_macro_template():
    screen = _convert("pip_menu.edl")
    pip = screen.root.children[1]
    assert pip.type == "embedded-display"
    # ${VAR} form preserved for view-time resolution; extension appended is
    # deferred (macro refs cannot be rewritten by screenRef).
    assert pip.props["file"] == "mgnt_unit_${DISP}"
    assert not [r for r in pip.rules if r.target_property == "file"]


def test_macros_declared_from_rule_pvs_and_action_commands():
    screen = _convert("pip_menu.edl")
    declared = {m.name for m in screen.macros}
    # TEMLOCATION rides the menu pip's file rule; DISP the file template;
    # STRIPCONFIG hides inside the shell-command actions list.
    assert {"TEMLOCATION", "DISP", "STRIPCONFIG"} <= declared
