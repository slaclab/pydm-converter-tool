"""EDM array tags keep their indices (``symbols { 2 "P=X" }`` is display 2).

EDM reads array tags (displayFileName, symbols, minValues, xPv, command, ...)
as ``<index> <value>`` lines into fixed slots, so parallel arrays line up by
index, not by position, and a file may skip indices or start at 1.
"""

from pydmconverter.edm.ir_adapter import _fixup_shell_cmd, _object_to_source, _pip_rules, edm_file_to_ir
from pydmconverter.edm.parser import EDMFileParser, EDMObject, IndexedBlock
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
