"""EDM menu mux screens: the generated .py swaps macros on the embedded .ui (#65)."""

import ast
import json
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


def convert_elsewhere(tmp_path, monkeypatch, text):
    """Convert text into tmp_path/out, then run from another directory."""
    source = tmp_path / "screen.edl"
    source.write_text(text)
    out = tmp_path / "out"
    out.mkdir()
    # The converter logs skipped widget classes (menuMuxClass) to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    convert(str(source), str(out / "screen.ui"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return out / "screen.py"


def loc_connection(name):
    from pydm.data_plugins import plugin_for_address

    return plugin_for_address("loc://x").connections.get(name)


def variable_value(name):
    connection = loc_connection(name)
    return None if connection is None else connection.value


@pytest.fixture
def menumux_screen(request, tmp_path, monkeypatch):
    """Convert SCREEN, or the EDL text given as the fixture's param, into
    tmp_path/out, then run from another directory."""
    return convert_elsewhere(tmp_path, monkeypatch, getattr(request, "param", SCREEN))


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
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    # Load as on a PyDM install without the converter.
    for module in ("pydmconverter", "pydmconverter.edm", "pydmconverter.edm.parser"):
        monkeypatch.setitem(sys.modules, module, None)
    screen = load_file(str(menumux_screen), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)

    # initialState "$(START)" with START=1 opens the menu on "On" (FLAG=1).
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(VARIABLE) == 1, timeout=3000)

    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(VARIABLE) == 0, timeout=3000)
    menu.setCurrentIndex(1)
    qtbot.waitUntil(lambda: variable_value(VARIABLE) == 1, timeout=3000)

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


