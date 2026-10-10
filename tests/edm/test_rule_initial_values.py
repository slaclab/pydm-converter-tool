"""Rules that read only loc:// variables start at the value their variables'
initial values give (see start_rules_at_loc_inits)."""

import json
import uuid
import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.converter_helpers import start_rules_at_loc_inits

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


def rectangle(vis_pv, x=10, vis_min="1", vis_max="2", *lines):
    return edm_object(
        "activeRectangleClass", x, 10, 50, 20, f'visPv "{vis_pv}"', f'visMin "{vis_min}"', f'visMax "{vis_max}"', *lines
    )


def text_control(pv):
    return edm_object("activeXTextDspClass", 10, 100, 100, 20, f'controlPv "{pv}"')


def choice(pv):
    # Tall and away from everything, so it does not read as a tab bar.
    return edm_object("activeChoiceButtonClass", 350, 300, 20, 60, f'controlPv "{pv}"')


def group(vis_pv, *objects):
    return edm_object(
        "activeGroupClass", 10, 10, 200, 50, f'visPv "{vis_pv}"', 'visMin "1"', 'visMax "2"', "beginGroup"
    ).replace("\nendObjectProperties\n", "\n" + "".join(objects) + "endGroup\nendObjectProperties\n")


@pytest.fixture
def out(tmp_path, monkeypatch):
    # The converter logs skipped widget classes to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    return tmp_path


def convert_screen(directory, *objects):
    source = directory / "screen.edl"
    source.write_text(HEADER + "".join(objects))
    convert(str(source), str(directory / "screen.ui"))
    return directory / "screen.ui"


