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
# As the .ui names it; window_variable gives an open screen's name (see window_macros).
VARIABLE = "${EDM_W}menumuxFlag"


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


GROUP = """\
# (Group)
object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y {y}
w {w}
h {h}

beginGroup

{objects}
endGroup

endObjectProperties
"""


def in_groups(screen, *boxes):
    """screen with its first menu mux inside groups at these (x, y, w, h)
    boxes, outermost first. EDM keeps a group's objects in screen coordinates."""
    start = screen.index("# (Menu Mux)")
    end = screen.index("endObjectProperties\n", start) + len("endObjectProperties\n")
    block = screen[start:end]
    for x, y, w, h in reversed(boxes):
        block = GROUP.format(x=x, y=y, w=w, h=h, objects=block)
    return screen[:start] + block + screen[end:]


# Only menu mux inside a group, as in lcls/lasr_in20_main_heater.edl (#164).
GROUPED_SCREEN = in_groups(SCREEN, (5, 5, 110, 35))
NESTED_SCREEN = in_groups(SCREEN, (2, 2, 200, 100), (5, 5, 110, 35))
MODE_MENU = """\
# (Menu Mux)
object menuMuxClass
beginObjectProperties
major 4
minor 1
release 0
x 150
y 85
w 100
h 25
numItems 1
symbolTag {
  0 "Only"
}
symbol0 {
  0 "MODE"
}
value0 {
  0 "m"
}
endObjectProperties
"""
# A grouped menu mux ahead of SCREEN's top-level one.
MIXED_SCREEN = SCREEN.replace("# (Menu Mux)", in_groups(MODE_MENU, (145, 80, 110, 35)) + "\n# (Menu Mux)", 1)
# A grouped menu labelled by its values.
NO_TAG_GROUPED_SCREEN = in_groups(SCREEN.replace('symbolTag {\n  0 "Off"\n  1 "On"\n}\n', "", 1), (5, 5, 110, 35))
# A grouped menu ahead of SCREEN's top-level one that sets the same macro.
FLAG_MENU = (
    MODE_MENU.replace("numItems 1", "numItems 2")
    .replace('symbolTag {\n  0 "Only"\n}', 'symbolTag {\n  0 "A"\n  1 "B"\n}')
    .replace('symbol0 {\n  0 "MODE"\n}', 'symbol0 {\n  0 "FLAG"\n  1 "FLAG"\n}')
    .replace('value0 {\n  0 "m"\n}', 'value0 {\n  0 "a"\n  1 "b"\n}')
)
SHADOWED_SCREEN = SCREEN.replace("# (Menu Mux)", in_groups(FLAG_MENU, (145, 80, 110, 35)) + "\n# (Menu Mux)", 1)


# A label showing the macros of PER_ITEM_SCREEN's menu.
LABEL = textwrap.dedent(
    """
    # (Static Text)
    object activeXTextClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 10
    y 50
    w 280
    h 20
    value {
      "$(sector) $(visibleLI20) $(visibleLI24)"
    }
    endObjectProperties
    """
)

# A menu mux like misc/thyratronRange.edl, whose items name different macros:
# "LI24" sets visibleLI24 through symbol1 and visibleLI20 through symbol2,
# "LI21" leaves visibleLI24's value out, and "?" sets nothing.
PER_ITEM_SCREEN = (
    menu_mux_screen(
        """
        initialState "0"
        numItems 4
        symbolTag {
          0 "LI20"
          1 "LI24"
          2 "LI21"
          3 "?"
        }
        symbol0 {
          0 "sector"
          1 "sector"
          2 "sector"
        }
        value0 {
          0 "LI20"
          1 "LI24"
          2 "LI21"
        }
        symbol1 {
          0 "visibleLI20"
          1 "visibleLI24"
          2 "visibleLI20"
        }
        value1 {
          0 "0"
          1 "0"
          2 "1"
        }
        symbol2 {
          0 "visibleLI24"
          1 "visibleLI20"
          2 "visibleLI24"
        }
        value2 {
          0 "1"
          1 "1"
        }
        """
    )
    + LABEL
)

