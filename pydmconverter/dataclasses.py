import xml.etree.ElementTree as etree

from dataclasses import dataclass, field
from typing import ClassVar


ALARM_CONTENT_DEFAULT = False
ALARM_BORDER_DEFAULT = True


class XMLConvertible:
    def to_xml(self):
        raise NotImplementedError

    def to_string(self):
        element = self.to_xml()
        etree.indent(element)
        return etree.tostring(element, encoding="unicode")


@dataclass
class Tangible:
    """Defines a widget that takes up space on a screen"""

    count: ClassVar[int] = 1
    x: int = None
    y: int = None
    w: int = None
    h: int = None

    def __post_init__(self):
        self.name = f"{type(self).__name__}_{type(self).count}"
        (type(self)).count += 1


@dataclass
class Legible(Tangible):
    """Defines a widget that displays text"""

    text: str = None
    text_format: str = None
    font: dict = field(default_factory=dict)
    alignment: str = None


@dataclass
class Controllable(Tangible):
    """Defines a widget that uses an EPICS PV"""

    channel: str = None


@dataclass
class Alarmable(Controllable):
    """Defines a widget that changes color based on an EPICS PV"""

    alarm_sensitive_content: bool = ALARM_CONTENT_DEFAULT
    alarm_sensitive_border: bool = ALARM_BORDER_DEFAULT


@dataclass
class Drawable(Tangible):
    penStyle: str = None
    penColor: tuple[int] = None
    penWidth: int = None
    brushColor: tuple[int] = None
    brushFill: bool = False

    def generate_properties(self):
        props = []
        if self.penColor is not None:
            props.append(PenColor(*self.penColor).to_xml())
        if self.penStyle is not None:
            props.append(PenStyle(style=self.penStyle).to_xml())
        if self.penWidth is not None:
            props.append(PenWidth(width=self.penWidth).to_xml())
        if self.brushColor is not None:
            props.append(Brush(*self.brushColor, fill=self.brushFill).to_xml())

        return props


class PyDMFrame:
    pass


class QLabel:
    pass


class PyDMLabel:
    pass


class PyDMLineEdit:
    pass


@dataclass
class test_PyDMDrawingRectangle(XMLConvertible, Alarmable, Drawable):
    count: ClassVar[int] = 1

    # TODO: __init__ with .components? widget.append([c.to_xml() for c in components])

    def to_xml(self):
        widget = etree.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )
        widget.append(Bool("alarmSensitiveContent", self.alarm_sensitive_content).to_xml())
        widget.append(Bool("alarmSensitiveBorder", self.alarm_sensitive_border).to_xml())
        widget.append(Channel(self.channel).to_xml())
        widget.append(Geometry(self.x, self.y, self.w, self.h).to_xml())
        properties = self.generate_properties()
        for prop in properties:
            widget.append(prop)
        return widget


@dataclass
class PyDMDrawingRectangle(XMLConvertible, Alarmable):
    count: ClassVar[int] = 1

    penStyle: str = None
    penColor: tuple[int] = None
    penWidth: int = None
    brushColor: tuple[int] = None
    brushFill: bool = False

    # TODO: __init__ with .components? widget.append([c.to_xml() for c in components])

    def to_xml(self):
        widget = etree.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )
        widget.append(Bool("alarmSensitiveContent", self.alarm_sensitive_content).to_xml())
        widget.append(Bool("alarmSensitiveBorder", self.alarm_sensitive_border).to_xml())
        widget.append(Channel(self.channel).to_xml())
        if self.penColor is not None:
            widget.append(PenColor(*self.penColor).to_xml())
        if self.penStyle is not None:
            widget.append(PenStyle(style=self.penStyle).to_xml())
        if self.penWidth is not None:
            widget.append(PenWidth(width=self.penWidth).to_xml())
        if self.brushColor is not None:
            widget.append(Brush(*self.brushColor, fill=self.brushFill).to_xml())
        widget.append(Geometry(self.x, self.y, self.w, self.h).to_xml())
        return widget


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
    pointsize: int = None
    weight: int = None
    bold: bool = None
    italic: bool = None

    def to_xml(self) -> etree.Element:
        prop = etree.Element("property", attrib={"name": "font"})
        font = etree.SubElement(prop, "font")
        if self.pointsize is not None:
            pointsize_tag = etree.SubElement(font, "pointsize")
            pointsize_tag.text = str(self.pointsize)
        if self.weight is not None:
            weight_tag = etree.SubElement(font, "weight")
            weight_tag.text = str(self.weight)
        if self.bold is not None:
            bold_tag = etree.SubElement(font, "bold")
            bold_tag.text = "true" if self.bold else "false"
        if self.italic is not None:
            italic_tag = etree.SubElement(font, "italic")
            italic_tag.text = "true" if self.italic else "false"
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
    x: int
    y: int
    width: int
    height: int

    def to_xml(self):
        prop = etree.Element("property", attrib={"name": "geometry"})
        rect = etree.SubElement(prop, "rect")
        for attr, value in self.__dict__.items():
            elem = etree.SubElement(rect, attr)
            elem.text = str(value)
        return prop


@dataclass
class Color(XMLConvertible):
    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self):
        color = etree.Element("color", attrib={"alpha": str(self.alpha)})
        red = etree.SubElement(color, "red")
        red.text = str(self.red)
        green = etree.SubElement(color, "green")
        green.text = str(self.green)
        blue = etree.SubElement(color, "blue")
        blue.text = str(self.blue)
        return color


@dataclass
class PenColor(XMLConvertible):
    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": "penColor",
                "stdset": "0",
            },
        )
        color = Color(self.red, self.green, self.blue, alpha=self.alpha)
        prop.append(color.to_xml())
        return prop


@dataclass
class PenStyle(XMLConvertible):
    style: str = None

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": "penStyle",
                "stdset": "0",
            },
        )
        enum = etree.SubElement(prop, "enum")
        enum.text = "Qt::DashLine" if self.style == "dash" else "Qt::SolidLine"
        return prop


@dataclass
class PenWidth(XMLConvertible):
    width: int = None

    def to_xml(self):
        prop = etree.Element("property", attrib={"name": "penWidth", "stdset": "0"})
        double = etree.SubElement(prop, "double")
        double.text = str(self.width)
        return prop


@dataclass
class Brush(XMLConvertible):
    red: int
    green: int
    blue: int
    alpha: int = 255
    fill: bool = True

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": "brush",
                "stdset": "0",
            },
        )
        brush = etree.SubElement(
            prop,
            "brush",
            attrib={
                "brushstyle": "SolidPattern" if self.fill else "NoBrush",
            },
        )
        color = Color(self.red, self.green, self.blue, self.alpha)
        brush.append(color.to_xml())
        return prop
