"""Render converted rectangles, circles, arcs and lines in PyDM, under PyDM's own stylesheet: each
outline is drawn with EDM's lineWidth, on the pixels EDM draws it on, in or out of alarm. A lineAlarm
polygon's widget holds its whole stroke, in or out of alarm.

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


def show_converted(qtbot, tmp_path, edl: str, width: int, height: int):
    """The .edl converted and shown in PyDM."""
    (tmp_path / "screen.edl").write_text(edl)
    convert(str(tmp_path / "screen.edl"), str(tmp_path / "screen.ui"))
    ui = (tmp_path / "screen.ui").read_text()
    # A local PV instead of CA, and no hide-on-disconnect rules.
    ui = re.sub(r"(<string>)X:(\w+)(</string>)", r"\1loc://\2?type=int&amp;init=0\3", ui)
    ui = re.sub(r'<property name="rules" stdset="0">\s*<string>.*?</string>\s*</property>', "", ui, flags=re.S)
    (tmp_path / "screen.ui").write_text(ui)
    top = uic.loadUi(str(tmp_path / "screen.ui"))
    qtbot.addWidget(top)
    top.resize(width, height)
    top.show()
    qtbot.waitExposed(top)
    return top


@pytest.fixture
def screen(qtbot, pydm_style, tmp_path):
    """The converted screen shown in PyDM: its drawings by name, and the window drawn into an image."""
    top = show_converted(qtbot, tmp_path, screen_edl(), 420, 200)
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
    """PyDM's MAJOR alarm colour (also half covered)."""
    return colour.red() > 200 and colour.green() < 160 and colour.blue() < 160


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
    assert polyline_rows == x_pixels(py, OBJECTS["polyline_alarm"][-1])


# Closed, filled lines under lineAlarm, which PyDM draws as irregular polygons: points and pen.
POLYGONS = {
    "triangle": ([(10, 10), (70, 10), (40, 50)], 2),
    "flat": ([(90, 10), (150, 10), (120, 11)], 2),
    "small": ([(170, 10), (174, 10), (172, 14)], 6),
    "wide pen": ([(200, 10), (212, 10), (206, 22)], 6),
}


def polygon_edl() -> str:
    edl = (
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 240\nh 60\n"
        "bgColor rgb 65535 65535 65535\nendScreenProperties\n"
    )
    for points, pen in POLYGONS.values():
        xs, ys = zip(*points, points[0])
        x_block = "".join(f"  {x}\n" for x in xs)
        y_block = "".join(f"  {y}\n" for y in ys)
        edl += (
            f"object activeLineClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 1\n"
            f"x {min(xs)}\ny {min(ys)}\nw {max(xs) - min(xs)}\nh {max(ys) - min(ys)}\n"
            f"{FILLED}\nclosePolygon\nlineWidth {pen}\n{ALARM}\nnumPoints {len(xs)}\n"
            f"xPoints {{\n{x_block}}}\nyPoints {{\n{y_block}}}\nendObjectProperties\n"
        )
    return edl


def test_alarm_polygon_widget_holds_its_whole_stroke(qtbot, pydm_style, tmp_path):
    """PyDM draws a polygon's points at the same place whatever its widget's size, so growing every
    widget shows any stroke the widget clips. None is clipped, in or out of alarm."""
    top = show_converted(qtbot, tmp_path, polygon_edl(), 240, 60)
    polygons = top.findChildren(PyDMDrawing)
    assert {type(polygon).__name__ for polygon in polygons} == {"PyDMDrawingIrregularPolygon"}
    assert len(polygons) == len(POLYGONS)

    def unclipped() -> QImage:
        for polygon in polygons:
            polygon.resize(polygon.width() + 20, polygon.height() + 20)
        image = render(top)
        for polygon in polygons:
            polygon.resize(polygon.width() - 20, polygon.height() - 20)
        return image

    images = []
    for severity in (0, 2):
        for polygon in polygons:
            polygon.alarm_severity_changed(severity)
        images.append(render(top))

        assert images[-1] == unclipped()
        assert sorted(polygon.penWidth for polygon in polygons) == sorted(pen for _, pen in POLYGONS.values())
    assert images[0] != images[1]


