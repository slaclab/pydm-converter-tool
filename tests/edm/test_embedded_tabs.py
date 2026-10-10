"""EDM choice buttons driving a menu embedded window (activePipClass with
displaySource "menu"): a button sitting on the window becomes a QTabWidget, any
other arrangement keeps the button and switches one display per file (#144).
A menu mux writing the variable always switches one display per file."""

import ast
import json
import re
import textwrap
import xml.etree.ElementTree as ET

import pytest
from pydm.widgets import PyDMEmbeddedDisplay as QtEmbeddedDisplay
from qtpy import uic

from pydmconverter.edm.converter import convert
from pydmconverter.edm.parser import EDMFileParser
from pydmconverter.widgets import edm_to_ui_filename

HEADER = """\
4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 1162
h 538
endScreenProperties
"""


def pip(file_pv, files, x=4, y=24, w=1148, h=508, labels=(), symbols=()):
    """files, labels and symbols are lists (indexed 0, 1, ...) or {EDM index: value}
    dicts, for blocks that skip indices or start at 1."""

    def block(name, values):
        if not values:
            return ""
        items = values.items() if isinstance(values, dict) else enumerate(values)
        lines = "\n".join(f'  {i} "{v}"' for i, v in items)
        return f"{name} {{\n{lines}\n}}\n"

    num_dsps = max(files) + 1 if isinstance(files, dict) else len(files)
    return (
        "object activePipClass\nbeginObjectProperties\nmajor 4\nminor 1\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n"
        f'displaySource "menu"\nfilePv "{file_pv}"\nnumDsps {num_dsps}\n'
        + block("displayFileName", files)
        + block("menuLabel", labels)
        + block("symbols", symbols)
        + "noScroll\nendObjectProperties\n"
    )


def choice(control_pv, x=12, y=4, w=328, h=20, orientation="horizontal"):
    # orientation=None omits the line: EDM leaves the property out more often than not.
    line = f'orientation "{orientation}"\n' if orientation else ""
    return (
        "object activeChoiceButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x {x}\ny {y}\nw {w}\nh {h}\ncontrolPv "{control_pv}"\n'
        f'font "helvetica-medium-r-12.0"\n{line}endObjectProperties\n'
    )


def labeled_group(vis_pv, vis_min, vis_max, x=600, y=4, w=180, h=16):
    """A group whose visibility rides the given PV, wrapping one static label."""
    return (
        "object activeGroupClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x {x}\ny {y}\nw {w}\nh {h}\nvisPv "{vis_pv}"\nvisMin {vis_min}\nvisMax {vis_max}\n'
        "beginGroup\n"
        "object activeXTextClass\nbeginObjectProperties\nmajor 4\nminor 1\nrelease 1\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\nvalue {{\n" + '  "Infrastructure"\n}\n'
        "endObjectProperties\n"
        "endGroup\n"
        "endObjectProperties\n"
    )


def message_button(control_pv, press_value):
    # press_value=None leaves pressValue out, as EDM does for a button writing only on release.
    press = "" if press_value is None else f'pressValue "{press_value}"\n'
    return (
        "object activeMessageButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x 404\ny 4\nw 124\nh 20\ncontrolPv "{control_pv}"\n{press}'
        'onLabel "li21"\nendObjectProperties\n'
    )


def convert_objects(tmp_path, *objects):
    source = tmp_path / "screen.edl"
    output = tmp_path / "screen.ui"
    source.write_text(HEADER + "\n".join(textwrap.dedent(o) for o in objects))
    convert(str(source), str(output))
    return ET.parse(output).getroot()


def top_level(root):
    return root.find(".//widget[@name='centralwidget']").findall("widget")


def prop(widget, name):
    element = widget.find(f"property[@name='{name}']")
    if element is None:
        return None
    value = element[0]
    if value.tag == "rect":
        return tuple(int(value.find(k).text) for k in ("x", "y", "width", "height"))
    return value.text


def loaded_macros(tmp_path, qtbot):
    """Load the converted screen in PyDM and return its embedded display's macros,
    without the window id every one gets (see window_macros)."""
    window = uic.loadUi(str(tmp_path / "screen.ui"))
    qtbot.addWidget(window)
    (display,) = window.findChildren(QtEmbeddedDisplay)
    macros = display.parsed_macros()
    assert macros.pop("EDM_W").startswith("${EDM_W_ROOT}")
    return macros


def custom_classes(root):
    return {c.find("class").text for c in root.iter("customwidget")}


def own_macros(display):
    """An embedded display's macros without the window id every one gets (see window_macros)."""
    macros = json.loads(prop(display, "macros"))
    assert macros.pop("EDM_W").startswith("${EDM_W_ROOT}")
    return macros


LASER = r"LOC\\laserDispPV=e:0,Drive Laser,Laser Heater,Infrastructure"
LASER_FILES = ["lasr_gunb_main_drivelaser.edl", "lasr_gunb_main_heater.edl", "lasr_gunb_main_misc.edl"]


