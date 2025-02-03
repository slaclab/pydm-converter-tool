from pydmconverter.dataclasses import (
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
    PyDMDrawingRectangle,
    Size,
    SizePolicy,
    StyleSheet,
    Text,
)


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
            '  <string notr="true">color: rgb(1402121);',
            "background-color: rgba(2552552550);</string>",
            "</property>",
        ]
    )
    styleSheet = StyleSheet(
        [
            "color: rgb(1402121);",
            "background-color: rgba(2552552550);",
        ]
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
    text = Text("LCLS")
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


def testDrawingRectangle():
    target = "\n".join(
        [
            '<widget class="PyDMDrawingRectangle" name="PyDMDrawingRectangle_1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>8</x>",
            "      <y>56</y>",
            "      <width>720</width>",
            "      <height>48</height>",
            "    </rect>",
            "  </property>",
            '  <property name="penColor" stdset="0">',
            '    <color alpha="255">',
            "      <red>200</red>",
            "      <green>200</green>",
            "      <blue>200</blue>",
            "    </color>",
            "  </property>",
            '  <property name="brush" stdset="0">',
            '    <brush brushstyle="SolidPattern">',
            '      <color alpha="255">',
            "        <red>200</red>",
            "        <green>200</green>",
            "        <blue>200</blue>",
            "      </color>",
            "    </brush>",
            "  </property>",
            '  <property name="channel" stdset="0">',
            "    <string />",
            "  </property>",
            '  <property name="alarmSensitiveContent" stdset="0">',
            "    <bool>false</bool>",
            "  </property>",
            '  <property name="alarmSensitiveBorder" stdset="0">',
            "    <bool>false</bool>",
            "  </property>",
            "</widget>",
        ]
    )
    drawing = PyDMDrawingRectangle(
        x=8,
        y=56,
        w=720,
        h=48,
        alarm_sensitive_border=False,
        penColor=(200, 200, 200),
        brushColor=(200, 200, 200, 255),
    )
    assert target == drawing.to_string()
