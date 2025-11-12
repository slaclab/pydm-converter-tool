from xml.etree import ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pydmconverter.custom_types import RGBA, RuleArguments
from pydmconverter.widgets_helpers import (
    Int,
    Double,
    Bool,
    Str,
    Drawable,
    Hidable,
    Alarmable,
    Legible,
    TransparentBackground,
    StyleSheet,
    Alignment,
    PixMap,
    StyleSheetObject,
    OnOffColor,
    ColorObject,
    Brush,
    Enum,
    StringList,
    Row,
    Column,
)
import logging
from epics import PV


@dataclass
class PyDMFrame(Alarmable):
    """
    PyDMFrame is a container widget that can hold other PyDM widgets.
    It inherits from Alarmable to support alarm-related features.

    Attributes
    ----------
    frameShape : Optional[str]
        The shape of the frame.
    frameShadow : Optional[str]
        The shadow style of the frame.
    lineWidth : Optional[int]
        The width of the frame's line.
    midLineWidth : Optional[int]
        The width of the mid-line of the frame.
    disableOnDisconnect : Optional[bool]
        If True, disables the frame on disconnect.
    children : List[PyDMFrame]
        A list of child PyDMFrame widgets.
    count : ClassVar[int]
        A class variable counting frames.
    """

    frameShape: Optional[str] = None
    frameShadow: Optional[str] = None
    lineWidth: Optional[int] = None
    midLineWidth: Optional[int] = None
    disableOnDisconnect: Optional[bool] = None

    children: List["PyDMFrame"] = field(default_factory=list)

    def add_child(self, child: "PyDMFrame") -> None:
        """
        Add a child widget to this frame's internal list.

        Parameters
        ----------
        child : PyDMFrame
            The child widget to add.

        Returns
        -------
        None
        """
        self.children.append(child)

    def to_xml(self) -> ET.Element:
        """
        Serialize the PyDMFrame and its children to an XML element.

        Returns
        -------
        ET.Element
            The XML element representing this PyDMFrame and its children.
        """
        widget_el: ET.Element = super().to_xml()

        for child in self.children:
            widget_el.append(child.to_xml())

        return widget_el

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMFrame-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of this PyDMFrame.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.frameShape is not None:
            properties.append(Str("frameShape", self.frameShape).to_xml())
        if self.frameShadow is not None:
            properties.append(Str("frameShadow", self.frameShadow).to_xml())
        if self.lineWidth is not None:
            properties.append(Int("lineWidth", self.lineWidth).to_xml())
        if self.midLineWidth is not None:
            properties.append(Int("midLineWidth", self.midLineWidth).to_xml())
        if self.disableOnDisconnect is not None:
            properties.append(Bool("disableOnDisconnect", self.disableOnDisconnect).to_xml())
        properties.append(TransparentBackground().to_xml())

        return properties


@dataclass
class QLabel(Legible, StyleSheetObject):
    """
    QLabel is a label widget that supports numerical precision, unit display,
    tool tip text, and a configurable frame shape.

    Attributes
    ----------
    precision : Optional[int]
        The numerical precision to display (if applicable).
    show_units : Optional[bool]
        Flag to indicate if units should be displayed.
    tool_tip : Optional[str]
        The tooltip text for the label.
    frame_shape : Optional[str]
        The frame shape style for the label.
    count : ClassVar[int]
        Class variable tracking the number of QLabel instances.
    """

    precision: Optional[int] = None
    show_units: Optional[bool] = None
    tool_tip: Optional[str] = None
    frame_shape: Optional[str] = None
    alignment: Optional[str] = None
    useDisplayBg: Optional[bool] = None
    filename: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate QLabel-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of the QLabel.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.precision is not None:
            properties.append(Int("precision", self.precision).to_xml())
        if self.show_units is not None:
            properties.append(Bool("showUnits", self.show_units).to_xml())
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.frame_shape is not None:
            properties.append(Str("frameShape", self.frame_shape).to_xml())
        if self.alignment is not None:
            properties.append(Alignment(self.alignment).to_xml())
        if self.filename is not None and self.name.startswith("activePngClass"):
            properties.append(PixMap(self.filename).to_xml())

        return properties


@dataclass
class PyDMLabel(QLabel, Alarmable):
    """
    PyDMLabel is an extension of QLabel that supports an additional property to indicate whether
    the numerical precision should be derived from the process variable (PV).

    Attributes
    ----------
    precision_from_pv : Optional[bool]
        If True, the numerical precision is determined from the process variable.
        If None, no such property is added.
    count : ClassVar[int]
        A class variable tracking the number of PyDMLabel instances.
    """

    precision_from_pv: Optional[bool] = None
    autoSize: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.autoSize:
            self.adjustSize()

    def setText(self, text):
        super().setText(text)
        if self.autoSize:
            self.adjustSize()

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMLabel-specific properties for XML serialization.

        This method extends the properties generated by its superclass by appending a property
        for 'precisionFromPV' if the corresponding attribute is not None.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of the PyDMLabel.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.precision_from_pv is not None:
            properties.append(Bool("precisionFromPV", self.precision_from_pv).to_xml())
        if self.autoSize:
            properties.append(Bool("autoSize", True).to_xml())
        return properties


@dataclass
class PyDMLineEdit(Legible, Alarmable, StyleSheetObject):
    """
    PyDMLineEdit represents a PyDMLineEdit widget with XML serialization capabilities.
    It extends Legible, and Alarmable to support additional features.

    Attributes
    ----------
    displayFormat : Optional[int]
        An integer representing the display format. If None, the display format property is omitted.
    count : ClassVar[int]
        A class variable tracking the number of PyDMLineEdit instances.
    """

    displayFormat: Optional[int] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMLineEdit-specific properties for XML serialization.

        This method extends the properties generated by the superclass by appending a property
        for 'displayFormat' if the attribute is not None.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of the PyDMLineEdit.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.displayFormat is not None:
            properties.append(Int("displayFormat", self.displayFormat).to_xml())
        return properties


@dataclass
class PyDMDrawingRectangle(Alarmable, Drawable, Hidable):
    """
    PyDMDrawingRectangle represents a drawable rectangle that supports XML serialization,
    alarm functionality, and can be hidden.

    Attributes
    ----------
    indicatorColor: Optional[RGBA]
        The fill color for specifically activebar/slacbarclass rectangles
    """

    indicatorColor: Optional[RGBA] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate XML properties for the drawable widget.

        Returns
        -------
        List[etree.Element]
            A list containing geometry, pen, brush, and rotation properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.indicatorColor is not None:
            properties.append(Brush(*self.indicatorColor, fill=True).to_xml())

        return properties


@dataclass
class PyDMDrawingEllipse(Alarmable, Drawable, Hidable, StyleSheetObject):
    """
    PyDMDrawingEllipse represents a drawable ellipse that supports XML serialization,
    alarm functionality, and can be hidden.

    This class does not add any extra properties beyond those provided by its base classes.

    Attributes
    ----------
    count : ClassVar[int]
        A class variable tracking the number of PyDMDrawingEllipse instances.
    """