def test_choice_button_on_menu_window_becomes_tabs(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(LASER, LASER_FILES, labels=["Driver Laser", "Laser Heater", "Misc"]),
        choice(r"LOC\\laserDispPV=e:0"),
    )
    (tabs,) = top_level(root)
    assert tabs.get("class") == "QTabWidget"
    # Covers the choice button and the window: x from the window, y from the button.
    assert prop(tabs, "geometry") == (4, 4, 1148, 528)
    assert prop(tabs, "channel") is None

    pages = tabs.findall("widget")
    # Titles are the variable's enum strings (what EDM's button shows), not menuLabel.
    assert [p.find("attribute[@name='title']/string").text for p in pages] == [
        "Drive Laser",
        "Laser Heater",
        "Infrastructure",
    ]
    displays = [p.find("widget") for p in pages]
    assert [prop(d, "filename") for d in displays] == [
        "lasr_gunb_main_drivelaser.ui",
        "lasr_gunb_main_heater.ui",
        "lasr_gunb_main_misc.ui",
    ]
    # Each page holds the window at its own size, below a tab bar as tall as the button.
    assert {prop(d, "geometry") for d in displays} == {(0, 0, 1148, 508)}
    style = prop(tabs, "styleSheet")
    assert "QTabWidget::tab-bar { left: 8px; }" in style
    assert "height: 18px;" in style
    assert "PyDMEmbeddedDisplay" in custom_classes(root)


def test_tab_pages_take_their_own_macros_and_extensionless_names(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(
            r"LOC\\$(!W)chose=e:1,LongTerm,ShortTerm",
            ["adsGraphEmb.edl", "adsGraphEmb"],
            symbols=["P=UND1,N=LTC", "P=UND1,N=STC"],
        ),
        choice(r"LOC\\$(!W)chose"),
    )
    (tabs,) = top_level(root)
    displays = [p.find("widget") for p in tabs.findall("widget")]
    assert [prop(d, "filename") for d in displays] == ["adsGraphEmb.ui", "adsGraphEmb.ui"]
    assert [own_macros(d) for d in displays] == [
        {"P": "UND1", "N": "LTC"},
        {"P": "UND1", "N": "STC"},
    ]
    # The variable starts at 1, so the second tab opens first.
    assert prop(tabs, "currentIndex") == "1"


def test_variable_shared_with_another_widget_switches_stacked_displays(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(LASER, LASER_FILES),
        choice(r"LOC\\laserDispPV=e:0"),
        message_button(r"LOC\\laserDispPV=e:0", "1"),
    )
    widgets = top_level(root)
    assert [w.get("class") for w in widgets] == [
        "PyDMEmbeddedDisplay",
        "PyDMEmbeddedDisplay",
        "PyDMEmbeddedDisplay",
        "PyDMEnumButton",
        "PyDMPushButton",
    ]
    displays, enum_button, message = widgets[:3], widgets[3], widgets[4]
    assert [prop(d, "filename") for d in displays] == [
        "lasr_gunb_main_drivelaser.ui",
        "lasr_gunb_main_heater.ui",
        "lasr_gunb_main_misc.ui",
    ]
    assert {prop(d, "geometry") for d in displays} == {(4, 24, 1148, 508)}
    for index, display in enumerate(displays):
        (rule,) = json.loads(prop(display, "rules"))
        assert rule["expression"] == f"(float(ch[0]) >= {index}.0 and float(ch[0]) < {index + 1}.0)"
        assert rule["channels"][0]["channel"] == "loc://laserDispPV"
        # Qt sizes the screen to what shows first, so the starting display is not hidden.
        assert rule["initial_value"] == ("true" if index == 0 else "false")

    # Both writers carry the full definition, so the enum button gets its states
    # whichever widget connects first.
    definition = "loc://laserDispPV?type=int&init=0&enum_string=['Drive Laser', 'Laser Heater', 'Infrastructure']"
    assert prop(enum_button, "channel") == definition
    assert prop(message, "channel") == definition


def test_choice_button_away_from_window_keeps_edm_layout(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(LASER, LASER_FILES[:2], y=4, h=400),
        choice(r"LOC\\laserDispPV=e:0", y=420),
    )
    classes = [w.get("class") for w in top_level(root)]
    assert classes == ["PyDMEmbeddedDisplay", "PyDMEmbeddedDisplay", "PyDMEnumButton"]


def test_menu_window_without_choice_button_shows_its_starting_entry(tmp_path, qtbot):
    root = convert_objects(
        tmp_path,
        pip(
            r"LOC\\myLocalPV=e:1",
            ["GigE_controls", "GigE_other.edl"],
            symbols=["P=PROF:,ID=1020", "P=PROF:,ID=1800"],
        ),
    )
    (display,) = top_level(root)
    assert prop(display, "filename") == "GigE_other.ui"
    assert own_macros(display) == {"P": "PROF:", "ID": "1800"}
    assert loaded_macros(tmp_path, qtbot) == {"P": "PROF:", "ID": "1800"}


def test_menu_window_shows_its_entry_over_its_file(tmp_path):
    source = pip(r"LOC\\myLocalPV=e:1", ["GigE_controls", "GigE_other.edl"])
    root = convert_objects(tmp_path, source.replace('displaySource "menu"\n', 'displaySource "menu"\nfile "unused"\n'))
    (display,) = top_level(root)
    assert prop(display, "filename") == "GigE_other.ui"


@pytest.mark.parametrize("file_pv_line", [r'filePv "LOC\\sel=i:0"' "\n", ""])
def test_menu_window_without_entries_ignores_its_file(tmp_path, file_pv_line):
    # EDM (pip.cc) opens a menu window's displayFileName entries only, when it has
    # a filePv and numDsps > 0; it never opens its file attribute.
    source = pip("unused", []).replace('filePv "unused"\n', file_pv_line)
    root = convert_objects(
        tmp_path, source.replace('displaySource "menu"\n', 'displaySource "menu"\nfile "fallback"\n')
    )
    (display,) = top_level(root)
    assert display.get("class") == "PyDMEmbeddedDisplay"
    assert prop(display, "filename") is None


