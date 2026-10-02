"""EDM choice buttons driving a menu embedded window (activePipClass with
displaySource "menu"): a button sitting on the window becomes a QTabWidget, any
other arrangement keeps the button and switches one display per file (#144)."""

import json
import textwrap
import xml.etree.ElementTree as ET

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
    return (
        "object activeChoiceButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f'x {x}\ny {y}\nw {w}\nh {h}\ncontrolPv "{control_pv}"\n'
        f'font "helvetica-medium-r-12.0"\norientation "{orientation}"\nendObjectProperties\n'
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


def test_file_window_keeps_multi_entry_symbols_unpicked(tmp_path):
    # symbols belong to a window's menu entries; a file window does not apply them.
    source = pip(r"$(sector)", ["sector_li20", "sector_li21"], symbols=["sector=LI20", "sector=LI21"])
    root = convert_objects(tmp_path, source.replace('displaySource "menu"', 'displaySource "file"'))
    (display,) = top_level(root)
    assert prop(display, "filename") == "sector_li20.ui"
    assert not isinstance(json.loads(prop(display, "macros")), dict)


def test_edm_to_ui_filename():
    assert edm_to_ui_filename("screen.edl") == "screen.ui"
    assert edm_to_ui_filename("screen") == "screen.ui"
    assert edm_to_ui_filename("screen.ui") == "screen.ui"
    assert edm_to_ui_filename("GigE_v1.2") == "GigE_v1.2.ui"
    assert edm_to_ui_filename("composite file calc.edl;P=$(P),N=1") == "composite file calc.ui"


def test_choice_button_without_channel_stays_an_empty_tab_widget(tmp_path):
    source = choice("").replace('controlPv ""\n', "")
    (tabs,) = top_level(convert_objects(tmp_path, source))
    assert tabs.get("class") == "QTabWidget"
    assert tabs.findall("widget") == []
    assert prop(tabs, "styleSheet") is None
