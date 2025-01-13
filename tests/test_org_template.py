import xml.etree.ElementTree as etree

from pydmconverter.org_template import OrgTemplate


class TestOrgTemplate:
    @staticmethod
    def test_form_layout():
        """A temparary test that always passes."""
        target = (
            '<layout class="QVBoxLayout" name="verticalLayout_3">'
            '<property name="spacing">'
            "<number>0</number>"
            "</property>"
            '<property name="leftMargin">'
            "<number>0</number>"
            "</property>"
            '<property name="topMargin">'
            "<number>0</number>"
            "</property>"
            '<property name="rightMargin">'
            "<number>0</number>"
            "</property>"
            '<property name="bottomMargin">'
            "<number>9</number>"
            "</property>"
            "</layout>"
        )
        generated = OrgTemplate.form_layout()
        xml = etree.tostring(generated, encoding="unicode")
        assert target == xml

    @staticmethod
    def test_background_widget():
        target = (
            "<item>"
            '<widget class="QFrame" name="Background">'
            '<property name="toolTip">'
            "<string />"
            "</property>"
            '<property name="styleSheet">'
            '<string notr="true">QWidget #Background {\n'
            "background-color: rgb(193, 193, 193);\n"
            "border-radius: 0px;\n"
            "}</string>"
            "</property>"
            "</widget>"
            "</item>"
        )
        generated = OrgTemplate.background_widget()
        xml = etree.tostring(generated, encoding="unicode")
        assert target == xml
