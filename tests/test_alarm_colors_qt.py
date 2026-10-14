"""Render a converted screen in PyDM, under PyDM's own stylesheet, at forced alarm severities: a widget
takes PyDM's alarm colour only where its EDM alarm flags say, and keeps its own colours otherwise and at
NO_ALARM."""

import re
from collections import Counter

import pytest
from pydm.utilities.stylesheet import GLOBAL_STYLESHEET
from pydm.widgets import PyDMLabel as QtPyDMLabel
from pydm.widgets.base import PyDMWidget
from qtpy import uic
from qtpy.QtGui import QColor, QImage, QPalette
from qtpy.QtWidgets import QWidget

from pydmconverter.edm.converter import convert

BLUE, GREY, RED = "#0000ff", "#bbbbbb", "#ff0000"
# PyDM's default stylesheet colours, by alarm severity.
ALARM_COLORS = {1: "#ebeb00", 2: RED, 3: "#eb00eb", 4: "#ffffff"}
PARSE_ERROR = "Could not parse stylesheet"
NO_ALARM, MAJOR = 0, 2

COLORS = "fgColor rgb 0 0 65535\nbgColor rgb 48059 48059 48059"
BUTTON = 'controlPv "X:{pv}"\nfgColor rgb 0 0 65535\nonColor rgb 48059 48059 48059\noffColor rgb 48059 48059 48059\n'
BUTTON += 'onLabel "Go"\noffLabel "Go"\nlabelType "literal"'
DRAWING = 'alarmPv "X:{pv}"\nlineColor rgb 0 0 65535\nfill\nfillColor rgb 48059 48059 48059'
# (row, EDM class, version, properties)
OBJECTS = {
    "label": (10, "activeXTextDspClass:noedit", 7, f'controlPv "X:LABEL"\n{COLORS}\nfgAlarm'),
    "plain_label": (50, "activeXTextDspClass:noedit", 7, f'controlPv "X:PLAIN_LABEL"\n{COLORS}'),
    "static_text": (90, "activeXTextClass", 1, f'alarmPv "X:STATIC"\n{COLORS}\nfgAlarm\nvalue {{\n  "Status"\n}}'),
    "button": (130, "activeButtonClass", 0, BUTTON.format(pv="BUTTON") + "\nfgAlarm"),
    "plain_button": (170, "activeButtonClass", 0, BUTTON.format(pv="PLAIN_BUTTON")),
    "fill_alarm": (210, "activeRectangleClass", 0, DRAWING.format(pv="FILL") + "\nfillAlarm"),
    "line_alarm": (250, "activeRectangleClass", 0, DRAWING.format(pv="LINE") + "\nlineAlarm"),
    "no_flag": (290, "activeRectangleClass", 0, DRAWING.format(pv="NO_FLAG")),
    # A drawing with a stylesheet of its own.
    "circle": (330, "activeCircleClass", 0, DRAWING.format(pv="CIRCLE") + "\nfillAlarm"),
}


def screen_edl() -> str:
    edl = "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 300\nh 370\nendScreenProperties\n"
    for row, edm_class, minor, properties in OBJECTS.values():
        edl += (
            f"object {edm_class}\nbeginObjectProperties\nmajor 4\nminor {minor}\nrelease 0\n"
            f'x 10\ny {row}\nw 140\nh 30\nfont "helvetica-bold-r-18.0"\n{properties}\nendObjectProperties\n'
        )
    return edl


@pytest.fixture
def pydm_style(qapp):
    """PyDM's default stylesheet on the application, as PyDMApplication applies it (read from its file, so
    neither PYDM_STYLESHEET nor PyDM's cache of it changes what the tests see)."""
    previous = qapp.styleSheet()
    with open(GLOBAL_STYLESHEET) as sheet:
        qapp.setStyleSheet(sheet.read())
    yield
    qapp.setStyleSheet(previous)


@pytest.fixture
def screen(qtbot, pydm_style, tmp_path):
    """The converted screen loaded in PyDM: its widgets by name, and the window."""
    (tmp_path / "screen.edl").write_text(screen_edl())
    convert(str(tmp_path / "screen.edl"), str(tmp_path / "screen.ui"))
    ui = (tmp_path / "screen.ui").read_text()
    # Local PVs instead of CA, and no hide-on-disconnect rules.
    ui = re.sub(r"(<string>)X:(\w+)(</string>)", r"\1loc://\2?type=int&amp;init=0\3", ui)
    ui = re.sub(r'<property name="rules" stdset="0">\s*<string>.*?</string>\s*</property>', "", ui, flags=re.S)
    (tmp_path / "screen.ui").write_text(ui)
    top = uic.loadUi(str(tmp_path / "screen.ui"))
    qtbot.addWidget(top)
    top.resize(300, 370)
    rows = {row: name for name, (row, *_) in OBJECTS.items()}
    widgets = {rows[w.geometry().y()]: w for w in top.findChildren(PyDMWidget) if w.geometry().y() in rows}
    assert widgets.keys() == OBJECTS.keys()
    return widgets, top


