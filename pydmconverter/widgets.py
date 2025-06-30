from xml.etree import ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pydmconverter.widgets_helpers import Int, Bool, Str, Drawable, Hidable, Alarmable, Legible, Color, RGBAStyleSheet


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

        return properties


@dataclass
class QLabel(Legible):
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
    foreground_color: Optional[Tuple[int, int, int, int]] = None

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
        if self.foreground_color is not None:
            r, g, b, _ = self.foreground_color
            properties.append(RGBAStyleSheet(r, g, b, _).to_xml())

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
class PyDMLineEdit(Legible, Alarmable):
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

    This class does not add any extra properties beyond those provided by its base classes.

    Attributes
    ----------
    count : ClassVar[int]
        A class variable tracking the number of PyDMDrawingRectangle instances.
    """


@dataclass
class PyDMDrawingEllipse(Alarmable, Drawable, Hidable):
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
class QPushButton(Legible):
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

    text: Optional[str] = None
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

        if self.text is not None:
            properties.append(Str("text", self.text).to_xml())
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

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMPushButton-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMPushButton properties.
        """
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
        return properties


@dataclass
class PyDMShellCommand(PyDMPushButtonBase):
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
    titles : Optional[str]
        Titles associated with the command.
    commands : Optional[str]
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
    titles: Optional[str] = None
    commands: Optional[str] = None

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
        if self.redirect_command_output is not None:
            properties.append(Bool("redirectCommandOutput", self.redirect_command_output).to_xml())
        if self.allow_multiple_executions is not None:
            properties.append(Bool("allowMultipleExecutions", self.allow_multiple_executions).to_xml())
        if self.titles is not None:
            properties.append(Str("titles", self.titles).to_xml())
        if self.commands is not None:
            properties.append(Str("commands", self.commands).to_xml())
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
        if self.filenames is not None:
            properties.append(Str("filenames", self.filenames).to_xml())
        if self.titles is not None:
            properties.append(Str("titles", self.titles).to_xml())
        if self.macros is not None:
            properties.append(Str("macros", self.macros).to_xml())
        if self.open_in_new_window is not None:
            properties.append(Bool("openInNewWindow", self.open_in_new_window).to_xml())
        if self.follow_symlinks is not None:
            properties.append(Bool("followSymlinks", self.follow_symlinks).to_xml())
        return properties


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
class PyDMEnumComboBox(QComboBox, Alarmable):
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
    margin_top: Optional[int] = None
    margin_bottom: Optional[int] = None
    margin_left: Optional[int] = None
    margin_right: Optional[int] = None
    horizontal_spacing: Optional[int] = None
    vertical_spacing: Optional[int] = None
    checkable: Optional[bool] = None

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
            properties.append(Str("orientation", self.orientation).to_xml())
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
class PyDMDrawingLine(Legible, Drawable):
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

    pen_color: Optional[Tuple[int, int, int]] = None
    pen_width: Optional[int] = None

    arrow_size: Optional[int] = None
    arrow_end_point: Optional[bool] = None
    arrow_start_point: Optional[bool] = None
    arrow_mid_point: Optional[bool] = None
    flip_mid_point_arrow: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingLine-specific properties for XML serialization.

        Returns
        -------
        List[ET.Element]
            A list of XML elements representing the PyDMDrawingLine properties.
        """
        properties: List[ET.Element] = super().generate_properties()
        if self.pen_color is not None:
            r, g, b = self.pen_color
            property = ET.Element("property", attrib={"name": "penColor", "stdset": "0"})
            property.append(Color(r, g, b).to_xml())
            properties.append(property)
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
                string_el.text = point

            properties.append(points_prop)

        return properties
