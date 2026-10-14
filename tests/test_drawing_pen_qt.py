"""Render converted rectangles, circles and arcs in PyDM, under PyDM's own stylesheet: each outline is
drawn with EDM's lineWidth, on the pixels EDM draws it on, in or out of alarm.

X draws a pen of width w centred on coordinate c over the pixels ceil(c - w/2) .. ceil(c + w/2) - 1
(EDM's XDrawRectangle and XDrawArc). PyDM antialiases, so an odd width straddles half pixels; even
widths land on whole ones. EDM's lineAlarm only recolours the line (rectangle_obj.cc, line_obj.cc)."""

import math
import re

import pytest
from pydm.utilities.stylesheet import GLOBAL_STYLESHEET
from pydm.widgets.drawing import PyDMDrawing
from qtpy import uic
from qtpy.QtGui import QColor, QImage

from pydmconverter.edm.converter import convert

LINE = "lineColor rgb 0 0 65535\nfillColor rgb 48059 48059 48059"
FILLED = f"{LINE}\nfill"
ALARM = 'alarmPv "X:ALARM"\nlineAlarm'
# name: (EDM class, properties, x, y, w, h, pen width in PyDM)
OBJECTS = {
    "default": ("activeRectangleClass", LINE, 10, 10, 60, 30, 1),
    "zero": ("activeRectangleClass", f"{LINE}\nlineWidth 0", 90, 10, 60, 30, 1),
    "two": ("activeRectangleClass", f"{LINE}\nlineWidth 2", 170, 10, 60, 30, 2),
    "four": ("activeRectangleClass", f"{LINE}\nlineWidth 4", 250, 10, 60, 30, 4),
    "filled": ("activeRectangleClass", f"{FILLED}\nlineWidth 3", 330, 10, 60, 30, 3),
    "flat": ("activeRectangleClass", f"{LINE}\nlineWidth 2", 10, 70, 60, 0, 2),
    "circle": ("activeCircleClass", f"{LINE}\nlineWidth 4", 90, 100, 60, 30, 4),
    "round": ("activeCircleClass", f"{LINE}\nlineWidth 2", 170, 150, 30, 30, 2),
    "arc": ("activeArcClass", f"{LINE}\nlineWidth 4\nstartAngle 90\ntotalAngle 180", 250, 100, 60, 30, 4),
    "pie": (
        "activeArcClass",
        f'{FILLED}\nlineWidth 2\nfillMode "pie"\nstartAngle 90\ntotalAngle 180',
        330,
        100,
        60,
        30,
        2,
    ),
    # PyDM's stylesheet sets an alarm-sensitive border's pen to 2 px at every polish; the drawing's own
    # stylesheet keeps EDM's width.
    "line_alarm": ("activeRectangleClass", f"{LINE}\nlineWidth 4\n{ALARM}", 10, 150, 60, 30, 4),
    "fill_alarm": ("activeRectangleClass", f"{FILLED}\nlineWidth 2\n{ALARM}", 250, 150, 60, 30, 2),
    "polyline_alarm": (
        "activeLineClass",
        f"lineColor rgb 0 0 65535\nlineWidth 4\n{ALARM}\nnumPoints 2\nxPoints {{\n  330\n  390\n}}\n"
        "yPoints {\n  170\n  170\n}",
        330,
        170,
        60,
        0,
        4,
    ),
}
ALARMED = ["line_alarm", "fill_alarm", "polyline_alarm"]


def screen_edl() -> str:
    edl = (
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 420\nh 200\n"
        "bgColor rgb 65535 65535 65535\nendScreenProperties\n"
    )
    for edm_class, properties, x, y, w, h, _ in OBJECTS.values():
        edl += (
            f"object {edm_class}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
            f"x {x}\ny {y}\nw {w}\nh {h}\n{properties}\nendObjectProperties\n"
        )
    return edl


@pytest.fixture
def pydm_style(qapp):
    """PyDM's default stylesheet on the application, as PyDMApplication applies it."""
    previous = qapp.styleSheet()
    with open(GLOBAL_STYLESHEET) as sheet:
        qapp.setStyleSheet(sheet.read())
    yield
    qapp.setStyleSheet(previous)


def render(top) -> QImage:
    image = QImage(top.size(), QImage.Format_ARGB32)
    image.setDevicePixelRatio(1)
    image.fill(QColor("white"))
    top.render(image)
    return image


