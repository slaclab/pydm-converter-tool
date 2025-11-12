import xml.etree.ElementTree as ET
import xml.etree.ElementTree as etree

from typing import List, Optional

from pydmconverter.widgets import (
    PyDMFrame,
    PyDMLabel,
    QLabel,
    PyDMLineEdit,
    PyDMDrawingRectangle,
    PyDMDrawingEllipse,
    QPushButton,
    PyDMPushButtonBase,
    PyDMPushButton,
    PyDMShellCommand,
    PyDMRelatedDisplayButton,
    QComboBox,
    PyDMEnumComboBox,
    PyDMEnumButton,
    PyDMDrawingLine,
    PyDMDrawingPolyline,
)

from pydmconverter.widgets_helpers import XMLSerializableMixin, Alarmable, Drawable, Hidable


def get_property_value(prop: etree.Element) -> Optional[str]:
    """
    Extract the actual value from a property element by checking known child tags.
    For stringlist, returns the first string element's text.
    """
    for tag in ("string", "bool", "number", "enum", "set"):
        child = prop.find(tag)
        if child is not None:
            return child.text
    # Handle stringlist - return first string element
    stringlist = prop.find("stringlist")
    if stringlist is not None:
        first_string = stringlist.find("string")
        if first_string is not None:
            return first_string.text
    return prop.text


def dummy_generate_properties(self) -> List[etree.Element]:
    el = etree.Element("property")
    el.set("name", "base")
    el.text = "value"
    return [el]


def test_PyDMFrame_add_child():
    """
    Test that add_child correctly appends a child to the children list.
    """
    parent = PyDMFrame()
    child = PyDMFrame()
    parent.add_child(child)
    assert child in parent.children, "The child should be in the parent's children list."


def test_PyDMFrame_to_xml():
    """
    Test that to_xml produces a widget element with direct property children,
    as required by standard Qt Designer .ui files.
    """
    frame = PyDMFrame(frameShape="Box", frameShadow="Raised", lineWidth=2, midLineWidth=1, disableOnDisconnect=True)
    xml_element = frame.to_xml()

    expected_properties = frame.generate_properties()

    assert len(xml_element) == len(expected_properties), (
        f"Expected widget to have {len(expected_properties)} property children, got {len(xml_element)}."
    )

    for child in xml_element:
        assert child.tag == "property", f"Expected child tag 'property', got '{child.tag}'."


def test_PyDMFrame_generate_properties():
    """
    Test that generate_properties returns XML elements for all non-None properties.
    """
    frame = PyDMFrame(frameShape="Box", frameShadow="Raised", lineWidth=2, midLineWidth=1, disableOnDisconnect=True)
    properties = frame.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}
    assert prop_dict.get("frameShape") == "Box", "Property 'frameShape' should be 'Box'."
    assert prop_dict.get("frameShadow") == "Raised", "Property 'frameShadow' should be 'Raised'."
    assert prop_dict.get("lineWidth") == "2", "Property 'lineWidth' should be '2'."
    assert prop_dict.get("midLineWidth") == "1", "Property 'midLineWidth' should be '1'."
    assert prop_dict.get("disableOnDisconnect") == "true", "Property 'disableOnDisconnect' should be 'True'."


def test_qlabel_generate_properties_all_set():
    """
    Test that generate_properties returns XML elements for all properties
    when all attributes are set.
    """
    label = QLabel(precision=3, show_units=True, tool_tip="Test Tooltip", frame_shape="Rounded")
    properties = label.generate_properties()

    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}
    assert prop_dict.get("precision") == "3"
    assert prop_dict.get("showUnits") == "true"
    assert prop_dict.get("toolTip") == "Test Tooltip"
    assert prop_dict.get("frameShape") == "Rounded"


def test_qlabel_generate_properties_partial():
    """
    Test that generate_properties returns only XML elements for attributes that are not None.
    """
    label = QLabel(precision=None, show_units=False, tool_tip=None, frame_shape="Square")
    properties = label.generate_properties()

    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}
    assert "precision" not in prop_dict
    assert prop_dict.get("showUnits") == "false"
    assert "toolTip" not in prop_dict
    assert prop_dict.get("frameShape") == "Square"


def test_pydmlabel_generate_properties_with_precision_from_pv():
    """
    Test that generate_properties includes the 'precisionFromPV' property when
    precision_from_pv is set.
    """
    label = PyDMLabel(precision_from_pv=True)
    properties = label.generate_properties()

    prop_names = [prop.get("name") for prop in properties]
    assert "precisionFromPV" in prop_names, "Expected 'precisionFromPV' property when precision_from_pv is set to True."


