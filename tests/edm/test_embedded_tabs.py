"""EDM choice buttons driving a menu embedded window (activePipClass with
displaySource "menu"): a button sitting on the window becomes a QTabWidget, any
other arrangement keeps the button and switches one display per file (#144)."""

import json
import textwrap
import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert
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
    def block(name, values):
        if not values:
            return ""
        lines = "\n".join(f'  {i} "{v}"' for i, v in enumerate(values))
        return f"{name} {{\n{lines}\n}}\n"

    return (
        "object activePipClass\nbeginObjectProperties\nmajor 4\nminor 1\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n"
        f'displaySource "menu"\nfilePv "{file_pv}"\nnumDsps {len(files)}\n'
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
    return (
        "object activeMessageButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x 404\ny 4\nw 124\nh 20\ncontrolPv "{control_pv}"\npressValue "{press_value}"\n'
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


def custom_classes(root):
    return {c.find("class").text for c in root.iter("customwidget")}


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
    assert [json.loads(prop(d, "macros")) for d in displays] == [
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


def test_menu_window_without_choice_button_shows_its_starting_entry(tmp_path):
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
    assert json.loads(prop(display, "macros")) == {"P": "PROF:", "ID": "1800"}


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
    assert not isinstance(json.loads(prop(display, "macros")), dict)


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
    # Every reference names one variable: the screen's token plus the bare name.
    names = {c.split("://", 1)[1].split("?", 1)[0] for c in channels}
    (name,) = names
    assert name.endswith("v") and name != "v"


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
