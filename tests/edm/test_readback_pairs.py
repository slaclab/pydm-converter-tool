"""EDM readbacks: no units unless the object asks, and a background that matches the text it carries.

From the AR magnet screens (MML2EDM, ``activeXTextDspClass:noedit`` with ``useDisplayBg``):
the converted ``pv-label`` had a literal black foreground and no background, so a viewer
drew its own dark readback field under black text, and showed units EDM never shows.
"""

from __future__ import annotations

from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.edm.parser import EDMObject
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.pairing import TRANSPARENT
from pydmconverter.scheme import load_scheme

COLORS = Path(__file__).parent / "fixtures" / "colors.list"

_SCREEN = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 400
h 200
font "helvetica-medium-r-14.0"
bgColor rgb 48059 48059 48059
endScreenProperties

"""


def _object(cls: str, y: int, *props: str) -> str:
    body = "\n".join(props)
    return (
        f"object {cls}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x 10\ny {y}\nw 63\nh 20\n{body}\nendObjectProperties\n\n"
    )


_MONITOR = _object(
    "activeXTextDspClass:noedit",
    10,
    'controlPv "AR01:QF1:Monitor"',
    "fgColor rgb 0 0 0",
    "bgColor rgb 65535 65535 65535",
    "useDisplayBg",
    "precision 3",
)
_MONITOR_UNITS = _object(
    "activeXTextDspClass:noedit", 40, 'controlPv "AR01:QF1:Setpoint"', "fgColor rgb 0 0 0", "useDisplayBg", "showUnits"
)
_FILLED = _object(
    "activeXTextDspClass:noedit",
    70,
    'controlPv "AR01:QF1:Voltage"',
    "fgColor rgb 0 0 0",
    "bgColor rgb 52428 52428 52428",
)
_TEXTUPDATE = _object("TextupdateClass", 100, 'controlPv "AR01:QF1:Leakage"', "fgColor rgb 0 0 0")
_TEXTUPDATE_FILLED = _object(
    "TextupdateClass", 130, 'controlPv "AR01:QF1:Leak2"', "fgColor rgb 0 0 0", "bgColor rgb 65535 65535 0", "fill"
)


def _wire(tmp_path: Path, body: str, scheme=None) -> dict:
    path = tmp_path / "mag.edl"
    path.write_text(_SCREEN + body, encoding="utf-8")
    return to_wire_dict(edm_file_to_ir(path, color_list_path=COLORS, scheme=scheme))


def _labels(wire: dict) -> list[dict]:
    return [c for c in wire["root"]["children"] if c["type"] == "pv-label"]


def test_readbacks_show_no_units_unless_the_object_asks(tmp_path: Path):
    labels = _labels(_wire(tmp_path, _MONITOR + _MONITOR_UNITS + _FILLED + _TEXTUPDATE))
    assert [label["props"]["showUnits"] for label in labels] == [False, True, False, False]


def test_a_readback_that_shows_the_display_through_says_so(tmp_path: Path):
    for scheme in (None, load_scheme(None)):
        monitor, textupdate = _labels(_wire(tmp_path, _MONITOR + _TEXTUPDATE, scheme))
        for label in (monitor, textupdate):
            assert label["props"]["foregroundColor"] == "#000000"
            assert label["props"]["backgroundColor"] == TRANSPARENT


def test_a_filled_readback_keeps_its_own_background_beside_its_text(tmp_path: Path):
    filled, textupdate = _labels(_wire(tmp_path, _FILLED + _TEXTUPDATE_FILLED))
    assert (filled["props"]["foregroundColor"], filled["props"]["backgroundColor"]) == ("#000000", "#cccccc")
    assert (textupdate["props"]["foregroundColor"], textupdate["props"]["backgroundColor"]) == ("#000000", "#ffff00")


def test_no_readback_is_left_with_a_foreground_alone(tmp_path: Path):
    body = _MONITOR + _MONITOR_UNITS + _FILLED + _TEXTUPDATE + _TEXTUPDATE_FILLED
    for label in _labels(_wire(tmp_path, body, load_scheme(None))):
        assert "foregroundColor" in label["props"] and "backgroundColor" in label["props"], label["id"]


def test_object_without_pv_class_is_unaffected():
    # Static xText becomes a text-label: it takes no showUnits.
    from pydmconverter.edm.ir_adapter import _object_to_source

    obj = EDMObject.__new__(EDMObject)
    obj.name, obj.properties = "activeXTextClass", {"value": ["hi"], "fgColor": "rgb 0 0 0"}
    obj.x, obj.y, obj.width, obj.height = 0, 0, 10, 10
    assert "showUnits" not in _object_to_source(obj).qt_props
