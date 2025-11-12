from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, List, Optional, Tuple, Union, Dict
import xml.etree.ElementTree as etree
from xml.etree import ElementTree as ET
from pydmconverter.custom_types import RGBA, RuleArguments
import logging

logger = logging.getLogger(__name__)

ALARM_CONTENT_DEFAULT = False
ALARM_BORDER_DEFAULT = True


class XMLConvertible:
    """
    Abstract base class for objects that can be converted to XML.

    Methods
    -------
    to_xml() -> ET.Element
        Convert the object to an XML element.
    to_string() -> str
        Return a formatted string representation of the XML element.
    """

    secretId: str = None

    secretId: str = None

    def to_xml(self) -> ET.Element:
        """
        Convert the object to an XML element.

        Returns
        -------
        ET.Element
            The XML element representation of the object.

        Raises
        ------
        NotImplementedError
            If the method is not implemented by the subclass.
        """
        raise NotImplementedError

    def to_string(self) -> str:
        """
        Convert the XML element to a formatted string.

        Returns
        -------
        str
            The formatted string representation of the XML element.
        """
        element: ET.Element = self.to_xml()
        etree.indent(element)
        return etree.tostring(element, encoding="unicode")


@dataclass
class XMLSerializableMixin(XMLConvertible):
    """
    Mixin class that provides a generic XML serialization method.

    This mixin assumes that the class has a 'name' attribute and a
    'generate_properties' method.

    Attributes
    ----------
    name : Optional[str]
        The name of the widget.
    count : ClassVar[int]
        A class variable used to generate default names.
    """

    name: Optional[str] = None
    count: ClassVar[int] = 1
    secretId: str = None
    secretId: str = None

    def __post_init__(self) -> None:
        """
        Set a default name if not provided.
        """
        if not self.name:
            self.name = f"{type(self).__name__}{type(self).count}"
        type(self).count += 1

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate a list of XML property elements.
        Subclasses should override this method to add thier own custom properties.

        Returns
        -------
        List[etree.Element]
            A list of XML elements representing properties.
        """
        el: etree.Element = etree.Element("property")
        el.set("name", "base")
        el.text = "value"
        return [el]

    def to_xml(self) -> ET.Element:
        """
        Generate an XML element representing the object.

        Returns
        -------
        ET.Element
            The XML element representation of the object.

        Raises
        ------
        ValueError
            If the 'name' attribute is not set.
        """
        if not hasattr(self, "name") or not self.name:
            raise ValueError(f"The 'name' attribute must be set for {type(self).__name__}.")

        widget: ET.Element = ET.Element(
            "widget",
            attrib={
                "class": type(self).__name__,
                "name": self.name,
            },
        )

        properties: List[etree.Element] = self.generate_properties()
        for prop in properties:
            widget.append(prop)

        additional_properties: List[etree.Element] = (
            self.get_additional_properties() if hasattr(self, "get_additional_properties") else []
        )
        for prop in additional_properties:
            if widget.find(prop.tag) is None:
                widget.append(prop)

        return widget

    def get_additional_properties(self) -> List[ET.Element]:
        """
        Provide additional XML properties for the object.
        Hook method for subclasses to provide additional XML properties.
        Subclasses can override this method to add custom properties.

        Returns
        -------
        List[ET.Element]
            A list of additional XML elements representing properties.
        """
        return []


@dataclass
class Row(XMLConvertible):
    value: Optional[str]
    font: dict = field(default_factory=dict)

    def to_xml(self) -> etree.Element:
        """
        Convert the Row properties to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the font.
        """
        row: etree.Element = etree.Element("row")
        prop: etree.Element = etree.SubElement(row, "property", attrib={"name": "text"})
        string_tag: etree.Element = etree.SubElement(prop, "string")
        string_tag.text = self.value
        row.append(Font(**self.font).to_xml())
        return row


@dataclass
class Column:
    """
    Represents end </column> tag for tables.
    """

    def to_xml(self) -> etree.Element:
        """
        Generates a Column XML element.

        Returns
        -------
        etree.Element
            The XML element representing a column.
        """
        return etree.Element("column")


@dataclass
class Font(XMLConvertible):
    """
    Represents font properties for a widget.

    Attributes
    ----------
    pointsize : Optional[int]
        The size of the font.
    weight : Optional[int]
        The weight of the font.
    bold : Optional[bool]
        Whether the font is bold.
    italic : Optional[bool]
        Whether the font is italic.
    """

    family: Optional[str] = None
    family: Optional[str] = None
    pointsize: Optional[int] = None
    weight: Optional[int] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None

    def to_xml(self) -> etree.Element:
        """
        Convert the font properties to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the font.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "font"})
        font: etree.Element = etree.SubElement(prop, "font")
        if self.family is not None:
            family_tag: etree.Element = etree.SubElement(font, "family")
            family_tag.text = str(self.family)
        if self.family is not None:
            family_tag: etree.Element = etree.SubElement(font, "family")
            family_tag.text = str(self.family)
        if self.pointsize is not None:
            pointsize_tag: etree.Element = etree.SubElement(font, "pointsize")
            pointsize_tag.text = str(self.pointsize)
        if self.weight is not None:
            weight_tag: etree.Element = etree.SubElement(font, "weight")
            weight_tag.text = str(self.weight)
        if self.bold is not None:
            bold_tag: etree.Element = etree.SubElement(font, "bold")
            bold_tag.text = "true" if self.bold else "false"
        if self.italic is not None:
            italic_tag: etree.Element = etree.SubElement(font, "italic")
            italic_tag.text = "true" if self.italic else "false"
        return prop