def test_file_window_opens_its_file_not_a_menu_entry(tmp_path):
    # EDM (pip.cc) opens a file window's file attribute (macros expanded from the
    # parent); displayFileName and symbols belong to menu entries, which a window
    # switched from "menu" to "file" keeps but ignores (misc/opsKlys_disp_li24.edl).
    source = pip(
        r"$(sector)", ["opsKlys_sector_li20", "opsKlys_sector_noepics"], symbols=["sector=LI20", "sector=LI21"]
    )
    root = convert_objects(
        tmp_path, source.replace('displaySource "menu"\n', 'displaySource "file"\nfile "opsKlys_sector_$(sector)"\n')
    )
    (display,) = top_level(root)
    assert prop(display, "filename") == "opsKlys_sector_${sector}.ui"
    assert own_macros(display) == {}


@pytest.mark.parametrize("symbols", [["sector=LI20"], ["sector=LI20", "sector=LI21"]])
def test_file_window_ignores_symbols(tmp_path, qtbot, symbols):
    # EDM (pip.cc) opens a file window with the parent's macros only: symbols belong
    # to a menu window's entries, so a window switched to "file" ignores them.
    source = pip(r"$(sector)", ["sector_li20", "sector_li21"][: len(symbols)], symbols=symbols)
    root = convert_objects(tmp_path, source.replace('displaySource "menu"', 'displaySource "file"\nfile "sector_li20"'))
    (display,) = top_level(root)
    assert prop(display, "filename") == "sector_li20.ui"
    assert own_macros(display) == {}
    assert loaded_macros(tmp_path, qtbot) == {}


@pytest.mark.parametrize("file_line", ["", 'file ""\n'])
def test_file_window_without_a_file_shows_nothing(tmp_path, file_line):
    # EDM opens nothing when a file window's file is blank (fileExists = 0).
    source = pip(r"$(sector)", ["RESwaveforms", "RESwaveforms"])
    root = convert_objects(tmp_path, source.replace('displaySource "menu"\n', f'displaySource "file"\n{file_line}'))
    (display,) = top_level(root)
    assert display.get("class") == "PyDMEmbeddedDisplay"
    assert prop(display, "filename") is None


def test_string_pv_window_opens_its_local_variable_value(tmp_path):
    # No displaySource line means "stringPV": the window opens the file its filePv
    # names, which for a LOC string is its initial value (misc/tdsEmbd.edl).
    source = pip(r"LOC\\showMe=s:tdsVert", [], symbols=[])
    root = convert_objects(tmp_path, source.replace('displaySource "menu"\n', 'file "unused"\n'))
    (display,) = top_level(root)
    assert prop(display, "filename") == "tdsVert.ui"


def test_string_pv_window_on_a_channel_shows_nothing(tmp_path):
    # The file name is the PV's value at runtime, which a .ui file cannot follow.
    source = pip("CUDBMPR:MCC0:VIDEO1", ["GigE_controls"])
    root = convert_objects(tmp_path, source.replace('displaySource "menu"\n', ""))
    (display,) = top_level(root)
    assert prop(display, "filename") is None


def test_edm_to_ui_filename():
    assert edm_to_ui_filename("screen.edl") == "screen.ui"
    assert edm_to_ui_filename("screen") == "screen.ui"
    assert edm_to_ui_filename("screen.ui") == "screen.ui"
    assert edm_to_ui_filename("GigE_v1.2") == "GigE_v1.2.ui"
    assert edm_to_ui_filename("composite file calc.edl;P=$(P),N=1") == "composite file calc.ui"


def test_group_using_the_variable_switches_stacked_displays(tmp_path):
    # The button sits on the window, but a group's visibility also rides the
    # variable, so tabs (which would delete the window) would break the group.
    root = convert_objects(
        tmp_path,
        pip(LASER, LASER_FILES),
        choice(r"LOC\\laserDispPV=e:0"),
        labeled_group(r"LOC\\laserDispPV", 1, 2),
    )
    widgets = top_level(root)
    classes = [w.get("class") for w in widgets]
    assert "QTabWidget" not in classes
    assert classes.count("PyDMEmbeddedDisplay") == 3
    assert "PyDMEnumButton" in classes

    (label,) = [w for w in widgets if w.get("class") == "PyDMLabel"]
    (rule,) = json.loads(prop(label, "rules"))
    assert rule["channels"][0]["channel"].startswith("loc://laserDispPV")


def test_choice_button_without_orientation_still_reads_as_a_tab_bar(tmp_path):
    # EDM lays the states out to fill the rect, so a wide button is a tab bar
    # whether or not the file bothers to declare an orientation.
    root = convert_objects(
        tmp_path,
        pip(LASER, LASER_FILES),
        choice(r"LOC\\laserDispPV=e:0", orientation=None),
    )
    (tabs,) = top_level(root)
    assert tabs.get("class") == "QTabWidget"
    assert len(tabs.findall("widget")) == 3


def test_unique_marker_resolved_on_the_stacked_path(tmp_path):
    source = tmp_path / "screen.edl"
    output = tmp_path / "screen.ui"
    source.write_text(
        HEADER
        + pip(r"LOC\\$(!W)v=e:0,A,B", ["embA.edl", "embB.edl"])
        # Tall and far below the window: not a tab bar, so the pair stacks.
        + choice(r"LOC\\$(!W)v", x=12, y=400, w=20, h=60, orientation="vertical")
    )
    convert(str(source), str(output))
    text = output.read_text()
    assert "__UNIQUE__" not in text

    root = ET.parse(output).getroot()
    widgets = top_level(root)
    channels = set()
    for widget in widgets:
        rules = prop(widget, "rules")
        for rule in json.loads(rules) if rules else []:
            channels.update(c["channel"] for c in rule["channels"])
        if widget.get("class") == "PyDMEnumButton":
            channels.add(prop(widget, "channel"))
    assert channels
    # Every reference names one variable: the screen's window macro plus the bare name.
    names = {c.split("://", 1)[1].split("?", 1)[0] for c in channels}
    assert names == {"${EDM_W}v"}