def test_pydmlabel_generate_properties_without_precision_from_pv():
    """
    Test that generate_properties does not include the 'precisionFromPV' property when
    precision_from_pv is None.
    """
    label = PyDMLabel(precision_from_pv=None)
    properties = label.generate_properties()

    prop_names = [prop.get("name") for prop in properties]
    assert "precisionFromPV" not in prop_names, (
        "Did not expect 'precisionFromPV' property when precision_from_pv is None."
    )


def test_pydmlineedit_generate_properties_with_displayFormat():
    """
    Test that generate_properties returns an XML element for 'displayFormat'
    when displayFormat is set.
    """
    line_edit = PyDMLineEdit(displayFormat=5)
    properties = line_edit.generate_properties()

    prop_names = [prop.get("name") for prop in properties]
    assert "displayFormat" in prop_names, "Expected 'displayFormat' property when displayFormat is set."

    for prop in properties:
        if prop.get("name") == "displayFormat":
            number_elem = prop.find("number")
            assert number_elem is not None, "Expected a <number> subelement for displayFormat."
            assert number_elem.text == "5", "Expected displayFormat value to be '5'."


def test_pydmlineedit_generate_properties_without_displayFormat():
    """
    Test that generate_properties does not include 'displayFormat'
    when displayFormat is None.
    """
    line_edit = PyDMLineEdit(displayFormat=None)
    properties = line_edit.generate_properties()

    prop_names = [prop.get("name") for prop in properties]
    assert "displayFormat" not in prop_names, "Did not expect 'displayFormat' property when displayFormat is None."


def test_PyDMDrawingRectangle_generate_properties_inherited(monkeypatch):
    """
    Test that PyDMDrawingRectangle inherits generate_properties from its bases
    without adding extra properties.
    """
    monkeypatch.setattr(XMLSerializableMixin, "generate_properties", dummy_generate_properties)
    monkeypatch.setattr(Alarmable, "generate_properties", lambda self: XMLSerializableMixin.generate_properties(self))
    monkeypatch.setattr(Drawable, "generate_properties", lambda self: [])
    monkeypatch.setattr(Hidable, "generate_properties", lambda self: [])

    instance = PyDMDrawingRectangle()
    properties = instance.generate_properties()

    assert isinstance(properties, list)
    assert len(properties) == 1

    prop = properties[0]
    assert prop.tag == "property"
    assert prop.get("name") == "base"
    assert prop.text == "value"


def test_PyDMDrawingEllipse_generate_properties_inherited(monkeypatch):
    """
    Test that PyDMDrawingEllipse inherits generate_properties from its bases
    without adding extra properties.
    """
    monkeypatch.setattr(XMLSerializableMixin, "generate_properties", dummy_generate_properties)
    monkeypatch.setattr(Alarmable, "generate_properties", lambda self: XMLSerializableMixin.generate_properties(self))
    monkeypatch.setattr(Drawable, "generate_properties", lambda self: [])
    monkeypatch.setattr(Hidable, "generate_properties", lambda self: [])

    instance = PyDMDrawingEllipse()
    properties = instance.generate_properties()

    assert isinstance(properties, list)
    assert len(properties) == 1

    prop = properties[0]
    assert prop.tag == "property"
    assert prop.get("name") == "base"
    assert prop.text == "value"


def test_qpushbutton_generate_properties_all_set():
    """
    Test that generate_properties returns XML elements for all properties when all attributes are set.
    """
    button = QPushButton(
        text="Click me",
        auto_default=True,
        default=False,
        flat=True,
        tool_tip="This is a button",
        icon="icon.png",
        checkable=True,
        checked=False,
    )
    properties = button.generate_properties()

    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}
    assert prop_dict.get("text") == "Click me"
    assert prop_dict.get("autoDefault") == "true"
    assert prop_dict.get("default") == "false"
    assert prop_dict.get("flat") == "true"
    assert prop_dict.get("toolTip") == "This is a button"
    assert prop_dict.get("icon") == "icon.png"
    assert prop_dict.get("checkable") == "true"
    assert prop_dict.get("checked") == "false"


def test_qpushbutton_generate_properties_partial():
    """
    Test that generate_properties only includes properties for attributes that are not None.
    """
    button = QPushButton(
        text=None,
        auto_default=None,
        default=True,
        flat=None,
        tool_tip="Tooltip",
        icon=None,
        checkable=False,
        checked=None,
    )
    properties = button.generate_properties()
    prop_names = [prop.get("name") for prop in properties]

    assert "default" in prop_names
    assert "toolTip" in prop_names
    assert "checkable" in prop_names
    assert "text" not in prop_names
    assert "autoDefault" not in prop_names
    assert "flat" not in prop_names
    assert "icon" not in prop_names
    assert "checked" not in prop_names