@dataclass
class PyDMDrawingArc(Alarmable, Drawable, Hidable, StyleSheetObject):
    """
    PyDMDrawingArc represents a drawable ellipse that supports XML serialization,
    alarm functionality, and can be hidden.

    This class does not add any extra properties beyond those provided by its base classes.
    """

    startAngle: Optional[float] = None
    spanAngle: Optional[int] = 180

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate XML properties for the drawable widget.

        Returns
        -------
        List[etree.Element]
            A list containing arc properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.startAngle is not None:
            properties.append(
                Double("startAngle", self.startAngle).to_xml()
            )  # TODO: Maybe make a float class (probabaly unnecessary)
        properties.append(Int("spanAngle", self.spanAngle).to_xml())

        return properties


@dataclass
class PyDMDrawingPie(Alarmable, Drawable, Hidable, StyleSheetObject):
    """
    PyDMDrawingPie represents a filled pie/wedge shape that supports XML serialization,
    alarm functionality, and can be hidden.

    This is used for EDM arcs that have fill enabled.
    """

    startAngle: Optional[float] = None
    spanAngle: Optional[int] = 180

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate XML properties for the pie widget.

        Returns
        -------
        List[etree.Element]
            A list containing pie properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.startAngle is not None:
            properties.append(Double("startAngle", self.startAngle).to_xml())
        properties.append(Int("spanAngle", self.spanAngle).to_xml())

        return properties


@dataclass
class QPushButton(
    Legible, StyleSheetObject
):  # TODO: This creates a stylesheet for children classes but is overriden later (may need to remove to prevent repeated properties)
    """
    QPushButton is a button widget that supports text, icons, and various behavioral properties.

    Attributes
    ----------
    text : Optional[str]
        The label text displayed on the button.
    auto_default : Optional[bool]
        Determines if the button should automatically become the default button.
    default : Optional[bool]
        Indicates if the button is the default action.
    flat : Optional[bool]
        If True, the button is drawn with a flat appearance.
    tool_tip : Optional[str]
        The tooltip text that appears when hovering over the button.
    icon : Optional[str]
        The icon name or path displayed on the button.
    checkable : Optional[bool]
        Specifies whether the button supports a toggled (checked/unchecked) state.
    checked : Optional[bool]
        The initial checked state of the button.
    count : ClassVar[int]
        A class variable tracking the number of QPushButton instances.
    """

    auto_default: Optional[bool] = None
    default: Optional[bool] = None
    flat: Optional[bool] = None
    tool_tip: Optional[str] = None
    icon: Optional[str] = None
    checkable: Optional[bool] = None
    checked: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate QPushButton-specific properties for XML serialization.

        This method extends the properties generated by the superclass by appending
        QPushButton-specific properties if they are set.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the QPushButton properties.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.auto_default is not None:
            properties.append(Bool("autoDefault", self.auto_default).to_xml())
        if self.default is not None:
            properties.append(Bool("default", self.default).to_xml())
        if self.flat is not None:
            properties.append(Bool("flat", self.flat).to_xml())
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.icon is not None:
            properties.append(Str("icon", self.icon).to_xml())
        if self.checkable is not None:
            properties.append(Bool("checkable", self.checkable).to_xml())
        if self.checked is not None:
            properties.append(Bool("checked", self.checked).to_xml())

        return properties


@dataclass
class PyDMPushButtonBase(QPushButton, Alarmable):
    """
    PyDMPushButtonBase extends QPushButton with additional PyDM-specific properties,
    including icon settings and password protection features.

    Attributes
    ----------
    pydm_icon : Optional[str]
        Icon identifier or file path for the PyDM button.
    pydm_icon_color : Optional[str]
        The color to apply to the PyDM icon.
    password_protected : Optional[bool]
        Indicates whether the button is password protected.
    password : Optional[str]
        The password used by the button (if applicable).
    protected_password : Optional[str]
        A version of the password that is protected or encrypted.
    count : ClassVar[int]
        Class variable tracking the number of PyDMPushButtonBase instances.
    """

    pydm_icon: Optional[str] = None
    pydm_icon_color: Optional[str] = None
    password_protected: Optional[bool] = None
    password: Optional[str] = None
    protected_password: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMPushButtonBase-specific properties for XML serialization.

        This method extends the properties generated by the superclass (QPushButton) by appending
        additional properties related to PyDM-specific features if they are not None.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMPushButtonBase properties.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.pydm_icon is not None:
            properties.append(Str("PyDMIcon", self.pydm_icon).to_xml())
        if self.pydm_icon_color is not None:
            properties.append(Str("PyDMIconColor", self.pydm_icon_color).to_xml())
        if self.password_protected is not None:
            properties.append(Bool("passwordProtected", self.password_protected).to_xml())
        if self.password is not None:
            properties.append(Str("password", self.password).to_xml())
        if self.protected_password is not None:
            properties.append(Str("protectedPassword", self.protected_password).to_xml())
        if isinstance(self.name, str) and self.name.startswith("activeMenuButtonClass"):
            properties.append(Str("text", "Menu").to_xml())

        return properties