def test_site_skipping_choice_buttons_leaves_the_pair_alone(tmp_path):
    from pydmconverter.edm.converter_helpers import TAB_PAGES, pair_menu_pips
    from pydmconverter.edm.parser import EDMFileParser

    source = tmp_path / "screen.edl"
    source.write_text(HEADER + pip(LASER, LASER_FILES) + choice(r"LOC\\laserDispPV=e:0"))
    parser = EDMFileParser(str(source), str(tmp_path / "screen.ui"))

    pair_menu_pips(parser.ui, {}, skip_widgets={"activechoicebuttonclass"})

    names = [obj.name.lower() for obj in parser.ui.objects]
    assert "activepipclass" in names
    (button,) = [obj for obj in parser.ui.objects if obj.name.lower() == "activechoicebuttonclass"]
    assert TAB_PAGES not in button.properties


def test_choice_button_without_channel_stays_an_empty_tab_widget(tmp_path):
    source = choice("").replace('controlPv ""\n', "")
    (tabs,) = top_level(convert_objects(tmp_path, source))
    assert tabs.get("class") == "QTabWidget"
    assert tabs.findall("widget") == []
    assert prop(tabs, "styleSheet") is None


def menu_mux(control_pv, initial_state=None, x=710, y=4, w=75, h=20):
    """A menu mux whose screen writes the chosen item's index to control_pv,
    laid out as in b34/profile_b34.edl."""
    state = f'initialState "{initial_state}"\n' if initial_state is not None else ""
    return (
        "object menuMuxClass\nbeginObjectProperties\nmajor 4\nminor 1\nrelease 0\n"
        f'x {x}\ny {y}\nw {w}\nh {h}\ncontrolPv "{control_pv}"\n{state}'
        'numItems 2\nsymbolTag {\n  0 "OFF"\n  1 "ON"\n}\nendObjectProperties\n'
    )


@pytest.fixture
def convert_with_menus(tmp_path, monkeypatch):
    """convert_objects, also returning the menus of the generated menu mux screen."""
    # The converter logs skipped widget classes (menuMuxClass) to a file in the cwd.
    monkeypatch.chdir(tmp_path)

    def run(*objects):
        root = convert_objects(tmp_path, *objects)
        module = ast.parse((tmp_path / "screen.py").read_text())
        (menus,) = [
            ast.literal_eval(node.value)
            for node in ast.walk(module)
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "attr", None) == "menus"
        ]
        return root, menus

    return run


def switched_displays(root):
    """(filename, rule channel, starts visible) for each top-level embedded display."""
    displays = []
    for widget in top_level(root):
        if widget.get("class") == "PyDMEmbeddedDisplay":
            (rule,) = json.loads(prop(widget, "rules"))
            (channel,) = rule["channels"]
            displays.append((prop(widget, "filename"), channel["channel"], rule["initial_value"] == "true"))
    return displays


CAMERA_FILES = ["Rectangle.edl", "CamImage.edl"]


def test_menu_mux_switches_displays_starting_at_its_initial_state(convert_with_menus):
    # b34/profile_b34.edl: nothing configures LOC\Display, so the menu declares
    # it when its screen runs, starting at initialState.
    root, (menu,) = convert_with_menus(
        pip(r"LOC\\Display", CAMERA_FILES, x=620, y=195, w=165, h=125),
        menu_mux(r"LOC\\Display", initial_state="1"),
    )
    assert [w.get("class") for w in top_level(root)] == ["PyDMEmbeddedDisplay", "PyDMEmbeddedDisplay"]
    # The displays read the bare variable and start on the menu's item...
    assert switched_displays(root) == [
        ("Rectangle.ui", "loc://Display", False),
        ("CamImage.ui", "loc://Display", True),
    ]
    # ...which the screen declares the same way.
    assert menu["controlPv"] == "loc://Display?type=int&init=1"


def test_menu_mux_never_becomes_tabs(convert_with_menus):
    # Where a choice button would read as a tab bar: the menu is not in the .ui.
    root, (menu,) = convert_with_menus(
        pip(r"LOC\\Display", CAMERA_FILES),
        menu_mux(r"LOC\\Display", initial_state="1", x=12, y=4, w=328, h=20),
    )
    assert [w.get("class") for w in top_level(root)] == ["PyDMEmbeddedDisplay", "PyDMEmbeddedDisplay"]
    assert [starts for _, _, starts in switched_displays(root)] == [False, True]


@pytest.mark.parametrize(
    "file_pv, control_pv, initial_state, address, start",
    [
        # The menu's configuration defines the variable (prof/GigE_control_screen.edl).
        (r"LOC\\Display", r"LOC\\Display=i:0", "1", "loc://Display?type=int&init=0", 0),
        # The window's comes first and reaches the menu (prof/XTCAV4Experiments.edl).
        (r"LOC\\Display=i:1", r"LOC\\Display=i:0", "1", "loc://Display?type=int&init=1", 1),
        (r"LOC\\Display=i:1", r"LOC\\Display", "0", "loc://Display?type=int&init=1", 1),
        # With enum strings (prof/aravisGigE_cameras.edl).
        (
            r"LOC\\Display",
            r"LOC\\Display=e:1,OFF,ON",
            "0",
            "loc://Display?type=int&init=1&enum_string=['OFF', 'ON']",
            1,
        ),
        # Nothing configures it: the menu starts at initialState, or at 0 past its items.
        (r"LOC\\Display", r"LOC\\Display", None, "loc://Display?type=int&init=0", 0),
        (r"LOC\\Display", r"LOC\\Display", "5", "loc://Display?type=int&init=0", 0),
        # A start from the screen's macros is known only when it runs, which declares it then.
        (r"LOC\\Display", r"LOC\\Display", "$(START)", "loc://Display", 0),
    ],
)
def test_menu_mux_and_displays_start_together(convert_with_menus, file_pv, control_pv, initial_state, address, start):
    root, (menu,) = convert_with_menus(pip(file_pv, CAMERA_FILES), menu_mux(control_pv, initial_state))
    assert menu["controlPv"] == address
    displays = switched_displays(root)
    assert [starts for _, _, starts in displays] == [index == start for index in range(len(CAMERA_FILES))]
    # Configuration aside, the displays read the variable the menu writes.
    assert {channel.split("?", 1)[0] for _, channel, _ in displays} == {"loc://Display"}