@dataclass
class Size(XMLConvertible):
    """
    Represents a size property for a widget.

    Attributes
    ----------
    name : str
        The name of the property.
    width : str
        The width value.
    height : str
        The height value.
    """

    name: str
    width: str
    height: str

    def to_xml(self) -> etree.Element:
        """
        Convert the size properties to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the size.
        """
        top: etree.Element = etree.Element("property", attrib={"name": self.name})
        size_elem: etree.Element = etree.SubElement(top, "size")
        width_elem: etree.Element = etree.SubElement(size_elem, "width")
        width_elem.text = self.width
        height_elem: etree.Element = etree.SubElement(size_elem, "height")
        height_elem.text = self.height
        return top


@dataclass
class SizePolicy(XMLConvertible):
    """
    Represents the size policy for a widget.

    Attributes
    ----------
    hsizetype : str
        The horizontal size type.
    vsizetype : str
        The vertical size type.
    """

    hsizetype: str
    vsizetype: str

    def to_xml(self) -> etree.Element:
        """
        Convert the size policy to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the size policy.
        """
        top: etree.Element = etree.Element("property", attrib={"name": "sizePolicy"})
        sizePolicy_elem: etree.Element = etree.SubElement(
            top,
            "sizepolicy",
            attrib={
                "hsizetype": self.hsizetype,
                "vsizetype": self.vsizetype,
            },
        )
        horstretch: etree.Element = etree.SubElement(sizePolicy_elem, "horstretch")
        horstretch.text = "0"
        verstretch: etree.Element = etree.SubElement(sizePolicy_elem, "verstretch")
        verstretch.text = "0"
        return top


@dataclass
class Bool(XMLConvertible):
    """
    Represents a boolean property.

    Attributes
    ----------
    name : str
        The name of the property.
    value : bool
        The boolean value.
    """

    name: str
    value: bool

    def to_xml(self) -> etree.Element:
        """
        Convert the boolean property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the boolean.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        bool_tag: etree.Element = etree.SubElement(prop, "bool")
        bool_tag.text = "true" if self.value else "false"
        return prop


@dataclass
class Int(XMLConvertible):
    """
    Represents an integer property.

    Attributes
    ----------
    name : str
        The name of the property.
    value : int
        The integer value.
    """

    name: str
    value: int = 0

    def to_xml(self) -> etree.Element:
        """
        Convert the integer property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the integer.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        int_tag: etree.Element = etree.SubElement(prop, "number")
        int_tag.text = str(self.value)
        return prop


@dataclass
class Double(XMLConvertible):
    """
    Represents a double/float property.

    Attributes
    ----------
    name : str
        The name of the property.
    value : float
        The decimal value.
    """

    name: str
    value: float = 0.0

    def to_xml(self) -> etree.Element:
        """
        Convert the float property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the float (converted to double).
        """
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        double_tag: etree.Element = etree.SubElement(prop, "double")  # Need to use double because float is unsupported
        double_tag.text = str(self.value)
        return prop


@dataclass
class Str(XMLConvertible):
    """
    Represents a string property.

    Attributes
    ----------
    name : str
        The name of the property.
    string : str
        The string value.
    """

    name: str
    string: str | bool

    def to_xml(self) -> etree.Element:
        """
        Convert the string property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the string.
        """
        if (
            isinstance(self.string, bool) and self.string
        ):  # This came from edgecases with strings having empty values and were converted into bool True
            self.string = ""
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        string_tag: etree.Element = etree.SubElement(prop, "string")
        if isinstance(self.string, list):
            raise TypeError(f"Element <{self.string}> has list as .text: {self.string}")
        if isinstance(self.string, list):
            raise TypeError(f"Element <{self.string}> has list as .text: {self.string}")
        string_tag.text = self.string
        return prop


@dataclass
class StringList(XMLConvertible):
    """
    Represents a property containing a list of strings.

    Attributes
    ----------
    name : str
        The name of the property.
    items : List[str]
        A list of string values.
    """

    name: str
    items: List[str]

    def to_xml(self) -> etree.Element:
        prop = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        stringlist = etree.SubElement(prop, "stringlist")

        for item in self.items:
            if not isinstance(item, str):
                raise TypeError(f"Expected string in StringList.items, got {type(item)}: {item}")
            string_el = etree.SubElement(stringlist, "string")
            string_el.text = item
        return prop

    def escape_for_stringlist(self, s: str) -> str:
        return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Enum(XMLConvertible):
    """
    Represents an enumeration property.

    Attributes
    ----------
    name : str
        The name of the property.
    value : str
        The enum value.
    """

    name: str
    value: str

    def to_xml(self) -> etree.Element:
        """
        Convert the enum property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the enum.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        enum_elem: etree.Element = etree.SubElement(prop, "enum")
        enum_elem.text = self.value
        return prop


@dataclass
class PyDMRule(XMLConvertible):
    """
    Represents a PyDM rule for a widget.

    Attributes
    ----------
    name : str
        The name of the rule.
    rule_property : str
        The property the rule affects.
    expression : str
        The expression for the rule.
    channel : str
        The channel associated with the rule.
    initial_value : Any, optional
        The initial value for the rule.
    """

    name: str
    rule_property: str
    expression: str
    channel: str
    initial_value: Any = None

    def to_xml(self) -> etree.Element:
        """
        Convert the PyDM rule to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the rule.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "rules", "stdset": "0"})
        rules_struct: list[dict[str, Any]] = [
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
        rules: etree.Element = etree.SubElement(prop, "rules")
        rules.text = str(rules_struct)
        return prop


class Layout:
    """
    Represents a layout configuration for widgets.

    This is a placeholder class for layout-related properties.
    """

    pass


@dataclass
class Text(XMLConvertible):
    """
    Represents a text property for a widget.

    Attributes
    ----------
    name : str
        The name of the text property.
    string : str
        The text content.
    """

    name: str
    string: str

    def to_xml(self) -> ET.Element:
        """
        Convert the text property to an XML element.

        Returns
        -------
        ET.Element
            The XML element representing the text.
        """
        prop: ET.Element = ET.Element("property", attrib={"name": self.name})
        string_tag: ET.Element = ET.SubElement(prop, "string")
        string_tag.text = self.string
        return prop


@dataclass
class Channel(XMLConvertible):
    """
    Represents a channel property for a widget.

    Attributes
    ----------
    channel : str
        The channel name.
    """

    channel: str

    def to_xml(self) -> etree.Element:
        """
        Convert the channel property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the channel.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "channel", "stdset": "0"})
        string_elem: etree.Element = etree.SubElement(prop, "string")
        string_elem.text = self.channel
        return prop


@dataclass
class PyDMToolTip(XMLConvertible):
    """
    Represents a tooltip for a PyDM widget.

    Attributes
    ----------
    PyDMToolTip : str
        The tooltip text.
    """

    PyDMToolTip: str

    def to_xml(self) -> etree.Element:
        """
        Convert the tooltip to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the tooltip.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "PyDMToolTip", "stdset": "0"})
        string_elem: etree.Element = etree.SubElement(prop, "string")
        string_elem.text = self.PyDMToolTip
        return prop


