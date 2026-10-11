"""EDM's $(!W): one id per window, a new one for every embedded window, so two
open copies of a screen keep their own local variables (see window_macros)."""

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert

HEADER = """\
4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 400
h 400
endScreenProperties
"""


def edm_object(name, x, y, w, h, *lines):
    body = "\n".join(lines)
    return (
        f"object {name}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n{body}\nendObjectProperties\n"
    )


def text_control(pv, y=10):
    return edm_object("activeXTextDspClass", 10, y, 100, 20, f'controlPv "{pv}"')


def rectangle(vis_pv, y=40):
    # Shown while the variable is 1.
    return edm_object("activeRectangleClass", 150, y, 50, 20, f'visPv "{vis_pv}"', 'visMin "1"', 'visMax "2"')


def message_button(pv, value, vis_pv=None):
    lines = [f'controlPv "{pv}"', f'pressValue "{value}"', 'onLabel "go"']
    if vis_pv:
        lines += [f'visPv "{vis_pv}"', 'visMin "0"', 'visMax "1"']
    return edm_object("activeMessageButtonClass", 250, 10, 60, 20, *lines)


def group(vis_pv, *objects):
    return edm_object(
        "activeGroupClass", 250, 40, 60, 20, f'visPv "{vis_pv}"', 'visMin "1"', 'visMax "2"', "beginGroup"
    ).replace("\nendObjectProperties\n", "\n" + "".join(objects) + "endGroup\nendObjectProperties\n")


def embedded(files, y, source="file", file_pv=None, symbols=()):
    if source == "file":
        # A file window opens its file attribute (pip.cc).
        (file,) = files
        lines = ['displaySource "file"', f'file "{file}"']
    else:
        lines = [f'displaySource "{source}"', f"numDsps {len(files)}", "displayFileName {"]
        lines += [f'  {i} "{f}"' for i, f in enumerate(files)] + ["}"]
    if file_pv:
        lines.append(f'filePv "{file_pv}"')
    if symbols:
        lines += ["symbols {"] + [f'  {i} "{s}"' for i, s in enumerate(symbols)] + ["}"]
    return edm_object("activePipClass", 10, y, 200, 100, *lines, "noScroll")


def choice(pv):
    # Tall and away from the window, so it does not read as a tab bar.
    return edm_object("activeChoiceButtonClass", 350, 300, 20, 60, f'controlPv "{pv}"')


def convert_screen(directory, name, *objects):
    source = directory / f"{name}.edl"
    source.write_text(HEADER + "".join(objects))
    convert(str(source), str(directory / f"{name}.ui"))
    return directory / f"{name}.ui"


def loc_names(text):
    return set(re.findall(r"loc://([^?&\s\"',<]+)", text))


def window_ids(ui_path):
    """The EDM_W macro of each embedded display, in document order."""
    root = ET.parse(ui_path).getroot()
    return [
        json.loads(widget.find("property[@name='macros']/string").text)
        for widget in root.iter("widget")
        if widget.get("class") == "PyDMEmbeddedDisplay"
    ]


@pytest.fixture
def out(tmp_path, monkeypatch):
    # The converter logs skipped widget classes to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "out"
    directory.mkdir()
    return directory


def test_every_use_of_a_window_variable_names_it_the_same(out):
    ui = convert_screen(
        out,
        "screen",
        # A menu window switched by message buttons (not paired, keeps its filePv)...
        embedded(["a.edl", "b.edl"], 100, source="menu", file_pv=r"LOC\\$(!W)tab=i:0"),
        message_button(r"LOC\\$(!W)tab", "1", vis_pv=r"LOC\\$(!W)tab"),
        group(r"LOC\\$(!W)tab", rectangle(r"LOC\\$(!W)tab")),
        # ...and one a choice button switches (stacked displays with visibility rules).
        embedded(["c.edl", "d.edl"], 250, source="menu", file_pv=r"LOC\\$(!W)v=e:0,C,D"),
        choice(r"LOC\\$(!W)v"),
    )
    text = ui.read_text()
    assert "__UNIQUE__" not in text
    # Channels, rules and the window's own channel name one variable each, for
    # PyDM to substitute once per loaded copy.
    assert loc_names(text) == {"${EDM_W}tab", "${EDM_W}v"}


