import pytest

from pydmconverter.widgets_helpers import (
    XMLConvertible,
    XMLSerializableMixin,
    Enum,
    PyDMRule,
    PyDMToolTip,
    TextFormat,
    Color,
    Rotation,
    Tangible,
    Legible,
    Controllable,
    Alarmable,
    Hidable,
    Drawable,
    Alignment,
    Bool,
    Int,
    Str,
    Brush,
    Channel,
    CustomWidget,
    Geometry,
    Font,
    PenColor,
    PenStyle,
    PenWidth,
    Size,
    SizePolicy,
    StyleSheet,
    Text,
)


def test_XMLConvertible():
    """
    Test that XMLConvertible.to_xml() raises NotImplementedError.
    """
    x = XMLConvertible()
    with pytest.raises(NotImplementedError):
        _ = x.to_xml()


def test_XMLSerializableMixin():
    """
    Test XMLSerializableMixin by instantiating it with a given name.
    """
    instance = XMLSerializableMixin(name="testMixin")
    expected = "\n".join(
        [
            '<widget class="XMLSerializableMixin" name="testMixin">',
            '  <property name="base">value</property>',
            "</widget>",
        ]
    )
    assert expected == instance.to_string()


def test_Enum():
    """
    Test the Enum class XML output.
    """
    e = Enum("enumTest", "Value1")
    expected = "\n".join(['<property name="enumTest" stdset="0">', "  <enum>Value1</enum>", "</property>"])
    assert expected == e.to_string()


def test_PyDMRule():
    """
    Test the PyDMRule class XML output.
    """
    rule = PyDMRule("rule1", "someProp", "1+1", "channel1", initial_value=42)
    expected = "\n".join(
        [
            '<property name="rules" stdset="0">',
            "  <rules>[{'name': 'rule1', 'property': 'someProp', 'initialValue': 42, 'expression': '1+1', 'channel': [{'channel': 'channel1', 'trigger': True, 'use_enum': False}]}]</rules>",
            "</property>",
        ]
    )
    assert expected == rule.to_string()


def test_PyDMToolTip():
    """
    Test the PyDMToolTip XML output.
    """
    tooltip = PyDMToolTip("This is a tooltip")
    expected = "\n".join(
        ['<property name="PyDMToolTip" stdset="0">', "  <string>This is a tooltip</string>", "</property>"]
    )
    assert expected == tooltip.to_string()


def test_TextFormat():
    """
    Test the TextFormat XML output.
    """
    tf = TextFormat("plain")
    expected = "\n".join(['<property name="textFormat">', "  <enum>Qt::Plain</enum>", "</property>"])
    assert expected == tf.to_string()


def test_Color():
    """
    Test the Color class XML output.
    """
    color = Color(10, 20, 30)
    expected = "\n".join(
        ['<color alpha="255">', "  <red>10</red>", "  <green>20</green>", "  <blue>30</blue>", "</color>"]
    )
    assert expected == color.to_string()


def test_Rotation():
    """
    Test the Rotation XML output.
    """
    rotation = Rotation("rotation", 45)
    expected = "<rotation>45</rotation>"
    assert expected == rotation.to_string().strip()


def test_tangible():
    """
    Test the Tangible class XML output when no name is provided.

    The Tangible instance auto‑generates its name. We capture that name and use it
    in the expected XML output.
    """
    tangible = Tangible(x=5, y=10, width=15, height=20)
    auto_name = tangible.name
    expected = "\n".join(
        [
            f'<widget class="Tangible" name="{auto_name}">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>5</x>",
            "      <y>10</y>",
            "      <width>15</width>",
            "      <height>20</height>",
            "    </rect>",
            "  </property>",
            "</widget>",
        ]
    )
    assert expected == tangible.to_string()


def test_Legible():
    """
    Test the Legible class XML output (combining geometry, text, font, and alignment).
    """
    legible = Legible(
        x=0, y=0, width=100, height=50, name="legible1", text="Hello", font={"pointsize": 10}, alignment="center"
    )
    expected = "\n".join(
        [
            '<widget class="Legible" name="legible1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>0</x>",
            "      <y>0</y>",
            "      <width>100</width>",
            "      <height>50</height>",
            "    </rect>",
            "  </property>",
            '  <property name="text">',
            "    <string>Hello</string>",
            "  </property>",
            '  <property name="font">',
            "    <font>",
            "      <pointsize>10</pointsize>",
            "    </font>",
            "  </property>",
            '  <property name="alignment">',
            "    <set>Qt::AlignHCenter|Qt::AlignVCenter</set>",
            "  </property>",
            "</widget>",
        ]
    )
    assert expected == legible.to_string()


def test_Controllable():
    """
    Test the Controllable class XML output (combining geometry, channel, and tooltip).
    """
    controllable = Controllable(
        x=0, y=0, width=100, height=50, name="controllable1", channel="PV:1", pydm_tool_tip="Tooltip text"
    )
    expected = "\n".join(
        [
            '<widget class="Controllable" name="controllable1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>0</x>",
            "      <y>0</y>",
            "      <width>100</width>",
            "      <height>50</height>",
            "    </rect>",
            "  </property>",
            '  <property name="channel" stdset="0">',
            "    <string>PV:1</string>",
            "  </property>",
            '  <property name="PyDMToolTip" stdset="0">',
            "    <string>Tooltip text</string>",
            "  </property>",
            '  <property name="rules" stdset="0">',
            "    <string>[]</string>",
            "  </property>",
            "</widget>",
        ]
    )
    assert expected == controllable.to_string()