@dataclass
class CustomWidget(XMLConvertible):
    """
    Represents a custom widget configuration.

    Attributes
    ----------
    cls : str
        The class name of the custom widget.
    base : str
        The base class that this widget extends.
    header : str
        The header file for the widget.
    container : str, optional
        The container information (default is an empty string).
    """

    cls: str
    base: str
    header: str
    container: str = ""

    def to_xml(self) -> etree.Element:
        """
        Convert the custom widget configuration to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the custom widget.
        """
        top: etree.Element = etree.Element("customwidget")
        cls_elem: etree.Element = etree.SubElement(top, "class")
        cls_elem.text = self.cls
        extends: etree.Element = etree.SubElement(top, "extends")
        extends.text = self.base
        header_elem: etree.Element = etree.SubElement(top, "header")
        header_elem.text = self.header
        if self.container:
            container_elem: etree.Element = etree.SubElement(top, "container")
            container_elem.text = self.container
        return top


@dataclass
class Alignment(XMLConvertible):
    """
    Represents alignment properties for a widget.

    Attributes
    ----------
    alignment : str
        The alignment value (e.g., 'left', 'center').
    """

    alignment: str

    def to_xml(self) -> etree.Element:
        """
        Convert the alignment property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the alignment.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "alignment"})
        set_tag: etree.Element = etree.SubElement(prop, "set")
        if self.alignment == "center":
            set_tag.text = "Qt::AlignHCenter|Qt::AlignVCenter"
        else:
            set_tag.text = f"Qt::Align{self.alignment.capitalize()}|Qt::AlignVCenter"
        if self.alignment == "center":
            set_tag.text = "Qt::AlignHCenter|Qt::AlignVCenter"
        else:
            set_tag.text = f"Qt::Align{self.alignment.capitalize()}|Qt::AlignVCenter"
        return prop


@dataclass
class TextFormat(XMLConvertible):
    """
    Represents text format properties for a widget.

    Attributes
    ----------
    text_format : str
        The text format value.
    """

    text_format: str

    def to_xml(self) -> etree.Element:
        """
        Convert the text format property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the text format.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "textFormat"})
        set_tag: etree.Element = etree.SubElement(prop, "enum")
        set_tag.text = f"Qt::{self.text_format.capitalize()}"
        return prop


