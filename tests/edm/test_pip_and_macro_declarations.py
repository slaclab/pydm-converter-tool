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


def _convert_pip(tmp_path, lines):
    """One activePipClass carrying the given property lines -> its IR node."""
    edl = tmp_path / "pip.edl"
    edl.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 400\nh 300\n"
        "endScreenProperties\n\nobject activePipClass\nbeginObjectProperties\nmajor 4\nminor 1\n"
        "release 0\nx 20\ny 20\nw 233\nh 137\n" + lines + "noScroll\nendObjectProperties\n",
        encoding="utf-8",
    )
    (pip,) = edm_file_to_ir(edl).root.children
    assert pip.type == "embedded-display"
    return pip


LEFTOVER_MENU = (
    'numDsps 2\ndisplayFileName {\n  0 "menu_a"\n  1 "menu_b"\n}\nsymbols {\n  0 "sector=LI20"\n  1 "sector=LI21"\n}\n'
)


def test_file_pip_ignores_leftover_menu_entries_and_symbols(tmp_path):
    # misc/opsKlys_disp_li24.edl: a window switched to "file" keeps its menu
    # entries; EDM (pip.cc) opens the file with the parent's macros only.
    pip = _convert_pip(tmp_path, 'displaySource "file"\nfilePv "$(sector)"\nfile "sector_$(sector)"\n' + LEFTOVER_MENU)
    assert pip.props["file"] == "sector_${sector}"
    # Only its own window id ($(!W)), none of the menu entries' symbols.
    assert list(pip.props["macros"]) == ["EDM_W", "EDM_W_ROOT"]


def test_file_pip_without_a_file_opens_nothing(tmp_path):
    pip = _convert_pip(tmp_path, 'displaySource "file"\nfile ""\n' + LEFTOVER_MENU)
    assert "file" not in pip.props


def test_string_pv_pip_opens_its_local_variable_value(tmp_path):
    # No displaySource line is "stringPV" (the enum default EDM leaves out): the
    # file is the filePv's value, here a LOC string's initial one (misc/tdsEmbd.edl).
    pip = _convert_pip(tmp_path, 'filePv "LOC\\\\showMe=s:tdsVert"\nfile "unused"\nnumDsps 0\n')
    assert pip.props["file"] == "tdsVert.screen.json"
    assert not pip.rules


def test_string_pv_pip_on_a_channel_opens_nothing(tmp_path):
    pip = _convert_pip(tmp_path, 'filePv "CUDBMPR:MCC0:VIDEO1"\nfile "unused"\nnumDsps 0\n')
    assert "file" not in pip.props
    assert any("stringPV" in w and "CUDBMPR:MCC0:VIDEO1" in w for w in pip.warnings)


def test_pip_without_display_source_ignores_its_file(tmp_path):
    pip = _convert_pip(tmp_path, 'file "mgnt_unit_$(DISP)"\nnumDsps 0\n')
    assert "file" not in pip.props


def test_menu_pip_without_file_pv_opens_nothing(tmp_path):
    # EDM opens a menu window's entries only when its filePv's value arrives.
    pip = _convert_pip(tmp_path, 'displaySource "menu"\nfile "unused"\n' + LEFTOVER_MENU)
    assert "file" not in pip.props
    assert not pip.rules


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


def test_shell_variables_are_not_declared_as_macros(tmp_path):
    """EDM expands only $(NAME). und/mc_undh_cam_main.edl runs
    `for m in \\{1..5\\}; do caput $(CM):CM$\\{m\\}CALIBRATE.PROC 1; done` and
    facet/evnt_in10_main.edl passes CRATE=$\\{CRATE\\} to pydm: ${m} and ${CRATE}
    are shell variables. Declared with default "", the runtime would blank them."""
    edl = tmp_path / "shell.edl"
    edl.write_text(
        r"""4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 300
h 100
endScreenProperties

object shellCmdClass
beginObjectProperties
major 4
minor 3
release 0
x 10
y 10
w 100
h 20
buttonLabel "Calibrate"
numCmds 2
command {
  0 "for m in \{1..5\}; do caput $(CM):CM$\{m\}CALIBRATE.PROC 1; done"
  1 "pydm -m \"LOCA=IN10,CRATE=$\{CRATE\}\" tprDiagNC.ui"
}
endObjectProperties
""",
        encoding="utf-8",
    )
    screen = edm_file_to_ir(edl)
    (button,) = screen.root.children
    assert [action["command"] for action in button.props["actions"]] == [
        "for m in {1..5}; do caput ${CM}:CM${m}CALIBRATE.PROC 1; done",
        'pydm -m "LOCA=IN10,CRATE=${CRATE}" tprDiagNC.ui',
    ]
    assert [m.name for m in screen.macros] == ["CM"]
    assert screen.root.warnings == []
