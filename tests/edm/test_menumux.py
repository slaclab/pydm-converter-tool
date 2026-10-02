"""EDM menu mux screens: the generated .py swaps macros on the embedded .ui (#65)."""

import textwrap

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.parser import EDMObject

SCREEN = textwrap.dedent(
    r"""
    4 0 1
    beginScreenProperties
    major 4
    minor 0
    release 1
    x 0
    y 0
    w 300
    h 120
    endScreenProperties

    # (Menu Mux)
    object menuMuxClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 10
    y 10
    w 100
    h 25
    initialState "$(START)"
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

    # (Text Control) on a local variable initialised from the menu's macro
    object activeXTextDspClass
    beginObjectProperties
    major 4
    minor 7
    release 0
    x 10
    y 50
    w 100
    h 20
    controlPv "LOC\\$(!W)menumuxFlag=i:$(FLAG)"
    endObjectProperties

    # (Rectangle) whose visibility rule also holds the variable
    object activeRectangleClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 150
    y 50
    w 50
    h 20
    visPv "LOC\\$(!W)menumuxFlag=i:$(FLAG)"
    visMin "1"
    visMax "2"
    endObjectProperties
    """
)
VARIABLE = "__UNIQUE__menumuxFlag"


@pytest.fixture
def menumux_screen(tmp_path, monkeypatch):
    """Convert SCREEN into tmp_path/out, then run from another directory."""
    source = tmp_path / "screen.edl"
    source.write_text(SCREEN)
    out = tmp_path / "out"
    out.mkdir()
    # The converter logs skipped widget classes (menuMuxClass) to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    convert(str(source), str(out / "screen.ui"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return out / "screen.py"


def test_generated_screen_compiles_and_names_its_ui_without_a_path(menumux_screen):
    code = menumux_screen.read_text()
    compile(code, str(menumux_screen), "exec")
    # PyDM resolves this against the .py's own directory, wherever PyDM was started.
    assert 'self.embedded.filename = "screen.ui"' in code
    assert "def __init__(self, parent=None, args=None, macros=None):" in code


def test_menu_change_reinitialises_local_variables(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    def variable_value():
        connection = plugin_for_address("loc://x").connections.get(VARIABLE)
        return None if connection is None else connection.value

    screen = load_file(str(menumux_screen), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)

    # initialState "$(START)" with START=1 opens the menu on "On" (FLAG=1).
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value() == 1, timeout=3000)

    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value() == 0, timeout=3000)
    menu.setCurrentIndex(1)
    qtbot.waitUntil(lambda: variable_value() == 1, timeout=3000)

    # Macros the screen was opened with reach the embedded .ui too.
    assert screen.embedded.parsed_macros()["START"] == "1"

    # initialState reads like strtol and falls back to the first item.
    def initial(state, count=5):
        return screen.initial_index(EDMObject(properties={"initialState": state}), count)

    assert initial("${START}+1") == 1
    assert initial("3") == 3
    assert initial("9") == 0
    assert initial("${MISSING}") == 0