@dataclass
class PyDMPushButton(PyDMPushButtonBase):
    """
    PyDMPushButton extends PyDMPushButtonBase with additional properties for push button behavior.

    Attributes
    ----------
    monitor_disp : Optional[bool]
        If True, enables monitoring of the display.
    show_confirm_dialog : Optional[bool]
        If True, displays a confirmation dialog before action.
    confirm_message : Optional[str]
        The confirmation message to display.
    press_value : Optional[str]
        The value to send when the button is pressed.
    release_value : Optional[str]
        The value to send when the button is released.
    relative_change : Optional[bool]
        If True, indicates that the change is relative.
    write_when_release : Optional[bool]
        If True, writes the value when the button is released.
    count : ClassVar[int]
        Class variable tracking the number of PyDMPushButton instances.
    """

    monitor_disp: Optional[bool] = None
    show_confirm_dialog: Optional[bool] = None
    confirm_message: Optional[str] = None
    press_value: Optional[str] = None
    release_value: Optional[str] = None
    relative_change: Optional[bool] = None
    write_when_release: Optional[bool] = None
    on_color: Optional[RGBA] = None  # TODO: clean up where these attributes are called to a parent to reduce redundancy
    off_color: Optional[RGBA] = (
        None  # TODO: clean up where these attributes are called to a parent to reduce redundancy
    )
    foreground_color: Optional[RGBA] = None
    background_color: Optional[RGBA] = None
    useDisplayBg: Optional[bool] = None
    on_label: Optional[str] = None
    off_label: Optional[str] = None
    is_off_button: Optional[bool] = None
    is_freeze_button: Optional[bool] = None
    text: Optional[str] = None
    visMin: Optional[int] = None
    visMax: Optional[int] = None
    pressValue: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMPushButton-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMPushButton properties.
        """
        if self.is_off_button is not None:
            show_button = not self.is_off_button

            self.rules.append(RuleArguments("Visible", self.channel, False, show_button, None, None))
            self.rules.append(RuleArguments("Enable", self.channel, False, show_button, None, None))
            enum_index = 0 if self.is_off_button else 1
            if self.text is None and self.channel is not None:
                pv = PV(self.channel, connection_timeout=0.5)
                if pv and pv.enum_strs and len(list(pv.enum_strs)) >= 2:
                    self.text = pv.enum_strs[enum_index]
        if self.is_freeze_button is not None and not self.is_freeze_button:
            self.channel = "loc://FROZEN_STATE?type=int&init=0"
            self.rules.append(RuleArguments("Visible", "loc://FROZEN_STATE", False, False, None, None))
            self.rules.append(RuleArguments("Enable", "loc://FROZEN_STATE", False, False, None, None))
        elif self.is_freeze_button is not None and self.is_freeze_button:
            self.channel = "loc://FROZEN_STATE"
            self.rules.append(RuleArguments("Visible", "loc://FROZEN_STATE", False, True, None, None))
            self.rules.append(RuleArguments("Enable", "loc://FROZEN_STATE", False, True, None, None))

        properties: List[ET.Element] = super().generate_properties()
        if self.monitor_disp is not None:
            properties.append(Bool("monitorDisp", self.monitor_disp).to_xml())
        if self.show_confirm_dialog is not None:
            properties.append(Bool("showConfirmDialog", self.show_confirm_dialog).to_xml())
        if self.confirm_message is not None:
            properties.append(Str("confirmMessage", self.confirm_message).to_xml())
        if self.press_value is not None:
            properties.append(Str("pressValue", self.press_value).to_xml())
        if self.release_value is not None:
            properties.append(Str("releaseValue", self.release_value).to_xml())
        if self.relative_change is not None:
            properties.append(Bool("relativeChange", self.relative_change).to_xml())
        if self.write_when_release is not None:
            properties.append(Bool("writeWhenRelease", self.write_when_release).to_xml())
        if self.on_label is not None:
            properties.append(Str("text", self.on_label).to_xml())
        if self.is_freeze_button is not None and not self.is_freeze_button:
            properties.append(Str("pressValue", "1").to_xml())
        if self.is_freeze_button is not None and self.is_freeze_button:
            properties.append(Str("pressValue", "0").to_xml())
        if (
            self.on_color is not None
            or self.foreground_color is not None
            or self.background_color is not None
            or (
                isinstance(self.name, str)
                and (
                    self.name.startswith("activeMenuButtonClass") or self.name.startswith("activeMessageButtonClass")
                )  # TODO: Eventually remove this whole stylesheet property
            )
        ):
            styles: Dict[str, any] = {}
            if self.name.startswith("activeMenuButtonClass") or self.name.startswith("activeMessageButtonClass"):
                styles["border"] = "1px solid black"
            if self.foreground_color is not None:
                styles["color"] = self.foreground_color
            if (
                self.on_color is not None
            ):  # TODO: find if on_color/background_color should take precedent (they are used for diff edm classes anyway) #TODO: Replace with OnOffColor class eventually
                styles["background-color"] = self.on_color
            elif self.background_color is not None and self.useDisplayBg is None:
                styles["background-color"] = self.background_color
            if self.on_color is not None and self.off_color != self.on_color:
                logging.warning("on and off colors are different, need to modify code")
            properties.append(StyleSheet(styles).to_xml())
        return properties


@dataclass
class PyDMShellCommand(PyDMPushButtonBase, StyleSheetObject):
    """
    PyDMShellCommand extends PyDMPushButtonBase to execute shell commands.

    Attributes
    ----------
    show_confirm_dialog : Optional[bool]
        If True, displays a confirmation dialog before executing the command.
    confirm_message : Optional[str]
        The message to display in the confirmation dialog.
    run_commands_in_full_shell : Optional[bool]
        If True, runs commands in a full shell environment.
    environment_variables : Optional[str]
        Environment variables to pass to the command.
    show_icon : Optional[bool]
        If True, displays an icon on the button.
    redirect_command_output : Optional[bool]
        If True, redirects the command output.
    allow_multiple_executions : Optional[bool]
        If True, permits multiple command executions.
    titles : Optional[List[str]]
        Titles associated with the commands (one per command).
    command : Optional[List[str]]
        The shell commands to execute.
    count : ClassVar[int]
        Class variable tracking the number of PyDMShellCommand instances.
    """

    show_confirm_dialog: Optional[bool] = None
    confirm_message: Optional[str] = None
    run_commands_in_full_shell: Optional[bool] = None
    environment_variables: Optional[str] = None
    show_icon: Optional[bool] = None
    redirect_command_output: Optional[bool] = None
    allow_multiple_executions: Optional[bool] = None
    titles: Optional[List[str]] = None
    command: Optional[List[str]] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMShellCommand-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMShellCommand properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.show_confirm_dialog is not None:
            properties.append(Bool("showConfirmDialog", self.show_confirm_dialog).to_xml())
        if self.confirm_message is not None:
            properties.append(Str("confirmMessage", self.confirm_message).to_xml())
        if self.run_commands_in_full_shell is not None:
            properties.append(Bool("runCommandsInFullShell", self.run_commands_in_full_shell).to_xml())
        if self.environment_variables is not None:
            properties.append(Str("environmentVariables", self.environment_variables).to_xml())
        if self.show_icon is not None:
            properties.append(Bool("showIcon", self.show_icon).to_xml())
        else:
            properties.append(Bool("showIcon", False).to_xml())
        if self.redirect_command_output is not None:
            properties.append(Bool("redirectCommandOutput", self.redirect_command_output).to_xml())
        if self.allow_multiple_executions is not None:
            properties.append(Bool("allowMultipleExecutions", self.allow_multiple_executions).to_xml())
        if self.titles is not None and self.command is not None:
            properties.append(StringList("titles", self.titles).to_xml())
            properties.append(StringList("commands", self.command).to_xml())
        return properties


@dataclass
class PyDMRelatedDisplayButton(PyDMPushButtonBase):
    """
    PyDMRelatedDisplayButton extends PyDMPushButtonBase to support opening related displays.

    Attributes
    ----------
    show_icon : Optional[bool]
        If True, an icon is displayed.
    filenames : Optional[str]
        The filenames associated with the display.
    titles : Optional[str]
        The titles for the display.
    macros : Optional[str]
        Macros used for the display.
    open_in_new_window : Optional[bool]
        If True, opens the display in a new window.
    follow_symlinks : Optional[bool]
        If True, follows symbolic links.
    count : ClassVar[int]
        Class variable tracking the number of PyDMRelatedDisplayButton instances.
    """

    show_icon: Optional[bool] = None
    filenames: Optional[str] = None
    titles: Optional[str] = None
    macros: Optional[str] = None
    open_in_new_window: Optional[bool] = None
    follow_symlinks: Optional[bool] = None
    displayFileName = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMRelatedDisplayButton-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMRelatedDisplayButton properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.show_icon is not None:
            properties.append(Bool("showIcon", self.show_icon).to_xml())
        else:
            properties.append(Bool("showIcon", False).to_xml())
        # if self.filenames is not None:
        #    properties.append(Str("filenames", self.filenames).to_xml()) #TODO: Maybe come back and include this if it comes up in edm
        if self.titles is not None:
            properties.append(Str("titles", self.titles).to_xml())
        if self.macros is not None:
            properties.append(Str("macros", self.macros).to_xml())
        # if self.open_in_new_window is not None:
        properties.append(Bool("openInNewWindow", True).to_xml())
        if self.follow_symlinks is not None:
            properties.append(Bool("followSymlinks", self.follow_symlinks).to_xml())
        if (
            self.displayFileName is not None and self.displayFileName
        ):  # TODO: Come back and find out why sometimes an empty list
            converted_filenames = list(map(self.convert_filetype, self.displayFileName))
            properties.append(StringList("filenames", converted_filenames).to_xml())
        return properties

    def convert_filetype(self, file_string: str) -> None:
        """
        Converts file strings of .<type> to .ui
        """
        filearr = file_string.split(".")
        if len(filearr) > 1:
            filename = ".".join(filearr[:-1])
        else:
            filename = file_string
        return f"{filename}.ui"


@dataclass
class QComboBox(Legible):
    """
    QComboBox represents a combo box widget with various configurable properties.

    Attributes
    ----------
    editable : Optional[bool]
        If True, the combo box is editable.
    current_text : Optional[str]
        The current text displayed in the combo box.
    max_visible_items : Optional[int]
        Maximum number of visible items in the dropdown.
    max_count : Optional[int]
        Maximum number of items allowed.
    insert_policy : Optional[str]
        The policy for inserting new items.
    size_adjust_policy : Optional[str]
        The policy for adjusting the size.
    minimum_contents_length : Optional[int]
        The minimum content length.
    icon_size : Optional[str]
        The size for the icons.
    duplicates_enabled : Optional[bool]
        If True, duplicate items are allowed.
    frame : Optional[bool]
        If True, the combo box is framed.
    model_column : Optional[int]
        The model column used.
    count : ClassVar[int]
        Class variable tracking the number of QComboBox instances.
    """

    editable: Optional[bool] = None
    current_text: Optional[str] = None
    max_visible_items: Optional[int] = None
    max_count: Optional[int] = None
    insert_policy: Optional[str] = None
    size_adjust_policy: Optional[str] = None
    minimum_contents_length: Optional[int] = None
    icon_size: Optional[str] = None
    duplicates_enabled: Optional[bool] = None
    frame: Optional[bool] = None
    model_column: Optional[int] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate QComboBox-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the QComboBox properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.editable is not None:
            properties.append(Bool("editable", self.editable).to_xml())
        if self.current_text is not None:
            properties.append(Str("currentText", self.current_text).to_xml())
        if self.max_visible_items is not None:
            properties.append(Int("maxVisibleItems", self.max_visible_items).to_xml())
        if self.max_count is not None:
            properties.append(Int("maxCount", self.max_count).to_xml())
        if self.insert_policy is not None:
            properties.append(Str("insertPolicy", self.insert_policy).to_xml())
        if self.size_adjust_policy is not None:
            properties.append(Str("sizeAdjustPolicy", self.size_adjust_policy).to_xml())
        if self.minimum_contents_length is not None:
            properties.append(Int("minimumContentsLength", self.minimum_contents_length).to_xml())
        if self.icon_size is not None:
            properties.append(Str("iconSize", self.icon_size).to_xml())
        if self.duplicates_enabled is not None:
            properties.append(Bool("duplicatesEnabled", self.duplicates_enabled).to_xml())
        if self.frame is not None:
            properties.append(Bool("frame", self.frame).to_xml())
        if self.model_column is not None:
            properties.append(Int("modelColumn", self.model_column).to_xml())
        return properties


@dataclass
class PyDMEnumComboBox(QComboBox, Alarmable, StyleSheetObject):
    """
    PyDMEnumComboBox extends QComboBox to support enumeration with additional properties.

    Attributes
    ----------
    tool_tip : Optional[str]
        The tooltip text for the combo box.
    monitor_disp : Optional[bool]
        If True, enables monitoring of the display.
    """

    tool_tip: Optional[str] = None
    monitor_disp: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMEnumComboBox-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMEnumComboBox properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.monitor_disp is not None:
            properties.append(Bool("monitorDisp", self.monitor_disp).to_xml())
        return properties


@dataclass
class PyDMEnumButton(Alarmable, Legible):
    """
    PyDMEnumButton represents a button widget with enumerated options and layout properties.

    Attributes
    ----------
    tool_tip : Optional[str]
        The tooltip text for the button.
    monitor_disp : Optional[bool]
        If True, enables monitoring of the display.
    items_translatable : Optional[bool]
        If True, the items are translatable.
    items_disambiguation : Optional[str]
        Disambiguation text for the items.
    items_comment : Optional[str]
        Comment text for the items.
    use_custom_order : Optional[bool]
        If True, a custom order is used.
    invert_order : Optional[bool]
        If True, inverts the order of the items.
    custom_order_translatable : Optional[bool]
        If True, the custom order is translatable.
    custom_order_disambiguation : Optional[str]
        Disambiguation text for the custom order.
    custom_order_comment : Optional[str]
        Comment for the custom order.
    widget_type : Optional[str]
        The widget type.
    orientation : Optional[str]
        The orientation of the widget.
    margin_top : Optional[int]
        Top margin.
    margin_bottom : Optional[int]
        Bottom margin.
    margin_left : Optional[int]
        Left margin.
    margin_right : Optional[int]
        Right margin.
    horizontal_spacing : Optional[int]
        Horizontal spacing.
    vertical_spacing : Optional[int]
        Vertical spacing.
    checkable : Optional[bool]
        If True, the button is checkable.
    count : ClassVar[int]
        Class variable tracking the number of PyDMEnumButton instances.
    """

    tool_tip: Optional[str] = None
    monitor_disp: Optional[bool] = None
    items_translatable: Optional[bool] = None
    items_disambiguation: Optional[str] = None
    items_comment: Optional[str] = None
    use_custom_order: Optional[bool] = None
    invert_order: Optional[bool] = None
    custom_order_translatable: Optional[bool] = None
    custom_order_disambiguation: Optional[str] = None
    custom_order_comment: Optional[str] = None
    widget_type: Optional[str] = None
    orientation: Optional[str] = None
    margin_top: Optional[int] = 0
    margin_bottom: Optional[int] = 0
    margin_left: Optional[int] = 0
    margin_right: Optional[int] = 0
    horizontal_spacing: Optional[int] = 0
    vertical_spacing: Optional[int] = 0
    checkable: Optional[bool] = None
    tab_names: Optional[List[str]] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMEnumButton-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMEnumButton properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.monitor_disp is not None:
            properties.append(Bool("monitorDisp", self.monitor_disp).to_xml())
        if self.items_translatable is not None:
            properties.append(Bool("itemsTranslatable", self.items_translatable).to_xml())
        if self.items_disambiguation is not None:
            properties.append(Str("itemsDisambiguation", self.items_disambiguation).to_xml())
        if self.items_comment is not None:
            properties.append(Str("itemsComment", self.items_comment).to_xml())
        if self.use_custom_order is not None:
            properties.append(Bool("useCustomOrder", self.use_custom_order).to_xml())
        if self.invert_order is not None:
            properties.append(Bool("invertOrder", self.invert_order).to_xml())
        if self.custom_order_translatable is not None:
            properties.append(Bool("customOrderTranslatable", self.custom_order_translatable).to_xml())
        if self.custom_order_disambiguation is not None:
            properties.append(Str("customOrderDisambiguation", self.custom_order_disambiguation).to_xml())
        if self.custom_order_comment is not None:
            properties.append(Str("customOrderComment", self.custom_order_comment).to_xml())
        if self.widget_type is not None:
            properties.append(Str("widgetType", self.widget_type).to_xml())
        if self.orientation is not None:
            properties.append(Enum("orientation", f"Qt::{self.orientation.capitalize()}").to_xml())
        elif self.tab_names is not None:
            properties.append(Enum("orientation", "Qt::Horizontal").to_xml())
        if self.margin_top is not None:
            properties.append(Int("marginTop", self.margin_top).to_xml())
        if self.margin_bottom is not None:
            properties.append(Int("marginBottom", self.margin_bottom).to_xml())
        if self.margin_left is not None:
            properties.append(Int("marginLeft", self.margin_left).to_xml())
        if self.margin_right is not None:
            properties.append(Int("marginRight", self.margin_right).to_xml())
        if self.horizontal_spacing is not None:
            properties.append(Int("horizontalSpacing", self.horizontal_spacing).to_xml())
        if self.vertical_spacing is not None:
            properties.append(Int("verticalSpacing", self.vertical_spacing).to_xml())
        if self.checkable is not None:
            properties.append(Bool("checkable", self.checkable).to_xml())
        return properties


@dataclass
class PyDMDrawingLine(Legible, Drawable, Alarmable):
    """
    PyDMDrawingLine represents a drawable line with arrow properties.

    Attributes
    ----------
    arrow_size : Optional[int]
        The size of the arrow.
    arrow_end_point : Optional[bool]
        If True, draws an arrow at the end point.
    arrow_start_point : Optional[bool]
        If True, draws an arrow at the start point.
    arrow_mid_point : Optional[bool]
        If True, draws an arrow at the midpoint.
    flip_mid_point_arrow : Optional[bool]
        If True, flips the midpoint arrow.
    count : ClassVar[int]
        Class variable tracking the number of PyDMDrawingLine instances.
    """

    pen_width: Optional[int] = None
    arrow_size: Optional[int] = None
    arrow_end_point: Optional[bool] = None
    arrow_start_point: Optional[bool] = None
    arrow_mid_point: Optional[bool] = None
    flip_mid_point_arrow: Optional[bool] = None
    arrows: Optional[str] = None
    penColor: Optional[RGBA] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingLine-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMDrawingLine properties.
        """
        if self.arrows in ("to", "from", "both"):
            self.brushFill = True
            self.brushColor = self.penColor

        properties: List[ET.Element] = super().generate_properties()
        if self.pen_width is not None:
            properties.append(Int("penWidth", self.pen_width).to_xml())
        if self.arrow_size is not None:
            properties.append(Int("arrowSize", self.arrow_size).to_xml())
        if self.arrow_end_point is not None:
            properties.append(Bool("arrowEndPoint", self.arrow_end_point).to_xml())
        if self.arrow_start_point is not None:
            properties.append(Bool("arrowStartPoint", self.arrow_start_point).to_xml())
        if self.arrow_mid_point is not None:
            properties.append(Bool("arrowMidPoint", self.arrow_mid_point).to_xml())
        if self.flip_mid_point_arrow is not None:
            properties.append(Bool("flipMidPointArrow", self.flip_mid_point_arrow).to_xml())
        if self.arrows is not None and (self.arrows == "both" or self.arrows == "to"):
            properties.append(Bool("arrowStartPoint", True).to_xml())
        if self.arrows is not None and (self.arrows == "both" or self.arrows == "from"):
            properties.append(Bool("arrowEndPoint", True).to_xml())
        properties.append(TransparentBackground().to_xml())
        return properties


