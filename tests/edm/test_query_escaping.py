"""Values in loc:// and calc:// queries keep "%", "&" and "+": the parser
percent-encodes them (parser_helpers.qs_escape), PyDM's parse_qs decodes them
(local_plugin.py, calc_plugin.py UrlToPython), and so do the converter's own
readers (enum strings, string inits, the IR's calc formulas)."""

import ast
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.parser_helpers import loc_conversion, loc_str_init, qs_escape, translate_calc_pv_to_pydm
from pydmconverter.ir.fox import parse_calc_url
from pydmconverter.react import convert_to_ir

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

# misc/L3_vernier_dither.edl's dither mode: an enum state with "&" in it.
DITHER = r"LOC\\qsDitherMode=e:0,Min/Max,Ampl & Offset"
# Every character parse_qs reads specially, and the URL delimiters "#" and "?".
TEXT = "a+b%41&c#d?e"


def edm_object(name, x, y, w, h, *lines):
    body = "\n".join(lines)
    return (
        f"object {name}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n{body}\nendObjectProperties\n"
    )


def choice(pv, x=10, y=10, w=228, h=25):
    return edm_object("activeChoiceButtonClass", x, y, w, h, f'controlPv "{pv}"')


def text_control(pv, y=10):
    return edm_object("activeXTextDspClass", 10, y, 100, 20, f'controlPv "{pv}"')


def rectangle(vis_pv, vis_min, vis_max, y=40):
    return edm_object(
        "activeRectangleClass", 250, y, 50, 20, f'visPv "{vis_pv}"', f'visMin "{vis_min}"', f'visMax "{vis_max}"'
    )


def menu_pip(file_pv, files):
    lines = ['displaySource "menu"', f'filePv "{file_pv}"', f"numDsps {len(files)}", "displayFileName {"]
    lines += [f'  {i} "{f}"' for i, f in enumerate(files)] + ["}"]
    return edm_object("activePipClass", 4, 24, 392, 300, *lines, "noScroll")


def write_screen(directory, *objects):
    source = directory / "screen.edl"
    source.write_text(HEADER + "".join(objects))
    return source


def convert_screen(directory, *objects):
    source = write_screen(directory, *objects)
    convert(str(source), str(directory / "screen.ui"))
    return directory / "screen.ui"


def calc_config(url):
    """A calc:// address's configuration, read as PyDM's calc plugin reads it."""
    return parse_qs(url.split("?", 1)[1].replace("+", "%2B"))


@pytest.fixture
def out(tmp_path, monkeypatch):
    # The converter logs skipped widget classes to a file in the cwd.
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_qs_escape_leaves_macros_alone():
    assert qs_escape("${EDM_W}a+b%&c") == "${EDM_W}a%2Bb%25%26c"
    assert qs_escape("A+B%2&C", plus=False) == "A+B%252%26C"


def test_loc_string_value_round_trips():
    url = loc_conversion(rf"LOC\\v=s:{TEXT}")
    assert parse_qs(url.split("?", 1)[1]) == {"type": ["str"], "init": [TEXT]}
    assert loc_str_init(url) == TEXT


def test_loc_enum_strings_round_trip():
    url = loc_conversion(DITHER)
    config = parse_qs(url.split("?", 1)[1])
    assert config["init"] == ["0"]
    assert ast.literal_eval(config["enum_string"][0]) == ["Min/Max", "Ampl & Offset"]


def test_calc_over_local_variables_keeps_their_initial_values():
    url = translate_calc_pv_to_pydm(r"CALC\\\{A*B\}(LOC\\charge=d:0.15, LOC\\rate=d:120)")
    config = calc_config(url)
    # No ca:// in front of an argument that names its own protocol.
    assert config["A"] == ["loc://charge?type=float&init=0.15"]
    assert config["B"] == ["loc://rate?type=float&init=120"]
    assert config["expr"] == ["A*B"]


@pytest.mark.parametrize(
    "edm_pv, expression",
    [
        # misc/facetMapCud: EPICS bitwise AND.
        (r"CALC\\\{(A&4)=4\}(X:STAT)", "(A&4)==4"),
        # misc/clock: "%32" is not read as an escaped "2".
        (r"CALC\\\{A%32\}(X:STAT)", "A%32"),
        (r"CALC\\\{A+1\}(X:STAT)", "A+1"),
    ],
)
def test_calc_expression_keeps_ampersand_and_percent(edm_pv, expression):
    url = translate_calc_pv_to_pydm(edm_pv)
    assert calc_config(url) == {"A": ["ca://X:STAT"], "expr": [expression]}
    # The IR reads the query as PyDM does.
    assert parse_calc_url(url) == (expression, {"A": "X:STAT"})


def test_tab_titles_keep_ampersand_and_plus(out):
    ui = convert_screen(
        out,
        menu_pip(r"LOC\\qsTabs=e:0,Ampl & Offset,1+1,50%", ["a.edl", "b.edl", "c.edl"]),
        choice(r"LOC\\qsTabs=e:0", x=12, y=4, w=328, h=20),
    )
    pages = ET.parse(ui).getroot().find(".//widget[@class='QTabWidget']").findall("widget")
    # Qt shows "&&" in a tab title as "&" (widgets_helpers escapes mnemonics).
    assert [p.find("attribute[@name='title']/string").text for p in pages] == ["Ampl && Offset", "1+1", "50%"]