@dataclass
class Geometry(XMLConvertible):
    """
    Represents geometry properties for a widget.

    Attributes
    ----------
    x : Union[int, str]
        The x-coordinate.
    y : Union[int, str]
        The y-coordinate.
    width : Union[int, str]
        The width of the widget.
    height : Union[int, str]
        The height of the widget.
    """

    x: Union[int, str]
    y: Union[int, str]
    width: Union[int, str]
    height: Union[int, str]

    def to_xml(self) -> etree.Element:
        """
        Convert the geometry properties to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the geometry.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "geometry"})
        rect: etree.Element = etree.SubElement(prop, "rect")

        for field_def in fields(self):
            value = getattr(self, field_def.name)
            elem: etree.Element = etree.SubElement(rect, field_def.name)

            if value is None:
                default_values = {"x": 0, "y": 0, "width": 100, "height": 100}
                value = default_values.get(field_def.name, 0)
            else:
                try:
                    if isinstance(value, str) and "." in value:
                        value = int(float(value))
                    else:
                        value = int(value)
                except (ValueError, TypeError):
                    default_values = {"x": 0, "y": 0, "width": 100, "height": 100}
                    value = default_values.get(field_def.name, 0)

            elem.text = str(value)
        return prop


@dataclass
class Color(XMLConvertible):
    """
    Represents a color.

    Attributes
    ----------
    red : int
        The red component (0-255).
    green : int
        The green component (0-255).
    blue : int
        The blue component (0-255).
    alpha : int, optional
        The alpha component (0-255), default is 255.
    """

    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self) -> etree.Element:
        """
        Convert the color to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the color.
        """
        color_elem: etree.Element = etree.Element("color", attrib={"alpha": str(self.alpha)})
        red_elem: etree.Element = etree.SubElement(color_elem, "red")
        red_elem.text = str(self.red)
        green_elem: etree.Element = etree.SubElement(color_elem, "green")
        green_elem.text = str(self.green)
        blue_elem: etree.Element = etree.SubElement(color_elem, "blue")
        blue_elem.text = str(self.blue)
        return color_elem


@dataclass
class BoolRule(XMLConvertible):
    """
    Represents a simple boolean rule for widget properties.

    Attributes
    ----------
    rule_type : str
        The type of rule (e.g., "Visible", "Enable").
    channel : str
        The channel address used as input for the rule.
    initial_value : bool, optional
        The default value for the rule when no condition is met. Defaults to True.
    show_on_true : bool, optional
        Determines whether the rule evaluates to true when the condition is satisfied. Defaults to True.
    visMin : int, optional
        Minimum threshold value for a channel to be considered "active". Used for range-based visibility rules.
    visMax : int, optional
        Maximum threshold value for a channel to be considered "active". Used for range-based visibility rules.
    notes : str, optional
        Additional metadata or notes about the rule.
    """

    rule_type: str
    channel: str
    initial_value: Optional[bool] = True
    show_on_true: Optional[bool] = True
    visMin: Optional[int] = None
    visMax: Optional[int] = None
    notes: Optional[str] = ""

    def to_string(self):
        """
        Convert the rule properties to a string.

        Returns
        -------
        str
            A string representing the rule.
        """
        if self.visMin is not None and self.visMax is not None:
            show_on_true_string = f"True if float(ch[0]) >= {self.visMin} and float(ch[0]) < {self.visMax} else False"
            show_on_false_string = f"False if float(ch[0]) >= {self.visMin} and float(ch[0]) < {self.visMax} else True"
        else:
            show_on_true_string = "True if ch[0]==1 else False"
            show_on_false_string = "True if ch[0]!=1 else False"
        expression = show_on_true_string if self.show_on_true else show_on_false_string

        output_string = (
            "{"
            f'"name": "{self.rule_type}_{self.channel}", '
            f'"property": "{self.rule_type}", '
            f'"initial_value": "{self.initial_value}", '
            f'"expression": "{expression}", '
            '"channels": ['
            "{"
            f'"channel": "{self.channel}", '
            '"trigger": true, '
            '"use_enum": false'
            "}"
            "], "
            '"notes": "{self.notes}"'
            "}"
        )
        return output_string


@dataclass
class MultiRule(XMLConvertible):
    """
    Represents a compound rule composed of multiple conditions.

    Attributes
    ----------
    rule_type : str
        The type of rule (e.g., "Visible", "Enable").
    rule_list : list of RuleArguments, optional
        A list of rule argument tuples, where each tuple contains:
        (rule_type, channel, initial_value, show_on_true, visMin, visMax).
    hide_on_disconnect_channel : str, optional
        An additional channel used to hide the widget if it disconnects.
    initial_value : bool, optional
        Default value for the rule when no conditions are satisfied. Defaults to False.
    notes : str, optional
        Additional metadata or notes about the rule.
    """

    rule_type: str
    rule_list: Optional[List[RuleArguments]] = None
    hide_on_disconnect_channel: Optional[str] = None
    initial_value: Optional[bool] = False
    notes: Optional[str] = ""

    def to_string(self):
        """
        Convert the rule properties to a string.

        Returns
        -------
        str
            A string representing the rule.
        """

        channel_list = []
        expression_list = []
        if self.rule_list is not None:
            for i, rule in enumerate(self.rule_list):
                rule_type, channel, initial_value, show_on_true, visMin, visMax = rule
                replacement_init = None
                if channel.startswith("loc://") and "init=${" in channel:
                    replacement_init = channel[channel.find("init=") + len("init=") :]
                    replacement_init = replacement_init[: replacement_init.find("}") + 1]
                channel_list.append(f'{{"channel": "{channel}", "trigger": true, "use_enum": false}}')
                expression_list.append(self.get_expression(i, show_on_true, visMin, visMax, replacement_init))
        if self.hide_on_disconnect_channel is not None:
            new_index = len(self.rule_list)
            replacement_init = None
            if self.hide_on_disconnect_channel.startswith("loc://") and "init=${" in self.hide_on_disconnect_channel:
                replacement_init = self.hide_on_disconnect_channel[
                    self.hide_on_disconnect_channel.find("init=") + len("init=") :
                ]
                replacement_init = replacement_init[: replacement_init.find("}") + 1]
            expression_list.append(self.get_hide_on_disconnect_expression(new_index, replacement_init))
            channel_list.append(
                f'{{"channel": "{self.hide_on_disconnect_channel}", "trigger": true, "use_enum": false}}'
            )
        if not expression_list:
            return ""
        expression_str = "(" + ") and (".join(expression_list) + ")"

        output_string = (
            "{"
            f'"name": "{self.rule_type}", '
            f'"property": "{self.rule_type}", '
            f'"initial_value": "false", '
            f'"expression": "{expression_str}", '
            f'"channels": [{", ".join(channel_list)}], '
            f'"notes": "{self.notes}"'
            "}"
        )
        return output_string

    def get_expression(self, index, show_on_true, visMin, visMax, init):  # TODO: Can clean up with fstrings
        """
        Build a conditional expression string for a specific channel.

        Parameters
        ----------
        index : int
            The index of the channel in the rule list.
        show_on_true : bool
            Whether the expression should evaluate to true on match.
        visMin : int, optional
            Minimum threshold value for range-based conditions.
        visMax : int, optional
            Maximum threshold value for range-based conditions.
        init : str, optional
            Replacement initialization value for the channel, if applicable.

        Returns
        -------
        str
            A string representing the conditional expression for the given channel.
        """

        ch = f"ch[{index}]"

        if visMin is not None and visMax is not None:
            show_on_true_string = f"float({ch}) >= {visMin} and float({ch}) < {visMax}"
            show_on_false_string = f"float({ch}) < {visMin} or float({ch}) >= {visMax}"
        else:
            show_on_true_string = f"{ch}==1"
            show_on_false_string = f"{ch}!=1"  # TODO: maybe need to change from specifically 1 (== 0 or != 0)?

        return show_on_true_string if show_on_true else show_on_false_string

    def get_hide_on_disconnect_expression(self, index, init):
        """
        Build an expression that ensures the widget is hidden if a channel disconnects.

        Parameters
        ----------
        index : int
            The index of the disconnect channel in the channel list.

        Returns
        -------
        str
            An expression string that evaluates true when the channel is connected.
        """

        ch = f"ch[{index}]"

        return f"{ch} is not None"


@dataclass
class Rules(XMLConvertible):
    """
    Represents a collection of rules grouped by type.

    Attributes
    ----------
    rules : list of RuleArguments
        A list of rule argument tuples, where each tuple contains:
        (rule_type, channel, initial_value, show_on_true, visMin, visMax).
    hide_on_disconnect_channel : str, optional
        An additional channel used to hide widgets if it disconnects.
    """

    rules: List[RuleArguments]
    hide_on_disconnect_channel: Optional[str] = None

    def to_xml(self):
        """
        Convert the collection of rules into an XML element.

        Returns
        -------
        etree.Element
            An XML element representing all grouped rules.
        """

        rule_list = []
        rule_variables = self.group_by_rules()

        for rule_type, rule_var_list in rule_variables.items():
            if rule_var_list:
                rule_string = MultiRule(rule_type, rule_var_list, self.hide_on_disconnect_channel).to_string()
                rule_list.append(rule_string)
            elif rule_type == "Visible":
                rule_string = MultiRule(rule_type, [], self.hide_on_disconnect_channel).to_string()
                rule_list.append(rule_string)
        output_string = f"[{', '.join(rule_list)}]"
        return Str("rules", output_string).to_xml()

    def group_by_rules(self):
        """
        Group rules by their rule type, removing duplicates.

        Returns
        -------
        dict of str to list of RuleArguments
            A dictionary where the keys are rule types (e.g., "Visible", "Enable"),
            and the values are lists of unique rules for that type.
        """

        bool_rule_types = ["Visible", "Enable"]
        rule_variables = {key: [] for key in bool_rule_types}
        for rule in self.rules:
            if rule.rule_type in rule_variables:
                rule_variables[rule.rule_type].append(rule)
        for rule_name in rule_variables.keys():  # removes repeated tuples
            rule_variables[rule_name] = list(set(rule_variables[rule_name]))
        return rule_variables


@dataclass
class StyleSheet(XMLConvertible):
    """
    Represents a stylesheet for a widget.

    Attributes
    ----------
    lines : List[str]
        A list of stylesheet lines.
    """

    styles: Dict[str, Any]

    def _format_value(self, key: str, value: Any) -> str:
        if isinstance(value, RGBA) and key in ("color", "background-color"):
            r, g, b, *a = value
            alpha = a[0] if a else 1.0
            return f"{key}: rgba({r}, {g}, {b}, {round(alpha, 2)});"
        return f"{key}: {value};"

    def to_style_string(self) -> str:
        return " ".join(self._format_value(k, v) for k, v in self.styles.items())

    def to_xml(self) -> etree.Element:
        """
        Convert the stylesheet to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the stylesheet.
        """
        prop = ET.Element("property", {"name": "styleSheet"})
        string_elem = ET.SubElement(prop, "string")
        style_str: str = self.to_style_string()
        if "background-color" not in self.styles:
            style_str += "background-color: none;"
        string_elem.text = style_str
        return prop


@dataclass
class RGBABackgroundSheet(XMLConvertible):  # eventually combine with rgbastylesheet
    """
    Represents a background style sheet with an RGBA (Red, Green, Blue, Alpha) color.

    Attributes:
        red : int
            Red component of the background color (0–255).
        green : int
            Green component of the background color (0–255).
        blue : int
            Blue component of the background color (0–255).
        alpha : int
            Alpha transparency value (0–255).
    """

    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self):
        """
        Convert the stylesheet to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the background stylesheet.
        """
        style = f"background-color: rgba({self.red}, {self.green}, {self.blue}, {round(self.alpha / 255, 2)});"
        prop = ET.Element("property", {"name": "styleSheet"})
        string_elem = ET.SubElement(prop, "string")
        string_elem.text = style
        return prop


@dataclass
class TransparentBackground(XMLConvertible):
    """
    Represents a stylesheet that gives an object no background.
    """

    def to_xml(self):
        """
        Convert the stylesheet to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the background stylesheet.
        """

        style = "background-color: transparent;"
        prop = ET.Element("property", {"name": "styleSheet"})
        string_elem = ET.SubElement(prop, "string")
        string_elem.text = style
        return prop


@dataclass
class Curves(XMLConvertible):
    """
    Represents a curve for a PyDMWaveformPlot.

    Attributes:
        x_channel : str
            The channel for x values
        y_channel : str
            The channel for y values
        plotColor : RGBA
            The color given to the curve
    """

    x_channel: Optional[str] = None
    y_channel: Optional[str] = None
    plotColor: Optional[RGBA] = None


@dataclass
class RGBAStyleSheet(XMLConvertible):
    """
    Represents a background style sheet with an RGBA (Red, Green, Blue, Alpha) color.

    Attributes:
        red : int
            Red component of the background color (0–255).
        green : int
            Green component of the background color (0–255).
        blue : int
            Blue component of the background color (0–255).
        alpha : int
            Alpha transparency value (0–255).
    """

    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self):
        """
        Convert the stylesheet into an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the image.
        """

        style = f"color: rgba({self.red}, {self.green}, {self.blue}, {round(self.alpha / 255, 2)}); background-color: transparent;"
        prop = ET.Element("property", {"name": "styleSheet"})
        string_elem = ET.SubElement(prop, "string")
        string_elem.text = style
        return prop


@dataclass
class PixMap(XMLConvertible):
    """
    Represents an image widget.

    Attributes
    ----------
    filename : str
        The filename of the imported image.
    """

    filename: str

    def to_xml(self) -> etree.Element:
        """
        Convert the filename property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the image.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "pixmap"})
        pixmap_tag: etree.Element = etree.SubElement(prop, "pixmap")
        pixmap_tag.text = self.filename
        return prop