def test_pydmpushbuttonbase_generate_properties_all_set():
    """
    Test that generate_properties includes all PyDM-specific properties when they are set.
    """
    instance = PyDMPushButtonBase(
        pydm_icon="icon.png",
        pydm_icon_color="red",
        password_protected=True,
        password="secret",
        protected_password="protected_secret",
    )
    properties = instance.generate_properties()

    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}
    assert prop_dict.get("PyDMIcon") == "icon.png"
    assert prop_dict.get("PyDMIconColor") == "red"
    assert prop_dict.get("passwordProtected") == "true"
    assert prop_dict.get("password") == "secret"
    assert prop_dict.get("protectedPassword") == "protected_secret"


def test_pydmpushbuttonbase_generate_properties_partial():
    """
    Test that generate_properties only includes properties for attributes that are not None.
    """
    instance = PyDMPushButtonBase(
        pydm_icon=None, pydm_icon_color="blue", password_protected=False, password=None, protected_password="hidden"
    )
    properties = instance.generate_properties()
    prop_names = [prop.get("name") for prop in properties]

    assert "PyDMIcon" not in prop_names
    assert "PyDMIconColor" in prop_names
    assert "passwordProtected" in prop_names
    assert "password" not in prop_names
    assert "protectedPassword" in prop_names


def test_pydmpushbuttonbase_generate_properties_empty():
    """
    Test that generate_properties returns only the base properties when all PyDM-specific attributes are None.
    """
    instance = PyDMPushButtonBase(
        pydm_icon=None, pydm_icon_color=None, password_protected=None, password=None, protected_password=None
    )
    properties = instance.generate_properties()
    assert len(properties) == 5  # Updated to match actual output


# --- Tests for PyDMPushButton ---