def test_ir_binds_a_calc_to_its_local_variables(out):
    source = write_screen(
        out,
        text_control(r"CALC\\\{A*B\}(LOC\\charge=d:0.15, LOC\\rate=d:120)"),
        text_control(r"CALC\\\{(A&4)=4\}(X:STAT)", y=40),
    )
    formulas = {f.expression: f.bindings for f in convert_to_ir(str(source)).formulas}
    assert formulas == {
        "A*B": {"A": "loc://charge?type=float&init=0.15", "B": "loc://rate?type=float&init=120"},
        "(A&4)==4": {"A": "X:STAT"},
    }


def open_screen(qtbot, path):
    from pydm.display import load_file

    screen = load_file(str(path), target=None)
    qtbot.addWidget(screen)
    screen.show()
    return screen


def connection(address):
    from pydm.data_plugins import plugin_for_address

    return plugin_for_address(address).connections.get(address.split("://", 1)[1].split("?", 1)[0])


def widget_on(screen, cls, prefix):
    (widget,) = [w for w in screen.findChildren(cls) if w.channel and w.channel.startswith(prefix)]
    return widget


def test_enum_variable_with_ampersand_is_set_up_in_pydm(out, qtbot):
    """misc/L3_vernier_dither: parse_qs used to cut the enum strings at "&", PyDM's
    local plugin raised SyntaxError reading them and never set the variable up,
    so every widget on it stayed hidden."""
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMDrawingRectangle, PyDMEnumButton

    ui = convert_screen(
        out,
        choice(DITHER),
        rectangle(r"LOC\\qsDitherMode", 0, 1, y=40),
        rectangle(r"LOC\\qsDitherMode", 1, 2, y=70),
    )
    screen = open_screen(qtbot, ui)
    button = screen.findChild(PyDMEnumButton)
    first, second = sorted(screen.findChildren(PyDMDrawingRectangle), key=lambda r: r.y())

    qtbot.waitUntil(lambda: getattr(connection("loc://qsDitherMode"), "value", None) == 0, timeout=3000)
    qtbot.waitUntil(lambda: button.isVisible() and first.isVisible(), timeout=3000)
    assert button.enum_strings == ("Min/Max", "Ampl & Offset")
    assert second.isHidden()

    connection("loc://qsDitherMode").put_value(1)
    qtbot.waitUntil(lambda: second.isVisible(), timeout=3000)


def test_string_value_round_trips_in_pydm(out, qtbot):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLineEdit

    screen = open_screen(qtbot, convert_screen(out, text_control(rf"LOC\\qsText=s:{TEXT}")))
    edit = screen.findChild(PyDMLineEdit)
    qtbot.waitUntil(lambda: edit.value == TEXT, timeout=3000)
    assert edit.text() == TEXT


def test_calc_over_local_variables_computes_in_pydm(out, qtbot):
    """misc/ePowerCalc: each argument was given a ca:// prefix and cut at "&", so
    the calc never had a value."""
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLineEdit

    screen = open_screen(
        qtbot,
        convert_screen(
            out,
            text_control(r"LOC\\qsCharge=d:0.15", y=10),
            text_control(r"LOC\\qsRate=d:120", y=40),
            text_control(r"CALC\\\{A*B\}(LOC\\qsCharge=d:0.15, LOC\\qsRate=d:120)", y=70),
        ),
    )
    result = widget_on(screen, PyDMLineEdit, "calc://")

    qtbot.waitUntil(lambda: result.value == pytest.approx(18.0), timeout=3000)
    connection("loc://qsRate").put_value(60.0)
    qtbot.waitUntil(lambda: result.value == pytest.approx(9.0), timeout=3000)


def test_calc_declaring_its_local_variable_computes_in_pydm(out, qtbot):
    """A variable only the calc uses is declared by the calc's own argument."""
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLineEdit

    screen = open_screen(qtbot, convert_screen(out, text_control(r"CALC\\\{A*120\}(LOC\\qsChargeOnly=d:0.15)")))
    result = widget_on(screen, PyDMLineEdit, "calc://")
    qtbot.waitUntil(lambda: result.value == pytest.approx(18.0), timeout=3000)


@pytest.mark.parametrize(
    "expression, init, value",
    [(r"A&4", 5, 4), (r"A&4", 3, 0), (r"A%32", 37, 5)],
)
def test_calc_with_ampersand_or_percent_evaluates_in_pydm(out, qtbot, expression, init, value):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLineEdit

    name = f"qsBits{init}_{len(expression)}"
    screen = open_screen(qtbot, convert_screen(out, text_control(rf"CALC\\\{{{expression}\}}(LOC\\{name}=i:{init})")))
    result = widget_on(screen, PyDMLineEdit, "calc://")
    qtbot.waitUntil(lambda: result.value == value, timeout=3000)


def test_menu_mux_starts_at_an_escaped_initial_value(out, qtbot):
    """The generated menu mux screen decodes the init it reads ("+1" is "%2B1")."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from qtpy.QtWidgets import QComboBox

    convert_screen(
        out,
        edm_object(
            "menuMuxClass",
            10,
            10,
            100,
            25,
            r'controlPv "LOC\\qsMenu=i:+1"',
            'initialState "0"',
            "numItems 2",
            'symbolTag {\n  0 "Off"\n  1 "On"\n}',
            'symbol0 {\n  0 "FLAG"\n  1 "FLAG"\n}',
            'value0 {\n  0 "0"\n  1 "1"\n}',
        ),
    )
    screen = load_file(str(out / "screen.py"), target=None)
    qtbot.addWidget(screen)
    assert screen.findChild(QComboBox).currentIndex() == 1