def force_severity(widgets: dict, severity: int) -> None:
    for widget in widgets.values():
        widget.alarmSeverityChanged(severity)


def text_color(widget) -> str:
    return widget.palette().color(widget.foregroundRole()).name()


def face_color(widget) -> str:
    return widget.palette().color(QPalette.Button).name()


def hue(color: QColor) -> str:
    """Red, blue or other: antialiased glyphs hold few pixels of the exact text colour, and the fonts differ
    between platforms."""
    r, g, b = color.red(), color.green(), color.blue()
    if r > 200 and g < 80 and b < 80:
        return "red"
    if b > 200 and r < 80 and g < 80:
        return "blue"
    return "other"


def hues(top: QWidget, widget: QWidget) -> Counter:
    """The hues of the widget's pixels, rendered in place in the window."""
    image = QImage(top.size(), QImage.Format_ARGB32)
    image.setDevicePixelRatio(1)
    image.fill(QColor("black"))
    top.render(image)
    g = widget.geometry()
    return Counter(
        hue(image.pixelColor(x, y)) for x in range(g.left(), g.right() + 1) for y in range(g.top(), g.bottom() + 1)
    )


def colours(widgets: dict) -> dict:
    return {
        "label": text_color(widgets["label"]),
        "plain_label": text_color(widgets["plain_label"]),
        "static_text": text_color(widgets["static_text"]),
        "button": face_color(widgets["button"]),
        "plain_button": face_color(widgets["plain_button"]),
        **{
            name: (widgets[name].brush.color().name(), widgets[name].penColor.name())
            for name in ("fill_alarm", "line_alarm", "no_flag", "circle")
        },
    }


STATIC_COLOURS = {
    "label": BLUE,
    "plain_label": BLUE,
    "static_text": BLUE,
    "button": GREY,
    "plain_button": GREY,
    "fill_alarm": (GREY, BLUE),
    "line_alarm": (GREY, BLUE),
    "no_flag": (GREY, BLUE),
    "circle": (GREY, BLUE),
}


def test_major_alarm_colours_what_the_flags_select(screen, qtlog):
    widgets, top = screen

    force_severity(widgets, MAJOR)

    assert not [record.message for record in qtlog.records if PARSE_ERROR in record.message]
    assert colours(widgets) == {
        **STATIC_COLOURS,
        "label": RED,
        "static_text": RED,
        "button": RED,
        "fill_alarm": (RED, BLUE),
        "line_alarm": (GREY, RED),
        "circle": (RED, BLUE),
    }
    assert widgets["static_text"].text() == "Status"
    text = hues(top, widgets["static_text"])
    assert text["red"] > 0
    assert text["blue"] == 0


@pytest.mark.parametrize("severity", [1, 3, 4], ids=["minor", "invalid", "disconnected"])
def test_text_takes_each_pydm_alarm_colour(screen, severity):
    widgets, _ = screen

    force_severity(widgets, severity)

    assert text_color(widgets["label"]) == ALARM_COLORS[severity]
    assert text_color(widgets["plain_label"]) == BLUE


def test_no_alarm_shows_the_static_colours(screen, qtlog):
    widgets, top = screen

    force_severity(widgets, NO_ALARM)
    before = hues(top, widgets["static_text"])
    force_severity(widgets, MAJOR)
    force_severity(widgets, NO_ALARM)

    assert not [record.message for record in qtlog.records if PARSE_ERROR in record.message]
    assert colours(widgets) == STATIC_COLOURS
    assert hues(top, widgets["static_text"]) == before
    assert before["blue"] > 0
    assert before["red"] == 0


def test_plain_style_sheet_hides_pydm_alarm_colour(qtbot, pydm_style):
    # The cause of the bug: a widget's own declarations beat the application's [alarmSeverity] selectors.
    label = QtPyDMLabel(init_channel="loc://X_PLAIN?type=int&init=0")
    qtbot.addWidget(label)
    label.setStyleSheet(f"background-color: {GREY}; color: {BLUE};")
    label.alarmSensitiveContent = True
    label.alarmSeverityChanged(MAJOR)

    assert text_color(label) == BLUE
