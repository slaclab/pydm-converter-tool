"""Slider orientation in .ui output: a multi-mover's comes from its numeric
orientation, as EDM reads it, and only a Qt orientation is written (#225)."""

import xml.etree.ElementTree as ET

import pytest
from pydm.widgets import PyDMSlider as QtSlider
from qtpy import uic
from qtpy.QtCore import Qt

from pydmconverter.edm.converter import convert

HEADER = """\
4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 400
h 400
endScreenProperties
"""


def edm_object(name, x, y, w, h, *lines):
    body = "\n".join(lines)
    return (
        f"object {name}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n{body}\nendObjectProperties\n"
    )


def mmv(orientation=None, orient_str=None, *lines):
    tags = [f"orientation {orientation}"] if orientation is not None else []
    if orient_str is not None:
        tags.append(f'orientStr "{orient_str}"')
    return edm_object("mmvClass", 20, 20, 20, 150, 'ctrl1Pv "DEMO:MARK_1"', *tags, *lines)


@pytest.fixture
def out(tmp_path, monkeypatch):
    # The converter logs skipped widget classes to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    return tmp_path


def convert_screen(directory, *objects):
    source = directory / "screen.edl"
    source.write_text(HEADER + "".join(objects))
    convert(str(source), str(directory / "screen.ui"))
    return directory / "screen.ui"


def orientations(ui_path):
    """The orientation enum of each slider, in document order (None if not written)."""
    root = ET.parse(ui_path).getroot()
    return [
        widget.findtext("property[@name='orientation']/enum")
        for widget in root.iter("widget")
        if widget.get("class") == "PyDMSlider"
    ]


def rects(ui_path):
    """The (x, y, width, height) of each slider, sorted."""
    root = ET.parse(ui_path).getroot()
    return sorted(
        tuple(int(widget.findtext(f"property[@name='geometry']/rect/{key}")) for key in ("x", "y", "width", "height"))
        for widget in root.iter("widget")
        if widget.get("class") == "PyDMSlider"
    )


@pytest.mark.parametrize(
    "orientation, orient_str, expected",
    [
        ("0", "HorizTop", "Qt::Horizontal"),
        ("1", "VertLeft", "Qt::Vertical"),
        ("2", "HorizBot", "Qt::Horizontal"),
        ("3", "VertRight", "Qt::Vertical"),
    ],
)
def test_multi_mover_orientation_is_a_qt_orientation(out, orientation, orient_str, expected):
    assert orientations(convert_screen(out, mmv(orientation, orient_str))) == [expected]


def test_multi_mover_follows_its_numeric_orientation(out):
    """EDM reads the number (mmover.cc createFromFile); orientStr is the editor's name for it."""
    assert orientations(convert_screen(out, mmv("1", "HorizTop"))) == ["Qt::Vertical"]


@pytest.mark.parametrize("orient_str, expected", [("VertRight", "Qt::Vertical"), ("HorizBot", "Qt::Horizontal")])
def test_multi_mover_without_orientation_reads_orient_str(out, orient_str, expected):
    assert orientations(convert_screen(out, mmv(orient_str=orient_str))) == [expected]


def test_multi_mover_without_either_is_left_horizontal(out):
    assert orientations(convert_screen(out, mmv())) == [None]


def test_every_slider_of_a_multi_mover_gets_its_orientation(out):
    ui = convert_screen(out, mmv("3", "VertRight", 'ctrl2Pv "DEMO:MARK_2"'))
    assert orientations(ui) == ["Qt::Vertical", "Qt::Vertical"]


def test_vertical_multi_mover_sliders_sit_side_by_side(out):
    """Each control keeps the mover's full height, as its marker runs the whole track in EDM."""
    ui = convert_screen(out, mmv("1", "VertLeft", 'ctrl2Pv "DEMO:MARK_2"'))
    assert rects(ui) == [(20, 20, 10, 150), (30, 20, 10, 150)]


def test_horizontal_multi_mover_sliders_stack(out):
    mover = mmv("0", "HorizTop", 'ctrl2Pv "DEMO:MARK_2"').replace("x 20\ny 20\nw 20\nh 150", "x 100\ny 20\nw 200\nh 20")
    assert rects(convert_screen(out, mover)) == [(100, 20, 200, 10), (100, 30, 200, 10)]


def test_orientation_qt_has_no_name_for_is_not_written(out):
    """EDM's plain slider doesn't read orientation (slider.cc), so it stays horizontal."""
    slider = edm_object(
        "activeSliderClass", 10, 10, 12, 336, 'controlPv "DEMO:A"', 'orientStr "VertLeft"', "orientation 1"
    )
    assert orientations(convert_screen(out, slider)) == [None]


def test_motif_slider_keeps_its_orientation(out):
    slider = edm_object("activeMotifSliderClass", 10, 10, 20, 150, 'controlPv "DEMO:A"', 'orientation "vertical"')
    assert orientations(convert_screen(out, slider)) == ["Qt::Vertical"]


def test_screen_with_vertical_multi_movers_loads_in_pydm(out, qtbot):
    ui = convert_screen(
        out,
        mmv("1", "VertLeft"),
        mmv("3", "VertRight").replace("x 20\n", "x 60\n"),
        mmv("0", "HorizTop").replace("x 20\ny 20\nw 20\nh 150", "x 100\ny 20\nw 200\nh 12"),
    )
    window = uic.loadUi(str(ui))
    qtbot.addWidget(window)
    sliders = sorted(window.findChildren(QtSlider), key=lambda slider: slider.x())
    assert [slider.orientation for slider in sliders] == [Qt.Vertical, Qt.Vertical, Qt.Horizontal]
