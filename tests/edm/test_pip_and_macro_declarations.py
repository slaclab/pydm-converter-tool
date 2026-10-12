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
    assert "macros" not in pip.props


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


# ── menu windows whose entries pass different macros ────────────────────────


def _menu_screen(tmp_path, file_pv, entries, extra_lines="", other_objects=""):
    """A screen with one menu pip on ``file_pv``; ``entries`` are
    ``(index, file, symbols or None)``."""
    names = "".join(f'  {index} "{name}"\n' for index, name, _ in entries)
    symbols = "".join(f'  {index} "{symbol}"\n' for index, _, symbol in entries if symbol is not None)
    edl = tmp_path / "menu.edl"
    edl.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 400\nh 300\n"
        "endScreenProperties\n\n" + other_objects + "object activePipClass\nbeginObjectProperties\nmajor 4\n"
        'minor 1\nrelease 0\nx 20\ny 20\nw 233\nh 137\ndisplaySource "menu"\n'
        f'filePv "{file_pv}"\nnumDsps {len(entries)}\ndisplayFileName {{\n{names}}}\nsymbols {{\n{symbols}}}\n'
        + extra_lines
        + "noScroll\nendObjectProperties\n",
        encoding="utf-8",
    )
    return edm_file_to_ir(edl)


def _shape(rule):
    return [(c.expression, c.value) for c in rule.conditions], rule.default


DURATIONS = [(0, "plot.edl", "DUR=LAST_N"), (1, "plot.edl", "DUR=1MIN"), (2, "other.edl", "DUR=WEEK")]


def test_menu_window_with_uniform_macros_keeps_its_file_rule(tmp_path):
    entries = [(0, "a.edl", "P=X"), (1, "b.edl", "P=X")]
    screen = _menu_screen(tmp_path, "LOC\\\\sel=i:1", entries)
    (pip,) = screen.root.children
    assert pip.props["file"] == "a.screen.json"
    assert pip.props["macros"] == {"P": "X"}
    assert [r.target_property for r in pip.rules] == ["file"]


def test_menu_window_on_a_local_variable_splits_per_entry(tmp_path):
    """Archive/laser-orig/pid_plot_terms.edl: one file, nine entries, each with
    its own DUR. The merged macros opened every entry with the last DUR."""
    from pydmconverter.ir.emit import to_wire_dict
    from pydmconverter.ir.schema import validate_screen_json

    screen = _menu_screen(tmp_path, "LOC\\\\sel=i:1", DURATIONS)
    displays = screen.root.children
    assert [d.type for d in displays] == ["embedded-display"] * 3
    assert [d.props["file"] for d in displays] == ["plot.screen.json", "plot.screen.json", "other.screen.json"]
    assert [d.props["macros"] for d in displays] == [{"DUR": "LAST_N"}, {"DUR": "1MIN"}, {"DUR": "WEEK"}]
    assert [d.geometry for d in displays] == [displays[0].geometry] * 3
    rules = [d.rules for d in displays]
    assert all(len(r) == 1 and r[0].target_property == "visible" for r in rules)
    assert all([pv.name for pv in r[0].pvs] == ["loc://sel?type=int&init=1"] for r in rules)
    # The first entry also shows for a value no entry has (pip.cc opens entry 0).
    assert _shape(rules[0][0]) == ([("{0} == 1", False), ("{0} == 2", False)], True)
    assert _shape(rules[1][0]) == ([("{0} == 1", True)], False)
    assert _shape(rules[2][0]) == ([("{0} == 2", True)], False)
    assert not any(d.warnings for d in displays)
    assert validate_screen_json(to_wire_dict(screen)) == []


def test_split_menu_window_keeps_edm_indices(tmp_path):
    screen = _menu_screen(tmp_path, "LOC\\\\sel=i:3", [(1, "a.edl", "P=A"), (3, "b.edl", "P=B")])
    first, second = screen.root.children
    assert _shape(first.rules[0]) == ([("{0} == 3", False)], True)
    assert _shape(second.rules[0]) == ([("{0} == 3", True)], False)
    assert (first.props["macros"], second.props["macros"]) == ({"P": "A"}, {"P": "B"})


def test_split_menu_entry_without_symbols_gets_no_macros(tmp_path):
    # laser/profile1.edl: entry 0 (Rectangle) has no symbols line; it got entry 1's ID.
    screen = _menu_screen(tmp_path, "LOC\\\\sel=i:0", [(0, "blank.edl", None), (1, "cam.edl", "ID=$(ID)")])
    blank, cam = screen.root.children
    assert "macros" not in blank.props
    assert cam.props["macros"] == {"ID": "${ID}"}


