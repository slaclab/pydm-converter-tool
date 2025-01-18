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


@dataclass
class Font(XMLConvertible):
    pointsize: str = None
    weight: str = None
    bold: str = None
    italic: str = None

    def to_xml(self) -> etree.Element:
        prop = etree.Element("property", attrib={"name": "font"})
        font = etree.SubElement(prop, "font")
        for attr, value in self.__dict__.items():
            if value is not None:
                tag = etree.SubElement(font, attr)
                tag.text = value
        return prop


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


@dataclass
class Bool(XMLConvertible):
    name: str
    value: bool

    def to_xml(self) -> etree.Element:
        prop = etree.Element(
            "property",
            attrib={
                "name": self.name,
                "stdset": "0",
            },
        )
        bool_tag = etree.SubElement(prop, "bool")
        bool_tag.text = "true" if self.value else "false"
        return prop


class Layout:
    pass


@dataclass
class Channel(XMLConvertible):
    channel: str

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": "channel",
                "stdset": "0",
            },
        )
        string = etree.SubElement(prop, "string")
        string.text = self.channel
        return prop


@dataclass
class Text(XMLConvertible):
    string: str

    def to_xml(self):
        prop = etree.Element("property", attrib={"name": "text"})
        string_tag = etree.SubElement(prop, "string")
        string_tag.text = self.string
        return prop


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


@dataclass
class Alignment(XMLConvertible):
    alignment: str

    def to_xml(self) -> etree.Element:
        prop = etree.Element("property", attrib={"name": "alignment"})
        set_tag = etree.SubElement(prop, "set")
        set_tag.text = f"Qt::Align{self.alignment.capitalize()}|Qt::AlignVCenter"
        return prop


@dataclass
class Geometry(XMLConvertible):
    x: str
    y: str
    width: str
    height: str

    def to_xml(self):
        prop = etree.Element("property", attrib={"name": "geometry"})
        rect = etree.SubElement(prop, "rect")
        for attr, value in self.__dict__.items():
            elem = etree.SubElement(rect, attr)
            elem.text = value
        return prop