def test_menu_mux_writes_the_resolved_unique_variable(tmp_path, convert_with_menus):
    root, (menu,) = convert_with_menus(
        pip(r"LOC\\$(!W)Display", CAMERA_FILES), menu_mux(r"LOC\\$(!W)Display", initial_state="1")
    )
    assert "__UNIQUE__" not in (tmp_path / "screen.ui").read_text()
    assert "__UNIQUE__" not in (tmp_path / "screen.py").read_text()
    # One variable: the screen's token plus the bare name, in the .ui and the .py.
    names = {channel.split("://", 1)[1].split("?", 1)[0] for _, channel, _ in switched_displays(root)}
    assert names == {menu["controlPv"].split("://", 1)[1].split("?", 1)[0]}
    (name,) = names
    assert name.endswith("Display") and name != "Display"
    assert menu["controlPv"] == f"loc://{name}?type=int&init=1"


def test_choice_button_and_menu_mux_share_the_definition(convert_with_menus):
    root, (menu,) = convert_with_menus(
        pip(r"LOC\\Display", CAMERA_FILES),
        choice(r"LOC\\Display"),
        menu_mux(r"LOC\\Display", initial_state="1"),
    )
    widgets = top_level(root)
    # Two writers: never tabs, even with the button sitting on the window.
    assert [w.get("class") for w in widgets] == ["PyDMEmbeddedDisplay", "PyDMEmbeddedDisplay", "PyDMEnumButton"]
    assert prop(widgets[2], "channel") == menu["controlPv"] == "loc://Display?type=int&init=1"
    assert [starts for _, _, starts in switched_displays(root)] == [False, True]


def test_menu_mux_on_another_variable_leaves_the_window_static(convert_with_menus):
    root, (menu,) = convert_with_menus(
        pip(r"LOC\\Display=i:1", CAMERA_FILES), menu_mux(r"LOC\\DISP", initial_state="0")
    )
    (display,) = top_level(root)
    assert prop(display, "filename") == "CamImage.ui"
    assert json.loads(prop(display, "rules") or "[]") == []
    assert menu["controlPv"] == "loc://DISP"


def test_site_skipping_menu_muxes_leaves_their_window_alone(tmp_path):
    from pydmconverter.edm.converter_helpers import pair_menu_pips
    from pydmconverter.edm.parser import EDMFileParser

    source = tmp_path / "screen.edl"
    source.write_text(HEADER + pip(r"LOC\\Display", CAMERA_FILES) + menu_mux(r"LOC\\Display", initial_state="1"))
    parser = EDMFileParser(str(source), str(tmp_path / "screen.ui"))

    pair_menu_pips(parser.ui, {}, skip_widgets={"menumuxclass"})

    assert [obj.name.lower() for obj in parser.ui.objects] == ["activepipclass", "menumuxclass"]
    assert parser.ui.objects[1].properties["controlPv"] == "loc://Display"


# EDM selects displayFileName[v] for the variable's value v, and symbols[i] and
# menuLabel[i] belong to displayFileName[i]: blocks pair by EDM array index, and
# a file may skip indices or start at 1.
LASER_CHOICE = r"LOC\\laserDispPV=e:0"
LASER_LABELS = ["Driver Laser", "Laser Heater", "Misc"]
LASER_SYMBOLS = ["P=DRV", "P=HTR", "P=MISC"]
DENSE_ARRANGEMENTS = {
    "tabs": lambda: [pip(LASER, LASER_FILES, labels=LASER_LABELS, symbols=LASER_SYMBOLS), choice(LASER_CHOICE)],
    "stacked": lambda: [
        pip(LASER, LASER_FILES, labels=LASER_LABELS, symbols=LASER_SYMBOLS),
        choice(LASER_CHOICE),
        message_button(LASER_CHOICE, "1"),
    ],
    "shown": lambda: [pip(r"LOC\\laserDispPV=e:2", LASER_FILES, labels=LASER_LABELS, symbols=LASER_SYMBOLS)],
}


def normalised_ui(path):
    # Widget names carry id(obj) (repeated in their own styleSheet selectors) or
    # a running count; nothing else differs between two conversions.
    text = re.sub(r"(?<=[A-Za-z])\d{6,}", "#", path.read_text())
    return re.sub(r'name="[^"]*"', lambda name: re.sub(r"\d+", "#", name.group()), text)


