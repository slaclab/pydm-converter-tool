"""Tests for the Phoebus ``.bob`` / BOY ``.opi`` XML parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.bob.parser import (
    BobAction,
    BobDisplay,
    BobParseError,
    BobRule,
    BobScript,
    BobWidget,
    parse_bob,
)


def _doc(body: str, display_extra: str = "") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<display version="2.0.0">\n'
        "  <name>Test Screen</name>\n"
        "  <width>800</width>\n"
        "  <height>600</height>\n"
        f"{display_extra}{body}</display>\n"
    ).encode()


def test_display_basics_and_widget_tree():
    display = parse_bob(
        _doc(
            '<widget type="label" version="2.0.0"><name>L1</name><x>10</x><y>20</y>'
            "<width>100</width><height>20</height><text>Hello</text></widget>"
        )
    )
    assert isinstance(display, BobDisplay)
    assert display.name == "Test Screen"
    assert display.props["width"] == "800"
    assert display.props["height"] == "600"
    assert len(display.widgets) == 1
    w = display.widgets[0]
    assert isinstance(w, BobWidget)
    assert w.type == "label"
    assert w.name == "L1"
    assert w.type_id is None
    assert w.props["x"] == "10"
    assert w.props["y"] == "20"
    assert w.props["text"] == "Hello"
    assert "name" not in w.props
    assert w.children == [] and w.rules == [] and w.scripts == [] and w.actions == []
    assert w.macros == {}


def test_missing_x_y_default_to_zero():
    display = parse_bob(_doc('<widget type="label"><name>L</name><width>5</width></widget>'))
    w = display.widgets[0]
    assert w.props["x"] == "0"
    assert w.props["y"] == "0"


def test_legacy_typeid_node_keeps_type_id():
    display = parse_bob(
        _doc('<widget typeId="org.csstudio.opibuilder.widgets.Label" version="1.0.0"><name>Old</name></widget>')
    )
    w = display.widgets[0]
    assert w.type_id == "org.csstudio.opibuilder.widgets.Label"
    assert w.type == "org.csstudio.opibuilder.widgets.Label"


def test_group_children_and_font_retained():
    display = parse_bob(
        _doc(
            '<widget type="group"><name>G</name><x>5</x><y>6</y>'
            '<font><font family="Liberation Sans" style="BOLD" size="18.0"></font></font>'
            '<widget type="label"><name>Inner</name></widget>'
            '<widget type="group"><name>G2</name><widget type="led"><name>Deep</name></widget></widget>'
            "</widget>"
        )
    )
    g = display.widgets[0]
    assert g.type == "group"
    assert [c.name for c in g.children] == ["Inner", "G2"]
    assert g.children[1].children[0].name == "Deep"
    font = g.props["font"]
    assert isinstance(font, ET.Element)
    inner = font.find("font")
    assert inner is not None and inner.get("size") == "18.0"
    assert inner.get("style") == "BOLD"


def test_color_prop_is_element():
    display = parse_bob(
        _doc(
            '<widget type="label"><name>L</name>'
            '<foreground_color><color name="Text" red="0" green="0" blue="0"></color></foreground_color>'
            "</widget>"
        )
    )
    color = display.widgets[0].props["foreground_color"]
    assert isinstance(color, ET.Element)
    assert color.find("color").get("name") == "Text"


def test_display_and_widget_macros_become_dicts():
    display = parse_bob(
        _doc(
            '<widget type="embedded"><name>E</name><file>sub.bob</file>'
            "<macros><DEV>MOTOR:1</DEV><N>3</N></macros></widget>",
            display_extra="<macros><P>SR01</P><R>BPM</R></macros>\n",
        )
    )
    assert display.macros == {"P": "SR01", "R": "BPM"}
    assert "macros" not in display.props
    w = display.widgets[0]
    assert w.macros == {"DEV": "MOTOR:1", "N": "3"}
    assert "macros" not in w.props


def test_empty_macro_value_is_empty_string():
    display = parse_bob(_doc("", display_extra="<macros><P></P></macros>"))
    assert display.macros == {"P": ""}


def test_actions_parsed():
    display = parse_bob(
        _doc(
            '<widget type="action_button"><name>B</name><pv_name>SR:PV</pv_name>'
            '<actions execute_as_one="false">'
            '<action type="write_pv"><pv_name>OTHER:PV</pv_name><value>1</value>'
            "<description>Write it</description></action>"
            '<action type="open_display"><file>other.bob</file><target>tab</target>'
            "<macros><A>1</A></macros><description>Open</description></action>"
            '<action type="execute"><command>ls -l</command></action>'
            "</actions></widget>"
        )
    )
    acts = display.widgets[0].actions
    assert [a.type for a in acts] == ["write_pv", "open_display", "execute"]
    assert all(isinstance(a, BobAction) for a in acts)
    assert acts[0].description == "Write it"
    assert acts[0].fields == {"pv_name": "OTHER:PV", "value": "1"}
    assert acts[1].fields["file"] == "other.bob"
    assert acts[1].fields["target"] == "tab"
    assert acts[1].fields["macros"] == {"A": "1"}
    assert acts[2].description == ""
    assert acts[2].fields == {"command": "ls -l"}
    assert "actions" not in display.widgets[0].props


def test_rules_parsed():
    display = parse_bob(
        _doc(
            '<widget type="label"><name>L</name>'
            '<rules><rule name="vis" prop_id="visible" out_exp="false">'
            '<exp bool_exp="pv0==1"><value>false</value></exp>'
            '<exp bool_exp="true"><value>true</value></exp>'
            '<pv_name trig="true">A:PV</pv_name><pv_name trig="false">B:PV</pv_name>'
            "</rule>"
            '<rule name="val" prop_id="text" out_exp="true">'
            '<exp bool_exp="pv0 &gt; 1"><expression>pv0*2</expression></exp>'
            "<pv_name>C:PV</pv_name></rule>"
            '<rule name="col" prop_id="background_color" out_exp="false">'
            '<exp bool_exp="pv0"><value><color name="MAJOR" red="255" green="0" blue="0"></color></value></exp>'
            "<pv_name>D:PV</pv_name></rule>"
            "</rules></widget>"
        )
    )
    rules = display.widgets[0].rules
    assert all(isinstance(r, BobRule) for r in rules)
    r0, r1, r2 = rules
    assert (r0.name, r0.prop_id, r0.out_exp) == ("vis", "visible", False)
    assert r0.expressions == [("pv0==1", "false"), ("true", "true")]
    assert r0.pvs == [("A:PV", True), ("B:PV", False)]
    assert r1.out_exp is True
    assert r1.expressions == [("pv0 > 1", "pv0*2")]
    assert r1.pvs == [("C:PV", True)]
    # structured value: serialized XML that re-parses to the <value> element
    value = ET.fromstring(r2.expressions[0][1])
    assert value.tag == "value"
    assert value.find("color").get("name") == "MAJOR"
    assert "rules" not in display.widgets[0].props


def test_embedded_script_parsed():
    display = parse_bob(
        _doc(
            '<widget type="label"><name>L</name><scripts>'
            '<script file="EmbeddedPy"><text><![CDATA[print("hi")\n]]></text>'
            '<pv_name>A:PV</pv_name><pv_name trig="false">B:PV</pv_name></script>'
            "</scripts></widget>"
        )
    )
    (s,) = display.widgets[0].scripts
    assert isinstance(s, BobScript)
    assert s.file == "EmbeddedPy"
    assert s.text == 'print("hi")\n'
    assert s.pvs == [("A:PV", True), ("B:PV", False)]
    assert "scripts" not in display.widgets[0].props


def test_script_file_read_from_beside_input(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "calc.py").write_text("x = 1\n")
    bob = tmp_path / "screen.bob"
    bob.write_bytes(
        _doc(
            '<widget type="label"><name>L</name><scripts>'
            '<script file="scripts/calc.py"><pv_name>A:PV</pv_name></script>'
            '<script file="missing.py"><pv_name>B:PV</pv_name></script>'
            "</scripts></widget>"
        )
    )
    s_found, s_missing = parse_bob(bob).widgets[0].scripts
    assert s_found.file == "scripts/calc.py"
    assert s_found.text == "x = 1\n"
    assert s_missing.file == "missing.py"
    assert s_missing.text is None


def test_parse_accepts_str_path(tmp_path: Path):
    bob = tmp_path / "s.bob"
    bob.write_bytes(_doc('<widget type="label"><name>L</name></widget>'))
    display = parse_bob(str(bob))
    assert display.widgets[0].name == "L"
    assert display.path == bob


def test_widget_scope_pv_name_macro_substituted():
    display = parse_bob(
        _doc(
            '<widget type="action_button"><name>B</name><pv_name>SR:DEV:SP</pv_name>'
            '<actions><action type="write_pv"><pv_name>$(pv_name)</pv_name>'
            "<value>$(pv_name).PROC</value></action></actions>"
            '<rules><rule name="r" prop_id="visible" out_exp="false">'
            '<exp bool_exp="pv0"><value>true</value></exp>'
            "<pv_name>$(pv_name)</pv_name><pv_name>${pv_name}.SEVR</pv_name></rule></rules>"
            '<scripts><script file="EmbeddedPy"><text>pass</text>'
            "<pv_name>$(pv_name)</pv_name></script></scripts>"
            "</widget>"
        )
    )
    w = display.widgets[0]
    assert w.actions[0].fields == {"pv_name": "SR:DEV:SP", "value": "SR:DEV:SP.PROC"}
    assert w.rules[0].pvs == [("SR:DEV:SP", True), ("SR:DEV:SP.SEVR", True)]
    assert w.scripts[0].pvs == [("SR:DEV:SP", True)]


def test_pv_name_macro_left_alone_without_widget_pv():
    display = parse_bob(
        _doc(
            '<widget type="action_button"><name>B</name>'
            '<actions><action type="write_pv"><pv_name>$(pv_name)</pv_name><value>1</value></action></actions>'
            "</widget>"
        )
    )
    assert display.widgets[0].actions[0].fields["pv_name"] == "$(pv_name)"


def test_other_macros_not_substituted():
    display = parse_bob(
        _doc(
            '<widget type="action_button"><name>B</name><pv_name>$(P):X</pv_name>'
            '<actions><action type="write_pv"><pv_name>$(P):Y</pv_name><value>1</value></action></actions>'
            "</widget>"
        )
    )
    w = display.widgets[0]
    assert w.actions[0].fields["pv_name"] == "$(P):Y"
    assert w.props["pv_name"] == "$(P):X"


def test_malformed_xml_raises():
    with pytest.raises(BobParseError):
        parse_bob(b"<display><widget type='label'><name>oops</widget></display>")


def test_malformed_error_is_value_error():
    with pytest.raises(ValueError):
        parse_bob(b"not xml at all")


def test_wrong_root_raises():
    with pytest.raises(BobParseError):
        parse_bob(b"<notadisplay/>")
