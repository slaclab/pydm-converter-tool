from pydmconverter.dataclasses import Bool, CustomWidget, Font, Size, SizePolicy, StyleSheet


def testBool():
    target = "".join(
        [
            '<property name="showUnits" stdset="0">',
            "<bool>false</bool>",
            "</property>",
        ]
    )
    generated = Bool("showUnits", False)
    assert target == generated.to_string()


def testCustomWidget():
    target = (
        "<customwidget>"
        "<class>PyDMEnumButton</class>"
        "<extends>QWidget</extends>"
        "<header>pydm.widgets.enum_button</header>"
        "</customwidget>"
    )
    widget = CustomWidget(
        "PyDMEnumButton",
        "QWidget",
        "pydm.widgets.enum_button",
    )
    assert target == widget.to_string()

    target = (
        "<customwidget>"
        "<class>PyDMEDMDisplayButton</class>"
        "<extends>PyDMRelatedDisplayButton</extends>"
        "<header>edmbutton.edm_button</header>"
        "<container>1</container>"
        "</customwidget>"
    )
    widget = CustomWidget("PyDMEDMDisplayButton", "PyDMRelatedDisplayButton", "edmbutton.edm_button", container="1")
    assert target == widget.to_string()


def testFont():
    target = "".join(
        [
            '<property name="font">',
            "<font>",
            "<pointsize>8</pointsize>",
            "<weight>50</weight>",
            "<bold>false</bold>",
            "</font>",
            "</property>",
        ]
    )
    font = Font(
        pointsize="8",
        weight="50",
        bold="false",
    )
    assert target == font.to_string()


def testSize():
    target = "".join(
        [
            '<property name="minimumSize">',
            "<size>",
            "<width>85</width>",
            "<height>0</height>",
            "</size>",
            "</property>",
        ]
    )
    size = Size("minimumSize", "85", "0")
    assert target == size.to_string()


def testSizePolicy():
    target = (
        '<property name="sizePolicy">'
        '<sizepolicy hsizetype="Preferred" vsizetype="Fixed">'
        "<horstretch>0</horstretch>"
        "<verstretch>0</verstretch>"
        "</sizepolicy>"
        "</property>"
    )
    sizePolicy = SizePolicy("Preferred", "Fixed")
    assert target == sizePolicy.to_string()


def testStyleSheet():
    target = (
        '<property name="styleSheet">'
        '<string notr="true">color: rgb(1402121);\n'
        "background-color: rgba(2552552550);</string>"
        "</property>"
    )
    styleSheet = StyleSheet(
        [
            "color: rgb(1402121);",
            "background-color: rgba(2552552550);",
        ]
    )
    assert target == styleSheet.to_string()