@dataclass
class PenColor(XMLConvertible):
    """
    Represents a pen color property for a widget.

    Attributes
    ----------
    red : int
        The red component.
    green : int
        The green component.
    blue : int
        The blue component.
    alpha : int, optional
        The alpha component, default is 255.
    """

    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self) -> etree.Element:
        """
        Convert the pen color property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the pen color.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "penColor", "stdset": "0"})
        color: Color = Color(self.red, self.green, self.blue, alpha=self.alpha)
        prop.append(color.to_xml())
        return prop


@dataclass
class PenStyle(XMLConvertible):
    """
    Represents a pen style property for a widget.

    Attributes
    ----------
    style : Optional[str]
        The style of the pen ('dash' for dashed, otherwise solid).
    """

    style: Optional[str] = None

    def to_xml(self) -> etree.Element:
        """
        Convert the pen style property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the pen style.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "penStyle", "stdset": "0"})
        enum: etree.Element = etree.SubElement(prop, "enum")
        enum.text = "Qt::DashLine" if self.style == "dash" else "Qt::SolidLine"
        return prop


@dataclass
class PenWidth(XMLConvertible):
    """
    Represents a pen width property for a widget.

    Attributes
    ----------
    width : Optional[int]
        The width of the pen.
    """

    width: Optional[int] = None

    def to_xml(self) -> etree.Element:
        """
        Convert the pen width property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the pen width.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "penWidth", "stdset": "0"})
        double_elem: etree.Element = etree.SubElement(prop, "double")
        double_elem.text = str(self.width)
        return prop


@dataclass
class Brush(XMLConvertible):
    """
    Represents a brush property for a widget.

    Attributes
    ----------
    red : int
        The red component.
    green : int
        The green component.
    blue : int
        The blue component.
    alpha : int, optional
        The alpha component, default is 255.
    fill : bool, optional
        Whether the brush is filled, default is True.
    """

    red: int
    green: int
    blue: int
    alpha: int = 255
    fill: bool = True

    def to_xml(self) -> etree.Element:
        """
        Convert the brush property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the brush.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": "brush", "stdset": "0"})
        brush_elem: etree.Element = etree.SubElement(
            prop, "brush", attrib={"brushstyle": "SolidPattern" if self.fill else "NoBrush"}
        )
        color: Color = Color(self.red, self.green, self.blue, self.alpha)
        brush_elem.append(color.to_xml())
        return prop


