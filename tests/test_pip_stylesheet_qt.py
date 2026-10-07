"""Render an activePipClass embedded display in Qt: its border and colours must apply to the display, not the
embedded screen."""

import pytest
from pydm.display import Display
from pydm.widgets import PyDMEmbeddedDisplay as QtEmbeddedDisplay
from qtpy.QtGui import QColor, QImage
from qtpy.QtWidgets import QLabel, QWidget

from pydmconverter.custom_types import RGBA
from pydmconverter.widgets import PyDMEmbeddedDisplay

NAME = "activePipClass1"
WHITE, BLACK, RED, LIME = "#ffffffff", "#ff000000", "#ffff0000", "#ff00ff00"
# Probe points in window coordinates: the PIP spans (10, 10)-(159, 159) and its label's top-left corner is at
# (50, 50). Corners and edges only, so font differences between platforms can't reach them.
BACKGROUND, PIP_EDGE, LABEL_EDGE = (5, 5), (10, 80), (50, 50)
# An embedded screen smaller than the PIP covers (11, 11)-(70, 70) of it.
COVERED, UNCOVERED = (65, 65), (150, 150)
PARSE_ERROR = "Could not parse stylesheet"


def pip_style_sheet(**fields) -> str:
    """The styleSheet the converter emits for a PIP, the last one in its XML."""
    xml = PyDMEmbeddedDisplay(name=NAME, **fields).to_xml()
    return xml.findall("property[@name='styleSheet']")[-1].find("string").text


def render(top: QWidget) -> QImage:
    # A fixed devicePixelRatio of 1 keeps the probes valid on HiDPI screens, and render() needs no shown window.
    image = QImage(top.size(), QImage.Format_ARGB32)
    image.setDevicePixelRatio(1)
    image.fill(QColor("red"))
    top.render(image)
    return image


def render_pip(qtbot, style_sheet: str) -> list:
    """Render a white window holding a styled PIP with a child QLabel; return the probe colours as #AARRGGBB."""
    top = QWidget()
    qtbot.addWidget(top)
    top.resize(200, 200)
    top.setStyleSheet("background-color: white;")
    pip = QtEmbeddedDisplay(top)
    pip.setObjectName(NAME)
    pip.setGeometry(10, 10, 150, 150)
    pip.setStyleSheet(style_sheet)
    QLabel("x", pip).setGeometry(40, 40, 60, 60)
    image = render(top)
    return [image.pixelColor(*point).name(QColor.HexArgb) for point in (BACKGROUND, PIP_EDGE, LABEL_EDGE)]


def render_embedded_screen(qtbot, style_sheet: str, loaded: bool) -> tuple:
    """Render a white window holding a styled PIP that shows a lime 60x60 screen with a label, or PyDM's
    load-error text. Return the COVERED and UNCOVERED probe colours, then the text colours of the label in
    the PIP and of one outside it."""
    top = QWidget()
    qtbot.addWidget(top)
    top.resize(200, 200)
    top.setStyleSheet("background-color: white;")
    outside = QLabel("x", top)
    outside.setGeometry(170, 170, 20, 20)
    pip = QtEmbeddedDisplay(top)
    pip.setObjectName(NAME)
    pip.setGeometry(10, 10, 150, 150)
    pip.setStyleSheet(style_sheet)
    if loaded:
        # Like a converted screen: the Display fills the PIP but paints nothing; its centralwidget
        # has the screen's own size and background.
        screen = Display()
        screen.setStyleSheet("background-color: lime;")
        central = QWidget(screen)
        central.setGeometry(0, 0, 60, 60)
        inside = QLabel("x", central)
        inside.setGeometry(10, 10, 30, 30)
        pip.embedded_widget = screen
    else:
        pip.display_error_text("No such file")
        inside = pip.err_label
    image = render(top)
    probes = [image.pixelColor(*point).name(QColor.HexArgb) for point in (COVERED, UNCOVERED)]
    return probes, *(label.palette().color(label.foregroundRole()).name() for label in (inside, outside))


def test_pip_border_frames_display_not_embedded_widgets(qtbot, qtlog):
    style_sheet = pip_style_sheet(foreground_color=RGBA(0, 0, 255))

    background, pip_edge, label_edge = render_pip(qtbot, style_sheet)

    assert not [record.message for record in qtlog.records if PARSE_ERROR in record.message]
    assert background == WHITE
    assert pip_edge == BLACK
    assert label_edge == background


def test_bare_border_sheet_also_frames_child_widgets(qtbot):
    # The pre-fix sheet: Qt reads a selector-less sheet as `* { ... }`, so every child gets the border too.
    _, pip_edge, label_edge = render_pip(qtbot, "border: 1px solid black;background-color: none;")

    assert pip_edge == label_edge == BLACK


def test_mixed_sheet_is_dropped_with_parse_warning(qtbot, qtlog):
    # Bare declarations next to a selector rule: Qt warns and applies nothing, hence the converter's `*` block.
    background, pip_edge, _ = render_pip(qtbot, f"color: blue; #{NAME} {{ border: 1px solid black; }}")

    assert any(PARSE_ERROR in record.message for record in qtlog.records)
    assert pip_edge == background == WHITE


@pytest.mark.parametrize("loaded", [True, False], ids=["loaded", "load_failed"])
def test_pip_paints_background_not_foreground(qtbot, loaded):
    style_sheet = pip_style_sheet(
        filename="child.edl", foreground_color=RGBA(0, 0, 255), background_color=RGBA(255, 0, 0)
    )

    (covered, uncovered), inside_text, outside_text = render_embedded_screen(qtbot, style_sheet, loaded)

    # EDM fills the frame with bgColor wherever the embedded screen doesn't cover it, all of it when the
    # file fails to load, and never applies fgColor to the embedded screen.
    assert uncovered == RED
    assert inside_text == outside_text
    if loaded:
        assert covered == LIME


def test_pip_without_file_paints_no_background(qtbot):
    # EDM creates no frame for a PIP with no file.
    background, _, label_edge = render_pip(qtbot, pip_style_sheet(background_color=RGBA(255, 0, 0)))

    assert label_edge == background == WHITE