@pytest.fixture
def screen(qtbot, pydm_style, tmp_path):
    """The converted screen shown in PyDM: its drawings by name, and the window drawn into an image."""
    (tmp_path / "screen.edl").write_text(screen_edl())
    convert(str(tmp_path / "screen.edl"), str(tmp_path / "screen.ui"))
    ui = (tmp_path / "screen.ui").read_text()
    # A local PV instead of CA, and no hide-on-disconnect rules.
    ui = re.sub(r"(<string>)X:(\w+)(</string>)", r"\1loc://\2?type=int&amp;init=0\3", ui)
    ui = re.sub(r'<property name="rules" stdset="0">\s*<string>.*?</string>\s*</property>', "", ui, flags=re.S)
    (tmp_path / "screen.ui").write_text(ui)
    top = uic.loadUi(str(tmp_path / "screen.ui"))
    qtbot.addWidget(top)
    top.resize(420, 200)
    top.show()
    qtbot.waitExposed(top)
    drawings = {}
    for widget in top.findChildren(PyDMDrawing):
        g = widget.geometry()
        (name,) = [n for n, (*_, x, y, w, h, _) in OBJECTS.items() if g.contains(x + w // 2, y + h // 2)]
        drawings[name] = widget
    assert drawings.keys() == OBJECTS.keys()
    # Yielded, so the window and its drawings live until the test is done.
    yield drawings, render(top)


def x_pixels(c: int, width: int) -> list:
    """The pixels X covers with a pen of the given width centred on c."""
    return list(range(math.ceil(c - width / 2), math.ceil(c + width / 2)))


def blue(colour: QColor) -> bool:
    """The line colour (also half covered)."""
    return colour.red() < 160


def red(colour: QColor) -> bool:
    """PyDM's MAJOR alarm colour."""
    return colour.red() > 200 and colour.blue() < 100


def line_columns(image: QImage, row: int, around: int, line=blue) -> list:
    """The columns near ``around`` in the given row that the line colours."""
    return [x for x in range(around - 6, around + 7) if line(image.pixelColor(x, row))]


def line_rows(image: QImage, column: int, around: int, line=blue) -> list:
    return [y for y in range(around - 6, around + 7) if line(image.pixelColor(column, y))]


def test_pen_is_edm_line_width(screen):
    drawings, _ = screen

    assert {name: drawings[name].penWidth for name in OBJECTS} == {name: obj[-1] for name, obj in OBJECTS.items()}


@pytest.mark.parametrize("name", ["two", "four", "circle", "round", "arc", "line_alarm", "fill_alarm"])
def test_even_pen_draws_on_edm_pixels(screen, name):
    _, image = screen
    edm_class, _, x, y, w, h, pen = OBJECTS[name]
    middle = y + h // 2

    assert line_columns(image, middle, x) == x_pixels(x, pen)
    if name != "arc":
        assert line_columns(image, middle, x + w) == x_pixels(x + w, pen)
    if edm_class == "activeRectangleClass":
        assert line_rows(image, x + w // 2, y) == x_pixels(y, pen)
        assert line_rows(image, x + w // 2, y + h) == x_pixels(y + h, pen)


def test_rectangle_with_no_height_is_a_line(screen):
    _, image = screen
    _, _, x, y, w, _, pen = OBJECTS["flat"]

    assert line_rows(image, x + w // 2, y) == x_pixels(y, pen)


@pytest.mark.parametrize("name", ["default", "zero", "filled"])
def test_odd_pen_straddles_edm_pixels(screen, name):
    """Antialiased, a pen centred on a pixel edge also half covers the pixel next to EDM's."""
    _, image = screen
    _, _, x, y, w, h, pen = OBJECTS[name]
    middle = y + h // 2

    assert line_columns(image, middle, x) == [x_pixels(x, pen)[0] - 1, *x_pixels(x, pen)]
    assert line_columns(image, middle, x + w) == [x_pixels(x + w, pen)[0] - 1, *x_pixels(x + w, pen)]


def test_alarm_recolours_the_line_at_edm_width(screen):
    """Each severity change re-polishes the drawing under PyDM's stylesheet; the line changes colour only."""
    drawings, before = screen
    top = drawings["line_alarm"].window()
    _, _, px, py, pw, _, _ = OBJECTS["polyline_alarm"]
    polyline_rows = line_rows(before, px + pw // 2, py)

    for severity, line in ((2, red), (0, blue)):
        for name in ALARMED:
            drawings[name].alarm_severity_changed(severity)
        image = render(top)

        assert {name: drawings[name].penWidth for name in ALARMED} == {name: OBJECTS[name][-1] for name in ALARMED}
        for name in ("line_alarm", "fill_alarm"):
            _, _, x, y, w, h, pen = OBJECTS[name]
            assert line_columns(image, y + h // 2, x, line) == x_pixels(x, pen)
            assert line_rows(image, x + w // 2, y + h, line) == x_pixels(y + h, pen)
        assert line_rows(image, px + pw // 2, py, line) == polyline_rows
    assert len(polyline_rows) == OBJECTS["polyline_alarm"][-1]