@dataclass
class PyDMDrawingPolyline(PyDMDrawingLine):
    """
    PyDMDrawingPolyline represents a drawable polyline defined by a sequence of points.

    Attributes
    ----------
    points : Optional[List[str]]
        A list of point strings in the format "x, y".
    count : ClassVar[int]
        Class variable tracking the number of PyDMDrawingPolyline instances.
    """

    points: Optional[List[str]] = None
    arrows: Optional[str] = None
    closePolygon: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingPolyline-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMDrawingPolyline properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.points is not None:
            points_prop = ET.Element("property", attrib={"name": "points", "stdset": "0"})
            stringlist = ET.SubElement(points_prop, "stringlist")
            for point in self.points:
                string_el = ET.SubElement(stringlist, "string")
                string_el.text = point  # Use points as-is, no offset adjustment

            # If closePolygon is True, add the first point at the end to close the shape
            if self.closePolygon is True:
                # Only add closing point if first and last are different
                if self.points and self.points[0] != self.points[-1]:
                    string_el = ET.SubElement(stringlist, "string")
                    string_el.text = self.points[0]  # Close polygon with first point

            properties.append(points_prop)
        return properties


@dataclass
class PyDMDrawingIrregularPolygon(Alarmable, Drawable, Hidable):
    """
    PyDMDrawingIrregularPolygon represents a filled irregular polygon defined by points.
    The first and last points must be the same to close the shape, creating a defined
    inside and outside that can be filled with color.

    Attributes
    ----------
    points : Optional[List[str]]
        A list of point strings in the format "x, y". First and last points should match
        to close the polygon.
    count : ClassVar[int]
        Class variable tracking the number of PyDMDrawingIrregularPolygon instances.
    """

    points: Optional[List[str]] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingIrregularPolygon-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMDrawingIrregularPolygon properties.
        """
        properties: List[ET.Element] = super().generate_properties()

        # Always add transparent background for widget itself (not the polygon fill)
        # This ensures the rectangular widget background doesn't obstruct other widgets
        # The polygon shape will still be filled via the brush property
        from pydmconverter.widgets_helpers import TransparentBackground

        properties.append(TransparentBackground().to_xml())

        if self.points is not None:
            points_prop = ET.Element("property", attrib={"name": "points", "stdset": "0"})
            stringlist = ET.SubElement(points_prop, "stringlist")

            for point in self.points:
                string_el = ET.SubElement(stringlist, "string")
                string_el.text = point

            # Ensure polygon is closed (first point == last point)
            if self.points and self.points[0] != self.points[-1]:
                string_el = ET.SubElement(stringlist, "string")
                string_el.text = self.points[0]  # Add first point again to close

            properties.append(points_prop)

        return properties


@dataclass
class PyDMEmbeddedDisplay(Alarmable, Hidable, Drawable):
    """
    PyDMEmbeddedDisplay embeds another UI file (display) inside the current display.

    Attributes
    ----------
    filename : Optional[str]
        The path to the embedded UI file.
    macros : Optional[Dict[str, str]]
        Macros to pass down to the embedded display.
    visible : Optional[bool]
        Whether the embedded display is visible.
    """

    filename: Optional[str] = None
    macros: Optional[Dict[str, str]] = field(default_factory=dict)
    visible: Optional[bool] = True
    noscroll: Optional[bool] = True
    background_color: Optional[bool] = None
    foreground_color: Optional[bool] = None

    def generate_properties(self) -> list:
        """
        Generate XML elements for PyDMEmbeddedDisplay properties.
        """
        properties = super().generate_properties()
        if self.filename is not None:
            converted_filename = self.convert_filetype(self.filename)
            properties.append(Str("filename", converted_filename).to_xml())
        if self.macros:
            import json

            macros_str = json.dumps(self.macros)
            properties.append(Str("macros", macros_str).to_xml())
        if self.visible is not None:
            properties.append(Bool("visible", self.visible).to_xml())
        if self.noscroll is not None:
            scroll: Bool = not self.noscroll
            properties.append(Bool("scrollable", scroll).to_xml())
        if (
            self.foreground_color is not None
            or self.background_color is not None
            or (isinstance(self.name, str) and self.name.startswith("activePipClass"))
        ):
            styles: Dict[str, any] = {}
            if self.name.startswith("activePipClass"):
                styles["border"] = "1px solid black"
            if self.foreground_color is not None:
                styles["color"] = self.foreground_color
            elif self.background_color is not None:
                styles["background-color"] = self.background_color
            properties.append(StyleSheet(styles).to_xml())
        return properties

    def convert_filetype(self, file_string: str) -> None:
        """
        Converts file strings of .<type> to .ui
        """
        filename = ".".join(file_string.split(".")[:-1])
        return f"{filename}.ui"  # TODO: ask if this should be expanded or be turned into a Path


@dataclass
class PyDMImageView(Alarmable):
    """
    PyDMImageView represents an image file to be inserted.

    Attributes
    ----------
    filename : Optional[str]
        A string representing the filename of the image file.
    """

    filename: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMImageView-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMImageView properties.
        """

        properties: List[ET.Element] = super().generate_properties()

        if self.filename is not None:
            properties.append(Str("filename", self.filename).to_xml())

        return properties


