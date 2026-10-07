"""EDM array tags keep their indices (``symbols { 2 "P=X" }`` is display 2).

EDM reads array tags (displayFileName, symbols, minValues, xPv, command, ...)
as ``<index> <value>`` lines into fixed slots, so parallel arrays line up by
index, not by position, and a file may skip indices or start at 1.
"""

import json

from pydmconverter.edm.ir_adapter import _fixup_shell_cmd, _object_to_source, _pip_rules, edm_file_to_ir
from pydmconverter.edm.converter_helpers import convert_attribute_value
from pydmconverter.edm.menumux import menu_items, menu_macros
from pydmconverter.edm.parser import EDMFileParser, EDMObject, IndexedBlock, block_list
from pydmconverter.widgets import PyDMWaveformPlot
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json


def _props(text):
    return EDMFileParser.get_object_properties(text)


def _obj(name, properties):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, 40, 20
    return obj


# ── parser ───────────────────────────────────────────────────────────────────


def test_sparse_block_keeps_indices_and_clean_values():
    symbols = _props('symbols {\n  2 "P=KLYS:LI20:41"\n}')["symbols"]
    assert isinstance(symbols, IndexedBlock)
    assert list(symbols) == ["P=KLYS:LI20:41"]  # was the raw line '2 "P=KLYS:LI20:41'
    assert symbols.indices == [2]


def test_one_based_block_keeps_its_indices():
    files = _props('displayFileName {\n  1 "b.edl"\n  2 "c.edl"\n}')["displayFileName"]
    assert list(files) == ["b.edl", "c.edl"]
    assert files.indices == [1, 2]


def test_quoted_text_starting_with_a_number_is_not_an_index():
    """value { "1 GeV" } is text; it lost its "1" when quotes were stripped first."""
    assert _props('value {\n  "1 GeV"\n  "2 bunches"\n}')["value"] == ["1 GeV", "2 bunches"]


def test_bare_number_lines_are_text_not_indices():
    """value { 5 } is the text "5", not index 5 with an empty value."""
    for text in ("value {\n  5\n}", "value {\n  5 \n}"):
        value = _props(text)["value"]
        assert not isinstance(value, IndexedBlock)
        assert value == ["5"]


def test_value_continued_onto_the_next_line_joins_its_entry():
    """und/asynOctet.edl: each label's closing quote sits on the next line."""
    labels = _props('menuLabel {\n  0 "Record parameters\n"\n  1 "Serial port\n"\n}')["menuLabel"]
    assert list(labels) == ["Record parameters", "Serial port"]  # was the raw lines and ""s
    assert labels.indices == [0, 1]


def test_repeated_index_replaces_the_earlier_entry():
    """laser/pid_plot_terms.edl writes index 1 twice; EDM's array read keeps the last."""
    labels = _props('menuLabel {\n  0 "LAST_N"\n  1 "1MIN"\n  1 "10MIN"\n  2 "30MIN"\n}')["menuLabel"]
    assert list(labels) == ["LAST_N", "10MIN", "30MIN"]
    assert labels.indices == [0, 1, 2]


def test_block_list_puts_each_value_at_its_index():
    assert block_list(_props('xPv {\n  1 "X1"\n  3 "X3"\n}')["xPv"]) == ["", "X1", "", "X3"]
    assert block_list(["a", "b"]) == ["a", "b"]
    assert block_list("a") == ["a"]
    assert block_list(None) == []


def test_index_with_an_empty_quoted_value_is_indexed():
    symbols = _props('symbols {\n  0 ""\n}')["symbols"]
    assert isinstance(symbols, IndexedBlock)
    assert list(symbols) == [""]
    assert symbols.indices == [0]


# ── related display ──────────────────────────────────────────────────────────


def test_related_display_takes_only_its_own_symbols():
    props = _props(
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n  2 "c.edl"\n}\nsymbols {\n  0 "P=A"\n  2 "P=C,Q=3"\n}\nnumDsps 3'
    )
    node = _object_to_source(_obj("relatedDisplayClass", props))
    assert node.qt_props["filenames"] == ["a.edl"]
    assert node.qt_props["macros"] == {"P": "A"}  # not merged with display 2's P=C,Q=3
    assert any("offers 3 displays" in w for w in node.warnings)


def test_symbols_for_another_display_do_not_leak():
    """symbols { 1 "P=B" } belong to display 1; read as a 1-based list they went to display 0."""
    props = _props('displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\nsymbols {\n  1 "P=B"\n}')
    node = _object_to_source(_obj("relatedDisplayClass", props))
    assert "macros" not in node.qt_props


def test_sparse_symbols_give_no_garbage_keys():
    props = _props('displayFileName {\n  0 "a.edl"\n  2 "c.edl"\n}\nsymbols {\n  0 "P=A"\n  2 "P=C"\n}')
    node = _object_to_source(_obj("relatedDisplayClass", props))
    # Both blocks used to come back as raw lines: file '0 "a.edl', macros {'0 "P': 'A', '2 "P': 'C'}.
    assert node.qt_props["filenames"] == ["a.edl"]
    assert node.qt_props["macros"] == {"P": "A"}