def test_two_menu_windows_on_one_window_variable_both_switch(out):
    # As in event/trig_linac_sector.edl: pairing the first window must leave the
    # second still naming the variable its users name.
    ui = convert_screen(
        out,
        "screen",
        embedded(["a.edl", "b.edl"], 10, source="menu", file_pv=r"LOC\\$(!W)v=e:0,A,B"),
        embedded(["c.edl", "d.edl"], 150, source="menu", file_pv=r"LOC\\$(!W)v=e:0,A,B"),
        choice(r"LOC\\$(!W)v"),
    )
    root = ET.parse(ui).getroot()
    displays = [w for w in root.iter("widget") if w.get("class") == "PyDMEmbeddedDisplay"]
    rules = [json.loads(d.find("property[@name='rules']/string").text) for d in displays]
    assert [rule[0]["channels"][0]["channel"] for rule in rules] == ["loc://${EDM_W}v"] * 4


def test_each_embedded_display_gets_its_own_window_id(out):
    objects = (
        embedded(["child.edl"], 10, source="menu", file_pv=r"LOC\\sel=i:0", symbols=["DEV=A"]),
        embedded(["child.edl"], 120),
        embedded(["c.edl", "d.edl"], 230, source="menu", file_pv=r"LOC\\$(!W)v=e:0,C,D"),
        choice(r"LOC\\$(!W)v"),
    )
    ui = convert_screen(out, "parent", *objects)
    macros = window_ids(ui)
    ids = [m.pop("EDM_W") for m in macros]
    assert len(ids) == 4 and len(set(ids)) == 4
    # Built on the top-level copy's id, never on EDM_W itself, so a screen
    # opened without it does not substitute its own name over and over.
    assert all(re.fullmatch(r"\$\{EDM_W_ROOT\}[0-9a-f]{8}_\d", i) for i in ids)
    assert macros[0] == {"DEV": "A"}

    # The same ids on every conversion; another screen's embedding sites differ.
    assert [m["EDM_W"] for m in window_ids(convert_screen(out, "parent", *objects))] == ids
    other = [m["EDM_W"] for m in window_ids(convert_screen(out, "other", *objects))]
    assert not set(other) & set(ids)


@pytest.fixture
def parent_with_two_children(out):
    """A screen embedding a $(!W) screen twice, with a variable of the same name of its own."""
    convert_screen(
        out,
        "child",
        text_control(r"LOC\\$(!W)flag=i:0"),
        rectangle(r"LOC\\$(!W)flag=i:0"),
    )
    return convert_screen(
        out,
        "parent",
        text_control(r"LOC\\$(!W)flag=i:5", y=370),
        embedded(["child.edl"], 10),
        embedded(["child.edl"], 150),
    )


def open_screen(qtbot, path, macros=None):
    from pydm.display import load_file
    from pydm.widgets import PyDMEmbeddedDisplay

    screen = load_file(str(path), macros=macros, target=None)
    qtbot.addWidget(screen)
    screen.show()
    children = screen.findChildren(PyDMEmbeddedDisplay)
    qtbot.waitUntil(lambda: all(child.embedded_widget is not None for child in children), timeout=3000)
    return screen, [child.embedded_widget for child in children]


def variable(widget):
    """The loc:// variable a widget's channel names, as loaded."""
    return widget.channel.split("://", 1)[1].split("?", 1)[0]


def connection(name):
    from pydm.data_plugins import plugin_for_address

    return plugin_for_address("loc://x").connections.get(name)