@dataclass
class QTabWidget(Alarmable):
    """
    PyDMTabWidget is a container widget that can hold tabWidgets.
    It inherits from Alarmable to support alarm-related features.

    Attributes
    ----------
    frameShape : Optional[str]
        The shape of the frame.
    frameShadow : Optional[str]
        The shadow style of the frame.
    lineWidth : Optional[int]
        The width of the frame's line.
    midLineWidth : Optional[int]
        The width of the mid-line of the frame.
    disableOnDisconnect : Optional[bool]
        If True, disables the frame on disconnect.
    tabs : List[str]
        A list of child tab widgets.
    """

    frameShape: Optional[str] = None
    frameShadow: Optional[str] = None
    lineWidth: Optional[int] = None
    midLineWidth: Optional[int] = None
    disableOnDisconnect: Optional[bool] = None

    tabs: List[str] = field(default_factory=list)
    children: List["PyDMFrame"] = field(default_factory=list)
    embeddedHeight: Optional[int] = None
    embeddedWidth: Optional[int] = None

    def add_child(self, child) -> None:
        """
        Add a child widget to this frame's internal list.

        Parameters
        ----------
        child : PyDMFrame
            The child widget to add.

        Returns
        -------
        None
        """
        self.children.append(child)

    def to_xml(self) -> ET.Element:
        """
        Serialize the PyDMTabWidget and its children to an XML element.

        Returns
        -------
        ET.Element
            The XML element representing this PyDMFrame and its children.
        """
        widget_el: ET.Element = super().to_xml()

        for child in self.children:
            widget_el.append(child.to_xml())

        return widget_el

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMFrame-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of this PyDMFrame.
        """
        if self.embeddedHeight is not None:
            self.height += self.embeddedHeight

        properties: List[ET.Element] = super().generate_properties()

        if self.frameShape is not None:
            properties.append(Str("frameShape", self.frameShape).to_xml())
        if self.frameShadow is not None:
            properties.append(Str("frameShadow", self.frameShadow).to_xml())
        if self.lineWidth is not None:
            properties.append(Int("lineWidth", self.lineWidth).to_xml())
        if self.midLineWidth is not None:
            properties.append(Int("midLineWidth", self.midLineWidth).to_xml())
        if self.disableOnDisconnect is not None:
            properties.append(Bool("disableOnDisconnect", self.disableOnDisconnect).to_xml())

        return properties


@dataclass
class QWidget(Alarmable):
    """
    QWidget is a base class for creating a QWidget that can be used
    as a child in other PyDM widgets like PyDMTabWidget.

    Attributes
    ----------
    title : Optional[str]
        The title of the tab associated with this QWidget.
    children : List[Alarmable]
        The list of child widgets within this QWidget.
    """

    title: Optional[str] = None
    children: List[Alarmable] = field(default_factory=list)

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate properties specific to the QWidget for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the properties of this QWidget.
        """
        # properties: List[ET.Element] = super().generate_properties()
        properties: List[ET.Element] = []

        if self.title is not None:
            title_element = ET.Element("attribute", name="title")
            title_string_element = ET.Element("string")
            title_string_element.text = self.title
            title_element.append(title_string_element)
            properties.append(title_element)

        return properties

    def add_child(self, child) -> None:
        """
        Add a child widget to this frame's internal list.

        Parameters
        ----------
        child : PyDMFrame
            The child widget to add.

        Returns
        -------
        None
        """
        self.children.append(child)

    def to_xml(self) -> ET.Element:
        """
        Serialize the PyDMTabWidget and its children to an XML element.

        Returns
        -------
        ET.Element
            The XML element representing this PyDMFrame and its children.
        """
        widget_el: ET.Element = super().to_xml()

        for child in self.children:
            widget_el.append(child.to_xml())

        return widget_el