# activeLineClass drawings, one 40 x 30 box per pen (EDM's lineWidth; None writes none, which is 1):
# open ones are polylines with a top and a right edge, closed and filled ones irregular polygons.
# name: (kind, x, y, lineWidth)
BOX_W, BOX_H = 40, 30
LINE_PENS = (None, 0, 1, 2, 3, 4, 5)
LINES = {
    **{f"polyline {pen}": ("polyline", 10 + 60 * i, 20, pen) for i, pen in enumerate(LINE_PENS)},
    **{f"polygon {pen}": ("polygon", 10 + 60 * i, 80, pen) for i, pen in enumerate(LINE_PENS)},
    # Arrowheads grow the widget by their size on every side.
    "arrows 2": ("arrows", 30, 150, 2),
    "arrows 3": ("arrows", 130, 150, 3),
}


def lines_edl() -> str:
    edl = (
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 430\nh 210\n"
        "bgColor rgb 65535 65535 65535\nendScreenProperties\n"
    )
    for kind, x, y, pen in LINES.values():
        points = [(x, y), (x + BOX_W, y), (x + BOX_W, y + BOX_H)]
        properties = LINE
        if kind == "polygon":
            points += [(x, y + BOX_H), (x, y)]
            properties = f"{FILLED}\nclosePolygon"
        elif kind == "arrows":
            properties = f'{LINE}\narrows "both"'
        if pen is not None:
            properties += f"\nlineWidth {pen}"
        xs, ys = zip(*points)
        x_block = "".join(f"  {i} {x}\n" for i, x in enumerate(xs))
        y_block = "".join(f"  {i} {y}\n" for i, y in enumerate(ys))
        edl += (
            f"object activeLineClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 1\n"
            f"x {min(xs)}\ny {min(ys)}\nw {max(xs) - min(xs)}\nh {max(ys) - min(ys)}\n"
            f"{properties}\n{ALARM}\nnumPoints {len(xs)}\n"
            f"xPoints {{\n{x_block}}}\nyPoints {{\n{y_block}}}\nendObjectProperties\n"
        )
    return edl


def line_pixels(c: int, pen, first: bool = False) -> list:
    """The pixels PyDM covers drawing an EDM line edge at c: X's, and for an odd width the half
    covered pixel before them. Width 0 is X's thin line, on pixel c; PyDM draws it with a 1 px
    cosmetic pen and no border, so the widget starts at the first point and clips that half pixel
    off the first (top or left) edge."""
    if pen and pen % 2 == 0:
        return x_pixels(c, pen)
    pixels = x_pixels(c, pen or 1)
    return pixels if pen == 0 and first else [pixels[0] - 1, *pixels]


def test_line_edges_draw_on_edm_pixels(qtbot, pydm_style, tmp_path):
    """PyDM draws a polyline's or polygon's points a pen width in from its widget's corner; the
    widget starts that far before EDM's points. Alarm recolours the line in place."""
    top = show_converted(qtbot, tmp_path, lines_edl(), 430, 210)
    drawings = top.findChildren(PyDMDrawing)
    assert sorted(type(drawing).__name__ for drawing in drawings) == sorted(
        "PyDMDrawingIrregularPolygon" if kind == "polygon" else "PyDMDrawingPolyline" for kind, *_ in LINES.values()
    )

    for severity, line in ((0, blue), (2, red)):
        for drawing in drawings:
            drawing.alarm_severity_changed(severity)
        image = render(top)
        found, expected = {}, {}
        for name, (kind, x, y, pen) in LINES.items():
            # (edge, first): a polyline's top and right edges, a polygon's four.
            rows = [(y, True), (y + BOX_H, False)] if kind == "polygon" else [(y, True)]
            columns = [(x, True), (x + BOX_W, False)] if kind == "polygon" else [(x + BOX_W, False)]
            for row, first in rows:
                found[name, "row", row] = line_rows(image, x + BOX_W // 2, row, line)
                expected[name, "row", row] = line_pixels(row, pen, first)
            for column, first in columns:
                found[name, "column", column] = line_columns(image, y + BOX_H // 2, column, line)
                expected[name, "column", column] = line_pixels(column, pen, first)

        assert found == expected
