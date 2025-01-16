import xml.etree.ElementTree as etree

from dataclasses import dataclass


class XMLConvertible:
    def to_xml(self):
        raise NotImplementedError

    def to_string(self):
        element = self.to_xml()
        return etree.tostring(element, encoding="unicode")


class PyDMFrame:
    pass


class QLabel:
    pass


class PyDMLabel:
    pass


class PyDMLineEdit:
    pass


class PyDMDrawingRectangle:
    pass


class PyDMDrawingEllipse:
    pass


class PyDMShellCommand:
    pass


class PyDMPushButton:
    pass


class PyDMEnumComboBox:
    pass


class PyDMEnumButton:
    pass


class PyDMRelatedDisplayButton:
    pass


class PyDMEDMDisplayButton:
    pass


class PyDMDrawingLine:
    pass


class PyDMDrawingPolyLine:
    pass


class Font:
    pass


@dataclass
class Size(XMLConvertible):
    name: str
    width: str
    height: str

    def to_xml(self):
        top = etree.Element("property", attrib={"name": self.name})
        size = etree.SubElement(top, "size")
        width = etree.SubElement(size, "width")
        width.text = self.width
        height = etree.SubElement(size, "height")
        height.text = self.height
        return top


@dataclass
class SizePolicy(XMLConvertible):
    hsizetype: str
    vsizetype: str

    def to_xml(self):
        top = etree.Element(
            "property",
            attrib={
                "name": "sizePolicy",
            },
        )
        sizePolicy = etree.SubElement(
            top,
            "sizepolicy",
            attrib={
                "hsizetype": self.hsizetype,
                "vsizetype": self.vsizetype,
            },
        )
        horstretch = etree.SubElement(sizePolicy, "horstretch")
        horstretch.text = "0"
        verstretch = etree.SubElement(sizePolicy, "verstretch")
        verstretch.text = "0"
        return top


class Bool:
    pass


class Layout:
    pass


@dataclass
class StyleSheet(XMLConvertible):
    lines: list[str]

    def to_xml(self):
        top = etree.Element(
            "property",
            attrib={
                "name": "styleSheet",
            },
        )
        string = etree.SubElement(
            top,
            "string",
            attrib={
                "notr": "true",
            },
        )
        string.text = "\n".join(self.lines)
        return top


@dataclass
class CustomWidget(XMLConvertible):
    cls: str
    base: str
    header: str
    container: str = ""

    def to_xml(self):
        top = etree.Element("customwidget")
        cls = etree.SubElement(top, "class")
        cls.text = self.cls
        extends = etree.SubElement(top, "extends")
        extends.text = self.base
        header = etree.SubElement(top, "header")
        header.text = self.header
        if self.container:
            container = etree.SubElement(top, "container")
            container.text = self.container
        return top
