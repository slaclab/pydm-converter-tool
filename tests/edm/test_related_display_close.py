"""A related display entry with closeAction (or closeDisplay) set opens its display
and then closes the parent window (EDM related_display.cc popupDisplay). The
converted button opens such a display in place: openInNewWindow false, which a
PyDM main window handles by swapping in the new display."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ui.ir_adapter import ui_file_to_ir

HEADER = """\
4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 300
h 200
endScreenProperties
"""

TWO_FILES = 'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\n'

# (blocks, .ui openInNewWindow, IR openInNewWindow). The IR button carries only the
# lowest-numbered display, so it follows that entry's flag.
CASES = {
    "none": (TWO_FILES, True, True),
    "closeAction": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\n", False, False),
    "closeDisplay": (TWO_FILES + "closeDisplay {\n  0 1\n  1 1\n}\n", False, False),
    "both tags": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\ncloseDisplay {\n  0 1\n  1 1\n}\n", False, False),
    "later tag clears": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\ncloseDisplay {\n  0 0\n  1 0\n}\n", True, True),
    "only the second entry": (TWO_FILES + "closeAction {\n  1 1\n}\n", True, True),
    "only the first entry": (TWO_FILES + "closeAction {\n  0 1\n}\n", True, False),
    "one-based": ('displayFileName {\n  1 "a.edl"\n  2 "b.edl"\n}\ncloseAction {\n  1 1\n  2 1\n}\n', False, False),
    # EDM never closes the parent from a popup: a right-click one (button3Popup) or a
    # hover one (useFocus on a button of one display; the later numDsps replaces
    # related_display's, as EDM reads it). useFocus on a menu still closes.
    "button3Popup": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\nbutton3Popup\n", True, True),
    "button3Popup 0": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\nbutton3Popup 0\n", False, False),
    "useFocus, one display": (
        'numDsps 1\ndisplayFileName {\n  0 "a.edl"\n}\ncloseAction {\n  0 1\n}\nuseFocus\n',
        True,
        True,
    ),
    "useFocus, a menu": (TWO_FILES + "closeAction {\n  0 1\n  1 1\n}\nuseFocus\n", False, False),
}


def related_display(blocks, symbols=""):
    return (
        "object relatedDisplayClass\nbeginObjectProperties\nmajor 4\nminor 4\nrelease 0\n"
        'x 10\ny 10\nw 80\nh 20\nbuttonLabel "Go"\nnumDsps 2\n' + blocks + symbols + "endObjectProperties\n"
    )


def _edl(tmp_path, blocks, symbols=""):
    edl = tmp_path / "parent.edl"
    edl.write_text(HEADER + related_display(blocks, symbols))
    return edl


def _convert(tmp_path, blocks, symbols=""):
    ui = tmp_path / "parent.ui"
    convert(str(_edl(tmp_path, blocks, symbols)), str(ui))
    return ui


def _ir_buttons(node):
    if node["type"] == "related-display-button":
        yield node
    for child in node.get("children", []):
        yield from _ir_buttons(child)


def _ui_open_in_new_window(ui):
    (button,) = [w for w in ET.parse(ui).getroot().iter("widget") if w.get("class") == "PyDMRelatedDisplayButton"]
    return button.find("property[@name='openInNewWindow']/bool").text == "true"


@pytest.mark.parametrize("blocks, ui_new_window, ir_new_window", CASES.values(), ids=CASES.keys())
def test_ui_opens_in_place_when_every_entry_closes(tmp_path, blocks, ui_new_window, ir_new_window):
    assert _ui_open_in_new_window(_convert(tmp_path, blocks)) is ui_new_window


@pytest.mark.parametrize("blocks, ui_new_window, ir_new_window", CASES.values(), ids=CASES.keys())
def test_ir_opens_in_place_when_the_carried_entry_closes(tmp_path, blocks, ui_new_window, ir_new_window):
    wire = to_wire_dict(edm_file_to_ir(_edl(tmp_path, blocks)))
    assert validate_screen_json(wire) == []
    (button,) = _ir_buttons(wire["root"])
    assert button["props"]["openInNewWindow"] is ir_new_window


@pytest.mark.parametrize("blocks, ui_new_window, ir_new_window", CASES.values(), ids=CASES.keys())
def test_converted_ui_carries_open_in_new_window_to_ir(tmp_path, blocks, ui_new_window, ir_new_window):
    wire = to_wire_dict(ui_file_to_ir(_convert(tmp_path, blocks)))
    assert validate_screen_json(wire) == []
    (button,) = _ir_buttons(wire["root"])  # inside the .ui's central widget
    assert button["props"]["openInNewWindow"] is ui_new_window


def test_closing_related_display_opens_in_place_in_pydm(tmp_path, qtbot, monkeypatch):
    """In a PyDM app the click swaps the display inside the main window (window().open)
    instead of starting a new one, with the parent's macros under the button's."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import related_display_button
    from qtpy.QtCore import Qt

    ui = _convert(
        tmp_path, 'displayFileName {\n  0 "a.edl"\n}\ncloseAction {\n  0 1\n}\n', 'symbols {\n  0 "DEV=B,S=2"\n}\n'
    )
    (tmp_path / "a.ui").write_text('<ui version="4.0"><class>Form</class><widget class="QWidget" name="Form"/></ui>')
    screen = load_file(str(ui), macros={"DEV": "A", "P": "X"}, target=None)
    qtbot.addWidget(screen)
    (button,) = screen.findChildren(related_display_button.PyDMRelatedDisplayButton)
    assert button.openInNewWindow is False

    opened, new_windows = [], []
    monkeypatch.setattr(related_display_button, "is_pydm_app", lambda: True)
    monkeypatch.setattr(related_display_button, "load_file", lambda *args, **kwargs: new_windows.append(args))
    monkeypatch.setattr(
        button.window(), "open", lambda fname, macros=None: opened.append((Path(fname).name, macros)), raising=False
    )
    qtbot.mouseClick(button, Qt.LeftButton)

    assert new_windows == []
    assert opened == [("a.ui", {"DEV": "B", "P": "X", "S": "2"})]
