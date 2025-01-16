import xml.etree.ElementTree as etree
import pytest

from pydm_converter_tool.src.main import XMLGenerator


class TestXMLGenerator:
    @staticmethod
    def testFont():
        target = (
                '<property name="font">'
                "<font>"
                "<pointsize>8</pointsize>"
                "<weight>50</weight>"
                "<bold>false</bold>"
                "</font>"
                "</property>"
        )
        generated = XMLGenerator.font(
            pointsize="8",
            weight="50",
            bold="false",
        )
        xml = etree.tostring(generated, encoding='unicode')
        assert target == xml

    @staticmethod
    def testText():
        target = (
            '<property name="text">'
            "<string>LCLS</string>"
            "</property>"
        )
        generated = XMLGenerator.text("LCLS")
        xml = etree.tostring(generated, encoding='unicode')
        assert target == xml

    @staticmethod
    def testBool():
        target = (
            '<property name="showUnits" stdset="0">'
            "<bool>false</bool>"
            "</property>"
        )
        generated = XMLGenerator.bool("showUnits", False)
        xml = etree.tostring(generated, encoding='unicode')
        assert target == xml

    @staticmethod
    def testChannel():
        target = (
            '<property name="channel" stdset="0">'
            "<string>SIOC:SYS0:AL00:TOD</string>"
            "</property>"
        )
        generated = XMLGenerator.channel("SIOC:SYS0:AL00:TOD")
        xml = etree.tostring(generated, encoding='unicode')
        assert target == xml


class TestMain:
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
        generated = XMLGenerator.form_layout()
        xml = etree.tostring(generated, encoding='unicode')
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
        generated = XMLGenerator.background_widget()
        xml = etree.tostring(generated, encoding="unicode")
        assert target == xml
