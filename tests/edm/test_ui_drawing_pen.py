"""The pen a rectangle, circle or arc is drawn with in the .ui
(converter_helpers.apply_widget_post_processing).

EDM draws the outline lineWidth wide, 1 by default, with width 0 being X11's
thinnest line, also one pixel (rectangle_obj.cc, circle_obj.cc, arc_obj.cc). It
centres the pen on the object's rect (XDrawRectangle, XDrawArc), while PyDM
insets the shape by the pen width (PyDMDrawing.get_bounds), so the widget
reaches past the rect by the pen on every side.
"""

import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert

HEADER = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 200
h 100
endScreenProperties
"""
LINE = "lineColor rgb 0 0 65535"
FILL = "fill\nfillColor rgb 48059 48059 48059"
BAR = 'indicatorPv "X:BAR"\nfgColor rgb 0 0 65535\nbgColor rgb 48059 48059 48059\nindicatorColor rgb 0 65535 0'


def convert_object(tmp_path, edm_class: str, body: str, w: int = 50, h: int = 30, minor: int = 0) -> ET.Element:
    """The one widget the converter writes for a single EDM object at (20, 20)."""
    edl = tmp_path / "screen.edl"
    edl.write_text(
        HEADER + f"object {edm_class}\nbeginObjectProperties\nmajor 4\nminor {minor}\nrelease 0\n"
        f"x 20\ny 20\nw {w}\nh {h}\n{body}\nendObjectProperties\n"
    )
    convert(str(edl), str(tmp_path / "screen.ui"))
    (widget,) = ET.parse(tmp_path / "screen.ui").getroot().find(".//widget[@name='centralwidget']").findall("widget")
    return widget


def pen_width(widget: ET.Element):
    element = widget.find("property[@name='penWidth']/double")
    return None if element is None else float(element.text)


def geometry(widget: ET.Element) -> tuple:
    rect = widget.find("property[@name='geometry']/rect")
    return tuple(int(rect.findtext(part)) for part in ("x", "y", "width", "height"))


@pytest.mark.parametrize(
    "edm_class, body, w, h, widget_class, pen, rect",
    [
        pytest.param("activeRectangleClass", LINE, 50, 30, "PyDMDrawingRectangle", 1, (19, 19, 52, 32), id="default"),
        pytest.param(
            "activeRectangleClass", f"{LINE}\nlineWidth 0", 50, 30, "PyDMDrawingRectangle", 1, (19, 19, 52, 32), id="0"
        ),
        pytest.param(
            "activeRectangleClass", f"{LINE}\nlineWidth 4", 50, 30, "PyDMDrawingRectangle", 4, (16, 16, 58, 38), id="4"
        ),
        pytest.param(
            "activeRectangleClass",
            f"{LINE}\nlineWidth 3\n{FILL}",
            50,
            30,
            "PyDMDrawingRectangle",
            3,
            (17, 17, 56, 36),
            id="filled",
        ),
        # X draws a rectangle with no height as a line lineWidth thick.
        pytest.param(
            "activeRectangleClass", f"{LINE}\nlineWidth 2", 50, 0, "PyDMDrawingRectangle", 2, (18, 18, 54, 4), id="h 0"
        ),
        pytest.param("activeCircleClass", f"{LINE}\nlineWidth 2", 50, 30, "PyDMDrawingEllipse", 2, (18, 18, 54, 34)),
        pytest.param(
            "activeArcClass",
            f"{LINE}\nlineWidth 3\nstartAngle 90\ntotalAngle 180",
            50,
            30,
            "PyDMDrawingArc",
            3,
            (17, 17, 56, 36),
            id="arc",
        ),
        pytest.param(
            "activeArcClass",
            f'{LINE}\nlineWidth 2\n{FILL}\nfillMode "pie"\nstartAngle 0\ntotalAngle 270',
            50,
            30,
            "PyDMDrawingPie",
            2,
            (18, 18, 54, 34),
            id="pie",
        ),
        # With no pen style written PyDM draws no outline, and insets nothing.
        pytest.param("activeRectangleClass", FILL, 50, 30, "PyDMDrawingRectangle", 1, (20, 20, 50, 30), id="no line"),
    ],
)
def test_closed_drawing_pen_is_edm_line_width_on_its_rect(tmp_path, edm_class, body, w, h, widget_class, pen, rect):
    widget = convert_object(tmp_path, edm_class, body, w, h)

    assert widget.get("class") == widget_class
    assert pen_width(widget) == pen
    assert geometry(widget) == rect


@pytest.mark.parametrize("edm_class", ["activeBarClass", "activeSlacBarClass"])
def test_bar_rectangle_keeps_its_rect(tmp_path, edm_class):
    """A bar has no lineWidth (bar.cc draws with width 1) and its rectangle no outline."""
    widget = convert_object(tmp_path, edm_class, BAR, minor=1)

    assert widget.get("class") == "PyDMDrawingRectangle"
    assert pen_width(widget) is None
    assert geometry(widget) == (20, 20, 50, 30)


POINTS = "numPoints 3\nxPoints {\n  20\n  70\n  70\n}\nyPoints {\n  20\n  20\n  50\n}"
POLYGON = "numPoints 4\nxPoints {\n  20\n  70\n  45\n  20\n}\nyPoints {\n  20\n  20\n  50\n  20\n}"


@pytest.mark.parametrize(
    "edm_class, body, sheet",
    [
        pytest.param("activeRectangleClass", f"{LINE}\nlineWidth 4", "background-color: transparent;", id="rectangle"),
        pytest.param("activeRectangleClass", f"{LINE}\nlineWidth 3\n{FILL}", None, id="filled rectangle"),
        pytest.param("activeCircleClass", f"{LINE}\nlineWidth 4", "background-color: transparent;", id="circle"),
        pytest.param(
            "activeCircleClass", f"{LINE}\nlineWidth 2\n{FILL}", "background-color: transparent;", id="filled circle"
        ),
        pytest.param(
            "activeArcClass",
            f"{LINE}\nlineWidth 3\nstartAngle 90\ntotalAngle 180",
            "background-color: transparent;",
            id="arc",
        ),
        pytest.param(
            "activeArcClass",
            f'{LINE}\nlineWidth 2\n{FILL}\nfillMode "pie"\nstartAngle 0\ntotalAngle 270',
            "background-color: transparent;",
            id="pie",
        ),
        pytest.param("activeLineClass", f"{LINE}\nlineWidth 3\n{POINTS}", "background-color: transparent;", id="line"),
        pytest.param(
            "activeLineClass",
            f'{LINE}\nlineWidth 2\narrows "both"\n{POINTS}',
            "background-color: transparent;",
            id="arrows",
        ),
        pytest.param(
            "activeLineClass",
            f"{LINE}\nlineWidth 2\n{FILL}\nclosePolygon\n{POLYGON}",
            "background-color: transparent;",
            id="polygon",
        ),
    ],
)
@pytest.mark.parametrize("line_alarm", [False, True])
def test_drawing_has_one_style_sheet_with_its_alarm_pen_width(tmp_path, edm_class, body, sheet, line_alarm):
    """PyDM's stylesheet sets an alarm-sensitive border's pen to 2 px at every polish, while EDM's lineAlarm
    only recolours the line: the drawing's own stylesheet, applied after PyDM's, keeps EDM's width. uic
    applies only the last styleSheet property, so there is one."""
    if line_alarm:
        body += '\nalarmPv "X:STAT"\nlineAlarm'
    widget = convert_object(tmp_path, edm_class, body)
    sheets = [prop.findtext("string") for prop in widget.findall("property[@name='styleSheet']")]
    pen = f"qproperty-penWidth: {pen_width(widget):g};"
    expected = [part for part in (sheet, pen if line_alarm else None) if part]

    assert sheets == ([" ".join(expected)] if expected else [])