# PER_ITEM_SCREEN with a second menu that also sets sector, except on "none".
TWO_MENU_SCREEN = PER_ITEM_SCREEN + textwrap.dedent(
    """
    # (Menu Mux)
    object menuMuxClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 150
    y 10
    w 100
    h 25
    numItems 2
    symbolTag {
      0 "LI30"
      1 "none"
    }
    symbol0 {
      0 "sector"
      1 "sector"
    }
    value0 {
      0 "LI30"
    }
    endObjectProperties
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


def window_variable(screen, name):
    """An open screen's name for a variable the .ui names with ${EDM_W}: the
    screen's window id takes its place (see window_macros)."""
    return name.replace("${EDM_W}", screen.macros()["EDM_W"])


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


def test_failed_conversion_leaves_no_menu_screen(tmp_path, monkeypatch):
    """The menu screen embeds the .ui, so it is written only after the .ui: a
    conversion that fails once the widgets are built leaves neither file."""
    import pydmconverter.edm.converter as converter

    def fail(*args, **kwargs):
        raise RuntimeError("late failure")

    source = tmp_path / "screen.edl"
    source.write_text(SCREEN)
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(converter, "resolve_window_macros", fail)
        with pytest.raises(RuntimeError, match="late failure"):
            convert(str(source), str(tmp_path / "screen.ui"))
    assert not (tmp_path / "screen.py").exists()
    assert not (tmp_path / "screen.ui").exists()

    convert(str(source), str(tmp_path / "screen.ui"))
    assert (tmp_path / "screen.ui").is_file()
    assert "self.embedded.filename = 'screen.ui'" in (tmp_path / "screen.py").read_text()


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
    variable = window_variable(screen, VARIABLE)
    (menu,) = screen.findChildren(QComboBox)

    # initialState "$(START)" with START=1 opens the menu on "On" (FLAG=1).
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(variable) == 1, timeout=3000)

    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(variable) == 0, timeout=3000)
    menu.setCurrentIndex(1)
    qtbot.waitUntil(lambda: variable_value(variable) == 1, timeout=3000)

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
        [("S0", "a"), ("S1", ""), ("S2", "x")],
        [("S0", "b"), ("S1", ""), ("S2", "y")],
        [("S0", ""), ("S1", ""), ("S2", "z")],
    ]


