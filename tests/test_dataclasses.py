from pydmconverter.dataclasses import CustomWidget, SizePolicy, StyleSheet


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