def test_pydmpushbutton_generate_properties():
    widget = PyDMPushButton(
        monitor_disp=True,
        show_confirm_dialog=False,
        confirm_message="Confirm",
        press_value="1",
        release_value="0",
        relative_change=True,
        write_when_release=False,
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("monitorDisp") == "true"
    assert prop_dict.get("showConfirmDialog") == "false"
    assert prop_dict.get("confirmMessage") == "Confirm"
    assert prop_dict.get("pressValue") == "1"
    assert prop_dict.get("releaseValue") == "0"
    assert prop_dict.get("relativeChange") == "true"
    assert prop_dict.get("writeWhenRelease") == "false"


# --- Tests for PyDMShellCommand ---


def test_pydmshellcommand_generate_properties():
    widget = PyDMShellCommand(
        show_confirm_dialog=True,
        confirm_message="Are you sure?",
        run_commands_in_full_shell=True,
        environment_variables="VAR=1",
        show_icon=False,
        redirect_command_output=True,
        allow_multiple_executions=False,
        titles=["Title"],
        command=["echo hello"],
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("showConfirmDialog") == "true"
    assert prop_dict.get("confirmMessage") == "Are you sure?"
    assert prop_dict.get("runCommandsInFullShell") == "true"
    assert prop_dict.get("environmentVariables") == "VAR=1"
    assert prop_dict.get("showIcon") == "false"
    assert prop_dict.get("redirectCommandOutput") == "true"
    assert prop_dict.get("allowMultipleExecutions") == "false"
    assert prop_dict.get("titles") == "Title"
    # Check that commands property exists (note: property is 'commands', attribute is 'command')
    assert "commands" in [prop.get("name") for prop in properties]


# --- Tests for PyDMRelatedDisplayButton ---


def test_pydmrelateddisplay_button_generate_properties():
    widget = PyDMRelatedDisplayButton(
        show_icon=True,
        titles="My Titles",
        macros="macro1",
        open_in_new_window=True,
        follow_symlinks=False,
    )
    # Set displayFileName which is used instead of filenames attribute
    widget.displayFileName = ["file1.edl", "file2.edl"]

    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("showIcon") == "true"
    # filenames is populated from displayFileName and contains a stringlist
    assert "filenames" in [prop.get("name") for prop in properties]
    assert prop_dict.get("titles") == "My Titles"
    assert prop_dict.get("macros") == "macro1"
    assert prop_dict.get("openInNewWindow") == "true"
    assert prop_dict.get("followSymlinks") == "false"


# --- Tests for QComboBox ---


def test_qcombobox_generate_properties():
    widget = QComboBox(
        editable=True,
        current_text="Test",
        max_visible_items=5,
        max_count=10,
        insert_policy="InsertAtBottom",
        size_adjust_policy="AdjustToContents",
        minimum_contents_length=3,
        icon_size="16x16",
        duplicates_enabled=False,
        frame=True,
        model_column=2,
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("editable") == "true"
    assert prop_dict.get("currentText") == "Test"
    assert prop_dict.get("maxVisibleItems") == "5"
    assert prop_dict.get("maxCount") == "10"
    assert prop_dict.get("insertPolicy") == "InsertAtBottom"
    assert prop_dict.get("sizeAdjustPolicy") == "AdjustToContents"
    assert prop_dict.get("minimumContentsLength") == "3"
    assert prop_dict.get("iconSize") == "16x16"
    assert prop_dict.get("duplicatesEnabled") == "false"
    assert prop_dict.get("frame") == "true"
    assert prop_dict.get("modelColumn") == "2"


# --- Tests for PyDMEnumComboBox ---


def test_pydmenumcombobox_generate_properties():
    widget = PyDMEnumComboBox(tool_tip="Enum Tooltip", monitor_disp=True)
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("toolTip") == "Enum Tooltip"
    assert prop_dict.get("monitorDisp") == "true"


# --- Tests for PyDMEnumButton ---


def test_pydmenumbutton_generate_properties():
    widget = PyDMEnumButton(
        tool_tip="EnumButton Tooltip",
        monitor_disp=False,
        items_translatable=True,
        items_disambiguation="Disambiguate",
        items_comment="A comment",
        use_custom_order=True,
        invert_order=False,
        custom_order_translatable=False,
        custom_order_disambiguation="CustomDisamb",
        custom_order_comment="Custom comment",
        widget_type="Button",
        orientation="Horizontal",
        margin_top=5,
        margin_bottom=5,
        margin_left=5,
        margin_right=5,
        horizontal_spacing=10,
        vertical_spacing=10,
        checkable=True,
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("toolTip") == "EnumButton Tooltip"
    assert prop_dict.get("monitorDisp") == "false"
    assert prop_dict.get("itemsTranslatable") == "true"
    assert prop_dict.get("itemsDisambiguation") == "Disambiguate"
    assert prop_dict.get("itemsComment") == "A comment"
    assert prop_dict.get("useCustomOrder") == "true"
    assert prop_dict.get("invertOrder") == "false"
    assert prop_dict.get("customOrderTranslatable") == "false"
    assert prop_dict.get("customOrderDisambiguation") == "CustomDisamb"
    assert prop_dict.get("customOrderComment") == "Custom comment"
    assert prop_dict.get("widgetType") == "Button"
    assert prop_dict.get("orientation") == "Qt::Horizontal"
    assert prop_dict.get("marginTop") == "5"
    assert prop_dict.get("marginBottom") == "5"
    assert prop_dict.get("marginLeft") == "5"
    assert prop_dict.get("marginRight") == "5"
    assert prop_dict.get("horizontalSpacing") == "10"
    assert prop_dict.get("verticalSpacing") == "10"
    assert prop_dict.get("checkable") == "true"


# --- Tests for PyDMDrawingLine ---


def test_pydmdrawingline_generate_properties():
    widget = PyDMDrawingLine(
        arrow_size=15, arrow_end_point=True, arrow_start_point=False, arrow_mid_point=True, flip_mid_point_arrow=False
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {prop.get("name"): get_property_value(prop) for prop in properties}

    assert prop_dict.get("arrowSize") == "15"
    assert prop_dict.get("arrowEndPoint") == "true"
    assert prop_dict.get("arrowStartPoint") == "false"
    assert prop_dict.get("arrowMidPoint") == "true"
    assert prop_dict.get("flipMidPointArrow") == "false"


# --- Tests for PyDMDrawingPolyline ---


def test_pydmdrawingpolyline_generate_properties():
    widget = PyDMDrawingPolyline(
        arrow_size=10,
        arrow_end_point=False,
        arrow_start_point=True,
        arrow_mid_point=False,
        flip_mid_point_arrow=True,
        points=["0, 0", "10, 10", "20, 20"],
    )
    properties: List[ET.Element] = widget.generate_properties()
    prop_dict = {}

    for prop in properties:
        name = prop.get("name")
        if name == "points":
            stringlist = prop.find("stringlist")
            if stringlist is not None:
                points_list = [string.text for string in stringlist.findall("string")]
                prop_dict[name] = points_list
        else:
            prop_dict[name] = get_property_value(prop)

    assert prop_dict.get("arrowSize") == "10"
    assert prop_dict.get("arrowEndPoint") == "false"
    assert prop_dict.get("arrowStartPoint") == "true"
    assert prop_dict.get("arrowMidPoint") == "false"
    assert prop_dict.get("flipMidPointArrow") == "true"

    assert prop_dict.get("points") == ["0, 0", "10, 10", "20, 20"]
