"""Links to a display with menu muxes open its menu screen (X.py), not the bare X.ui."""

import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.menu_links import link_menu_screens

HEADER = """4 0 1
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

MENU = """object menuMuxClass
beginObjectProperties
major 4
minor 1
release 0
x 10
y 10
w 100
h 25
numItems 2
symbolTag {
  0 "Off"
  1 "On"
}
symbol0 {
  0 "FLAG"
  1 "FLAG"
}
value0 {
  0 "0"
  1 "1"
}
endObjectProperties
"""

TEXT = """object activeXTextClass
beginObjectProperties
major 4
minor 1
release 0
x 10
y 50
w 100
h 20
value {
  "flag $(FLAG)"
}
endObjectProperties
"""

PARENT = """object relatedDisplayClass
beginObjectProperties
major 4
minor 4
release 0
x 10
y 10
w 100
h 20
numDsps 3
displayFileName {
  0 "child.edl"
  1 "plain"
  2 "$(dev)_child"
}
endObjectProperties

object activePipClass
beginObjectProperties
major 4
minor 1
release 0
x 10
y 40
w 200
h 100
displaySource "file"
file "child"
endObjectProperties
"""


def in_group(text):
    return (
        "object activeGroupClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        "x 5\ny 5\nw 120\nh 40\n\nbeginGroup\n\n" + text + "\nendGroup\n\nendObjectProperties\n"
    )


@pytest.fixture
def out(tmp_path, monkeypatch):
    # The converter logs skipped widget classes to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EDMDATAFILES", raising=False)
    return tmp_path


def links(ui_path):
    root = ET.parse(ui_path).getroot()
    related = [s.text for s in root.findall(".//widget[@class='PyDMRelatedDisplayButton']//stringlist/string")]
    embedded = [
        s.text for s in root.findall(".//widget[@class='PyDMEmbeddedDisplay']/property[@name='filename']/string")
    ]
    return related, embedded


def convert_parent(directory, **kwargs):
    (directory / "parent.edl").write_text(HEADER + PARENT)
    convert(str(directory / "parent.edl"), str(directory / "parent.ui"), **kwargs)
    return links(directory / "parent.ui")


@pytest.mark.parametrize("child", [MENU + TEXT, in_group(MENU) + TEXT], ids=["top-level", "in-group"])
def test_links_open_the_menu_screen(out, child):
    (out / "child.edl").write_text(HEADER + child)
    (out / "plain.edl").write_text(HEADER + TEXT)
    related, embedded = convert_parent(out)
    # A name with a macro is only known when the screen runs, so it keeps its .ui.
    assert related == ["child.py", "plain.ui", "${dev}_child.ui"]
    assert embedded == ["child.py"]
    # The embedded display keeps the window id resolve_window_macros gave it.
    macros = (
        ET.parse(out / "parent.ui")
        .getroot()
        .find(".//widget[@class='PyDMEmbeddedDisplay']/property[@name='macros']/string")
    )
    assert '"EDM_W": "${EDM_W_ROOT}' in macros.text


def test_missing_target_keeps_its_ui(out):
    related, embedded = convert_parent(out)
    assert related == ["child.ui", "plain.ui", "${dev}_child.ui"]
    assert embedded == ["child.ui"]


@pytest.mark.parametrize("where", ["search_paths", "EDMDATAFILES"])
def test_target_found_on_the_search_paths(out, monkeypatch, where):
    elsewhere = out / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "child.edl").write_text(HEADER + MENU + TEXT)
    if where == "search_paths":
        related, _ = convert_parent(out, search_paths=[elsewhere])
    else:
        # EDM's form: absolute directories joined with ":".
        (out / "empty").mkdir()
        monkeypatch.setenv("EDMDATAFILES", f"{out / 'empty'}:{elsewhere}")
        related, _ = convert_parent(out)
    assert related[0] == "child.py"


def test_site_dropping_menu_muxes_keeps_the_ui(tmp_path):
    (tmp_path / "child.edl").write_text(HEADER + MENU)
    ui = ET.fromstring(
        '<ui><widget class="PyDMEmbeddedDisplay"><property name="filename"><string>child.ui</string>'
        "</property></widget></ui>"
    )
    link_menu_screens(ui, [str(tmp_path)], {"menumuxclass"})
    assert ui.find(".//string").text == "child.ui"
    link_menu_screens(ui, [str(tmp_path)], set())
    assert ui.find(".//string").text == "child.py"


def test_embedded_menu_screen_shows_its_menu(out, qtbot):
    """PyDM loads the linked .py: the embedded display shows the menu and passes its macros."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMEmbeddedDisplay
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QComboBox

    (out / "child.edl").write_text(HEADER + MENU + TEXT)
    convert(str(out / "child.edl"), str(out / "child.ui"))
    assert (out / "child.py").exists()
    convert_parent(out)

    screen = load_file(str(out / "parent.ui"), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (embedded,) = [w for w in screen.findChildren(PyDMEmbeddedDisplay) if w.filename == "child.py"]
    qtbot.waitUntil(lambda: embedded.embedded_widget is not None, timeout=3000)
    (menu,) = embedded.embedded_widget.findChildren(QComboBox)
    assert [menu.itemText(i) for i in range(menu.count())] == ["Off", "On"]
    assert embedded.embedded_widget.embedded.parsed_macros()["FLAG"] == "0"
    # The menu screen's .ui fills it from its origin, so the content keeps its EDM
    # place in the embedded window, as when the .ui is embedded on its own.
    menu_screen = embedded.embedded_widget
    assert menu_screen.embedded.mapTo(menu_screen, QPoint(0, 0)) == QPoint(0, 0)
    assert menu_screen.embedded.size() == menu_screen.size()
