"""Phase 1 + Phase 2 combined integration snapshot.

To regenerate ``combined_phase12.screen.json`` deliberately (e.g. after an
intentional IR/prop-mapping change), run from the repo root:

    .venv/Scripts/python.exe -c "
    from pydmconverter.edm.ir_adapter import edm_file_to_ir
    from pydmconverter.ir.emit import to_json
    ir = edm_file_to_ir(
        'tests/edm/fixtures/combined_phase12.edl',
        color_list_path='tests/edm/fixtures/colors.list',
    )
    with open('tests/edm/fixtures/combined_phase12.screen.json', 'w', encoding='utf-8', newline='') as f:
        f.write(to_json(ir))
    "

``newline=''`` keeps the file LF-only on Windows checkouts (``Path.write_text``
would otherwise translate ``\\n`` -> ``\\r\\n``). Review the diff before
committing — this file is the checked-in regression snapshot.
"""

from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
COLORS = FIXTURES / "colors.list"
FIXTURE = FIXTURES / "combined_phase12.edl"
SNAPSHOT = FIXTURES / "combined_phase12.screen.json"


def _convert():
    return edm_file_to_ir(FIXTURE, color_list_path=COLORS)


def test_combined_conversion_matches_committed_snapshot():
    """Byte-for-byte (module ``Path.read_text`` newline translation aside) match against
    the committed snapshot. A failure here means the IR output changed — regenerate the
    snapshot deliberately (see module docstring) and review the diff before committing."""
    actual = to_json(_convert())
    expected = SNAPSHOT.read_text(encoding="utf-8")
    assert actual == expected


def test_combined_fixture_validates_against_schema():
    assert validate_screen_json(to_wire_dict(_convert())) == []


def test_combined_fixture_has_exactly_one_unknown_widget_menu_mux():
    unknown_nodes = []

    def visit(node):
        if node.type == "unknown-widget":
            unknown_nodes.append(node)
        for child in node.children:
            visit(child)

    visit(_convert().root)
    assert len(unknown_nodes) == 1
    assert unknown_nodes[0].props["originalClass"] == "menuMuxClass"


def test_combined_fixture_group_children_match_expectations():
    root = _convert().root
    group = root.children[0]
    assert group.type == "group"
    assert [child.type for child in group.children] == ["rectangle", "line", "text-label"]

    assert [child.type for child in root.children] == [
        "group",
        "arc",
        "pv-progress-bar",
        "pv-label",
        "regular-button",
        "regular-button",
        "pv-meter",
        "pv-radio-group",
        "image-view",
        "unknown-widget",
    ]