def test_one_based_display_pairs_with_one_based_symbols():
    props = _props('displayFileName {\n  1 "b.edl"\n}\nsymbols {\n  1 "P=B"\n}')
    node = _object_to_source(_obj("relatedDisplayClass", props))
    assert node.qt_props["filenames"] == ["b.edl"]
    assert node.qt_props["macros"] == {"P": "B"}


def test_related_display_screen_validates(tmp_path):
    edl = tmp_path / "rel.edl"
    edl.write_text(
        """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 100
h 100
endScreenProperties

object relatedDisplayClass
beginObjectProperties
major 4
minor 4
release 0
x 10
y 10
w 40
h 20
buttonLabel "Go"
numDsps 2
displayFileName {
  0 "sub_a.edl"
  1 "sub_b.edl"
}
symbols {
  1 "DEV=$(P)"
}
endObjectProperties
""",
        encoding="utf-8",
    )
    wire = to_wire_dict(edm_file_to_ir(edl))
    assert validate_screen_json(wire) == []
    (button,) = wire["root"]["children"]
    assert button["props"]["file"] == "sub_a.screen.json"
    assert "macros" not in button["props"]


# ── other array consumers ────────────────────────────────────────────────────


def test_shell_command_labels_pair_by_index():
    props = _props('command {\n  0 "echo a"\n  1 "echo b"\n}\ncommandLabel {\n  1 "B"\n}')
    qt_props = {}
    _fixup_shell_cmd(_obj("shellCmdClass", props), qt_props, [])
    assert qt_props["actions"] == [
        {"type": "shell_command", "command": "echo a"},
        {"type": "shell_command", "command": "echo b", "label": "B"},
    ]


def test_menu_pip_rule_uses_edm_indices():
    props = _props('displaySource "menu"\nfilePv "SEL"\ndisplayFileName {\n  1 "a.edl"\n  3 "b.edl"\n}')
    (rule,) = _pip_rules(_obj("activePipClass", props))
    assert rule.conditions == [("{0} == 1", "a.screen.json"), ("{0} == 3", "b.screen.json")]
    assert rule.default == "a.screen.json"


def test_symbol_state_ranges_follow_state_indices(tmp_path):
    parser = EDMFileParser.__new__(EDMFileParser)
    props = _props('numStates 2\nminValues {\n  1 "1"\n}\nmaxValues {\n  0 "1"\n  1 "2"\n}')
    # State 0's min is not written: EDM's default 0 (was: state 0 = [1, 1)).
    assert parser.generate_pv_ranges(props) == [["0", "1"], ["1", "2"]]


def test_plot_traces_pair_by_index_in_the_ui_output():
    """mps/mps_byk.edl: trace 0 has no xPv, so xPv starts at 1 (it was paired with trace 0)."""
    props = _props(
        'yPv {\n  0 "Y0"\n  1 "Y1"\n  3 "Y3"\n}\nxPv {\n  1 "X1"\n}\nplotColor {\n  0 index 0\n  1 index 1\n}'
    )
    obj = _obj("xyGraphClass", props)
    plot = PyDMWaveformPlot(name="plot")
    plot.foreground_color = (0, 255, 0, 255)
    plot.y_channel = convert_attribute_value("yPv", props["yPv"], plot, obj, {})
    plot.x_channel = convert_attribute_value("xPv", props["xPv"], plot, obj, {})
    plot.plotColor = [(0, 0, 0, 255), (255, 255, 255, 255)]
    assert plot.y_channel == ["Y0", "Y1", "", "Y3"]
    assert plot.x_channel == ["", "X1"]
    curves = [json.loads(curve) for curve in plot.get_curve_strings()]
    # Index 2 has no yPv and plots nothing; trace 3 has no plotColor and takes the foreground.
    assert [(c["x_channel"], c["y_channel"], c["color"]) for c in curves] == [
        ("", "Y0", "#000000"),
        ("X1", "Y1", "#ffffff"),
        ("", "Y3", "#00ff00"),
    ]


def test_menu_mux_items_keep_their_indices():
    """An item whose tag and value are empty is left out of symbolTag and value0."""
    props = _props(
        'numItems 3\nsymbolTag {\n  1 "B"\n  2 "C"\n}\nsymbol0 {\n  1 "SECT"\n  2 "SECT"\n}\n'
        'value0 {\n  1 "LI21"\n  2 "LI22"\n}'
    )
    obj = _obj("menuMuxClass", props)
    macros = menu_macros(obj, 3)
    assert macros == [[("", "")], [("SECT", "LI21")], [("SECT", "LI22")]]
    assert menu_items(obj, 3, macros) == ["", "B", "C"]
