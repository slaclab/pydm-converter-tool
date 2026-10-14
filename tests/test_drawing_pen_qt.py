"""Render converted rectangles, circles and arcs in PyDM, under PyDM's own stylesheet: each outline is
drawn with EDM's lineWidth, on the pixels EDM draws it on.

X draws a pen of width w centred on coordinate c over the pixels ceil(c - w/2) .. ceil(c + w/2) - 1
(EDM's XDrawRectangle and XDrawArc). PyDM antialiases, so an odd width straddles half pixels; even
widths land on whole ones."""

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
    # PyDM's alarm border is 2 px whatever the .ui says: its stylesheet sets the pen width at every polish.
    "line_alarm": ("activeRectangleClass", f'{LINE}\nlineWidth 4\nalarmPv "X:ALARM"\nlineAlarm', 10, 150, 60, 30, 2),
}


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
    image = QImage(top.size(), QImage.Format_ARGB32)
    image.setDevicePixelRatio(1)
    image.fill(QColor("white"))
    top.render(image)
    drawings = {}
    for widget in top.findChildren(PyDMDrawing):
        g = widget.geometry()
        (name,) = [n for n, (*_, x, y, w, h, _) in OBJECTS.items() if g.contains(x + w // 2, y + h // 2)]
        drawings[name] = widget
    assert drawings.keys() == OBJECTS.keys()
    return drawings, image


def x_pixels(c: int, width: int) -> list:
    """The pixels X covers with a pen of the given width centred on c."""
    return list(range(math.ceil(c - width / 2), math.ceil(c + width / 2)))


def blue_columns(image: QImage, row: int, around: int) -> list:
    """The columns near ``around`` in the given row that the blue line colours (also half covered)."""
    return [x for x in range(around - 6, around + 7) if image.pixelColor(x, row).red() < 160]


def blue_rows(image: QImage, column: int, around: int) -> list:
    return [y for y in range(around - 6, around + 7) if image.pixelColor(column, y).red() < 160]


def test_pen_is_edm_line_width(screen):
    drawings, _ = screen

    assert {name: drawings[name].penWidth for name in OBJECTS} == {name: obj[-1] for name, obj in OBJECTS.items()}


@pytest.mark.parametrize("name", ["two", "four", "circle", "round", "arc"])
def test_even_pen_draws_on_edm_pixels(screen, name):
    _, image = screen
    _, _, x, y, w, h, pen = OBJECTS[name]
    middle = y + h // 2

    assert blue_columns(image, middle, x) == x_pixels(x, pen)
    if name != "arc":
        assert blue_columns(image, middle, x + w) == x_pixels(x + w, pen)
    if name in ("two", "four"):
        assert blue_rows(image, x + w // 2, y) == x_pixels(y, pen)
        assert blue_rows(image, x + w // 2, y + h) == x_pixels(y + h, pen)


def test_rectangle_with_no_height_is_a_line(screen):
    _, image = screen
    _, _, x, y, w, _, pen = OBJECTS["flat"]

    assert blue_rows(image, x + w // 2, y) == x_pixels(y, pen)


@pytest.mark.parametrize("name", ["default", "zero", "filled"])
def test_odd_pen_straddles_edm_pixels(screen, name):
    """Antialiased, a pen centred on a pixel edge also half covers the pixel next to EDM's."""
    _, image = screen
    _, _, x, y, w, h, pen = OBJECTS[name]
    middle = y + h // 2

    assert blue_columns(image, middle, x) == [x_pixels(x, pen)[0] - 1, *x_pixels(x, pen)]
    assert blue_columns(image, middle, x + w) == [x_pixels(x + w, pen)[0] - 1, *x_pixels(x + w, pen)]