@pytest.mark.parametrize("arrangement", DENSE_ARRANGEMENTS)
def test_dense_blocks_convert_as_positional_lists(tmp_path, monkeypatch, arrangement):
    # A dense 0-based block's EDM indices are its positions, so the output matches
    # the parse that drops them (block_items then numbers entries by position).
    objects = DENSE_ARRANGEMENTS[arrangement]()
    (tmp_path / "indexed").mkdir()
    (tmp_path / "positional").mkdir()
    convert_objects(tmp_path / "indexed", *objects)

    remove_prepended_index = EDMFileParser.remove_prepended_index
    monkeypatch.setattr(
        EDMFileParser,
        "remove_prepended_index",
        staticmethod(lambda lines, *args: list(remove_prepended_index(lines, *args))),
    )
    convert_objects(tmp_path / "positional", *objects)

    indexed = normalised_ui(tmp_path / "indexed" / "screen.ui")
    assert indexed == normalised_ui(tmp_path / "positional" / "screen.ui")
    # Each arrangement shows entry 2 somewhere, with its own macros.
    assert "MISC" in indexed


SPARSE = {0: "a.edl", 2: "c.edl"}
SPARSE_SYMBOLS = {2: "P=X"}


def test_sparse_block_tabs_pair_titles_macros_and_start_by_index(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(r"LOC\\v=e:2,A,B,C", SPARSE, symbols=SPARSE_SYMBOLS),
        choice(r"LOC\\v=e:2"),
    )
    (tabs,) = top_level(root)
    pages = tabs.findall("widget")
    # Entry 2's title is the variable's state 2 ("C"), not state 1.
    assert [p.find("attribute[@name='title']/string").text for p in pages] == ["A", "C"]
    displays = [p.find("widget") for p in pages]
    assert [prop(d, "filename") for d in displays] == ["a.ui", "c.ui"]
    assert own_macros(displays[0]) == {}
    assert own_macros(displays[1]) == {"P": "X"}
    # The variable starts at 2, which is the second page.
    assert prop(tabs, "currentIndex") == "1"


def test_sparse_block_stacked_displays_switch_on_their_edm_index(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(r"LOC\\v=e:2,A,B,C", SPARSE, symbols=SPARSE_SYMBOLS),
        choice(r"LOC\\v=e:2"),
        message_button(r"LOC\\v", "1"),
    )
    displays = [w for w in top_level(root) if w.get("class") == "PyDMEmbeddedDisplay"]
    assert [prop(d, "filename") for d in displays] == ["a.ui", "c.ui"]
    assert own_macros(displays[0]) == {}
    assert own_macros(displays[1]) == {"P": "X"}
    rules = [json.loads(prop(d, "rules"))[0] for d in displays]
    assert [r["expression"] for r in rules] == [
        "(float(ch[0]) >= 0.0 and float(ch[0]) < 1.0)",
        "(float(ch[0]) >= 2.0 and float(ch[0]) < 3.0)",
    ]
    assert [r["initial_value"] for r in rules] == ["false", "true"]


@pytest.mark.parametrize(
    "init, filename, macros",
    [
        # symbols { 2 "P=X" } is display 2's alone, even as the only entry.
        (0, "a.ui", None),
        (2, "c.ui", {"P": "X"}),
    ],
)
def test_sparse_block_shown_display_takes_its_own_macros(tmp_path, init, filename, macros):
    root = convert_objects(tmp_path, pip(rf"LOC\\v=e:{init}", SPARSE, symbols=SPARSE_SYMBOLS))
    (display,) = top_level(root)
    assert prop(display, "filename") == filename
    assert own_macros(display) == (macros or {})


ONE_BASED = {1: "a.edl", 2: "b.edl"}
ONE_BASED_BLOCKS = {"labels": {1: "First", 2: "Second"}, "symbols": {1: "P=A", 2: "P=B"}}


def test_one_based_block_tabs(tmp_path):
    root = convert_objects(tmp_path, pip(r"LOC\\v=i:2", ONE_BASED, **ONE_BASED_BLOCKS), choice(r"LOC\\v"))
    (tabs,) = top_level(root)
    pages = tabs.findall("widget")
    # With no enum strings, titles fall back to each entry's own menuLabel.
    assert [p.find("attribute[@name='title']/string").text for p in pages] == ["First", "Second"]
    displays = [p.find("widget") for p in pages]
    assert [prop(d, "filename") for d in displays] == ["a.ui", "b.ui"]
    assert [own_macros(d) for d in displays] == [{"P": "A"}, {"P": "B"}]
    assert prop(tabs, "currentIndex") == "1"


def test_one_based_block_stacked_displays(tmp_path):
    root = convert_objects(
        tmp_path,
        pip(r"LOC\\v=i:1", ONE_BASED, **ONE_BASED_BLOCKS),
        choice(r"LOC\\v"),
        message_button(r"LOC\\v", "2"),
    )
    displays = [w for w in top_level(root) if w.get("class") == "PyDMEmbeddedDisplay"]
    assert [own_macros(d) for d in displays] == [{"P": "A"}, {"P": "B"}]
    rules = [json.loads(prop(d, "rules"))[0] for d in displays]
    assert [r["expression"] for r in rules] == [
        "(float(ch[0]) >= 1.0 and float(ch[0]) < 2.0)",
        "(float(ch[0]) >= 2.0 and float(ch[0]) < 3.0)",
    ]
    assert [r["initial_value"] for r in rules] == ["true", "false"]


@pytest.mark.parametrize(
    "init, filename, macros",
    [
        (2, "b.ui", {"P": "B"}),
        # No entry 0: the window starts on its lowest-numbered entry.
        (0, "a.ui", {"P": "A"}),
    ],
)
def test_one_based_block_shown_display(tmp_path, init, filename, macros):
    (display,) = top_level(convert_objects(tmp_path, pip(rf"LOC\\v=i:{init}", ONE_BASED, **ONE_BASED_BLOCKS)))
    assert prop(display, "filename") == filename
    assert own_macros(display) == macros