@pytest.mark.parametrize("macros", [None, {"EDM_W": "a", "EDM_W_ROOT": "a"}], ids=["plain", "root-id"])
def test_embedded_copies_keep_their_own_local_variables(parent_with_two_children, qtbot, macros):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMDrawingRectangle, PyDMLineEdit

    screen, copies = open_screen(qtbot, parent_with_two_children, macros)
    (own,) = [w for w in screen.findChildren(PyDMLineEdit) if not any(c.isAncestorOf(w) for c in copies)]
    edits = [copy.findChild(PyDMLineEdit) for copy in copies]
    rects = [copy.findChild(PyDMDrawingRectangle) for copy in copies]

    names = [variable(edit) for edit in edits]
    # In one copy the text control and the visibility rule share the variable.
    for name, rect in zip(names, rects):
        (rule,) = json.loads(rect.rules)
        assert rule["channels"][0]["channel"].startswith(f"loc://{name}?")
    # The parent and each copy have their own, short even when opened without
    # the root id (no repeated substitution).
    assert len({variable(own), *names}) == 3
    assert all(len(name) < 40 for name in [variable(own), *names])

    qtbot.waitUntil(lambda: all(connection(name) is not None for name in names), timeout=3000)
    connection(names[0]).put_value(1)
    qtbot.waitUntil(lambda: edits[0].text() == "1" and not rects[0].isHidden(), timeout=3000)
    assert edits[1].text() == "0" and rects[1].isHidden()
    assert own.text() == "5"


def test_two_copies_opened_with_their_own_root_id_share_nothing(parent_with_two_children, qtbot):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLineEdit

    names = []
    for window_id in ("a", "b"):
        screen, _ = open_screen(qtbot, parent_with_two_children, {"EDM_W": window_id, "EDM_W_ROOT": window_id})
        names += [variable(edit) for edit in screen.findChildren(PyDMLineEdit)]
    assert len(names) == 6 and len(set(names)) == 6


MENU_MUX_SCREEN = (
    HEADER
    + edm_object(
        "menuMuxClass",
        10,
        10,
        100,
        25,
        'initialState "0"',
        "numItems 2",
        'symbolTag {\n  0 "Off"\n  1 "On"\n}',
        'symbol0 {\n  0 "FLAG"\n  1 "FLAG"\n}',
        'value0 {\n  0 "0"\n  1 "1"\n}',
    )
    + text_control(r"LOC\\$(!W)menumuxFlag=i:$(FLAG)", y=50)
)


def test_two_open_menu_mux_screens_keep_their_own_local_variables(out, qtbot, monkeypatch):
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets import PyDMLineEdit
    from qtpy.QtWidgets import QComboBox

    source = out / "screen.edl"
    source.write_text(MENU_MUX_SCREEN)
    convert(str(source), str(out / "screen.ui"))
    # Load as on a PyDM install without the converter.
    for module in ("pydmconverter", "pydmconverter.edm", "pydmconverter.edm.parser"):
        monkeypatch.setitem(sys.modules, module, None)

    screens = [load_file(str(out / "screen.py"), target=None) for _ in range(2)]
    for screen in screens:
        qtbot.addWidget(screen)
        screen.show()

    def names():
        """The variable each screen's embedded .ui, as loaded now, names."""
        return [variable(screen.embedded.embedded_widget.findChild(PyDMLineEdit)) for screen in screens]

    def values():
        return [getattr(connection(name), "value", None) for name in first]

    qtbot.waitUntil(lambda: all(screen.embedded.embedded_widget is not None for screen in screens), timeout=3000)
    first = names()
    assert first[0] != first[1]

    qtbot.waitUntil(lambda: values() == [0, 0], timeout=3000)
    screens[0].findChild(QComboBox).setCurrentIndex(1)
    qtbot.waitUntil(lambda: values()[0] == 1, timeout=3000)
    assert values()[1] == 0
    # A menu change keeps the window, and so the variable's name.
    assert names() == first


def test_menu_mux_values_using_the_window_macro_name_this_window(out):
    source = out / "screen.edl"
    source.write_text(
        HEADER
        + edm_object(
            "menuMuxClass",
            10,
            10,
            100,
            25,
            'initialState "0"',
            "numItems 2",
            'symbolTag {\n  0 "A"\n  1 "B"\n}',
            'symbol0 {\n  0 "CH"\n  1 "CH"\n}',
            'value0 {\n  0 "$(!W)a"\n  1 "$(!W)b"\n}',
        )
        + text_control(r"LOC\\$(!W)x=i:0", y=50)
    )
    convert(str(source), str(out / "screen.ui"))
    # EDM expands a menu value's $(!W) in the window showing the menu, as in the .ui.
    text = (out / "screen.py").read_text()
    assert "__UNIQUE__" not in text
    assert "${EDM_W}a" in text and "${EDM_W}b" in text