@dataclass
class QTableWidget(Alarmable, Drawable, StyleSheetObject):
    """
    Represents a table widget with optional frame and line styling properties.

    Attributes:
        frameShape (Optional[str]): Shape of the frame (e.g., 'Box', 'Panel').
        frameShadow (Optional[str]): Style of the frame's shadow (e.g., 'Raised').
        lineWidth (Optional[int]): Width of the outer frame lines.
        midLineWidth (Optional[int]): Width of the mid-line frame.
        disableOnDisconnect (Optional[bool]): Whether to disable the widget if disconnected.
    """

    frameShape: Optional[str] = None
    frameShadow: Optional[str] = None
    lineWidth: Optional[int] = None
    midLineWidth: Optional[int] = None
    disableOnDisconnect: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generates a list of XML elements representing the widget's properties.

        Returns:
            List[ET.Element]: List of XML elements for serialization.
        """

        properties: List[ET.Element] = super().generate_properties()

        if self.frameShape is not None:
            properties.append(Str("frameShape", self.frameShape).to_xml())
        if self.frameShadow is not None:
            properties.append(Str("frameShadow", self.frameShadow).to_xml())
        if self.lineWidth is not None:
            properties.append(Int("lineWidth", self.lineWidth).to_xml())
        if self.midLineWidth is not None:
            properties.append(Int("midLineWidth", self.midLineWidth).to_xml())
        if self.disableOnDisconnect is not None:
            properties.append(Bool("disableOnDisconnect", self.disableOnDisconnect).to_xml())

        return properties


@dataclass
class PyDMByteIndicator(Alarmable):
    """
    Represents a widget that displays a multi-bit (byte) indicator.

    Attributes:
        numBits (Optional[int]): Number of bits to display.
        showLabels (Optional[bool]): Whether to show bit labels.
        on_color (Optional[RGBA]): RGBA color when a bit is on.
        off_color (Optional[RGBA]): RGBA color when a bit is off.
    """

    numBits: Optional[int] = None
    showLabels: Optional[bool] = None
    on_color: Optional[RGBA] = None
    off_color: Optional[RGBA] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generates a list of XML elements representing the byte indicator's properties.

        Returns:
            List[ET.Element]: List of XML elements for serialization.
        """

        properties: List[ET.Element] = super().generate_properties()

        if self.numBits is not None:
            properties.append(Int("numBits", self.numBits).to_xml())
        if self.showLabels is not None:
            properties.append(Bool("showLabels", self.showLabels).to_xml())
        if self.on_color is not None:
            properties.append(OnOffColor("on", *self.on_color).to_xml())
        if self.off_color is not None:
            properties.append(OnOffColor("off", *self.off_color).to_xml())

        return properties


