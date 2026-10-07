"""Render an activePipClass embedded display in Qt: its border must frame the display, not the embedded screen."""

from pydm.widgets import PyDMEmbeddedDisplay as QtEmbeddedDisplay
from qtpy.QtGui import QColor, QImage
from qtpy.QtWidgets import QLabel, QWidget

from pydmconverter.custom_types import RGBA
from pydmconverter.widgets import PyDMEmbeddedDisplay

NAME = "activePipClass1"
WHITE, BLACK = "#ffffffff", "#ff000000"
# Probe points in window coordinates: the PIP spans (10, 10)-(159, 159) and its label's top-left corner is at
# (50, 50). Corners and edges only, so font differences between platforms can't reach them.
BACKGROUND, PIP_EDGE, LABEL_EDGE = (5, 5), (10, 80), (50, 50)
PARSE_ERROR = "Could not parse stylesheet"


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
    # A fixed devicePixelRatio of 1 keeps the probes valid on HiDPI screens, and render() needs no shown window.
    image = QImage(top.size(), QImage.Format_ARGB32)
    image.setDevicePixelRatio(1)
    image.fill(QColor("red"))
    top.render(image)
    return [image.pixelColor(*point).name(QColor.HexArgb) for point in (BACKGROUND, PIP_EDGE, LABEL_EDGE)]


def test_pip_border_frames_display_not_embedded_widgets(qtbot, qtlog):
    xml = PyDMEmbeddedDisplay(name=NAME, foreground_color=RGBA(0, 0, 255)).to_xml()
    style_sheet = xml.findall("property[@name='styleSheet']")[-1].find("string").text

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