@pytest.mark.parametrize(
    "menumux_screen", [SPARSE_SCREEN.replace("numItems 3", "numItems 4")], ids=["four_items"], indirect=True
)
def test_items_past_the_tags_are_blank(menumux_screen):
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == ["A", "B", "C", ""]
    assert menu["macros"] == [
        [("S0", "a"), ("S1", ""), ("S2", "x")],
        [("S0", "b"), ("S1", ""), ("S2", "y")],
        [("S0", ""), ("S1", ""), ("S2", "z")],
        # symbol{i} names no macro for the fourth item either.
        [("", ""), ("", ""), ("", "")],
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
        return {name: parsed[name] for name in ("S0", "S1", "S2") if name in parsed}

    # initialState "2" opens the menu on "C", whose S0 and S1 values EDM left
    # out. As in EDM, an empty value sets nothing, so ${S0} and ${S1} stay
    # unexpanded.
    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    assert menu.currentIndex() == 2
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    assert macros() == {"S2": "z"}

    menu.setCurrentIndex(0)
    assert macros() == {"S0": "a", "S2": "x"}
    # S0 from "A" is not carried over to "C".
    menu.setCurrentIndex(2)
    assert macros() == {"S2": "z"}


@pytest.mark.parametrize("menumux_screen", [PER_ITEM_SCREEN], ids=["per_item"], indirect=True)
def test_items_name_their_own_macros(menumux_screen):
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == ["LI20", "LI24", "LI21", "?"]
    # Each item takes its macro names from its own entry of symbol{i}, not
    # from the first item's.
    assert menu["macros"] == [
        [("sector", "LI20"), ("visibleLI20", "0"), ("visibleLI24", "1")],
        [("sector", "LI24"), ("visibleLI24", "0"), ("visibleLI20", "1")],
        [("sector", "LI21"), ("visibleLI20", "1"), ("visibleLI24", "")],
        [("", ""), ("", ""), ("", "")],
    ]


def macros_and_label(screen):
    """The menu macros passed to screen's embedded display, and the text of
    the label showing them there."""
    from qtpy.QtWidgets import QLabel

    parsed = screen.embedded.parsed_macros()
    macros = {name: parsed[name] for name in ("sector", "visibleLI20", "visibleLI24") if name in parsed}
    (label,) = screen.embedded.embedded_widget.findChildren(QLabel)
    return macros, label.text()


@pytest.mark.parametrize("menumux_screen", [PER_ITEM_SCREEN], ids=["per_item"], indirect=True)
def test_menu_sets_only_the_selected_items_macros(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    (menu,) = screen.findChildren(QComboBox)
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    assert macros_and_label(screen) == ({"sector": "LI20", "visibleLI20": "0", "visibleLI24": "1"}, "LI20 0 1")

    menu.setCurrentIndex(1)
    assert macros_and_label(screen) == ({"sector": "LI24", "visibleLI20": "1", "visibleLI24": "0"}, "LI24 1 0")

    # "LI21" does not set visibleLI24, so EDM leaves $(visibleLI24) unexpanded
    # rather than keeping the value "LI24" set.
    menu.setCurrentIndex(2)
    assert macros_and_label(screen) == ({"sector": "LI21", "visibleLI20": "1"}, "LI21 1 ${visibleLI24}")

    # "?" sets nothing, and EDM then keeps every widget as it was.
    menu.setCurrentIndex(3)
    assert macros_and_label(screen) == ({"sector": "LI21", "visibleLI20": "1"}, "LI21 1 ${visibleLI24}")

    menu.setCurrentIndex(0)
    assert macros_and_label(screen) == ({"sector": "LI20", "visibleLI20": "0", "visibleLI24": "1"}, "LI20 0 1")


@pytest.mark.parametrize("menumux_screen", [TWO_MENU_SCREEN], ids=["two_menus"], indirect=True)
def test_first_menu_to_set_a_macro_wins(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    first, second = screen.findChildren(QComboBox)
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)

    # Both menus set sector; as in EDM the first one in the file wins.
    assert macros_and_label(screen)[0]["sector"] == "LI20"
    second.setCurrentIndex(1)
    second.setCurrentIndex(0)
    assert macros_and_label(screen)[0]["sector"] == "LI20"

    # The second menu's sector applies while the first sets none.
    first.setCurrentIndex(3)
    assert macros_and_label(screen) == ({"sector": "LI30"}, "LI30 ${visibleLI20} ${visibleLI24}")

    # With neither menu setting anything, the macros stay as they were.
    second.setCurrentIndex(1)
    assert macros_and_label(screen) == ({"sector": "LI30"}, "LI30 ${visibleLI20} ${visibleLI24}")


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
SHOW = "${EDM_W}menumuxShow"


@pytest.mark.parametrize(
    "menu_pv, rectangle_pv, address",
    [
        # Nothing configures the variable: the screen declares it from initialState when it runs.
        (r"LOC\\$(!W)menumuxShow", r"LOC\\$(!W)menumuxShow", "loc://${EDM_W}menumuxShow"),
        # Another widget configures it: the menu configures it the same way.
        (
            r"LOC\\$(!W)menumuxShow",
            r"LOC\\$(!W)menumuxShow=e:0,Off,On",
            "loc://${EDM_W}menumuxShow?type=int&init=0&enum_string=['Off', 'On']",
        ),
        # The .ui's widgets connect first, so their configuration wins over the menu's own.
        (r"LOC\\$(!W)menumuxShow=i:2", r"LOC\\$(!W)menumuxShow=i:1", "loc://${EDM_W}menumuxShow?type=int&init=1"),
        # The menu's own configuration stands when nothing else configures the variable.
        (r"LOC\\$(!W)menumuxShow=i:2", r"LOC\\$(!W)menumuxShow", "loc://${EDM_W}menumuxShow?type=int&init=2"),
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
    assert menu["controlPv"] == "loc://${EDM_W}menumuxShow?type=int&init=0&enum_string=['Off', 'On']"


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
    show = window_variable(screen, SHOW)
    (menu,) = screen.findChildren(QComboBox)
    writes = []
    screen.control_writers[0].send_value_signal.connect(writes.append)

    # Nothing else configures the variable, so the menu declares it as an int
    # starting at initialState.
    assert menu.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(show) == 1, timeout=3000)
    assert loc_connection(show)._configuration["type"] == ["int"]
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    (rectangle,) = screen.embedded.embedded_widget.findChildren(PyDMDrawingRectangle)
    qtbot.waitUntil(rectangle.isVisible, timeout=3000)

    # Choosing an item writes its index, and widgets reading the variable follow.
    menu.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(show) == 0, timeout=3000)
    qtbot.waitUntil(lambda: not rectangle.isVisible(), timeout=3000)
    assert writes == [0]

    # A write from elsewhere moves the menu without writing it back.
    loc_connection(show).put_value(2)
    qtbot.waitUntil(lambda: menu.currentIndex() == 2, timeout=3000)
    loc_connection(show).put_value(1)
    qtbot.waitUntil(lambda: menu.currentIndex() == 1, timeout=3000)
    # Like EDM, a value past the last item shows the last item and stays in the variable.
    loc_connection(show).put_value(7)
    qtbot.waitUntil(lambda: menu.currentIndex() == 2, timeout=3000)
    assert variable_value(show) == 7
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

    variable = "${EDM_W}menumuxDeclared"
    text = CONTROL_SCREEN.replace("menumuxShow", "menumuxDeclared").replace(
        r'visPv "LOC\\$(!W)menumuxDeclared"', r'visPv "LOC\\$(!W)menumuxDeclared=i:1"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "2"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    variable = window_variable(screen, variable)
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

    selection, flag = "${EDM_W}menumuxSel", "${EDM_W}menumuxSelFlag"
    text = SCREEN.replace("menumuxFlag", "menumuxSelFlag").replace(
        'initialState "$(START)"', 'controlPv "LOC\\\\$(!W)menumuxSel"\ninitialState "$(START)"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    selection = window_variable(screen, selection)
    flag = window_variable(screen, flag)
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
    gone = window_variable(screen, "${EDM_W}menumuxGone")
    qtbot.waitUntil(lambda: variable_value(gone) == 1, timeout=3000)

    # Not registered with qtbot: deleting it is the test.
    screen.deleteLater()
    qtbot.waitUntil(lambda: loc_connection(gone) is None, timeout=3000)


def test_rule_on_a_macro_menus_control_pv_follows_after_a_reload(tmp_path, monkeypatch, qtbot):
    """A menu whose items set macros reloads the .ui on every change; the
    reloaded .ui's rule on the menu's own variable still follows it."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMDrawingRectangle
    from qtpy.QtWidgets import QComboBox

    variable = "${EDM_W}menumuxReload"
    text = CONTROL_SCREEN.replace("menumuxShow", "menumuxReload").replace(
        'initialState "$(START)"',
        'initialState "$(START)"\nsymbol0 {\n  0 "M"\n  1 "M"\n  2 "M"\n}\nvalue0 {\n  0 "a"\n  1 "b"\n  2 "c"\n}',
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    variable = window_variable(screen, variable)
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

    selection = "${EDM_W}menumuxBurst"
    text = SCREEN.replace("menumuxFlag", "menumuxBurstFlag").replace(
        'initialState "$(START)"', 'controlPv "LOC\\\\$(!W)menumuxBurst"\ninitialState "$(START)"'
    )
    screen = load_file(str(convert_elsewhere(tmp_path, monkeypatch, text)), macros={"START": "1"}, target=None)
    qtbot.addWidget(screen)
    screen.show()
    selection = window_variable(screen, selection)
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


WINDOW_SCREEN = textwrap.dedent(
    r"""
    4 0 1
    beginScreenProperties
    major 4
    minor 0
    release 1
    x 0
    y 0
    w 300
    h 160
    endScreenProperties

    # (Menu Mux) switching the embedded window below, as in b34/profile_b34.edl
    object menuMuxClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 10
    y 10
    w 100
    h 25
    controlPv "LOC\\$(!W)menumuxWindow"
    initialState "1"
    numItems 2
    symbolTag {
      0 "OFF"
      1 "ON"
    }
    endObjectProperties

    # (Embedded Window) showing the file at the variable's index
    object activePipClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 10
    y 50
    w 200
    h 100
    displaySource "menu"
    filePv "LOC\\$(!W)menumuxWindow"
    numDsps 2
    displayFileName {
      0 "panelOff.edl"
      1 "panelOn.edl"
    }
    endObjectProperties
    """
)
PANEL = textwrap.dedent(
    """
    4 0 1
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
)


def test_menu_switches_the_embedded_window_it_writes(tmp_path, monkeypatch, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMEmbeddedDisplay
    from qtpy.QtWidgets import QComboBox

    path = convert_elsewhere(tmp_path, monkeypatch, WINDOW_SCREEN)
    for panel in ("panelOff", "panelOn"):
        (tmp_path / f"{panel}.edl").write_text(PANEL)
        convert(str(tmp_path / f"{panel}.edl"), str(path.parent / f"{panel}.ui"))
    # The .ui and the menu name one variable, which the menu declares from
    # initialState as the screen would.
    (menu,) = generated_menus(path)
    name, _, configuration = menu["controlPv"].removeprefix("loc://").partition("?")
    assert configuration == "type=int&init=1"
    assert f'"loc://{name}"' in (path.parent / "screen.ui").read_text()

    screen = load_file(str(path), target=None)
    qtbot.addWidget(screen)
    screen.show()
    name = window_variable(screen, name)
    (combo,) = screen.findChildren(QComboBox)
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    windows = screen.embedded.embedded_widget.findChildren(PyDMEmbeddedDisplay)
    assert sorted(window.filename for window in windows) == ["panelOff.ui", "panelOn.ui"]

    def shown():
        return [window.filename for window in windows if window.isVisible()]

    assert combo.currentIndex() == 1
    qtbot.waitUntil(lambda: variable_value(name) == 1 and shown() == ["panelOn.ui"], timeout=3000)

    # Choosing an item writes its index, and the window follows the variable.
    combo.setCurrentIndex(0)
    qtbot.waitUntil(lambda: variable_value(name) == 0 and shown() == ["panelOff.ui"], timeout=3000)

    # So does a write from elsewhere, which moves the menu too.
    loc_connection(name).put_value(1)
    qtbot.waitUntil(lambda: combo.currentIndex() == 1 and shown() == ["panelOn.ui"], timeout=3000)


# (Menu Mux) a camera menu setting the embedded .ui's macros, as in b34/profile_b34.edl
CAMERA_MENU = textwrap.dedent(
    r"""
    object menuMuxClass
    beginObjectProperties
    major 4
    minor 1
    release 0
    x 120
    y 10
    w 100
    h 25
    numItems 2
    symbolTag {
      0 "CAM1"
      1 "CAM2"
    }
    symbol0 {
      0 "ID"
      1 "ID"
    }
    value0 {
      0 "150"
      1 "250"
    }
    endObjectProperties
    """
)


@pytest.mark.parametrize(
    "variable, start, chosen, expected, camera_pv",
    [
        # The start display stays visible unless its rule hears the variable.
        ("menumuxReloadOff", "1", 0, ["panelOff.ui"], None),
        # The chosen display stays hidden unless its rule hears the variable.
        ("menumuxReloadOn", "0", 1, ["panelOn.ui"], None),
        # The camera menu reloads from its own controlPv's value.
        ("menumuxReloadCamera", "1", 0, ["panelOff.ui"], r"LOC\\$(!W)menumuxCamera"),
    ],
    ids=["start-display-hides", "chosen-display-shows", "camera-control-pv"],
)
def test_reload_keeps_the_window_on_the_menu_item(
    tmp_path, monkeypatch, qtbot, variable, start, chosen, expected, camera_pv
):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMEmbeddedDisplay
    from qtpy.QtWidgets import QComboBox

    camera = CAMERA_MENU if camera_pv is None else CAMERA_MENU.replace("numItems", f'controlPv "{camera_pv}"\nnumItems')
    text = WINDOW_SCREEN.replace("menumuxWindow", variable).replace('initialState "1"', f'initialState "{start}"')
    path = convert_elsewhere(tmp_path, monkeypatch, text + camera)
    for panel in ("panelOff", "panelOn"):
        (tmp_path / f"{panel}.edl").write_text(PANEL)
        convert(str(tmp_path / f"{panel}.edl"), str(path.parent / f"{panel}.ui"))
    menu, _ = generated_menus(path)
    name = menu["controlPv"].removeprefix("loc://").partition("?")[0]

    screen = load_file(str(path), target=None)
    qtbot.addWidget(screen)
    screen.show()
    name = window_variable(screen, name)
    window_menu, camera_menu = screen.findChildren(QComboBox)

    def shown():
        # A reload replaces the embedded .ui and its displays.
        embedded = screen.embedded.embedded_widget
        windows = [] if embedded is None else embedded.findChildren(PyDMEmbeddedDisplay)
        return [window.filename for window in windows if window.isVisible()]

    qtbot.waitUntil(lambda: shown() == [["panelOff.ui", "panelOn.ui"][int(start)]], timeout=3000)
    window_menu.setCurrentIndex(chosen)
    qtbot.waitUntil(lambda: variable_value(name) == chosen and shown() == expected, timeout=3000)

    # The camera's macros reload the .ui, whose rules join the variable the
    # window menu already holds. The window stays on the chosen item.
    old = screen.embedded.embedded_widget
    camera_menu.setCurrentIndex(1)
    qtbot.waitUntil(
        lambda: screen.embedded.embedded_widget is not old and screen.embedded.embedded_widget is not None,
        timeout=3000,
    )
    assert screen.embedded.parsed_macros()["ID"] == "250"
    qtbot.waitUntil(lambda: shown() == expected, timeout=3000)
    assert variable_value(name) == chosen


@pytest.mark.parametrize(
    "menumux_screen", [GROUPED_SCREEN, NESTED_SCREEN], ids=["group", "nested_groups"], indirect=True
)
def test_menu_inside_groups_gets_a_screen(menumux_screen):
    # The screen's only menu mux is inside a group, so before #164 no .py was written.
    compile(menumux_screen.read_text(), str(menumux_screen), "exec")
    (menu,) = generated_menus(menumux_screen)
    # A group's objects keep their screen coordinates, as in the .ui.
    assert (menu["x"], menu["y"], menu["width"], menu["height"]) == (10, 10, 100, 25)
    assert menu["items"] == ["Off", "On"]
    # A grouped menu sets no macros in EDM.
    assert not any(menu["macros"])


@pytest.mark.parametrize("menumux_screen", [NO_TAG_GROUPED_SCREEN], ids=["no_tags"], indirect=True)
def test_grouped_menu_without_tags_keeps_its_value_labels(menumux_screen):
    assert "symbolTag" not in NO_TAG_GROUPED_SCREEN
    (menu,) = generated_menus(menumux_screen)
    assert menu["items"] == ["0", "1"]
    assert not any(menu["macros"])


@pytest.mark.parametrize("menumux_screen", [MIXED_SCREEN], ids=["mixed"], indirect=True)
def test_grouped_and_top_level_menus_keep_the_screen_order(menumux_screen):
    menus = generated_menus(menumux_screen)
    assert [(menu["x"], menu["y"], menu["items"][0]) for menu in menus] == [(150, 85, "Only"), (10, 10, "Off")]


@pytest.mark.parametrize("menumux_screen", [SHADOWED_SCREEN], ids=["shadowed"], indirect=True)
def test_grouped_menu_leaves_the_macros_to_top_level_menus(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file

    def macros():
        return json.loads(screen.embedded.macros)

    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    grouped, top_level = screen.muxes
    assert [grouped.itemText(0), top_level.itemText(0)] == ["A", "Off"]
    # EDM takes macros only from top-level menus, so FLAG follows the top-level one.
    assert macros() == {"FLAG": "0"}
    grouped.setCurrentIndex(1)
    assert macros() == {"FLAG": "0"}
    top_level.setCurrentIndex(1)
    assert macros() == {"FLAG": "1"}


@pytest.mark.parametrize("menumux_screen", [NESTED_SCREEN], ids=["nested_groups"], indirect=True)
def test_grouped_menu_sits_where_edm_draws_it(menumux_screen, qtbot):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QComboBox

    screen = load_file(str(menumux_screen), target=None)
    qtbot.addWidget(screen)
    screen.show()
    qtbot.waitUntil(lambda: screen.embedded.embedded_widget is not None, timeout=3000)
    (menu,) = screen.findChildren(QComboBox)
    # The menu is the .ui's sibling, not its child, so compare both in the screen's frame.
    origin = QPoint(0, 0)
    position = menu.mapTo(screen, origin) - screen.embedded.embedded_widget.mapTo(screen, origin)
    assert (position.x(), position.y()) == (10, 10)
