"""A converted ``.bob`` screen never pairs text and its ground so that the dark theme hides the text.

The vendored ``canopy-default`` scheme restyles ``Text`` (light ``#161616``, not Phoebus
black), so the parity rule alone keeps default label text literal black while the
undeclared display background becomes the ``Display_Background`` role: black on
near-black in the dark theme. The pairing pass (:mod:`pydmconverter.pairing`) makes the
two flip together. These tests pin that on the vendored scheme and check the invariant
over every ``.bob`` fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.pairing import MIN_CONTRAST, TRANSPARENT, contrast
from pydmconverter.react import convert_bytes
from pydmconverter.scheme import load_scheme

FIXTURES = Path(__file__).parent / "fixtures"
_SCHEME = load_scheme(None)
_DARK = dict(zip(_SCHEME.flat["roles"], _SCHEME.flat["dark"]))
_TEXT_TYPES = {"text-label", "pv-label", "group-box"}


def _wire(body: str, background: str = "") -> dict:
    data = f'<?xml version="1.0"?>\n<display version="2.0.0"><name>t</name>{background}{body}</display>'.encode()
    return to_wire_dict(convert_bytes(data, kind="bob", scheme=_SCHEME))


def _role(role: str, fallback: str) -> dict:
    return {"$role": role, "fallback": fallback}


def _is_role(value) -> bool:
    return isinstance(value, dict) and "$role" in value


def _dark(value) -> str:
    return _DARK.get(value["$role"], value["fallback"]) if _is_role(value) else value


def _paint(node: dict):
    props = node.get("props", {})
    for key in ("fillColor", "backgroundColor"):
        value = props.get(key)
        if value is None or (key == "fillColor" and not props.get("fill")):
            continue
        if _is_role(value) and value["$role"] == "Transparent":
            continue
        if isinstance(value, str) and len(value) == 9 and value.endswith("00"):
            continue
        return value
    return None


def _unreadable(wire: dict) -> list[str]:
    """Text whose colour and ground do not flip together and cannot be read in the dark theme."""
    painted: list[tuple[tuple[float, float, float, float], object]] = []
    bad: list[str] = []

    def visit(node: dict) -> None:
        g = node.get("geometry", {})
        box = (g.get("x", 0), g.get("y", 0), g.get("width", 0), g.get("height", 0))
        fg = node.get("props", {}).get("foregroundColor")
        if node["type"] in _TEXT_TYPES and fg is not None:
            ground = _paint(node)
            if ground is None:
                cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
                ground = wire["root"]["props"].get("backgroundColor")
                for (x, y, w, h), value in reversed(painted):
                    if x <= cx <= x + w and y <= cy <= y + h:
                        ground = value
                        break
            if ground is not None and _is_role(fg) != _is_role(ground):
                ratio = contrast(_dark(fg), _dark(ground))
                if ratio is not None and ratio < MIN_CONTRAST:
                    bad.append(f"{node['id']}: {fg} on {ground}")
        if _paint(node) is not None:
            painted.append((box, _paint(node)))
        for child in node.get("children", []):
            visit(child)

    for child in wire["root"].get("children", []):
        visit(child)
    return bad


_LABEL = '<widget type="label" version="2.0.0"><name>L</name><text>a</text><x>10</x><y>10</y></widget>'
_TEXTUPDATE = (
    '<widget type="textupdate" version="2.0.0"><name>T</name><pv_name>sim://x</pv_name><x>10</x><y>40</y></widget>'
)


def test_default_label_text_on_the_default_background_is_the_text_role():
    # The AR acceptance repro (rfeps Overview.bob): 44 of 44 default labels were literal black.
    wire = _wire(_LABEL * 3)
    assert wire["root"]["props"]["backgroundColor"] == _role("Display_Background", "#ffffff")
    assert [c["props"]["foregroundColor"] for c in wire["root"]["children"]] == [_role("Text", "#000000")] * 3
    notes = [w for w in wire["root"]["children"][0].get("warnings", []) if w.startswith(("parity: ", "pair: "))]
    assert not any("'Text'" in n and n.startswith("parity: ") for n in notes)
    assert any(n.startswith("pair: color 'Text'") for n in notes)


def test_textupdate_default_text_and_background_are_a_role_pair():
    (node,) = _wire(_TEXTUPDATE)["root"]["children"]
    assert node["props"]["foregroundColor"] == _role("Text", "#000000")
    assert node["props"]["backgroundColor"] == _role("Read_Background", "#f0f0f0")


def test_default_text_on_a_literal_declared_background_stays_literal():
    background = '<background_color><color red="200" green="200" blue="200"/></background_color>'
    wire = _wire(_LABEL, background)
    assert wire["root"]["props"]["backgroundColor"] == "#c8c8c8"
    assert wire["root"]["children"][0]["props"]["foregroundColor"] == "#000000"


def test_authored_literal_black_text_keeps_the_display_background_literal():
    authored = (
        '<widget type="label" version="2.0.0"><name>A</name><text>a</text><x>100</x>'
        '<foreground_color><color red="0" green="0" blue="0"/></foreground_color></widget>'
    )
    wire = _wire(_LABEL + authored)
    assert wire["root"]["props"]["backgroundColor"] == "#ffffff"
    assert [c["props"]["foregroundColor"] for c in wire["root"]["children"]] == ["#000000", "#000000"]


def test_default_text_on_a_literal_light_rectangle_stays_literal():
    panel = (
        '<widget type="rectangle" version="2.0.0"><name>P</name><x>0</x><y>0</y><width>200</width>'
        '<height>100</height><background_color><color red="230" green="230" blue="230"/></background_color></widget>'
    )
    wire = _wire(panel + _LABEL)
    assert wire["root"]["children"][1]["props"]["foregroundColor"] == "#000000"
    assert wire["root"]["props"]["backgroundColor"] == _role("Display_Background", "#ffffff")


def test_transparent_textupdate_gets_a_transparent_background():
    body = (
        '<widget type="textupdate" version="2.0.0"><name>T</name><pv_name>sim://x</pv_name>'
        "<transparent>true</transparent></widget>"
    )
    (node,) = _wire(body)["root"]["children"]
    assert node["props"]["backgroundColor"] == TRANSPARENT
    assert node["props"]["foregroundColor"] == _role("Text", "#000000")


@pytest.mark.parametrize("name", sorted(p.stem for p in FIXTURES.glob("*.bob")))
def test_no_fixture_hides_text_in_the_dark_theme(name):
    wire = to_wire_dict(convert_bytes((FIXTURES / f"{name}.bob").read_bytes(), kind="bob", scheme=_SCHEME))
    assert _unreadable(wire) == []


def test_invariant_check_catches_the_old_output():
    # The check above is not vacuous: the pre-fix output (role canvas, literal black text) fails it.
    wire = {
        "root": {
            "props": {"backgroundColor": _role("Display_Background", "#ffffff")},
            "children": [{"id": "w-1", "type": "text-label", "props": {"foregroundColor": "#000000"}}],
        }
    }
    assert _unreadable(wire) == ["w-1: #000000 on {'$role': 'Display_Background', 'fallback': '#ffffff'}"]