@dataclass
class OnOffColor(XMLConvertible):
    """
    Represents the on/offColor property for a widget.

    Attributes
    ----------
    onOff : str
        The prefix for _color (either on or off).
    red : int
        The red component.
    green : int
        The green component.
    blue : int
        The blue component.
    alpha : int, optional
        The alpha component, default is 255.
    """

    onOff: str  # TODO: Make this an enum?
    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self) -> etree.Element:
        """
        Convert the onOff color property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the on//offcolor.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": f"{self.onOff}Color", "stdset": "0"})
        color: Color = Color(self.red, self.green, self.blue, alpha=self.alpha)
        prop.append(color.to_xml())
        return prop


@dataclass
class ColorObject(XMLConvertible):
    name: str
    red: int
    green: int
    blue: int
    alpha: int = 255

    def to_xml(self) -> etree.Element:
        """
        Convert the color property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the color.
        """
        prop: etree.Element = etree.Element("property", attrib={"name": self.name, "stdset": "0"})
        color: Color = Color(self.red, self.green, self.blue, alpha=self.alpha)
        prop.append(color.to_xml())
        return prop


@dataclass
class Rotation(XMLConvertible):
    """
    Represents a rotation property for a widget.

    Attributes
    ----------
    name : str
        The name of the rotation property.
    value : float
        The rotation angle.
    """

    name: str
    value: float

    def to_xml(self) -> etree.Element:
        """
        Convert the rotation property to an XML element.

        Returns
        -------
        etree.Element
            The XML element representing the rotation.
        """
        element: etree.Element = etree.Element(self.name)
        element.text = str(self.value)
        return element


@dataclass
class Tangible(XMLSerializableMixin):
    """
    Represents a tangible widget that occupies space on a screen.

    Attributes
    ----------
    x : int
        The x-coordinate.
    y : int
        The y-coordinate.
    width : int
        The width of the widget.
    height : int
        The height of the widget.
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    secretId: str = None

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate XML properties for the tangible widget.

        Returns
        -------
        List[etree.Element]
            A list containing the geometry property.
        """
        properties: List[etree.Element] = []
        properties.append(Geometry(self.x, self.y, max(self.width, 2), max(self.height, 2)).to_xml())
        if self.secretId is not None:
            properties.append(Str("secretId", self.secretId).to_xml())
            breakpoint()
        return properties


@dataclass
class Legible(Tangible):
    """
    Represents a widget that displays text.

    Attributes
    ----------
    text : Optional[str]
        The text to display.
    font : dict
        A dictionary containing font properties.
    alignment : Optional[str]
        The text alignment.
    """

    text: Optional[str] = None
    font: dict = field(default_factory=dict)
    alignment: Optional[str] = None

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate XML properties for the legible widget.

        Returns
        -------
        List[etree.Element]
            A list containing geometry, text, font, and alignment properties.
        """
        properties: List[etree.Element] = super().generate_properties()
        if self.text is not None:
            properties.append(Text("text", self.text).to_xml())
        if self.font:
            properties.append(Font(**self.font).to_xml())
        if self.alignment is not None:
            properties.append(Alignment(self.alignment).to_xml())
        return properties


