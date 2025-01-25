import xml.etree.ElementTree as etree

from dataclasses import dataclass, field
from typing import ClassVar, Any


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
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    def __post_init__(self):
        self.name = f"{type(self).__name__}_{type(self).count}"
        (type(self)).count += 1

    def generate_properties(self) -> list[etree.Element]:
        """Generate a list of defined properties of a tangible object

        Returns
        -------
        list[etree.Element]
            List of all size properties of the tangible object
        """
        properties = []
        properties.append(Geometry(self.x, self.y, self.w, self.h).to_xml())
        return properties


@dataclass
class Legible(Tangible):
    """Defines a widget that displays text"""

    text: str = None
    font: dict = field(default_factory=dict)
    alignment: str = None

    def generate_properties(self) -> list[etree.Element]:
        """Generate a list of defined properties of a legible object

        Returns
        -------
        list[etree.Element]
            List of all defined properties of the legible object
        """
        properties = super(Legible, self).generate_properties()
        if self.text is not None:
            properties.append(Text(self.text).to_xml())
        if self.font:
            properties.append(Font(**self.font).to_xml())
        if self.alignment is not None:
            properties.append(Alignment(self.alignment).to_xml())
        return properties


@dataclass
class Controllable(Tangible):
    """Defines a widget that uses an EPICS PV"""

    channel: str = None

    def generate_properties(self) -> list[etree.Element]:
        """Generate a list of defined properties of a controllable object

        Returns
        -------
        list[etree.Element]
            List of all defined properties of the controllable object
        """
        properties = super(Controllable, self).generate_properties()
        properties.append(Channel(self.channel).to_xml())
        return properties


@dataclass
class Alarmable(Controllable):
    """Defines a widget that changes color based on an EPICS PV"""

    alarm_sensitive_content: bool = ALARM_CONTENT_DEFAULT
    alarm_sensitive_border: bool = ALARM_BORDER_DEFAULT

    def generate_properties(self) -> list[etree.Element]:
        """Generate a list of defined properties of an alarmable object

        Returns
        -------
        list[etree.Element]
            List of all defined properties of the alarmable object
        """
        properties = super(Alarmable, self).generate_properties()
        properties.append(Bool("alarmSensitiveContent", self.alarm_sensitive_content).to_xml())
        properties.append(Bool("alarmSensitiveBorder", self.alarm_sensitive_border).to_xml())
        return properties


@dataclass
class Hidable(Tangible):
    """Defines a widget that can be hidden"""

    visibility_pv: str = None
    visibility_max: str = None
    visibility_min: str = None
    visibility_invert: bool = False


@dataclass
class Drawable(Tangible):
    """Defines a widget that can be drawn"""

    penStyle: str = None
    penColor: tuple[int] = None
    penWidth: int = None
    brushColor: tuple[int] = None
    brushFill: bool = None

    def generate_properties(self):
        """Generate a list of defined properties of a drawable object

        Returns
        -------
        list[etree.Element]
            List of all defined properties of the drawable object
        """
        properties = super(Drawable, self).generate_properties()
        if self.penColor is not None:
            properties.append(PenColor(*self.penColor).to_xml())
        if self.penStyle is not None:
            properties.append(PenStyle(style=self.penStyle).to_xml())
        if self.penWidth is not None:
            properties.append(PenWidth(width=self.penWidth).to_xml())
        if self.brushColor is not None:
            if self.brushFill is None:
                self.brushFill = True
            properties.append(Brush(*self.brushColor, fill=self.brushFill).to_xml())

        return properties


class PyDMFrame:
    pass


@dataclass
class QLabel(XMLConvertible, Legible):
    count: ClassVar[int] = 1

    precision: int = None
    show_units: bool = None
    tool_tip: str = None
    frame_shape: str = None

    def to_xml(self) -> etree.Element:
        """Generate an XML representation of the QLabel object

        Returns
        -------
        etree.Element
            The XML representation of the QLabel
        """
        # Create the base of the etree, the widget element
        widget = etree.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )

        # Get XML representation of all defined properties of the QLabel
        properties = self.generate_properties()
        if self.precision is not None:
            properties.append(Int("precision", self.precision).to_xml())
        if self.show_units is not None:
            properties.append(Bool("showUnits", self.show_units).to_xml())
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.frame_shape is not None:
            properties.append(Str("frameShape", self.frame_shape).to_xml())

        # Append all properties to the widget
        for prop in properties:
            widget.append(prop)
        return widget


