from xml.etree import ElementTree as ET
from dataclasses import dataclass, field
from typing import ClassVar, List, Optional
from widgets_helpers import Int, Bool, Str, Drawable, Hidable, Alarmable, Legible, XMLSerializableMixin


@dataclass
class PyDMFrame(XMLSerializableMixin, Alarmable):
    """
    PyDMFrame is a container widget that can hold other PyDM widgets.
    It inherits from Alarmable to support alarm-related features.
    """

    count: ClassVar[int] = 1

    frameShape: Optional[str] = None
    frameShadow: Optional[str] = None
    lineWidth: Optional[int] = None
    midLineWidth: Optional[int] = None
    disableOnDisconnect: Optional[bool] = None

    children: List["PyDMFrame"] = field(default_factory=list)

    def add_child(self, child: "PyDMFrame"):
        """Add a child widget to this frame's internal list."""
        self.children.append(child)

    def to_xml(self) -> ET.Element:
        widget_el = super().to_xml()

        for child in self.children:
            widget_el.append(child.to_xml())

        return widget_el

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMFrame-specific properties.
        """
        properties = super().generate_properties()

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
class QLabel(XMLSerializableMixin, Legible):
    count: ClassVar[int] = 1

    precision: int = None
    show_units: bool = None
    tool_tip: str = None
    frame_shape: str = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate QLabel-specific properties.
        """
        properties = super().generate_properties()
        if self.precision is not None:
            properties.append(Int("precision", self.precision).to_xml())
        if self.show_units is not None:
            properties.append(Bool("showUnits", self.show_units).to_xml())
        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.frame_shape is not None:
            properties.append(Str("frameShape", self.frame_shape).to_xml())
        return properties


@dataclass
class PyDMLabel(QLabel, Alarmable):
    count: ClassVar[int] = 1

    precision_from_pv: bool = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMLabel-specific properties.
        """
        properties = super().generate_properties()
        if self.precision_from_pv is not None:
            properties.append(Bool("precisionFromPV", self.precision_from_pv).to_xml())
        return properties


@dataclass
class PyDMLineEdit(XMLSerializableMixin, Legible, Alarmable):
    count: ClassVar[int] = 1
    displayFormat = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMLineEdit-specific properties.
        """
        properties = super().generate_properties()
        if self.displayFormat is not None:
            properties.append(Int("displayFormat", self.displayFormat).to_xml())
        return properties


@dataclass
class PyDMDrawingRectangle(XMLSerializableMixin, Alarmable, Drawable, Hidable):
    count: ClassVar[int] = 1
    # no extra properties in this class


@dataclass
class PyDMDrawingEllipse(XMLSerializableMixin, Alarmable, Drawable, Hidable):
    count: ClassVar[int] = 1
    # no extra properties in this class


@dataclass
class QPushButton(XMLSerializableMixin, Legible):
    count: ClassVar[int] = 1

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
        Generate QPushButton-specific properties.
        """
        properties = super().generate_properties()

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
    count: ClassVar[int] = 1

    pydm_icon: Optional[str] = None
    pydm_icon_color: Optional[str] = None
    password_protected: Optional[bool] = None
    password: Optional[str] = None
    protected_password: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMPushButton-specific properties.
        """
        properties = super().generate_properties()

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
    count: ClassVar[int] = 1

    monitor_disp: Optional[bool] = None
    show_confirm_dialog: Optional[bool] = None
    confirm_message: Optional[str] = None
    press_value: Optional[str] = None
    release_value: Optional[str] = None
    relative_change: Optional[bool] = None
    write_when_release: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMPushButton-specific properties.
        """
        properties = super().generate_properties()

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
    count: ClassVar[int] = 1

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
        Generate PyDMShellCommand-specific properties.
        """
        properties = super().generate_properties()

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
    count: ClassVar[int] = 1

    show_icon: Optional[bool] = None
    filenames: Optional[str] = None
    titles: Optional[str] = None
    macros: Optional[str] = None
    open_in_new_window: Optional[bool] = None
    follow_symlinks: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMRelatedDisplayButton-specific properties.
        """
        properties = super().generate_properties()

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
class QComboBox(XMLSerializableMixin, Legible):
    count: ClassVar[int] = 1

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
        Generate QComboBox-specific properties.
        """
        properties = super().generate_properties()

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
    tool_tip: Optional[str] = None
    monitor_disp: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMEnumComboBox-specific properties.
        """
        properties = super().generate_properties()

        if self.tool_tip is not None:
            properties.append(Str("toolTip", self.tool_tip).to_xml())
        if self.monitor_disp is not None:
            properties.append(Bool("monitorDisp", self.monitor_disp).to_xml())

        return properties


@dataclass
class PyDMEnumButton(XMLSerializableMixin, Alarmable, Legible):
    count: ClassVar[int] = 1

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
        Generate PyDMEnumButton-specific properties.
        """
        properties = super().generate_properties()

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
class PyDMDrawingLine(XMLSerializableMixin, Legible, Drawable):
    count: ClassVar[int] = 1

    arrow_size: Optional[int] = None
    arrow_end_point: Optional[bool] = None
    arrow_start_point: Optional[bool] = None
    arrow_mid_point: Optional[bool] = None
    flip_mid_point_arrow: Optional[bool] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingLine-specific properties.
        """
        properties = super().generate_properties()

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
    count: ClassVar[int] = 1

    points: Optional[str] = None

    def generate_properties(self) -> List[ET.Element]:
        """
        Generate PyDMDrawingPolyline-specific properties.
        """
        properties = super().generate_properties()

        if self.points is not None:
            properties.append(Str("points", self.points).to_xml())

        return properties
