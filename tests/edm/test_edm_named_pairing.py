"""EDM text and its ground pair through their palette names (:mod:`pydmconverter.pairing` for ``.edl``).

The adapter tells the pairing pass which colour props came from a ``colors.list`` name, so a
text colour the parity rule kept literal (its hex is not the role's light value) still becomes
its role when it sits on a role ground, and the pair flips together in a dark theme. The
palette and the scheme are synthetic: ``canopy-default`` imports no EDM text name.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.scheme import load_scheme

# "Label text" is plain black, as a stock palette's text colour is; canopy-default's Text role
# is #161616, so the parity rule keeps it literal and only the pairing can promote it.
# "Dim text" is exactly the Text role's light value, so it is a role as soon as it is resolved.
PALETTE = """4 0 0

blinkms=500
columns=5
max=0x10000

static 0 "Black" { 0 0 0 }
static 4 "GLOBAL canvas" { 0xffff 0xffff 0xffff }
static 14 "Label text" { 0 0 0 }
static 15 "Dim text" { 0x1616 0x1616 0x1616 }
"""

SCHEME = {"id": "site", "import": {"edm": {"Label text": "Text", "Dim text": "Text"}}}

SCREEN = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 400
h 200
font "helvetica-medium-r-14.0"
bgColor rgb 65535 65535 65535
endScreenProperties

"""

TEXT_ROLE = {"$role": "Text", "fallback": "#000000"}
CANVAS_ROLE = {"$role": "Display_Background", "fallback": "#ffffff"}


def _label(y: int, fg: str, bg: str) -> str:
    return (
        "object activeXTextClass\nbeginObjectProperties\nmajor 4\nminor 1\nrelease 1\n"
        f'x 10\ny {y}\nw 160\nh 18\nfont "helvetica-medium-r-14.0"\nfgColor {fg}\nbgColor {bg}\n'
        'value {\n  "Label"\n}\nendObjectProperties\n\n'
    )


def _group(body: str) -> str:
    return (
        "object activeGroupClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x 0\ny 0\nw 400\nh 200\n\nbeginGroup\n\n{body}endGroup\n\nendObjectProperties\n\n"
    )


@pytest.fixture
def palette(tmp_path: Path) -> Path:
    path = tmp_path / "colors.list"
    path.write_text(PALETTE, encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def scheme(tmp_path: Path):
    path = tmp_path / "site.json"
    path.write_text(json.dumps(SCHEME), encoding="utf-8")
    result = load_scheme(path)
    assert result.meta["errors"] == [] and result.meta["served"] == "site"
    return result


def _convert(tmp_path: Path, body: str, palette: Path, scheme):
    path = tmp_path / "pairing.edl"
    path.write_text(SCREEN + body, encoding="utf-8", newline="\n")
    return edm_file_to_ir(path, color_list_path=palette, scheme=scheme).root.children


def _notes(widgets, prefix: str) -> list[str]:
    return [w for widget in widgets for w in widget.warnings if w.startswith(prefix)]


def test_named_text_on_its_named_ground_becomes_a_role_pair(tmp_path, palette, scheme):
    (label,) = _convert(tmp_path, _label(10, "index 14", "index 4"), palette, scheme)
    assert label.props["foregroundColor"] == TEXT_ROLE
    assert label.props["backgroundColor"] == CANVAS_ROLE
    assert _notes([label], "parity: ") == []
    assert _notes([label], "pair: ") == [
        "pair: color 'Label text' written as scheme role 'Text' with its ground (fgColor) (1 use)"
    ]


def test_named_text_on_a_literal_ground_stays_literal(tmp_path, palette, scheme):
    (label,) = _convert(tmp_path, _label(10, "index 14", "rgb 65535 65535 65535"), palette, scheme)
    assert label.props["foregroundColor"] == "#000000"
    assert label.props["backgroundColor"] == "#ffffff"
    assert _notes([label], "pair: ") == []
    assert _notes([label], "parity: ") == [
        "parity: color 'Label text' kept as #000000, scheme role 'Text' has light #161616 (1 use: fgColor)"
    ]


def test_role_text_on_a_literal_ground_is_demoted(tmp_path, palette, scheme):
    (label,) = _convert(tmp_path, _label(10, "index 15", "rgb 65535 65535 65535"), palette, scheme)
    assert label.props["foregroundColor"] == "#161616"
    assert _notes([label], "pair: ") == [
        "pair: scheme role 'Text' of a text kept as #161616: its dark value is unreadable on #ffffff (1 use)"
    ]


def test_named_text_inside_a_group_pairs_with_its_own_ground(tmp_path, palette, scheme):
    (group,) = _convert(tmp_path, _group(_label(10, "index 14", "index 4")), palette, scheme)
    (label,) = group.children
    assert label.props["foregroundColor"] == TEXT_ROLE
    assert label.props["backgroundColor"] == CANVAS_ROLE
    assert _notes([group], "parity: ") == []