CONTROL_SCREEN = textwrap.dedent(
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

    # (Menu Mux) writing its item to a local variable, with no macros
    object menuMuxClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 10
    y 10
    w 100
    h 25
    controlPv "LOC\\$(!W)menumuxShow"
    initialState "$(START)"
    numItems 3
    symbolTag {
      0 "Off"
      1 "On"
      2 "Both"
    }
    endObjectProperties

    # (Rectangle) shown while the variable is 1
    object activeRectangleClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 150
    y 50
    w 50
    h 20
    visPv "LOC\\$(!W)menumuxShow"
    visMin "1"
    visMax "2"
    endObjectProperties
    """
)
SHOW = "__UNIQUE__menumuxShow"


@pytest.mark.parametrize(
    "menu_pv, rectangle_pv, address",
    [
        # Nothing configures the variable: the screen declares it from initialState when it runs.
        (r"LOC\\$(!W)menumuxShow", r"LOC\\$(!W)menumuxShow", "loc://__UNIQUE__menumuxShow"),
        # Another widget configures it: the menu configures it the same way.
        (
            r"LOC\\$(!W)menumuxShow",
            r"LOC\\$(!W)menumuxShow=e:0,Off,On",
            "loc://__UNIQUE__menumuxShow?type=int&init=0&enum_string=['Off', 'On']",
        ),
        # The .ui's widgets connect first, so their configuration wins over the menu's own.
        (r"LOC\\$(!W)menumuxShow=i:2", r"LOC\\$(!W)menumuxShow=i:1", "loc://__UNIQUE__menumuxShow?type=int&init=1"),
        # The menu's own configuration stands when nothing else configures the variable.
        (r"LOC\\$(!W)menumuxShow=i:2", r"LOC\\$(!W)menumuxShow", "loc://__UNIQUE__menumuxShow?type=int&init=2"),
        # A PV keeps its name; the screen expands its macros when it runs.
        ("$(P):MODE", r"LOC\\$(!W)menumuxShow", "${P}:MODE"),
    ],
)
def test_menu_control_pv_address(tmp_path, monkeypatch, menu_pv, rectangle_pv, address):
    text = CONTROL_SCREEN.replace(r'controlPv "LOC\\$(!W)menumuxShow"', f'controlPv "{menu_pv}"').replace(
        r'visPv "LOC\\$(!W)menumuxShow"', f'visPv "{rectangle_pv}"'
    )
    (menu,) = generated_menus(convert_elsewhere(tmp_path, monkeypatch, text))
    assert menu["controlPv"] == address


RECTANGLE = CONTROL_SCREEN[CONTROL_SCREEN.index("# (Rectangle)") :]


def test_menu_takes_the_richest_ui_declaration(tmp_path, monkeypatch):
    # Three rectangles configure the variable differently; the menu takes the
    # declaration with the most enum strings, not the first.
    text = (
        CONTROL_SCREEN.replace(r'visPv "LOC\\$(!W)menumuxShow"', r'visPv "LOC\\$(!W)menumuxShow=i:1"')
        + "\n"
        + RECTANGLE.replace(r'visPv "LOC\\$(!W)menumuxShow"', r'visPv "LOC\\$(!W)menumuxShow=e:0,Off,On"')
        + "\n"
        + RECTANGLE.replace(r'visPv "LOC\\$(!W)menumuxShow"', r'visPv "LOC\\$(!W)menumuxShow=i:2"')
    )
    (menu,) = generated_menus(convert_elsewhere(tmp_path, monkeypatch, text))
    assert menu["controlPv"] == "loc://__UNIQUE__menumuxShow?type=int&init=0&enum_string=['Off', 'On']"


def test_menu_without_control_pv_has_no_address(menumux_screen):
    (menu,) = generated_menus(menumux_screen)
    assert menu["controlPv"] is None


def test_menu_writes_and_follows_its_control_pv(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMDrawingRectangle
    from qtpy.QtWidgets import QComboBox

    screen = load_file(
        str(convert_elsewhere(tmp_path, monkeypatch, CONTROL_SCREEN)), macros={"START": "1"}, target=None
    )
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    writes = []
    screen.control_writers[0].send_value_signal.connect(writes.append)

    # Nothing else configures the variable, so the menu declares it as an int
    # starting at initialState.
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(SHOW) == 1, timeout=3000)
    assert loc_connection(SHOW)._configuration["type"] == ["int"]
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    (rectangle,) = screen.embedded.embedded_widget.findChildren(PyDMDrawingRectangle)
    qtbot.waitUntil(rectangle.isVisible, timeout=3000)

    # Choosing an item writes its index, and widgets reading the variable follow.
    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(SHOW) == 0, timeout=3000)
    qtbot.waitUntil(lambda: not rectangle.isVisible(), timeout=3000)
    assert writes == [0]

    # A write from elsewhere moves the menu without writing it back.
    loc_connection(SHOW).put_value(2)
    qtbot.waitUntil(lambda: menu.currentIndex() == 2, timeout=3000)
    loc_connection(SHOW).put_value(1)
    qtbot.waitUntil(lambda: menu.currentIndex() == 1, timeout=3000)
    # Like EDM, a value past the last item shows the last item and stays in the variable.
    loc_connection(SHOW).put_value(7)
    qtbot.waitUntil(lambda: menu.currentIndex() == 2, timeout=3000)
    assert variable_value(SHOW) == 7
    assert writes == [0]

    # EDM reads the PV as an integer, a string like strtol, clamped to the items.
    assert screen.menu_index("1.5", 3) == 1
    assert screen.menu_index("OFF", 3) == 0
    assert screen.menu_index(2.9, 3) == 2
    assert screen.menu_index(-4, 3) == 0
    assert screen.menu_index(float("nan"), 3) is None
    assert screen.control_address("${START}:MODE", 0) == "1:MODE"
    assert screen.control_address("loc://x?type=float&init=0", 2) == "loc://x?type=float&init=0"


def test_menu_follows_a_variable_the_ui_declares(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMDrawingRectangle
    from qtpy.QtWidgets import QComboBox

    variable = "__UNIQUE__menumuxDeclared"
    text = CONTROL_SCREEN.replace("menumuxShow", "menumuxDeclared").replace(
        r'visPv "LOC\\$(!W)menumuxDeclared"', r'visPv "LOC\\$(!W)menumuxDeclared=i:1"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "2"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    (rectangle,) = screen.embedded.embedded_widget.findChildren(PyDMDrawingRectangle)

    # The rectangle declares the variable, so the menu starts at its init, not
    # at initialState (EDM ignores initialState with a controlPv).
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(variable) == 1, timeout=3000)
    qtbot.waitUntil(rectangle.isVisible, timeout=3000)

    # The rectangle created the variable; its rule still follows the menu.
    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(variable) == 0 and not rectangle.isVisible(), timeout=3000)
    menu.setCurrentIndex(1)
    qtbot.waitUntil(lambda: variable_value(variable) == 1 and rectangle.isVisible(), timeout=3000)


def test_menu_with_macros_follows_its_control_pv(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    selection, flag = "__UNIQUE__menumuxSel", "__UNIQUE__menumuxSelFlag"
    text = SCREEN.replace("menumuxFlag", "menumuxSelFlag").replace(
        'initialState "$(START)"', 'controlPv "LOC\\\\$(!W)menumuxSel"\ninitialState "$(START)"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)

    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(selection) == 1 and variable_value(flag) == 1, timeout=3000)

    # The macros follow the variable the menu writes...
    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(selection) == 0 and variable_value(flag) == 0, timeout=3000)
    # ...including a write from elsewhere.
    loc_connection(selection).put_value(1)
    qtbot.waitUntil(lambda: menu.currentIndex() == 1 and variable_value(flag) == 1, timeout=3000)
    assert screen.embedded.parsed_macros()["FLAG"] == "1"


def test_closing_the_screen_releases_its_control_pv(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file

    text = CONTROL_SCREEN.replace("menumuxShow", "menumuxGone")
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    screen.show()
    qtbot.waitUntil(lambda: variable_value("__UNIQUE__menumuxGone") == 1, timeout=3000)

    # Not registered with qtbot: deleting it is the test.
    screen.deleteLater()
    qtbot.waitUntil(lambda: loc_connection("__UNIQUE__menumuxGone") is None, timeout=3000)


def test_rule_on_a_macro_menus_control_pv_follows_after_a_reload(tmp_path, monkeypatch, qtbot):
    """A menu whose items set macros reloads the .ui on every change; the
    reloaded .ui's rule on the menu's own variable still follows it."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMDrawingRectangle
    from qtpy.QtWidgets import QComboBox

    variable = "__UNIQUE__menumuxReload"
    text = CONTROL_SCREEN.replace("menumuxShow", "menumuxReload").replace(
        'initialState "$(START)"',
        'initialState "$(START)"\nsymbol0 {\n  0 "M"\n  1 "M"\n  2 "M"\n}\nvalue0 {\n  0 "a"\n  1 "b"\n  2 "c"\n}',
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)

    def rectangle():
        (found,) = screen.embedded.embedded_widget.findChildren(PyDMDrawingRectangle)
        return found

    qtbot.waitUntil(lambda: rectangle().isVisible(), timeout=3000)
    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(variable) == 0 and screen.embedded.parsed_macros()["M"] == "a", timeout=3000)
    qtbot.waitUntil(lambda: not rectangle().isVisible(), timeout=3000)
    menu.setCurrentIndex(1)
    qtbot.waitUntil(lambda: variable_value(variable) == 1 and screen.embedded.parsed_macros()["M"] == "b", timeout=3000)
    qtbot.waitUntil(lambda: rectangle().isVisible(), timeout=3000)


def test_a_value_arriving_during_a_reload_sets_the_macros(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    selection = "__UNIQUE__menumuxBurst"
    text = SCREEN.replace("menumuxFlag", "menumuxBurstFlag").replace(
        'initialState "$(START)"', 'controlPv "LOC\\\\$(!W)menumuxBurst"\ninitialState "$(START)"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    qtbot.waitUntil(lambda: variable_value(selection) == 1, timeout=3000)

    # Two queued writes: the second is delivered while the first one's reload
    # flushes posted events.
    loaded = []
    set_macros_and_filename = screen.embedded.set_macros_and_filename

    def recording(filename, macros):
        loaded.append(json.loads(macros).get("FLAG"))
        set_macros_and_filename(filename, macros)

    screen.embedded.set_macros_and_filename = recording
    writer = screen.control_writers[0].send_value_signal
    writer.emit(0)
    writer.emit(1)
    qtbot.waitUntil(lambda: variable_value(selection) == 1 and menu.currentIndex() == 1, timeout=3000)
    qtbot.wait(200)
    assert screen.embedded.parsed_macros()["FLAG"] == "1"
    # The reload the first write starts loads the macros the second one set,
    # not the first one's stale ones.
    assert "0" not in loaded, loaded