@dataclass
class Controllable(Tangible):
    """
    Represents a widget that uses an EPICS PV.

    Attributes
    ----------
    channel : Optional[str]
        The EPICS channel.
    pydm_tool_tip : Optional[str]
        The tooltip text for the widget.
    """

    channel: Optional[str] = None
    pydm_tool_tip: Optional[str] = None
    visPvList: Optional[List[Tuple[str, int, int]]] = None
    visPv: Optional[str] = None
    visInvert: Optional[bool] = None
    rules: Optional[List[str]] = field(default_factory=list)
    visMin: Optional[int] = None
    visMax: Optional[int] = None
    text = None
    hide_on_disconnect_channel: Optional[str] = None
    isSymbol: Optional[bool] = None
    symbolChannel: Optional[str] = None

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate XML properties for the controllable widget.

        Returns
        -------
        List[etree.Element]
            A list containing geometry, channel, and tooltip properties.
        """
        properties: List[etree.Element] = super().generate_properties()
        if self.channel is not None:
            if isinstance(self.channel, List):
                if len(self.channel) > 1:
                    logger.warning(f"This channel was given multiple pvs: {self.channel}, using the first channel")
                self.channel = self.channel[0]

            properties.append(Channel(self.channel).to_xml())
        if self.pydm_tool_tip is not None:
            properties.append(PyDMToolTip(self.pydm_tool_tip).to_xml())
        if self.visPvList is not None:
            for elem in self.visPvList:
                group_channel, group_min, group_max = elem
                self.rules.append(
                    RuleArguments(
                        "Visible",
                        group_channel,
                        False,
                        not self.visInvert if self.visInvert is not None else True,
                        group_min,
                        group_max,
                    )
                )

        if self.visPv is not None:
            self.rules.append(
                RuleArguments(
                    "Visible",
                    self.visPv,
                    False,
                    not self.visInvert if self.visInvert is not None else True,
                    self.visMin,
                    self.visMax,
                )
            )

        hidden_widgets = [
            "activextextdspclassnoedit",
            "activechoicebuttonclass, activextextclass",
            "mzxygraphclass",
            "activerampbuttonclass",
        ]
        is_hidden = False

        for elem in hidden_widgets:
            if self.name.lower().startswith(elem):
                is_hidden = True
        if is_hidden:
            hidden_channel = self.channel
        elif self.isSymbol is not None:
            hidden_channel = self.symbolChannel
        else:
            hidden_channel = None
        properties.append(Rules(self.rules, hidden_channel).to_xml())
        return properties


@dataclass
class Alarmable(Controllable):
    """
    Represents a widget that changes appearance based on an EPICS alarm state.

    Attributes
    ----------
    alarm_sensitive_content : bool
        Whether the content is alarm sensitive.
    alarm_sensitive_border : bool
        Whether the border is alarm sensitive.
    """

    alarm_sensitive_content: bool = ALARM_CONTENT_DEFAULT
    alarm_sensitive_border: bool = ALARM_BORDER_DEFAULT
    useDisplayBg: Optional[bool] = None

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate XML properties for the alarmable widget.

        Returns
        -------
        List[etree.Element]
            A list containing geometry, channel, tooltip, and alarm properties.
        """
        properties: List[etree.Element] = super().generate_properties()
        properties.append(Bool("alarmSensitiveContent", self.alarm_sensitive_content).to_xml())
        properties.append(Bool("alarmSensitiveBorder", self.alarm_sensitive_border).to_xml())
        if self.useDisplayBg is not None:
            properties.append(Bool("useDisplayBg", self.useDisplayBg).to_xml())
        return properties


@dataclass
class Hidable(Tangible):
    """
    Represents a widget that can be hidden.

    Attributes
    ----------
    visibility_pv : Optional[str]
        The visibility process variable.
    visibility_max : Optional[str]
        The maximum visibility value.
    visibility_min : Optional[str]
        The minimum visibility value.
    visibility_invert : bool
        Whether the visibility is inverted.
    """

    visibility_pv: Optional[str] = None
    visibility_max: Optional[str] = None
    visibility_min: Optional[str] = None
    visibility_invert: bool = False