# Menu windows that message buttons or a real PV switch.
HOMS = r"LOC\\\\intPV:=0"
HOMS_FILES = ["homs_gantry.edl", "homs_gantry.edl", "homs_emb_pitch.edl"]
HOMS_SYMBOLS = ["M1=Y1,ORIENT=Vertical", "M1=X1,ORIENT=Horizontal", "P=PITCH"]


def with_lines(edm_object, *lines):
    """edm_object with property lines added at its end."""
    return edm_object.replace("endObjectProperties\n", "".join(f"{line}\n" for line in lines) + "endObjectProperties\n")


def menu_button(control_pv):
    return (
        "object activeMenuButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x 404\ny 4\nw 124\nh 20\ncontrolPv "{control_pv}"\nendObjectProperties\n'
    )


def test_message_buttons_writing_indices_switch_stacked_displays(tmp_path):
    # xray/homs_main.edl: invisible message buttons over a drawing write the
    # index of the display to show.
    root = convert_objects(
        tmp_path,
        message_button(HOMS, "2"),
        pip(HOMS, HOMS_FILES, symbols=HOMS_SYMBOLS),
        message_button(HOMS, "0"),
        message_button(HOMS, "1"),
    )
    widgets = top_level(root)
    assert [w.get("class") for w in widgets] == ["PyDMPushButton"] + ["PyDMEmbeddedDisplay"] * 3 + [
        "PyDMPushButton"
    ] * 2
    assert switched_displays(root) == [
        ("homs_gantry.ui", "loc://intPV:", True),
        ("homs_gantry.ui", "loc://intPV:", False),
        ("homs_emb_pitch.ui", "loc://intPV:", False),
    ]
    assert [own_macros(d) for d in widgets[1:4]] == [
        {"M1": "Y1", "ORIENT": "Vertical"},
        {"M1": "X1", "ORIENT": "Horizontal"},
        {"P": "PITCH"},
    ]
    assert {prop(b, "channel") for b in widgets[:1] + widgets[4:]} == {"loc://intPV:?type=int&init=0"}


def test_bare_message_button_gets_the_variable_definition(tmp_path):
    root = convert_objects(tmp_path, pip(r"LOC\\sel=i:1", ["a.edl", "b.edl"]), message_button(r"LOC\\sel", "0"))
    assert switched_displays(root) == [("a.ui", "loc://sel", False), ("b.ui", "loc://sel", True)]
    # The button may connect first; PyDM's local plugin takes the variable's
    # type and initial value from the first channel.
    assert prop(top_level(root)[-1], "channel") == "loc://sel?type=int&init=1"


def test_message_button_writing_a_macro_switches_stacked_displays(tmp_path):
    root = convert_objects(tmp_path, pip(r"LOC\\sel=i:0", ["a.edl", "b.edl"]), message_button(r"LOC\\sel", "$(TAB)"))
    assert [d[0] for d in switched_displays(root)] == ["a.ui", "b.ui"]


def test_message_button_window_starting_at_minus_one_opens_on_entry_zero(tmp_path):
    # A window whose variable starts at -1 writes 0 on its first value rather
    # than popping its menu up (pip.cc), so the variable starts at 0.
    root = convert_objects(tmp_path, pip(r"LOC\\ebwM=i:-1", ["a.edl", "b.edl"]), message_button(r"LOC\\ebwM", "1"))
    assert switched_displays(root) == [("a.ui", "loc://ebwM", True), ("b.ui", "loc://ebwM", False)]
    assert prop(top_level(root)[-1], "channel") == "loc://ebwM?type=int&init=0"


SEL = r"LOC\\sel=i:0"


@pytest.mark.parametrize(
    "objects",
    [
        # A button writing no display index.
        pytest.param([pip(SEL, ["a.edl", "b.edl"]), message_button(SEL, "7")], id="not-an-index"),
        # vac/valve_password.edl: the converted button would not ask for the password.
        pytest.param(
            [pip(SEL, ["a.edl", "b.edl"]), with_lines(message_button(SEL, "1"), 'password "secret"')], id="password"
        ),
        pytest.param(
            [
                pip(SEL, ["a.edl", "b.edl"]),
                message_button(SEL, "1"),
                with_lines(message_button(SEL, "0"), 'releaseValue "-1"'),
            ],
            id="writes-minus-one",
        ),
        # llrf/res4cavity.edl: a "menu" button writes -1 on release, which pops the
        # window's menu up in EDM; the stacked displays would all hide.
        pytest.param(
            [
                pip(r"LOC\\ebwM=i:-1", ["a.edl", "b.edl"]),
                message_button(r"LOC\\ebwM", "1"),
                with_lines(message_button(r"LOC\\ebwM", None), 'releaseValue "-1"'),
            ],
            id="release-writes-minus-one",
        ),
        # cud/facet_bpms.edl: the converted menu button writes nothing.
        pytest.param([pip(SEL, ["a.edl", "b.edl"]), menu_button(SEL)], id="menu-button"),
        # misc/histViewer.edl: a LOC variable the parser leaves untranslated.
        pytest.param([pip(r"LOC\\$(SIG)_View=0", ["a.edl", "b.edl"])], id="untranslated-loc"),
        # A named calculation missing from calc.list stays untranslated.
        pytest.param([pip(r"CALC\\sum(X, Y)", ["a.edl", "b.edl"])], id="untranslated-calc"),
        pytest.param([pip("", ["a.edl", "b.edl"])], id="blank-file-pv"),
        pytest.param([pip("#GDET:FEE1:1:CONFIG", ["a.edl", "b.edl"])], id="comment-file-pv"),
    ],
)
def test_menu_window_nothing_switches_shows_one_display(tmp_path, objects):
    root = convert_objects(tmp_path, *objects)
    displays = [w for w in top_level(root) if w.get("class") == "PyDMEmbeddedDisplay"]
    assert [prop(d, "filename") for d in displays] == ["a.ui"]
    assert not any(rule["property"] == "Visible" for rule in json.loads(prop(displays[0], "rules") or "[]"))


