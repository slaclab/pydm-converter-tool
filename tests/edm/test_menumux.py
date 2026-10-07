"""EDM menu mux screens: the generated .py swaps macros on the embedded .ui (#65)."""

import ast
import sys
import textwrap

import pytest

from pydmconverter.edm.converter import convert

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


def menu_mux_screen(properties):
    """SCREEN's header and menu mux geometry with these menu mux properties."""
    return SCREEN[: SCREEN.index("initialState")] + textwrap.dedent(properties) + "endObjectProperties\n"


# A menu mux as EDM saves it: value0 without its trailing empty value, and
# value1 left out altogether since all of its values are empty.
SPARSE_SCREEN = menu_mux_screen(
    """
    initialState "2"
    numItems 3
    symbolTag {
      0 "A"
      1 "B"
      2 "C"
    }
    symbol0 {
      0 "S0"
      1 "S0"
      2 "S0"
    }
    value0 {
      0 "a"
      1 "b"
    }
    symbol1 {
      0 "S1"
      1 "S1"
      2 "S1"
    }
    symbol2 {
      0 "S2"
      1 "S2"
      2 "S2"
    }
    value2 {
      0 "x"
      1 "y"
      2 "z"
    }
    """
)


def generated_menus(py_file):
    """The menus literal of a generated screen."""
    module = ast.parse(py_file.read_text())
    (menus,) = [
        ast.literal_eval(node.value)
        for node in ast.walk(module)
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "attr", None) == "menus"
    ]
    return menus


@pytest.fixture
def menumux_screen(request, tmp_path, monkeypatch):
    """Convert SCREEN, or the EDL text given as the fixture's param, into
    tmp_path/out, then run from another directory."""
    source = tmp_path / "screen.edl"
    source.write_text(getattr(request, "param", SCREEN))
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
    assert "self.embedded.filename = 'screen.ui'" in code
    assert "def __init__(self, parent=None, args=None, macros=None):" in code
    # The screen runs where only qtpy and pydm are installed.
    assert "pydmconverter" not in code


def test_menu_without_tags_is_labelled_by_its_values(tmp_path, monkeypatch):
    source = tmp_path / "untagged.edl"
    source.write_text(SCREEN.replace('symbolTag {\n  0 "Off"\n  1 "On"\n}\n', ""))
    assert "symbolTag" not in source.read_text()
    monkeypatch.chdir(tmp_path)
    convert(str(source), str(tmp_path / "untagged.ui"))

    (menu,) = generated_menus(tmp_path / "untagged.py")
    assert menu["items"] == ["0", "1"]


def test_menu_change_reinitialises_local_variables(menumux_screen, qtbot, monkeypatch):
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    def variable_value():
        connection = plugin_for_address("loc://x").connections.get(VARIABLE)
        return None if connection is None else connection.value

    # Load as on a PyDM install without the converter.
    for module in ("pydmconverter", "pydmconverter.edm", "pydmconverter.edm.parser"):
        monkeypatch.setitem(sys.modules, module, None)
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
        return screen.initial_index(state, count)

    assert initial("${START}+1") == 1
    assert initial("3") == 3
    assert initial("9") == 0
    assert initial("${MISSING}") == 0


@pytest.mark.parametrize("menumux_screen", [SPARSE_SCREEN], ids=["sparse"], indirect=True)
def test_values_left_out_by_edm_are_empty(menumux_screen):
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == ["A", "B", "C"]
    # symbol2 still counts after symbol1, whose value1 is left out.
    assert menu["macros"] == [
        ("S0", ["a", "b", ""]),
        ("S1", ["", "", ""]),
        ("S2", ["x", "y", "z"]),
    ]


@pytest.mark.parametrize(
    "menumux_screen", [SPARSE_SCREEN.replace("numItems 3", "numItems 4")], ids=["four_items"], indirect=True
)
def test_items_past_the_tags_are_blank(menumux_screen):
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == ["A", "B", "C", ""]
    assert menu["macros"] == [
        ("S0", ["a", "b", "", ""]),
        ("S1", ["", "", "", ""]),
        ("S2", ["x", "y", "z", ""]),
    ]


@pytest.mark.parametrize(
    "menumux_screen", [menu_mux_screen('symbol0 {\n  0 "S0"\n}\n')], ids=["no_items"], indirect=True
)
def test_menu_without_items_sets_no_macros(menumux_screen):
    code = menumux_screen.read_text()
    compile(code, str(menumux_screen), "exec")
    # Without numItems, symbolTag or values the menu has no items, and so no
    # selected item to take S0's value from.
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == []
    assert menu["macros"] == []


@pytest.mark.parametrize("menumux_screen", [SPARSE_SCREEN], ids=["sparse"], indirect=True)
def test_menu_opens_on_an_item_whose_values_edm_left_out(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    def macros():
        parsed = screen.embedded.parsed_macros()
        return [parsed[name] for name in ("S0", "S1", "S2")]

    # initialState "2" opens the menu on "C", whose S0 and S1 values EDM left out.
    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    assert menu.currentIndex() == 2
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    assert macros() == ["", "", "z"]

    menu.setCurrentIndex(0)
    assert macros() == ["a", "", "x"]
    menu.setCurrentIndex(2)
    assert macros() == ["", "", "z"]