@pytest.mark.parametrize(
    "labels",
    [
        # Without symbolTag the converter labels each item by its first macro's value.
        'symbol0 {\n  0 "CH"\n  1 "CH"\n}\nvalue0 {\n  0 "$(!W)a"\n  1 "$(!W)b"\n}',
        'symbolTag {\n  0 "$(!W)a"\n  1 "$(!W)b"\n}',
    ],
    ids=["value-labels", "tags"],
)
def test_menu_mux_labels_name_the_window_macro(out, labels):
    source = out / "screen.edl"
    source.write_text(
        HEADER
        + edm_object("menuMuxClass", 10, 10, 100, 25, 'initialState "0"', "numItems 2", labels)
        + text_control(r"LOC\\$(!W)x=i:0", y=50)
    )
    convert(str(source), str(out / "screen.ui"))
    text = (out / "screen.py").read_text()
    assert "__UNIQUE__" not in text
    (menus,) = [
        ast.literal_eval(node.value)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "attr", None) == "menus"
    ]
    assert menus[0]["items"] == ["${EDM_W}a", "${EDM_W}b"]


def channel_button(value, y):
    """A bcs/BCS_Zone_3_Input.edl toggle writing its channel number."""
    return edm_object(
        "activeMessageButtonClass",
        10,
        y,
        150,
        50,
        r'controlPv "LOC\\$(!W)intPv=intPv=ShowChannels"',
        f'pressValue "{value}"',
        'releaseValue "0"',
        f'onLabel "ch{value}"',
        f'offLabel "ch{value}"',
        # Colours that differ split it into an off and an on button.
        "onColor index 56",
        "offColor index 55",
        "toggle",
    )


def channel_group(value, y):
    """The BCS group shown while the variable is the given channel number."""
    return edm_object(
        "activeGroupClass",
        200,
        y,
        50,
        20,
        "beginGroup\n" + edm_object("activeRectangleClass", 200, y, 50, 20) + "endGroup",
        r'visPv "LOC\\$(!W)intPv=ShowChannels"',
        f'visMin "{value}"',
        f'visMax "{value + 1}"',
    )


def test_both_forms_of_a_window_variable_name_one_int(out, qtbot):
    """bcs/BCS_Zone_3_Input.edl declares LOC\\$(!W)intPv=intPv=ShowChannels on its
    buttons, then names LOC\\$(!W)intPv=ShowChannels on its groups. EDM reads "i" as
    the type, skips "n" and reads "tPv" with atol, an int holding 0, and ignores the
    later declaration's attributes (loc_pv_factory.cc)."""
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMDrawingRectangle, PyDMPushButton

    ui = convert_screen(
        out, "screen", channel_button(1, 10), channel_button(2, 70), channel_group(1, 10), channel_group(2, 70)
    )
    screen, _ = open_screen(qtbot, ui)
    buttons = screen.findChildren(PyDMPushButton)
    (name,) = {variable(button) for button in buttons}
    off = [button for button in buttons if button.objectName().endswith("_off")]
    assert len(off) == 2
    one, two = sorted(screen.findChildren(PyDMDrawingRectangle), key=lambda rect: rect.y())

    qtbot.waitUntil(lambda: getattr(connection(name), "value", None) == 0, timeout=3000)
    assert type(connection(name).value) is int
    # Every off button shows, so there is something to press; no group shows yet.
    qtbot.waitUntil(lambda: all(not button.isHidden() for button in off), timeout=3000)
    assert one.isHidden() and two.isHidden()

    connection(name).put_value(2)
    qtbot.waitUntil(lambda: not two.isHidden(), timeout=3000)
    assert one.isHidden()