def test_site_skipping_message_buttons_leaves_their_window_alone(tmp_path):
    from pydmconverter.edm.converter_helpers import pair_menu_pips

    source = tmp_path / "screen.edl"
    source.write_text(HEADER + pip(SEL, ["a.edl", "b.edl"]) + message_button(r"LOC\\sel", "1"))
    parser = EDMFileParser(str(source), str(tmp_path / "screen.ui"))

    pair_menu_pips(parser.ui, {}, skip_widgets={"activemessagebuttonclass"})

    assert [obj.name.lower() for obj in parser.ui.objects] == ["activepipclass", "activemessagebuttonclass"]
    assert parser.ui.objects[1].properties["controlPv"] == "loc://sel"


@pytest.mark.parametrize(
    "file_pv, channel",
    [
        # xray/gdet_main.edl
        ("GDET:FEE1:241:CONFIG", "GDET:FEE1:241:CONFIG"),
        # rm/thermoFHT.edl
        ("$(P):CH_DISP01", "${P}:CH_DISP01"),
    ],
)
def test_menu_window_on_a_pv_switches_stacked_displays(tmp_path, file_pv, channel):
    root = convert_objects(
        tmp_path, pip(file_pv, ["gdet_a.edl", "gdet_b.edl"], symbols=["N=1", "N=2"]), choice(file_pv)
    )
    widgets = top_level(root)
    # A choice button on the PV stays one: only a LOC variable's pair becomes tabs.
    assert [w.get("class") for w in widgets] == ["PyDMEmbeddedDisplay", "PyDMEmbeddedDisplay", "PyDMEnumButton"]
    # EDM opens nothing until the PV's first value, so no display starts visible.
    assert switched_displays(root) == [("gdet_a.ui", channel, False), ("gdet_b.ui", channel, False)]
    assert [own_macros(d) for d in widgets[:2]] == [{"N": "1"}, {"N": "2"}]
    assert prop(widgets[2], "channel") == channel


def load_switched_screen(tmp_path, qtbot, macros=None):
    """Load tmp_path/screen.ui in PyDM; return its embedded displays and its
    message buttons by press value."""
    from pydm.display import load_file
    from pydm.widgets import PyDMPushButton

    screen = load_file(str(tmp_path / "screen.ui"), macros=macros, target=None)
    qtbot.addWidget(screen)
    screen.show()
    buttons = {button.pressValue: button for button in screen.findChildren(PyDMPushButton)}
    qtbot.waitUntil(lambda: all(button.value is not None for button in buttons.values()), timeout=3000)
    return screen.findChildren(QtEmbeddedDisplay), buttons


def visible_indices(displays):
    return [index for index, display in enumerate(displays) if display.isVisible()]


def test_message_buttons_switch_displays_in_pydm(tmp_path, qtbot):
    homs = r"LOC\\homsPV=i:0"
    convert_objects(
        tmp_path,
        message_button(homs, "2"),
        pip(homs, ["gantry.edl", "gantry.edl", "pitch.edl"], symbols=["ORIENT=V", "ORIENT=H", "P=PITCH"]),
        message_button(homs, "0"),
        message_button(homs, "1"),
    )
    for name in ("gantry", "pitch"):
        (tmp_path / f"{name}.ui").write_text(
            '<ui version="4.0"><class>Form</class><widget class="QWidget" name="Form"/></ui>'
        )
    displays, buttons = load_switched_screen(tmp_path, qtbot)
    assert [d.filename for d in displays] == ["gantry.ui", "gantry.ui", "pitch.ui"]

    qtbot.waitUntil(lambda: visible_indices(displays) == [0], timeout=3000)
    for press in ("2", "1", "0"):
        buttons[press].sendValue()
        qtbot.waitUntil(lambda: visible_indices(displays) == [int(press)], timeout=3000)
        # PyDM loads a hidden embedded display once it shows.
        assert displays[int(press)].embedded_widget is not None
    assert displays[1].embedded_widget.macros()["ORIENT"] == "H"


def test_message_button_window_starts_on_a_macro_value_in_pydm(tmp_path, qtbot):
    # llrf/rf_srf_cavity_main.edl: the variable starts at $(SELTAB).
    tab = r"LOC\\tabPV=i:$(SELTAB)"
    convert_objects(tmp_path, pip(tab, ["a.edl", "b.edl", "c.edl"]), message_button(tab, "0"))
    displays, buttons = load_switched_screen(tmp_path, qtbot, macros={"SELTAB": "2"})

    qtbot.waitUntil(lambda: visible_indices(displays) == [2], timeout=3000)
    buttons["0"].sendValue()
    qtbot.waitUntil(lambda: visible_indices(displays) == [0], timeout=3000)


def test_message_button_window_starting_at_minus_one_shows_entry_zero_in_pydm(tmp_path, qtbot):
    # EDM writes 0 to a window's variable that starts at -1 (pip.cc): entry 0
    # stays shown once the variable connects.
    convert_objects(tmp_path, pip(r"LOC\\ebwM=i:-1", ["a.edl", "b.edl"]), message_button(r"LOC\\ebwM", "1"))
    displays, buttons = load_switched_screen(tmp_path, qtbot)

    assert buttons["1"].value == 0
    qtbot.waitUntil(lambda: visible_indices(displays) == [0], timeout=3000)
    buttons["1"].sendValue()
    qtbot.waitUntil(lambda: visible_indices(displays) == [1], timeout=3000)
