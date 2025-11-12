import xml.etree.ElementTree as ET
import textwrap

from pydmconverter.edm.converter import convert, build_customwidgets_element, add_widgets_to_parent
from pydmconverter.widgets import PyDMLabel, PyDMFrame


def test_convert_valid_file(tmp_path):
    """Test successful EDM to PyDM conversion with a simple EDM file."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 100
        y 100
        w 800
        h 600
        endScreenProperties

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        major 4
        minor 1
        release 1
        x 10
        y 20
        w 100
        h 30
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    assert root.tag == "ui"
    assert root.find("class") is not None
    assert root.find("widget") is not None
    assert root.find("customwidgets") is not None
    assert root.find("resources") is not None
    assert root.find("connections") is not None


def test_convert_file_not_found(tmp_path, caplog):
    """Test FileNotFoundError handling when input file doesn't exist."""
    input_file = tmp_path / "nonexistent.edl"
    output_file = tmp_path / "output.ui"

    convert(str(input_file), str(output_file))
    assert "File Not Found" in caplog.text


def test_convert_with_scrollable(tmp_path):
    """Test conversion with scrollable option enabled."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        x 0
        y 0
        w 800
        h 600
        endScreenProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file), scrollable=True)

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()
    assert root.find("widget") is not None


def test_convert_with_background_color(tmp_path):
    """Test conversion when EDM file has background color property."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        x 0
        y 0
        w 800
        h 600
        bgColor index 14
        endScreenProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    widgets = root.findall(".//widget[@name='centralwidget']")
    assert len(widgets) > 0, "Should have a central widget"

    central_widget = widgets[0]

    style_props = central_widget.findall("property[@name='styleSheet']")

    if len(style_props) > 0:
        style_string = style_props[0].find("string")
        assert style_string is not None, "StyleSheet property should have a string element"
        assert style_string.text is not None, "StyleSheet string element should have text content"
        assert "background-color" in style_string.text, "StyleSheet should contain background-color property"


def test_build_customwidgets_element():
    """Test custom widgets XML generation for known widgets."""
    used_classes = {"PyDMLabel", "PyDMFrame", "PyDMPushButton"}

    customwidgets_el = build_customwidgets_element(used_classes)

    assert customwidgets_el.tag == "customwidgets"

    customwidgets = customwidgets_el.findall("customwidget")
    assert len(customwidgets) == 3

    first_widget = customwidgets[0]
    assert first_widget.find("class") is not None
    assert first_widget.find("extends") is not None
    assert first_widget.find("header") is not None

    class_names = [cw.find("class").text for cw in customwidgets]
    assert class_names == sorted(class_names)


def test_build_customwidgets_element_unknown_widget(caplog):
    """Test warning log for unknown widget type."""
    used_classes = {"PyDMLabel", "UnknownWidget"}

    with caplog.at_level("WARNING"):
        customwidgets_el = build_customwidgets_element(used_classes)

    assert "Could not find custom widget UnknownWidget" in caplog.text

    customwidgets = customwidgets_el.findall("customwidget")
    assert len(customwidgets) == 1


def test_build_customwidgets_element_empty_set():
    """Test custom widgets generation with empty set."""
    used_classes = set()

    customwidgets_el = build_customwidgets_element(used_classes)

    assert customwidgets_el.tag == "customwidgets"
    assert len(customwidgets_el.findall("customwidget")) == 0


def test_build_customwidgets_element_container_property():
    """Test that container property is only added when present."""
    used_classes = {"PyDMFrame"}
    customwidgets_el = build_customwidgets_element(used_classes)

    frame_widget = customwidgets_el.find("customwidget")
    assert frame_widget.find("container") is not None
    assert frame_widget.find("container").text == "1"

    used_classes = {"PyDMLabel"}
    customwidgets_el = build_customwidgets_element(used_classes)

    label_widget = customwidgets_el.find("customwidget")
    container_elem = label_widget.find("container")
    assert container_elem is None, "Container element should not exist for widgets with empty container value"


def test_add_widgets_to_parent():
    """Test adding multiple widgets to parent element."""
    widget1 = PyDMLabel(name="label1", x=10, y=20, width=100, height=30, text="Test 1")
    widget2 = PyDMLabel(name="label2", x=50, y=60, width=120, height=40, text="Test 2")
    widgets = [widget1, widget2]

    parent = ET.Element("widget", attrib={"class": "QWidget", "name": "parent"})

    add_widgets_to_parent(widgets, parent)

    children = parent.findall("widget")
    assert len(children) == 2

    assert children[0].get("name") == "label1"
    assert children[1].get("name") == "label2"


def test_add_widgets_to_parent_empty():
    """Test adding empty widget list doesn't modify parent."""
    parent = ET.Element("widget", attrib={"class": "QWidget", "name": "parent"})

    add_widgets_to_parent([], parent)

    assert len(parent.findall("widget")) == 0


def test_add_widgets_to_parent_single_widget():
    """Test adding a single widget to parent."""
    widget = PyDMFrame(name="frame1", x=0, y=0, width=800, height=600)

    parent = ET.Element("widget", attrib={"class": "QWidget", "name": "centralwidget"})

    add_widgets_to_parent([widget], parent)

    children = parent.findall("widget")
    assert len(children) == 1
    assert children[0].get("name") == "frame1"
    assert children[0].get("class") == "PyDMFrame"