def test_split_menu_window_declares_a_variable_nothing_gives_a_value(tmp_path):
    # laser/profile1.edl: LOC\Display is only ever named; unconnected, every display would show.
    screen = _menu_screen(tmp_path, "LOC\\\\Display", DURATIONS)
    for display in screen.root.children:
        assert [pv.name for pv in display.rules[0].pvs] == ["loc://Display?type=int&init=0"]


def test_split_menu_window_reads_a_variable_another_widget_declares(tmp_path):
    label = (
        "object activeXTextDspClass:noedit\nbeginObjectProperties\nmajor 4\nminor 7\nrelease 0\n"
        'x 10\ny 200\nw 100\nh 20\ncontrolPv "LOC\\\\sel=i:2"\nendObjectProperties\n\n'
    )
    screen = _menu_screen(tmp_path, "LOC\\\\sel", DURATIONS, other_objects=label)
    for display in screen.root.children[1:]:
        assert [pv.name for pv in display.rules[0].pvs] == ["loc://sel?type=int&init=2"]


def _loc_label(pv, y=200):
    """A text update on ``pv`` (EDL object text)."""
    return (
        "object activeXTextDspClass:noedit\nbeginObjectProperties\nmajor 4\nminor 7\nrelease 0\n"
        f'x 10\ny {y}\nw 100\nh 20\ncontrolPv "{pv}"\nendObjectProperties\n\n'
    )


def _group(objects):
    """An activeGroupClass holding ``objects`` (EDL object text)."""
    return (
        "object activeGroupClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        "x 0\ny 0\nw 400\nh 300\nbeginGroup\n\n" + objects + "endGroup\n\nendObjectProperties\n\n"
    )


def _split_rule_pvs(displays):
    assert [d.type for d in displays] == ["embedded-display"] * len(DURATIONS)
    return {pv.name for d in displays for pv in d.rules[0].pvs}


def test_split_menu_window_reads_a_declaration_inside_a_group(tmp_path):
    screen = _menu_screen(tmp_path, "LOC\\\\sel", DURATIONS, other_objects=_group(_loc_label("LOC\\\\sel=i:2")))
    _group_node, *displays = screen.root.children
    assert _split_rule_pvs(displays) == {"loc://sel?type=int&init=2"}


def test_split_menu_window_in_a_group_reads_a_declaration_outside_it(tmp_path):
    # A nested group's objects read the whole file's declarations, not just their group's.
    _menu_screen(tmp_path, "LOC\\\\sel", DURATIONS)
    edl = tmp_path / "menu.edl"
    head, pip = edl.read_text(encoding="utf-8").split("object activePipClass", 1)
    edl.write_text(head + _loc_label("LOC\\\\sel=i:2") + _group("object activePipClass" + pip), encoding="utf-8")
    _label, group = edm_file_to_ir(edl).root.children
    assert _split_rule_pvs(group.children) == {"loc://sel?type=int&init=2"}


def test_split_menu_window_reads_the_first_declaration(tmp_path):
    # EDM (loc_pv_factory.cc) keeps the first value a reference gives the variable.
    labels = _loc_label("LOC\\\\sel=i:2") + _loc_label("LOC\\\\sel=i:1", y=230)
    screen = _menu_screen(tmp_path, "LOC\\\\sel", DURATIONS, other_objects=labels)
    assert _split_rule_pvs(screen.root.children[2:]) == {"loc://sel?type=int&init=2"}


def test_split_menu_window_keeps_its_visibility_rule(tmp_path):
    screen = _menu_screen(tmp_path, "LOC\\\\sel=i:1", DURATIONS, extra_lines='visPv "SHOW"\nvisMin "1"\nvisMax "2"\n')
    for display in screen.root.children:
        assert (display.rules[0].name, display.rules[0].pvs[0].name) == ("Visibility", "SHOW")
        assert display.rules[1].target_property == "visible"


def test_menu_window_on_a_channel_opens_with_the_first_entrys_macros(tmp_path):
    # xray/gdet_main.edl: a real PV drives the window, so it stays one display
    # with the file rule; the macros cannot follow it.
    screen = _menu_screen(tmp_path, "GDET:FEE1:1:CONFIG", DURATIONS)
    (pip,) = screen.root.children
    assert pip.props["file"] == "plot.screen.json"
    assert pip.props["macros"] == {"DUR": "LAST_N"}
    assert [r.target_property for r in pip.rules] == ["file"]
    assert any("different symbols" in w and "first entry" in w for w in pip.warnings)


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