def unique(prefix="v"):
    """A loc:// name of its own: PyDM's local variables live as long as the app."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def rule_starts(ui_path, widget_class):
    """The initial_value of each rule of each widget of a class, in document order."""
    root = ET.parse(ui_path).getroot()
    return [
        [rule["initial_value"] for rule in json.loads(widget.find("property[@name='rules']/string").text)]
        for widget in root.iter("widget")
        if widget.get("class") == widget_class
    ]


# Converted screens


@pytest.mark.parametrize(
    "vis_pv, vis_min, vis_max, start",
    [
        (r"LOC\\a=i:1", "1", "2", "true"),
        (r"LOC\\a=i:0", "1", "2", "false"),
        (r"LOC\\a=i:-1", "-2", "0", "true"),
        # EDM d: and e: types become float and int.
        (r"LOC\\a=d:1.5", "1", "2", "true"),
        (r"LOC\\a=e:1,Off,On", "1", "2", "true"),
        (r"LOC\\a=e:0,Off,On", "1", "2", "false"),
        (r"LOC\\$(!W)a=i:1", "1", "2", "true"),
    ],
)
def test_rule_starts_at_its_variables_initial_value(out, vis_pv, vis_min, vis_max, start):
    ui = convert_screen(out, rectangle(vis_pv, 10, vis_min, vis_max))
    assert rule_starts(ui, "PyDMDrawingRectangle") == [[start]]


@pytest.mark.parametrize("init, start", [("1", "false"), ("0", "true")])
def test_inverted_rule_starts_at_its_variables_initial_value(out, init, start):
    ui = convert_screen(out, rectangle(rf"LOC\\a=i:{init}", 10, "1", "2", "visInvert"))
    assert rule_starts(ui, "PyDMDrawingRectangle") == [[start]]


def test_choice_button_starts_shown(out):
    # Its hide-on-disconnect rule (ch[0] is not None) reads the variable the
    # rectangle declares.
    ui = convert_screen(out, rectangle(r"LOC\\a=i:1"), choice(r"LOC\\a"))
    assert rule_starts(ui, "PyDMEnumButton") == [["true"]]


@pytest.mark.parametrize(
    "vis_pv",
    [
        # PyDM's rule raises on float("abc") and keeps the initial value.
        r"LOC\\a=s:abc",
        # Only PyDM knows a macro's value.
        r"LOC\\a=i:$(X)",
    ],
)
def test_rule_whose_start_is_unknown_is_left_alone(out, vis_pv):
    ui = convert_screen(out, rectangle(vis_pv))
    assert rule_starts(ui, "PyDMDrawingRectangle") == [["false"]]


def test_rule_reading_a_real_pv_too_is_left_alone(out):
    ui = convert_screen(out, group(r"LOC\\a=i:1", rectangle("REAL:PV")))
    rules = ET.parse(ui).getroot().find(".//widget[@class='PyDMDrawingRectangle']/property[@name='rules']/string")
    (rule,) = json.loads(rules.text)
    assert {c["channel"] for c in rule["channels"]} == {"loc://a?type=int&init=1", "REAL:PV"}
    assert rule["initial_value"] == "false"


# The pass on its own


def rule(expression, *channels, initial_value="?", prop="Visible"):
    """A rule as MultiRule writes it; by default with an initial value the pass
    never writes, to tell a rule it leaves alone from one it evaluates."""
    return {
        "name": prop,
        "property": prop,
        "initial_value": initial_value,
        "expression": expression,
        "channels": [{"channel": channel, "trigger": True, "use_enum": False} for channel in channels],
        "notes": "",
    }


IN_RANGE = "(float(ch[0]) >= 1.0 and float(ch[0]) < 2.0)"


def ui_with(*widgets):
    """A .ui element with a widget per (channel, rules text[, class])."""
    ui = ET.Element("ui")
    for channel, rules, *widget_class in widgets:
        widget = ET.SubElement(ui, "widget", {"class": widget_class[0] if widget_class else "PyDMLabel"})
        if channel is not None:
            ET.SubElement(ET.SubElement(widget, "property", {"name": "channel"}), "string").text = channel
        if rules is not None:
            ET.SubElement(ET.SubElement(widget, "property", {"name": "rules"}), "string").text = rules
    return ui


def rules_texts(ui):
    return [string.text for string in ui.iterfind(".//property[@name='rules']/string")]


def starts(ui):
    return [[r["initial_value"] for r in json.loads(text)] for text in rules_texts(ui)]


def test_bare_rule_channel_reads_a_variable_declared_later():
    ui = ui_with(
        (None, json.dumps([rule(IN_RANGE, "loc://x")])),
        ("loc://x?type=int&init=1", None),
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["true"]]


def test_undeclared_variable_is_left_alone():
    ui = ui_with((None, json.dumps([rule(IN_RANGE, "loc://x")])))
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"]]


@pytest.mark.parametrize("widget_class", ["PyDMEmbeddedDisplay", "PyDMWaveformPlot", "QWidget"])
def test_channel_pydm_does_not_connect_declares_nothing(widget_class):
    # PyDM sets it as a dynamic property: the variable stays unconfigured.
    ui = ui_with(
        ("loc://x?type=int&init=1", None, widget_class),
        (None, json.dumps([rule(IN_RANGE, "loc://x")])),
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"]]


def test_rules_of_a_tab_widget_declare_nothing():
    # PyDMTabWidget has no rules property.
    ui = ui_with(
        (None, json.dumps([rule(IN_RANGE, "loc://x?type=int&init=1")]), "PyDMTabWidget"),
        (None, json.dumps([rule(IN_RANGE, "loc://x")])),
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"], ["?"]]


def test_rules_pydm_cannot_read_declare_nothing():
    # PyDM logs the JSON error and registers no rule, so connects no channel.
    unreadable = '[, {"channels": [{"channel": "loc://x?type=int&init=0"}]}]'
    ui = ui_with(
        (None, unreadable),
        ("loc://x?type=int&init=1", json.dumps([rule(IN_RANGE, "loc://x")])),
    )
    start_rules_at_loc_inits(ui)
    assert rules_texts(ui)[0] == unreadable
    assert json.loads(rules_texts(ui)[1])[0]["initial_value"] == "true"


@pytest.mark.parametrize("first, start", [("0", "false"), ("1", "true")])
def test_first_declaration_wins(first, start):
    # As in PyDM, the first address with type and init configures the variable.
    ui = ui_with(
        ("loc://x", None),
        (f"loc://x?type=int&init={first}", None),
        (None, json.dumps([rule(IN_RANGE, "loc://x?type=int&init=1")])),
        ("loc://x?type=int&init=0", None),
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [[start]]


def test_first_declaration_wins_also_when_unknown():
    ui = ui_with(
        ("loc://x?type=int&init=${X}", None),
        (None, json.dumps([rule(IN_RANGE, "loc://x?type=int&init=1")])),
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"]]


@pytest.mark.parametrize(
    "address, start",
    [
        # PyDM converts the text: bool("0") is True.
        ("loc://x?type=bool&init=0", "true"),
        ("loc://x?type=str&init=1", "false"),
        # Without an init (blank counts as none) the address only listens.
        ("loc://x?type=int&init=", "?"),
        ("loc://x?type=array&init=[1]", "?"),
        ("loc://x?type=int&init=1.5", "?"),
    ],
)
def test_initial_value_is_read_as_pydm_reads_it(address, start):
    ui = ui_with((address, json.dumps([rule("(ch[0] == 1)", "loc://x")])))
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [[start]]


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getpid() > 0",
        "ch[0].bit_length() == 1",
        "True if ch[0] == 1 else False",
        "float(ch[0], x=1) == 1",
        "abs(ch[0]) == 1",
        "[c for c in ch] == [1]",
        "ch[0] == 'a'",
        "ch[-1] == 1",
        "ch[0] + 1 == 2",
        "ch[1] == 1",
        "ch[0]",
    ],
)
def test_expression_the_converter_does_not_write_is_left_alone(expression):
    ui = ui_with(("loc://x?type=int&init=1", json.dumps([rule(expression, "loc://x")])))
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"]]


def test_enable_rule_and_hide_on_disconnect_rule():
    ui = ui_with(
        (
            "loc://x?type=int&init=1",
            json.dumps(
                [
                    rule("(ch[0]==1) and (ch[1] is not None)", "loc://x", "loc://x"),
                    rule("(ch[0]!=1)", "loc://x", prop="Enable", initial_value="true"),
                ]
            ),
        )
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["true", "false"]]


def test_rule_on_another_property_or_without_channels_is_left_alone():
    # Only Visible and Enable take "true" or "false"; a rule with no channels
    # reads no variable.
    ui = ui_with(
        (
            "loc://x?type=int&init=1",
            json.dumps([rule("(ch[0]==1)", "loc://x", prop="Opacity"), rule("(1 == 1)")]),
        )
    )
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?", "?"]]


def test_rule_with_enum_substitution_is_left_alone():
    rules = [rule("(ch[0]==1)", "loc://x")]
    rules[0]["channels"][0]["use_enum"] = True
    ui = ui_with(("loc://x?type=int&init=1", json.dumps(rules)))
    start_rules_at_loc_inits(ui)
    assert starts(ui) == [["?"]]


def test_unchanged_rules_keep_their_text():
    unchanged = '[{"name":"Visible","property":"Visible","initial_value":"true","expression":"ch[0]==1",' + (
        '"channels":[{"channel":"loc://x","trigger":true,"use_enum":false}]}]'
    )
    left_alone = json.dumps([rule(IN_RANGE, "ca://PV")]).replace(", ", ",")
    ui = ui_with(("loc://x?type=int&init=1", unchanged), (None, left_alone))
    start_rules_at_loc_inits(ui)
    assert rules_texts(ui) == [unchanged, left_alone]


def test_changed_rules_are_written_as_the_converter_writes_them():
    rules = [rule(IN_RANGE, "loc://x?type=int&init=1"), rule("(ch[0]==1)", "ca://PV", prop="Enable")]
    ui = ui_with((None, json.dumps(rules, ensure_ascii=False)))
    start_rules_at_loc_inits(ui)
    rules[0]["initial_value"] = "true"
    assert rules_texts(ui) == [json.dumps(rules, ensure_ascii=False)]


# In PyDM


def open_screen(qtbot, path):
    from pydm.display import load_file

    screen = load_file(str(path), target=None)
    qtbot.addWidget(screen)
    screen.show()
    return screen


def by_x(widgets):
    return sorted(widgets, key=lambda widget: widget.x())


def test_every_rule_on_a_variable_shows_its_widget(out, qtbot):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMDrawingRectangle

    name = unique()
    ui = convert_screen(out, rectangle(rf"LOC\\{name}=i:1", 10), rectangle(rf"LOC\\{name}=i:1", 100))
    first, second = by_x(open_screen(qtbot, ui).findChildren(PyDMDrawingRectangle))
    qtbot.waitUntil(first.isVisible, timeout=3000)
    qtbot.wait(200)
    # The second rule joined the variable last: PyDM never evaluated it.
    assert second.isVisible()


def test_choice_button_after_a_rectangle_shows(out, qtbot):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMDrawingRectangle, PyDMEnumButton

    name = unique()
    ui = convert_screen(out, rectangle(rf"LOC\\{name}=i:1"), choice(rf"LOC\\{name}"))
    screen = open_screen(qtbot, ui)
    rect = screen.findChild(PyDMDrawingRectangle)
    button = screen.findChild(PyDMEnumButton)
    qtbot.waitUntil(rect.isVisible, timeout=3000)
    qtbot.wait(200)
    assert button.isVisible()


def test_rules_show_their_widgets_after_back_and_forward(out, qtbot):
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.utilities import close_widget_connections, establish_widget_connections
    from pydm.widgets import PyDMDrawingRectangle
    from pydm.widgets.rules import register_widget_rules, unregister_widget_rules

    name = unique()
    # The text control joins the variable after the rule, so the rule is
    # evaluated when the screen opens.
    ui = convert_screen(out, rectangle(rf"LOC\\{name}=i:1"), text_control(rf"LOC\\{name}=i:1"))
    screen = open_screen(qtbot, ui)
    rect = screen.findChild(PyDMDrawingRectangle)
    qtbot.waitUntil(rect.isVisible, timeout=3000)

    # What PyDM's main window does on leaving a display and coming back to it
    # (main_window.py clear_display_widget, back, forward): the rule now joins
    # after the text control.
    connections = plugin_for_address("loc://x").connections
    close_widget_connections(screen)
    unregister_widget_rules(screen)
    qtbot.waitUntil(lambda: name not in connections, timeout=3000)
    establish_widget_connections(screen)
    register_widget_rules(screen)
    qtbot.waitUntil(lambda: name in connections, timeout=3000)
    qtbot.wait(200)
    assert rect.isVisible()
