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


def test_digit_leading_macro_converts_on_both_sides(tmp_path):
    """llrf/rf_mux_alarms references $(6X6FBCKPV) and llrf/rf_abstr_debug passes
    6X6FBCKPV=... to it. The IR rejects the name, so both screens rename it the
    same way instead of the target aborting."""
    from pydmconverter.ir.emit import to_wire_dict
    from pydmconverter.ir.schema import validate_screen_json

    edl = tmp_path / "mux.edl"
    edl.write_text(
        """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 300
h 100
endScreenProperties

object activeXTextDspClass:noedit
beginObjectProperties
major 4
minor 7
release 0
x 10
y 10
w 100
h 20
controlPv "$(6X6FBCKPV).NAME"
endObjectProperties

object relatedDisplayClass
beginObjectProperties
major 4
minor 4
release 0
x 10
y 40
w 100
h 20
numDsps 1
displayFileName {
  0 "rf_mux_alarms.edl"
}
symbols {
  0 "MUX_REC=ACCL:LI22:1:PDES,6X6FBCKPV=FBCK:FB04:LG01:S5USED"
}
endObjectProperties
""",
        encoding="utf-8",
    )
    screen = edm_file_to_ir(edl)
    label, button = screen.root.children
    assert label.props["pv"] == "${M_6X6FBCKPV}.NAME"
    assert button.props["macros"] == {"MUX_REC": "ACCL:LI22:1:PDES", "M_6X6FBCKPV": "FBCK:FB04:LG01:S5USED"}
    assert [m.name for m in screen.macros] == ["M_6X6FBCKPV"]
    assert any("6X6FBCKPV -> M_6X6FBCKPV" in w for w in screen.root.warnings)
    assert validate_screen_json(to_wire_dict(screen)) == []