@dataclass
class PyDMLabel(QLabel, Alarmable):
    count: ClassVar[int] = 1

    precision_from_pv: bool = None
    pydm_tool_tip: str = None

    def to_xml(self) -> etree.Element:
        """Generate an XML representation of the PyDMLabel object

        Returns
        -------
        etree.Element
            The XML representation of the PyDMLabel
        """
        widget = super(PyDMLabel, self).to_xml()

        # Get XML representation of all defined properties of the QLabel
        properties = self.generate_properties()
        if self.precision_from_pv is not None:
            widget.append(Bool("precisionFromPV", self.precision_from_pv).to_xml())
        if self.pydm_tool_tip is not None:
            widget.append(Text("PyDMToolTip", self.pydm_tool_tip).to_xml())

        # Append all properties to the widget if they are already defined
        for prop in properties:
            if widget.find(prop.tag):
                continue
            widget.append(prop)
        return widget


class PyDMLineEdit:
    pass


@dataclass
class PyDMDrawingRectangle(XMLConvertible, Alarmable, Drawable):
    count: ClassVar[int] = 1

    def to_xml(self):
        """Generate an XML representation of the PyDMDrawingRectangle object

        Returns
        -------
        etree.Element
            The XML representation of the PyDMDrawingRectangle
        """
        # Create the base of the etree, the widget element
        widget = etree.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )

        # Get XML representations of all properties and append them to the widget
        properties = self.generate_properties()

        for prop in properties:
            widget.append(prop)
        return widget


@dataclass
class PyDMDrawingEllipse(XMLConvertible, Alarmable, Drawable):
    count: ClassVar[int] = 1

    def to_xml(self):
        """Generate an XML representation of the PyDMDrawingEllipse object

        Returns
        -------
        etree.Element
            The XML representation of the PyDMDrawingEllipse
        """
        # Create the base of the etree, the widget element
        widget = etree.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )

        # Get XML representations of all properties and append them to the widget
        properties = self.generate_properties()

        for prop in properties:
            widget.append(prop)
        return widget


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


@dataclass
class Int(XMLConvertible):
    name: str
    value: int = 0

    def to_xml(self) -> etree.Element:
        prop = etree.Element(
            "property",
            attrib={
                "name": self.name,
                "stdset": "0",
            },
        )
        int_tag = etree.SubElement(prop, "number")
        int_tag.text = str(self.value)
        return prop


@dataclass
class Str(XMLConvertible):
    name: str
    string: str

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": self.name,
                "stdset": "0",
            },
        )
        string_tag = etree.SubElement(prop, "string")
        string_tag.text = self.string
        return prop


@dataclass
class Enum(XMLConvertible):
    name: str
    value: str

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": self.name,
                "stdset": "0",
            },
        )
        enum = etree.SubElement(prop, "enum")
        enum.text = self.value
        return prop


@dataclass
class PyDMRule:
    name: str
    rule_property: str
    expression: str
    channel: str
    initial_value: Any = None

    def to_xml(self):
        prop = etree.Element(
            "property",
            attrib={
                "name": "rules",
                "stdset": "0",
            },
        )
        rules_struct = [
            {
                "name": self.name,
                "property": self.rule_property,
                "initialValue": self.initial_value,
                "expression": self.expression,
                "channel": [
                    {
                        "channel": self.channel,
                        "trigger": True,
                        "use_enum": False,
                    },
                ],
            },
        ]
        rules = etree.SubElement(prop, "rules")
        rules.text = str(rules_struct)
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
class TextFormat(XMLConvertible):
    text_format: str

    def to_xml(self) -> etree.Element:
        prop = etree.Element("property", attrib={"name": "textFormat"})
        set_tag = etree.SubElement(prop, "enum")
        set_tag.text = f"Qt::{self.text_format.capitalize()}"
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