@dataclass
class PyDMWaveformPlot(Alarmable, StyleSheetObject):
    """
    Represents a PyDM widget that displays a waveform plot (XY graph).

    This widget can be bound to one or more X and Y data channels.

    Attributes
    ----------
    x_channel : Optional[List[str]]
        List of process variable (PV) names for the X-axis data.
    y_channel : Optional[List[str]]
        List of PV names for the Y-axis data.
    plot_name : Optional[str]
        Title of the plot.
    color : Optional[RGBA]
        Default RGBA color for the plot.
    minXRange : Optional[int]
        Minimum value for the X-axis.
    minYRange : Optional[int]
        Minimum value for the Y-axis.
    maxXRange : Optional[int]
        Maximum value for the X-axis.
    maxYRange : Optional[int]
        Maximum value for the Y-axis.
    plotColor : Optional[List[RGBA]]
        List of colors for individual curves.
    xLabel : Optional[str]
        Label for the X-axis.
    yLabel : Optional[str]
        Label for the Y-axis.
    axisColor : Optional[RGBA]
        Color of the axis lines.
    pointsize : Optional[int]
        Font size for labels and titles.
    font : Optional[dict]
        Font properties (e.g., {"pointsize": 12}).
    yAxisSrc : Optional[str]
        Source of Y-axis scaling ("fromUser" disables auto-range).
    xAxisSrc : Optional[str]
        Source of X-axis scaling.
    """

    x_channel: Optional[List[str]] = field(default_factory=list)
    y_channel: Optional[List[str]] = field(default_factory=list)
    plot_name: Optional[str] = None
    color: Optional[RGBA] = None
    minXRange: Optional[float] = 0
    minYRange: Optional[float] = 0
    maxXRange: Optional[float] = None
    maxYRange: Optional[float] = None
    plotColor: Optional[List[RGBA]] = field(default_factory=list)
    xLabel: Optional[str] = None
    yLabel: Optional[str] = None
    axisColor: Optional[RGBA] = None
    pointsize: Optional[int] = None
    font = None
    yAxisSrc: Optional[str] = None
    xAxisSrc: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generates a list of XML elements representing the waveform plot's properties.

        Returns:
            List[ET.Element]: List of XML elements for serialization.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.plot_name is not None:
            properties.append(
                Str("name", self.plot_name).to_xml()
            )  # Possibly overrides other name (may need to remove other name for plots)
        if self.color is not None:
            properties.append(ColorObject("color", *self.color).to_xml())
        if self.minXRange is not None:
            properties.append(Double("minXRange", self.minXRange).to_xml())
        if self.minYRange is not None:
            properties.append(Double("minYRange", self.minYRange).to_xml())
        if self.maxXRange is not None:
            properties.append(Double("maxXRange", self.maxXRange).to_xml())
        if self.maxYRange is not None:
            properties.append(Double("maxYRange", self.maxYRange).to_xml())
        if self.yAxisSrc is not None and self.yAxisSrc == "fromUser":
            self.auto_range = "false"
        else:
            self.auto_range = "true"
        if (
            self.yLabel is not None and self.maxYRange is not None
        ):  # NOTE: The axes must be generated before the curves for the curves to display
            yAxisString = (
                "{"
                '"name": "Axis 1", '
                '"orientation": "left", '
                f'"label": "{self.yLabel}", '
                f'"minRange": {self.minYRange}, '
                f'"maxRange": {self.maxYRange}, '
                f'"autoRange": {self.auto_range}, '
                '"logMode": false'
                "}"
            )
            properties.append(StringList("yAxes", [yAxisString]).to_xml())
        elif self.auto_range == "false" and self.minXRange is not None and self.minYRange is not None:
            yAxisString = (
                "{"
                '"name": "Axis 1", '
                '"orientation": "left", '
                f'"minRange": {self.minYRange}, '
                f'"maxRange": {self.maxYRange}, '
                f'"autoRange": {self.auto_range}, '
                '"logMode": false'
                "}"
            )
            properties.append(StringList("yAxes", [yAxisString]).to_xml())
        if self.x_channel or self.y_channel:
            properties.append(StringList("curves", self.get_curve_strings()).to_xml())
        if self.plot_name is not None:
            color = self.color or self.axisColor or (175, 175, 175, 255)
            if self.font is not None:
                size = self.font["pointsize"]
            else:
                size = 12
            properties.append(
                Str(
                    "title",
                    (
                        f'<div style="text-align:center; color:{self.rgba_to_hex(*color)}; font-size:{size}pt;">'
                        f"{self.plot_name}"
                        "</div>"
                    ),
                ).to_xml()
            )
        if self.axisColor is not None:
            properties.append(ColorObject("axisColor", *self.axisColor).to_xml())
        if self.xLabel is not None:
            properties.append(StringList("xLabels", [self.xLabel]).to_xml())

        properties.append(Bool("useSharedAxis", True).to_xml())
        return properties

    def get_curve_strings(self) -> List[str]:
        """
        Build JSON-like strings representing individual curve configurations.

        Ensures that the x_channel, y_channel, and plotColor lists are padded
        to equal length before constructing curve entries.

        Returns
        -------
        List[str]
            A list of JSON-style strings, one for each curve in the plot.
        """

        lists = [self.x_channel, self.y_channel, self.plotColor]
        max_len = max(len(lst) for lst in lists)
        for i in range(max_len):
            if len(self.x_channel) <= i:
                self.x_channel.append("")
            if len(self.y_channel) <= i:
                self.y_channel.append("")
            if len(self.plotColor) <= i:
                self.plotColor.append("")

        curve_string_list = []
        for i in range(max_len):
            curve_string = (
                "{"
                f'"name": "", '
                f'"x_channel": "{self.x_channel[i]}", '
                f'"y_channel": "{self.y_channel[i]}", '
                f'"color": "{self.rgba_to_hex(*self.plotColor[i])}", '
                f'"yAxisName": "Axis 1"'
                "}"
            )
            curve_string_list.append(curve_string)
        return curve_string_list

    def rgba_to_hex(self, r, g, b, a=255) -> str:
        """
        Convert RGBA or RGB to a hex string in #RRGGBBAA format.

        Parameters
        ----------
        r : int
            Red component (0–255)
        g : int
            Green component (0–255)
        b : int
            Blue component (0–255)
        a : int, optional
            Alpha component (0–255), default is 255 (opaque)

        Returns
        -------
        str
            Hex color string like "#00e0e0"
        """
        return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class PyDMWaveformTable(Alarmable):
    rowLabels: Optional[Str] = None
    font: dict = field(default_factory=dict)

    def generate_properties(self) -> List[ET.Element]:
        """
        Generates a list of XML elements representing the pydmwaveformtable's properties.

        Returns:
            List[ET.Element]: List of XML elements for serialization.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.rowLabels is not None:
            rowList = self.rowLabels.split(", ")
            for row in rowList:
                properties.append(Row(row, self.font).to_xml())
            properties.append(Column().to_xml())

        return properties


@dataclass
class PyDMScaleIndicator(Alarmable):
    """
    Represents a PyDM widget that displays a scale indicator.

    Attributes
    ----------
    showUnits : Optional[bool]
        Whether to display units next to the scale.
    showLimits : Optional[bool]
        Whether to display min/max limits.
    showValue : Optional[bool]
        Whether to display the current value.
    flipScale : Optional[bool]
        Whether to reverse the scale orientation.
    precision : Optional[int]
        Number of decimal places for displayed values.
    minorTicks : Optional[int]
        Number of minor tick marks.
    majorTicks : Optional[int]
        Number of major tick marks.
    indicatorColor : Optional[RGBA]
        Color of the indicator line.
    background_color : Optional[RGBA]
        Background color of the scale widget.
    foreground_color : Optional[RGBA]
        Color of tick marks.
    """

    showUnits: Optional[bool] = None
    showLimits: Optional[bool] = False
    showValue: Optional[bool] = False
    flipScale: Optional[bool] = None
    precision: Optional[int] = None
    # numDivisions: Optional[int] = None
    minorTicks: Optional[int] = None
    majorTicks: Optional[int] = None
    indicatorColor: Optional[RGBA] = None
    background_color: Optional[RGBA] = None
    foreground_color: Optional[RGBA] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generates a list of XML elements representing the pydmscaleindicator's properties.

        Returns:
            List[ET.Element]: List of XML elements for serialization.
        """

        # The "flipScale" property should be included, as scaleIndicator does not load properly without it.
        # self.height += 20
        # self.y -= 10  # TODO: Find a better way to just get the bottom (can create a frame that cuts off the top)
        properties: List[ET.Element] = super().generate_properties()

        if self.showUnits is not None:
            properties.append(Bool("showUnits", self.showUnits).to_xml())
        # if self.showLimits is not None:
        #    properties.append(Bool("showLimits", self.showLimits).to_xml())
        # if self.showValue is not None:
        #    properties.append(Bool("showValue", self.showValue).to_xml())
        if self.flipScale is not None:
            properties.append(Bool("flipScale", self.flipScale).to_xml())
        if self.precision is not None:
            properties.append(Int("precision", self.precision).to_xml())
        if self.minorTicks is not None or self.majorTicks is not None:
            properties.append(Int("numDivisions", int(self.minorTicks or 0) + int(self.majorTicks or 0)).to_xml())
        if self.indicatorColor is not None:
            properties.append(ColorObject("indicatorColor", *self.indicatorColor).to_xml())
        # if self.background_color is not None:
        #    styles: Dict[str, any] = {}
        #    styles["color"] = self.background_color
        #    properties.append(StyleSheet(styles).to_xml())
        if self.background_color is not None:
            properties.append(ColorObject("backgroundColor", *self.background_color).to_xml())
        if self.foreground_color is not None:
            properties.append(ColorObject("tickColor", *self.foreground_color).to_xml())
        properties.append(TransparentBackground().to_xml())
        # properties.append(ColorObject("tickColor", 255, 255, 255).to_xml())
        properties.append(Bool("showTicks", True).to_xml())
        properties.append(Bool("showValue", self.showValue).to_xml())
        properties.append(Bool("showLimits", self.showLimits).to_xml())

        return properties