@dataclass
class StyleSheetObject(Tangible):
    """
    A base class for UI elements that support stylesheet-based customization.

    Attributes
    ----------
    foreground_color : Optional[RGBA]
        RGBA color tuple for the foreground (text) color.
    background_color : Optional[RGBA]
        RGBA color tuple for the background color.
    """

    foreground_color: Optional[RGBA] = None
    background_color: Optional[RGBA] = None
    useDisplayBg: Optional[bool] = None
    name: Optional[str] = ""

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate a list of XML property elements for this object, including
        any stylesheets derived from foreground or background color settings.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing properties, including inherited
            ones from the base class and additional style properties if specified.
        """
        properties: List[ET.Element] = super().generate_properties()

        # if self.background_color is not None or self.foreground_color is not None:
        styles: Dict[str, Any] = {}
        if self.background_color is not None and self.useDisplayBg is None:
            styles["background-color"] = self.background_color
        if self.foreground_color is not None:
            styles["color"] = self.foreground_color
        if self.name.startswith("activeMenuButtonClass") or self.name.startswith("activeMessageButtonClass"):
            styles["border"] = "1px solid black"
        properties.append(StyleSheet(styles).to_xml())

        return properties


@dataclass
class OnOffObject(Tangible):
    on_color: Optional[RGBA] = None
    off_color: Optional[RGBA] = None


@dataclass
class Drawable(Tangible):
    """
    Represents a widget that can be drawn with pen and brush properties.

    Attributes
    ----------
    penStyle : Optional[str]
        The style of the pen ('dash' for dashed, otherwise solid).
    penColor : Optional[RGBA]
        A tuple representing the pen color (red, green, blue, alpha).
    penWidth : Optional[int]
        The width of the pen.
    brushColor : Optional[RGBA]
        A tuple representing the brush color (red, green, blue, alpha).
    brushFill : Optional[bool]
        Whether the brush should fill.
    rotation : Optional[float]
        The rotation angle.
    """

    penStyle: Optional[str] = None
    penColor: Optional[RGBA] = None
    penWidth: Optional[int] = None
    brushColor: Optional[RGBA] = None
    brushFill: Optional[bool] = None
    rotation: Optional[float] = None

    def generate_properties(self) -> List[etree.Element]:
        """
        Generate XML properties for the drawable widget.

        Returns
        -------
        List[etree.Element]
            A list containing geometry, pen, brush, and rotation properties.
        """
        properties: List[etree.Element] = super().generate_properties()
        if self.penColor is not None:
            properties.append(PenColor(*self.penColor).to_xml())
        if self.penStyle is not None or self.penColor is not None:
            properties.append(PenStyle(style=self.penStyle).to_xml())
        if self.penWidth is not None:
            properties.append(PenWidth(width=self.penWidth).to_xml())
        if self.brushColor is not None:
            properties.append(Brush(*self.brushColor, fill=self.brushFill).to_xml())
        if self.brushFill is None:
            properties.append(TransparentBackground().to_xml())
        if self.rotation is not None:
            properties.append(Rotation("rotation", self.rotation).to_xml())
        return properties


class PageHeader:
    def create_page_header(self, edm_parser, scrollable=False):
        ui_element = ET.Element("ui", attrib={"version": "4.0"})

        class_element = ET.SubElement(ui_element, "class")
        class_element.text = "QWidget"

        main_widget = ET.SubElement(
            ui_element,
            "widget",
            attrib={
                "class": "QWidget",
                "name": "Form",
            },
        )

        geometry = ET.SubElement(main_widget, "property", attrib={"name": "geometry"})
        rect = ET.SubElement(geometry, "rect")
        ET.SubElement(rect, "x").text = "0"
        ET.SubElement(rect, "y").text = "0"

        """
        if scrollable:  # Setting max values for the screen to be initially
            ET.SubElement(rect, "width").text = str(min(edm_parser.ui.width, 120))
            ET.SubElement(rect, "height").text = str(min(edm_parser.ui.height, 80))
        else:
            ET.SubElement(rect, "width").text = str(edm_parser.ui.width)
            ET.SubElement(rect, "height").text = str(edm_parser.ui.height)
        """

        ET.SubElement(rect, "width").text = str(edm_parser.ui.width)
        ET.SubElement(rect, "height").text = str(edm_parser.ui.height)
        window_title = ET.SubElement(main_widget, "property", attrib={"name": "windowTitle"})
        title_string = ET.SubElement(window_title, "string")
        title_string.text = "PyDM Screen"

        screen_properties: dict[str, str] = edm_parser.ui.properties
        self.add_screen_properties(main_widget, screen_properties)

        if scrollable:
            print("Creating scrollable PyDM window")
            layout = ET.SubElement(main_widget, "layout", attrib={"class": "QVBoxLayout", "name": "verticalLayout"})
            layout_item = ET.SubElement(layout, "item")
            scroll_area = ET.SubElement(layout_item, "widget", attrib={"class": "QScrollArea", "name": "scrollArea"})

            sa_geometry = ET.SubElement(scroll_area, "property", attrib={"name": "geometry"})
            sa_rect = ET.SubElement(sa_geometry, "rect")
            ET.SubElement(sa_rect, "x").text = "0"
            ET.SubElement(sa_rect, "y").text = "0"
            ET.SubElement(sa_rect, "width").text = str(edm_parser.ui.width)
            ET.SubElement(sa_rect, "height").text = str(edm_parser.ui.height)
            widget_resizable = ET.SubElement(scroll_area, "property", attrib={"name": "widgetResizable"})
            ET.SubElement(widget_resizable, "bool").text = "false"

            scroll_contents = ET.SubElement(
                scroll_area, "widget", attrib={"class": "QWidget", "name": "scrollAreaWidgetContents"}
            )
            sc_geometry = ET.SubElement(scroll_contents, "property", attrib={"name": "geometry"})
            sc_rect = ET.SubElement(sc_geometry, "rect")
            ET.SubElement(sc_rect, "x").text = "0"
            ET.SubElement(sc_rect, "y").text = "0"
            ET.SubElement(sc_rect, "width").text = str(edm_parser.ui.width)
            ET.SubElement(sc_rect, "height").text = str(edm_parser.ui.height)

            central_widget = ET.SubElement(
                scroll_contents,
                "widget",
                attrib={
                    "class": "QWidget",
                    "name": "centralwidget",
                },
            )
        else:
            central_widget = ET.SubElement(
                main_widget,
                "widget",
                attrib={
                    "class": "QWidget",
                    "name": "centralwidget",
                },
            )

        return ui_element, central_widget

    """def add_screen_properties(self, main_widget: ET.Element, properties: dict[str, Any]) -> None:
        if "bgColor" in properties:
            style_prop = ET.SubElement(main_widget, "property", attrib={"name": "styleSheet"})
            style_string = ET.SubElement(style_prop, "string")
            style_string.text = f"#Form {{ background-color: rgba{properties['bgColor']} }}"  # commented code adds bg to all child widgets but for now, this is fine
            # TODO: There is a bug that the background does not show up normally but does in designer"""

    def add_screen_properties(self, main_widget: ET, properties: dict[str, Any]) -> None:
        if "bgColor" in properties:
            style_prop = ET.SubElement(main_widget, "property", attrib={"name": "styleSheet"})
            style_string = ET.SubElement(style_prop, "string")

            central_bg_dict = {"background-color": properties["bgColor"]}
            style_string.text = f"{StyleSheet(central_bg_dict).to_style_string()}"