def test_Alarmable():
    """
    Test the Alarmable class XML output (adding alarm properties).
    """
    alarmable = Alarmable(
        x=0,
        y=0,
        width=100,
        height=50,
        name="alarmable1",
        channel="PV:2",
        pydm_tool_tip="Alarm tip",
        alarm_sensitive_content=True,
        alarm_sensitive_border=False,
    )
    expected = "\n".join(
        [
            '<widget class="Alarmable" name="alarmable1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>0</x>",
            "      <y>0</y>",
            "      <width>100</width>",
            "      <height>50</height>",
            "    </rect>",
            "  </property>",
            '  <property name="channel" stdset="0">',
            "    <string>PV:2</string>",
            "  </property>",
            '  <property name="PyDMToolTip" stdset="0">',
            "    <string>Alarm tip</string>",
            "  </property>",
            '  <property name="rules" stdset="0">',
            "    <string>[]</string>",
            "  </property>",
            '  <property name="alarmSensitiveContent" stdset="0">',
            "    <bool>true</bool>",
            "  </property>",
            '  <property name="alarmSensitiveBorder" stdset="0">',
            "    <bool>false</bool>",
            "  </property>",
            "</widget>",
        ]
    )
    assert expected == alarmable.to_string()


def test_Hidable():
    """
    Test the Hidable class XML output.

    Note: Hidable does not override generate_properties, so only the geometry is output.
    """
    hidable = Hidable(
        x=5,
        y=10,
        width=15,
        height=20,
        name="hidable1",
        visibility_pv="VPV",
        visibility_max="Vmax",
        visibility_min="Vmin",
        visibility_invert=True,
    )
    expected = "\n".join(
        [
            '<widget class="Hidable" name="hidable1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>5</x>",
            "      <y>10</y>",
            "      <width>15</width>",
            "      <height>20</height>",
            "    </rect>",
            "  </property>",
            "</widget>",
        ]
    )
    assert expected == hidable.to_string()


def test_Drawable():
    """
    Test the Drawable class XML output (adding pen, brush, and rotation properties).
    """
    drawable = Drawable(
        x=0,
        y=0,
        width=100,
        height=50,
        name="drawable1",
        penColor=(10, 20, 30, 255),
        penStyle="dash",
        penWidth=3,
        brushColor=(40, 50, 60, 255),
        brushFill=True,
        rotation=90,
    )
    expected = "\n".join(
        [
            '<widget class="Drawable" name="drawable1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>0</x>",
            "      <y>0</y>",
            "      <width>100</width>",
            "      <height>50</height>",
            "    </rect>",
            "  </property>",
            '  <property name="penColor" stdset="0">',
            '    <color alpha="255">',
            "      <red>10</red>",
            "      <green>20</green>",
            "      <blue>30</blue>",
            "    </color>",
            "  </property>",
            '  <property name="penStyle" stdset="0">',
            "    <enum>Qt::DashLine</enum>",
            "  </property>",
            '  <property name="penWidth" stdset="0">',
            "    <double>3</double>",
            "  </property>",
            '  <property name="brush" stdset="0">',
            '    <brush brushstyle="SolidPattern">',
            '      <color alpha="255">',
            "        <red>40</red>",
            "        <green>50</green>",
            "        <blue>60</blue>",
            "      </color>",
            "    </brush>",
            "  </property>",
            "  <rotation>90</rotation>",
            "</widget>",
        ]
    )
    assert expected == drawable.to_string()


def testBool():
    target = "\n".join(
        [
            '<property name="showUnits" stdset="0">',
            "  <bool>false</bool>",
            "</property>",
        ]
    )
    generated = Bool("showUnits", False)
    assert target == generated.to_string()


def testInt():
    target = "\n".join(
        [
            '<property name="precision" stdset="0">',
            "  <number>8</number>",
            "</property>",
        ]
    )
    generated = Int("precision", 8)
    assert target == generated.to_string()


def testStr():
    target = "\n".join(
        [
            '<property name="toolTip" stdset="0">',
            "  <string>foo</string>",
            "</property>",
        ]
    )
    generated = Str("toolTip", "foo")
    assert target == generated.to_string()


def testChannel():
    target = "\n".join(
        [
            '<property name="channel" stdset="0">',
            "  <string>SIOC:SYS0:AL00:TOD</string>",
            "</property>",
        ]
    )
    channel = Channel("SIOC:SYS0:AL00:TOD")
    assert target == channel.to_string()

    target = "\n".join(
        [
            '<property name="channel" stdset="0">',
            "  <string />",
            "</property>",
        ]
    )
    channel = Channel(None)
    assert target == channel.to_string()