@dataclass
class PyDMSlider(Alarmable):
    """
    Represents a PyDM slider widget for adjusting values interactively.

    Attributes
    ----------
    orientation : Optional[str]
        Slider orientation ("Horizontal" or "Vertical").
    """

    orientation: Optional[Str] = None
    limitsFromDb: Optional[bool] = None
    showLimitLabels: Optional[bool] = None
    showValueLabel: Optional[bool] = None
    min: Optional[int] = None
    max: Optional[int] = None

    def generate_properties(self):
        """
        Generates a list of XML elements representing the slider's properties.

        Returns
        -------
        List[ET.Element]
            List of XML elements for serialization.
        """
        properties: List[ET.Element] = super().generate_properties()

        if self.orientation is not None:
            properties.append(Enum("orientation", f"Qt::{self.orientation.capitalize()}").to_xml())
        if self.limitsFromDb is not None:
            properties.append(Bool("userDefinedLimits", not self.limitsFromDb).to_xml())
        if not self.showLimitLabels:
            properties.append(Bool("showLimitLabels", False).to_xml())
        if not self.showValueLabel:
            properties.append(Bool("showValueLabel", False).to_xml())
        if self.min is not None:
            properties.append(Int("userMinimum", self.min).to_xml())
        if self.max is not None:
            properties.append(Int("userMaximum", self.max).to_xml())

        return properties