def testCustomWidget():
    target = "\n".join(
        [
            "<customwidget>",
            "  <class>PyDMEnumButton</class>",
            "  <extends>QWidget</extends>",
            "  <header>pydm.widgets.enum_button</header>",
            "</customwidget>",
        ]
    )
    widget = CustomWidget(
        "PyDMEnumButton",
        "QWidget",
        "pydm.widgets.enum_button",
    )
    assert target == widget.to_string()

    target = "\n".join(
        [
            "<customwidget>",
            "  <class>PyDMEDMDisplayButton</class>",
            "  <extends>PyDMRelatedDisplayButton</extends>",
            "  <header>edmbutton.edm_button</header>",
            "  <container>1</container>",
            "</customwidget>",
        ]
    )
    widget = CustomWidget("PyDMEDMDisplayButton", "PyDMRelatedDisplayButton", "edmbutton.edm_button", container="1")
    assert target == widget.to_string()


def testFont():
    target = "\n".join(
        [
            '<property name="font">',
            "  <font>",
            "    <pointsize>8</pointsize>",
            "    <weight>50</weight>",
            "    <bold>false</bold>",
            "  </font>",
            "</property>",
        ]
    )
    font = Font(
        pointsize=8,
        weight=50,
        bold=False,
    )
    assert target == font.to_string()


def testSize():
    target = "\n".join(
        [
            '<property name="minimumSize">',
            "  <size>",
            "    <width>85</width>",
            "    <height>0</height>",
            "  </size>",
            "</property>",
        ]
    )
    size = Size("minimumSize", "85", "0")
    assert target == size.to_string()


def testSizePolicy():
    target = "\n".join(
        [
            '<property name="sizePolicy">',
            '  <sizepolicy hsizetype="Preferred" vsizetype="Fixed">',
            "    <horstretch>0</horstretch>",
            "    <verstretch>0</verstretch>",
            "  </sizepolicy>",
            "</property>",
        ]
    )
    sizePolicy = SizePolicy("Preferred", "Fixed")
    assert target == sizePolicy.to_string()


def testStyleSheet():
    target = "\n".join(
        [
            '<property name="styleSheet">',
            "  <string>color: rgb(1402121); background-color: rgba(2552552550);</string>",
            "</property>",
        ]
    )
    styleSheet = StyleSheet(
        {
            "color": "rgb(1402121)",
            "background-color": "rgba(2552552550)",
        }
    )
    assert target == styleSheet.to_string()


def testText():
    target = "\n".join(
        [
            '<property name="text">',
            "  <string>LCLS</string>",
            "</property>",
        ]
    )
    text = Text("text", "LCLS")
    assert target == text.to_string()


def testAlignment():
    target = "\n".join(
        [
            '<property name="alignment">',
            "  <set>Qt::AlignLeft|Qt::AlignVCenter</set>",
            "</property>",
        ]
    )
    alignment = Alignment("left")
    assert target == alignment.to_string()


def testGeometry():
    target = "\n".join(
        [
            '<property name="geometry">',
            "  <rect>",
            "    <x>5</x>",
            "    <y>10</y>",
            "    <width>15</width>",
            "    <height>20</height>",
            "  </rect>",
            "</property>",
        ]
    )
    geometry = Geometry("5", "10", "15", "20")
    assert target == geometry.to_string()


def testPen():
    target = "\n".join(
        [
            '<property name="penStyle" stdset="0">',
            "  <enum>Qt::SolidLine</enum>",
            "</property>",
        ]
    )
    style = PenStyle()
    assert target == style.to_string()

    target = "\n".join(
        [
            '<property name="penStyle" stdset="0">',
            "  <enum>Qt::DashLine</enum>",
            "</property>",
        ]
    )
    style = PenStyle("dash")
    assert target == style.to_string()

    target = "\n".join(
        [
            '<property name="penColor" stdset="0">',
            '  <color alpha="255">',
            "    <red>50</red>",
            "    <green>100</green>",
            "    <blue>150</blue>",
            "  </color>",
            "</property>",
        ]
    )
    color = PenColor(50, 100, 150)
    assert target == color.to_string()

    target = "\n".join(
        [
            '<property name="penWidth" stdset="0">',
            "  <double>9</double>",
            "</property>",
        ]
    )
    width = PenWidth(9)
    assert target == width.to_string()


def testBrush():
    target = "\n".join(
        [
            '<property name="brush" stdset="0">',
            '  <brush brushstyle="SolidPattern">',
            '    <color alpha="255">',
            "      <red>50</red>",
            "      <green>100</green>",
            "      <blue>150</blue>",
            "    </color>",
            "  </brush>",
            "</property>",
        ]
    )
    brush = Brush(50, 100, 150)
    assert target == brush.to_string()

    target = "\n".join(
        [
            '<property name="brush" stdset="0">',
            '  <brush brushstyle="NoBrush">',
            '    <color alpha="255">',
            "      <red>50</red>",
            "      <green>100</green>",
            "      <blue>150</blue>",
            "    </color>",
            "  </brush>",
            "</property>",
        ]
    )
    brush = Brush(50, 100, 150, fill=False)
    assert target == brush.to_string()
