import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import textwrap
from pathlib import Path

import pytest

import pydmconverter
from pydmconverter.edm.converter import convert, build_customwidgets_element, add_widgets_to_parent, content_extent
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


CENTRAL_GEOMETRY_SCREEN = """
    4 0 1
    beginScreenProperties
    x 50
    y 60
    w 400
    h 300
    bgColor index 14
    endScreenProperties

    # (Static Text)
    object activeXTextClass
    beginObjectProperties
    major 4
    minor 1
    release 1
    x 10
    y 10
    w 100
    h 20
    endObjectProperties

    # (Rectangle hidden at startup, near the bottom)
    object activeRectangleClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 20
    y 200
    w 300
    h 80
    visPv "TEST:VIS"
    visMin "1"
    visMax "2"
    endObjectProperties
"""

OVERFLOW_RECTANGLE = """
    # (Rectangle extending past the screen's right and bottom edges)
    object activeRectangleClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 350
    y 260
    w 100
    h 80
    endObjectProperties
"""


SCREEN_RECT = {"x": "0", "y": "0", "width": "400", "height": "300"}
OVERFLOW_RECT = {"x": "0", "y": "0", "width": "450", "height": "340"}


def _convert_ui_root(tmp_path, edm_content, scrollable):
    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(textwrap.dedent(edm_content))

    convert(str(input_file), str(output_file), scrollable=scrollable)

    return ET.parse(output_file).getroot()


def _geometry_rect(widget):
    return {child.tag: child.text for child in widget.find("property[@name='geometry']/rect")}


def _central_widget_rect(tmp_path, edm_content, scrollable):
    central_widget = _convert_ui_root(tmp_path, edm_content, scrollable).find(".//widget[@name='centralwidget']")
    assert central_widget is not None

    properties = central_widget.findall("property")
    assert properties[0].get("name") == "geometry", "geometry should be centralwidget's first property"
    return {child.tag: child.text for child in properties[0].find("rect")}


@pytest.mark.parametrize("scrollable", [False, True])
def test_centralwidget_has_screen_geometry(tmp_path, scrollable):
    """centralwidget is sized to the full screen, not left for Qt to adjustSize().

    Without an explicit geometry, Qt sizes centralwidget to the children visible when
    the display is first shown, permanently clipping a rule-hidden (visPv) widget that
    lies below/right of them once it later becomes visible.
    """
    rect = _central_widget_rect(tmp_path, CENTRAL_GEOMETRY_SCREEN, scrollable)
    assert rect == SCREEN_RECT


@pytest.mark.parametrize("scrollable", [False, True])
def test_centralwidget_geometry_covers_widgets_past_screen_size(tmp_path, scrollable):
    """A widget past the declared screen size grows centralwidget to its right/bottom edge,
    so it is not clipped when the window is enlarged."""
    rect = _central_widget_rect(tmp_path, CENTRAL_GEOMETRY_SCREEN + OVERFLOW_RECTANGLE, scrollable)
    assert rect == OVERFLOW_RECT


@pytest.mark.parametrize(
    "edm_content, content_rect",
    [(CENTRAL_GEOMETRY_SCREEN, SCREEN_RECT), (CENTRAL_GEOMETRY_SCREEN + OVERFLOW_RECTANGLE, OVERFLOW_RECT)],
)
@pytest.mark.parametrize("scrollable", [False, True])
def test_page_geometry_covers_content(tmp_path, edm_content, content_rect, scrollable):
    """Form keeps the declared screen size while centralwidget (and, when scrollable,
    scrollAreaWidgetContents) covers the content, so overflow can be scrolled to."""
    root = _convert_ui_root(tmp_path, edm_content, scrollable)

    assert _geometry_rect(root.find("widget[@name='Form']")) == SCREEN_RECT

    central_widget = root.find(".//widget[@name='centralwidget']")
    assert len(central_widget.findall("property[@name='geometry']")) == 1
    assert _geometry_rect(central_widget) == content_rect

    scroll_contents = root.find(".//widget[@name='scrollAreaWidgetContents']")
    if scrollable:
        assert _geometry_rect(root.find(".//widget[@name='scrollArea']")) == SCREEN_RECT
        assert _geometry_rect(scroll_contents) == content_rect
    else:
        assert scroll_contents is None


def _widget_with_rect(**parts):
    widget = ET.Element("widget")
    rect = ET.SubElement(ET.SubElement(widget, "property", attrib={"name": "geometry"}), "rect")
    for tag, text in parts.items():
        ET.SubElement(rect, tag).text = text
    return widget


def test_content_extent_ignores_unparseable_geometry():
    """A child with an incomplete or non-numeric rect is skipped; float text is truncated."""
    elements = [
        _widget_with_rect(x="500", y="500", width="100"),  # height missing
        _widget_with_rect(x="abc", y="0", width="900", height="900"),
        ET.Element("widget"),  # no geometry at all
        _widget_with_rect(x="12.5", y="20", width="100.9", height="30"),
    ]

    assert content_extent(elements, 100, 40) == (112, 50)
    assert content_extent([], 400, 300) == (400, 300)


def test_convert_with_explicit_color_list(tmp_path, monkeypatch):
    """Test that an explicit color_list_file is used to resolve the screen bgColor."""
    monkeypatch.delenv("EDMCOLORFILE", raising=False)
    monkeypatch.delenv("EDMFILES", raising=False)

    palette = tmp_path / "colors.list"
    palette.write_text(
        '4 0 0\n\nmax=0x10000\n\nstatic 14 "Yellow" { 0xffff 0 0 }\n',
        encoding="utf-8",
        newline="\n",
    )

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

    convert(str(input_file), str(output_file), color_list_file=str(palette))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    style_props = root.findall(".//property[@name='styleSheet']")
    assert len(style_props) > 0, "Should have a styleSheet property"
    style_string = style_props[0].find("string")
    assert style_string is not None
    assert style_string.text is not None
    assert "rgba(255, 0, 0, 255)" in style_string.text, (
        f"Expected red background from explicit palette, got: {style_string.text}"
    )


def test_convert_explicit_color_list_beats_env(tmp_path, monkeypatch):
    """Test that an explicit color_list_file takes priority over EDMCOLORFILE."""
    env_palette = Path(__file__).parent / "fixtures" / "colors.list"
    monkeypatch.setenv("EDMCOLORFILE", str(env_palette))
    monkeypatch.delenv("EDMFILES", raising=False)

    palette = tmp_path / "colors.list"
    palette.write_text(
        '4 0 0\n\nmax=0x10000\n\nstatic 14 "Yellow" { 0xffff 0 0 }\n',
        encoding="utf-8",
        newline="\n",
    )

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

    convert(str(input_file), str(output_file), color_list_file=str(palette))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    style_props = root.findall(".//property[@name='styleSheet']")
    assert len(style_props) > 0, "Should have a styleSheet property"
    style_string = style_props[0].find("string")
    assert style_string is not None
    assert style_string.text is not None
    assert "rgba(255, 0, 0, 255)" in style_string.text, (
        f"Expected explicit red palette to beat EDMCOLORFILE yellow, got: {style_string.text}"
    )


def test_convert_xy_graph_curves_without_plot_color(tmp_path):
    """Curves past the end of the plotColor block fall back to the foreground colour
    instead of failing the conversion."""
    palette = Path(__file__).parent / "fixtures" / "colors.list"
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        object xyGraphClass
        beginObjectProperties
        major 4
        minor 8
        release 0
        x 10
        y 10
        w 400
        h 300
        fgColor index 14
        numTraces 3
        xPv {
          0 "X:ZERO"
          1 "X:ONE"
        }
        yPv {
          0 "Y:ZERO"
          1 "Y:ONE"
          2 "Y:TWO"
        }
        plotColor {
          0 index 25
        }
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file), color_list_file=str(palette))

    assert output_file.exists()
    curves = ET.parse(output_file).getroot().find(".//property[@name='curves']/stringlist")
    assert curves is not None
    assert [json.loads(curve.text)["color"] for curve in curves] == ["#0000ff", "#ffff00", "#ffff00"]


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


def test_convert_related_display_invisible_to_flat(tmp_path):
    """Test that EDM relatedDisplayClass with invisible property maps to PyDM flat property."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        # (Related Display)
        object relatedDisplayClass
        beginObjectProperties
        major 4
        minor 4
        release 0
        x 100
        y 100
        w 150
        h 50
        fgColor index 14
        bgColor index 0
        invisible
        numPvs 4
        numDsps 1
        displayFileName {
          0 "test.edl"
        }
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    # Find the PyDMRelatedDisplayButton widget
    related_display_buttons = root.findall(".//widget[@class='PyDMRelatedDisplayButton']")
    assert len(related_display_buttons) == 1, "Should have one PyDMRelatedDisplayButton"

    button = related_display_buttons[0]
    flat_property = button.find("property[@name='flat']")
    assert flat_property is not None, "Button should have flat property"

    # Check that flat is set to true
    bool_element = flat_property.find("bool")
    assert bool_element is not None, "flat property should have bool element"
    assert bool_element.text == "true", "flat property should be set to true when invisible is present"


def test_convert_escapes_ampersand_for_qt_mnemonics(tmp_path):
    """Button-family text/titles get && escaping; QLabel text stays a literal single &."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        # (Related Display)
        object relatedDisplayClass
        beginObjectProperties
        major 4
        minor 4
        release 0
        x 100
        y 100
        w 150
        h 50
        fgColor index 14
        bgColor index 0
        buttonLabel "PLC & UPS Diagnostics"
        numPvs 4
        numDsps 1
        displayFileName {
          0 "a.edl"
        }
        menuLabel {
          0 "Sub & Menu"
        }
        endObjectProperties

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        major 4
        minor 1
        release 1
        x 300
        y 100
        w 150
        h 30
        fgColor index 14
        value {
          "Foo & Bar"
        }
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    related_display_buttons = [w for w in root.iter("widget") if w.get("class") == "PyDMRelatedDisplayButton"]
    assert len(related_display_buttons) == 1, "Should have one PyDMRelatedDisplayButton"
    button = related_display_buttons[0]

    text_prop = button.find("property[@name='text']")
    assert text_prop is not None, "Button should have a text property"
    text_string = text_prop.find("string")
    assert text_string is not None
    assert text_string.text == "PLC && UPS Diagnostics"

    # menuLabel is carried through as the PyDM `titles` stringlist (QMenu actions).
    titles_prop = button.find("property[@name='titles']")
    assert titles_prop is not None, "Related display should have a titles property"
    stringlist = titles_prop.find("stringlist")
    assert stringlist is not None, "titles should be a stringlist"
    titles = [s.text for s in stringlist.findall("string")]
    assert titles == ["Sub && Menu"]

    label_widgets = [w for w in root.iter("widget") if w.get("class") in ("PyDMLabel", "QLabel")]
    assert len(label_widgets) == 1, "Should have one label widget for activeXTextClass"
    label = label_widgets[0]
    label_text_prop = label.find("property[@name='text']")
    assert label_text_prop is not None
    label_text_string = label_text_prop.find("string")
    assert label_text_string is not None
    assert label_text_string.text == "Foo & Bar"


def _convert_button_ui(tmp_path, edm_class, blocks):
    """Convert one ``edm_class`` button carrying ``blocks``; return the .ui path."""
    edm_content = (
        textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        object {edm_class}
        beginObjectProperties
        major 4
        minor 4
        release 0
        x 100
        y 100
        w 150
        h 50
        fgColor index 14
        bgColor index 0
        buttonLabel "Open"
        {blocks}
        endObjectProperties
    """)
        .replace("{edm_class}", edm_class)
        .replace("{blocks}", blocks)
    )
    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))
    return output_file


def _convert_button(tmp_path, edm_class, pydm_class, blocks):
    """Convert one ``edm_class`` button carrying ``blocks``; return its ``pydm_class`` widget element."""
    output_file = _convert_button_ui(tmp_path, edm_class, blocks)
    (button,) = [w for w in ET.parse(output_file).getroot().iter("widget") if w.get("class") == pydm_class]
    return button


def _convert_related_display(tmp_path, blocks, num_dsps=2):
    """Convert one relatedDisplayClass carrying ``blocks``; return the .ui path."""
    return _convert_button_ui(tmp_path, "relatedDisplayClass", f"numDsps {num_dsps}\n{blocks}")


def _stringlist(widget, name):
    """``widget``'s stringlist property ``name`` ("" for an empty entry), or None without one."""
    stringlist = widget.find(f"property[@name='{name}']/stringlist")
    if stringlist is None:
        return None
    return [s.text or "" for s in stringlist.findall("string")]


def _related_display_macros_and_filenames(tmp_path, blocks, num_dsps=2):
    """Convert one relatedDisplayClass carrying ``blocks``; return its (macros, filenames)."""
    button = _convert_button(
        tmp_path, "relatedDisplayClass", "PyDMRelatedDisplayButton", f"numDsps {num_dsps}\n{blocks}"
    )
    macros_prop = button.find("property[@name='macros']")
    macros = None if macros_prop is None else [s.text for s in macros_prop.findall("stringlist/string")]
    filenames = [s.text for s in button.findall("property[@name='filenames']/stringlist/string")]
    return macros, filenames


def _related_display_titles_and_filenames(tmp_path, blocks):
    """Convert one relatedDisplayClass carrying ``blocks``; return its (titles, filenames)."""
    button = _convert_button(tmp_path, "relatedDisplayClass", "PyDMRelatedDisplayButton", blocks)
    return _stringlist(button, "titles"), _stringlist(button, "filenames")


def test_convert_related_display_pairs_symbols_with_filenames_by_index(tmp_path):
    """symbols { 1 "P=X" } belongs to displayFileName 1, not to display 0."""
    macros, filenames = _related_display_macros_and_filenames(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\nsymbols {\n  1 "P=X"\n}',
    )
    assert filenames == ["a.ui", "b.ui"]
    assert macros == ["{}", '{"P": "X"}']


def test_convert_related_display_dense_symbols_unchanged(tmp_path):
    macros, filenames = _related_display_macros_and_filenames(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\nsymbols {\n  0 "P=A"\n  1 "P=B"\n}',
    )
    assert filenames == ["a.ui", "b.ui"]
    assert macros == ['{"P": "A"}', '{"P": "B"}']


def test_convert_related_display_macros_stringlist_pads_trailing_entries(tmp_path):
    """macros is a <stringlist> with one entry per filename, even past the last symbols entry."""
    macros, filenames = _related_display_macros_and_filenames(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n  2 "c.edl"\n}\nsymbols {\n  0 "P=A"\n}',
        num_dsps=3,
    )
    assert filenames == ["a.ui", "b.ui", "c.ui"]
    assert macros == ['{"P": "A"}', "{}", "{}"]


def test_convert_related_display_single_file_macros_stringlist(tmp_path):
    macros, filenames = _related_display_macros_and_filenames(
        tmp_path, 'displayFileName {\n  0 "a.edl"\n}\nsymbols {\n  0 "P=A,R=B"\n}', num_dsps=1
    )
    assert filenames == ["a.ui"]
    assert macros == ['{"P": "A", "R": "B"}']


def test_related_display_macros_load_one_per_filename_in_pydm(tmp_path, qtbot):
    """PyDM pairs macros[i] with filenames[i]; a single <string> would load as one entry."""
    pytest.importorskip("pydm")
    from pydm.utilities.macro import parse_macro_string
    from pydm.widgets.related_display_button import PyDMRelatedDisplayButton
    from qtpy import uic

    output_file = _convert_related_display(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n  2 "c.edl"\n}\n'
        'symbols {\n  1 "DEV=QUAD:L1B:0385,PDEV=PSC:L1B:MG04"\n  2 "DEV=XCOR:L1B:0385"\n}',
        num_dsps=3,
    )
    screen = uic.loadUi(str(output_file))
    qtbot.addWidget(screen)
    (button,) = screen.findChildren(PyDMRelatedDisplayButton)

    assert button.filenames == ["a.ui", "b.ui", "c.ui"]
    assert len(button.macros) == len(button.filenames)
    assert [parse_macro_string(m) for m in button.macros] == [
        {},
        {"DEV": "QUAD:L1B:0385", "PDEV": "PSC:L1B:MG04"},
        {"DEV": "XCOR:L1B:0385"},
    ]


# b.edl has an empty symbols entry and c.edl none (index 2 is skipped).
FOUR_DISPLAYS = (
    'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n  2 "c.edl"\n  3 "d.edl"\n}\n'
    'symbols {\n  0 "DEV=A1"\n  1 ""\n  3 "DEV=D4,N=2"\n}'
)


def test_convert_related_display_macros_keep_empty_and_skipped_entries(tmp_path):
    macros, filenames = _related_display_macros_and_filenames(tmp_path, FOUR_DISPLAYS, num_dsps=4)
    assert filenames == ["a.ui", "b.ui", "c.ui", "d.ui"]
    assert macros == ['{"DEV": "A1"}', "{}", "{}", '{"DEV": "D4", "N": "2"}']


def test_related_display_opens_each_file_with_its_own_macros(tmp_path, qtbot):
    """Opening each entry through PyDM gives that display its own symbols."""
    pytest.importorskip("pydm")
    from pydm.display import load_file
    from pydm.widgets.related_display_button import PyDMRelatedDisplayButton

    output_file = _convert_related_display(tmp_path, FOUR_DISPLAYS, num_dsps=4)
    for name in "abcd":
        (tmp_path / f"{name}.ui").write_text(
            '<ui version="4.0"><class>Form</class><widget class="QWidget" name="Form"/></ui>'
        )
    screen = load_file(str(output_file), target=None)
    qtbot.addWidget(screen)
    (button,) = screen.findChildren(PyDMRelatedDisplayButton)

    opened = {}
    for item in button._get_items():
        display = button.open_display(item["filename"], item["macros"])
        qtbot.addWidget(display)
        opened[item["filename"]] = display.macros()
    assert opened == {"a.ui": {"DEV": "A1"}, "b.ui": {}, "c.ui": {}, "d.ui": {"DEV": "D4", "N": "2"}}


def test_convert_related_display_pairs_menu_labels_with_filenames_by_index(tmp_path):
    """menuLabel { 1 .. 3 } labels displayFileName 1..3; display 0 keeps EDM's empty label.

    The shape of lerf/mgnt_l1b_main.edl's "EPSC Hardware..." button: compacting
    the labels handed display 0 the label of display 1, and so on.
    """
    titles, filenames = _related_display_titles_and_filenames(
        tmp_path,
        "displayFileName {\n"
        + "".join(f'  {i} "mgnt_epsc"\n' for i in range(4))
        + '}\nmenuLabel {\n  1 "QCM03"\n  2 "XCM03"\n  3 "YCM03"\n}',
    )
    assert filenames == ["mgnt_epsc.ui"] * 4
    assert titles == ["", "QCM03", "XCM03", "YCM03"]


def test_convert_related_display_dense_menu_labels_unchanged(tmp_path):
    titles, filenames = _related_display_titles_and_filenames(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\nmenuLabel {\n  0 "A"\n  1 "B"\n}',
    )
    assert filenames == ["a.ui", "b.ui"]
    assert titles == ["A", "B"]


def test_convert_related_display_menu_labels_follow_filename_order(tmp_path):
    """Titles follow the filenames' own indices, so a gap in both stays aligned and a
    trailing display with no label gets an empty title rather than none."""
    titles, filenames = _related_display_titles_and_filenames(
        tmp_path,
        'displayFileName {\n  1 "a.edl"\n  3 "b.edl"\n  4 "c.edl"\n}\nmenuLabel {\n  1 "A"\n  3 "B"\n}',
    )
    assert filenames == ["a.ui", "b.ui", "c.ui"]
    assert titles == ["A", "B", ""]


def test_convert_related_display_placeholder_menu_label_keeps_its_slot(tmp_path):
    """A \\x18 label is no label: it holds its display's slot instead of being dropped."""
    titles, _ = _related_display_titles_and_filenames(
        tmp_path,
        'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\nmenuLabel {\n  0 "\x18"\n  1 "B"\n}',
    )
    assert titles == ["", "B"]


@pytest.mark.parametrize("labels", ['menuLabel {\n  0 "\x18"\n}', 'menuLabel {\n  1 "\x18"\n}'])
def test_convert_related_display_without_labels_has_no_titles(tmp_path, labels):
    """With no real label PyDM's default titles (the filenames) stand."""
    titles, filenames = _related_display_titles_and_filenames(
        tmp_path, 'displayFileName {\n  0 "a.edl"\n  1 "b.edl"\n}\n' + labels
    )
    assert filenames == ["a.ui", "b.ui"]
    assert titles is None


def test_convert_shell_command_pairs_command_labels_with_commands_by_index(tmp_path):
    """commandLabel { 1 .. } labels command 1 on (shell_cmd.cc pairs them by index)."""
    button = _convert_button(
        tmp_path,
        "shellCmdClass",
        "PyDMShellCommand",
        'numCmds 3\ncommand {\n  0 "echo a"\n  1 "echo b"\n  2 "echo c"\n}\ncommandLabel {\n  1 "B"\n  2 "C"\n}',
    )
    assert _stringlist(button, "commands") == ["echo a", "echo b", "echo c"]
    assert _stringlist(button, "titles") == ["", "B", "C"]


def test_convert_shell_command_to_commands_property(tmp_path):
    """Test that EDM shellCmdClass command property maps to PyDM commands property."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        # (Shell Command)
        object shellCmdClass
        beginObjectProperties
        major 4
        minor 2
        release 0
        x 100
        y 100
        w 150
        h 50
        fgColor index 14
        bgColor index 0
        buttonLabel "Test Button"
        numCmds 2
        command {
          0 "echo hello"
          1 "echo world"
        }
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    # Find the PyDMShellCommand widget
    shell_command_widgets = root.findall(".//widget[@class='PyDMShellCommand']")
    assert len(shell_command_widgets) == 1, "Should have one PyDMShellCommand"

    widget = shell_command_widgets[0]
    commands_property = widget.find("property[@name='commands']")
    assert commands_property is not None, "Widget should have commands property"

    # Check the stringlist contains both commands
    stringlist = commands_property.find("stringlist")
    assert stringlist is not None, "commands property should have stringlist element"

    strings = stringlist.findall("string")
    assert len(strings) == 2, "Should have 2 commands"
    assert strings[0].text == "echo hello", "First command should be 'echo hello'"
    assert strings[1].text == "echo world", "Second command should be 'echo world'"


def test_convert_meter_widget(tmp_path):
    """Test that EDM meter widget converts to PyDMAnalogIndicator."""
    edm_content = textwrap.dedent("""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 800
        h 600
        endScreenProperties

        # (Meter)
        object activeMeterClass
        beginObjectProperties
        major 4
        minor 0
        release 1
        x 100
        y 100
        w 150
        h 150
        readPv "IOC:SYS0:PRESSURE"
        scaleMin 0
        scaleMax 100
        showScale
        label "Pressure"
        fgColor index 14
        bgColor index 0
        endObjectProperties

        # (Meter)
        object activeMeterClass
        beginObjectProperties
        major 4
        minor 0
        release 1
        x 300
        y 100
        w 150
        h 150
        readPv "IOC:SYS0:FLOW"
        labelType "pvName"
        fgColor index 14
        bgColor index 0
        endObjectProperties
    """)

    input_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    assert output_file.exists()

    tree = ET.parse(output_file)
    root = tree.getroot()

    meter_widgets = root.findall(".//widget[@class='PyDMAnalogIndicator']")
    assert len(meter_widgets) == 2, "Should have two PyDMAnalogIndicators"

    widget = meter_widgets[0]

    channel_prop = widget.find("property[@name='channel']")
    assert channel_prop is not None, "Widget should have channel property"
    assert channel_prop.find("string").text == "IOC:SYS0:PRESSURE"

    title_prop = widget.find("property[@name='title']")
    assert title_prop is not None, "Widget should have title property"
    assert title_prop.find("string").text == "Pressure"

    pv_name_widget = meter_widgets[1]
    pv_name_title = pv_name_widget.find("property[@name='title']")
    assert pv_name_title is not None, "labelType pvName should fall back to the PV name as title"
    assert pv_name_title.find("string").text == "IOC:SYS0:FLOW"

    show_ticks = widget.find("property[@name='showTicks']")
    assert show_ticks is not None, "Widget should have showTicks property"
    assert show_ticks.find("bool").text == "true"

    show_limits = widget.find("property[@name='showLimits']")
    assert show_limits is not None, "Widget should have showLimits property"
    assert show_limits.find("bool").text == "true"

    show_units = widget.find("property[@name='showUnits']")
    assert show_units is not None, "Widget should have showUnits property"
    assert show_units.find("bool").text == "true"


@pytest.mark.parametrize("on_label, off_label, buttons", [("Cancel ", "Cancel", 1), ("Open", "Cancel", 2)])
def test_message_button_off_variant_ignores_label_padding(tmp_path, on_label, off_label, buttons):
    """Labels that differ only in padding (xray/vac_iso_valve.edl) get no separate off button."""
    edm_content = textwrap.dedent(f"""
        4 0 1
        beginScreenProperties
        major 4
        minor 0
        release 1
        x 0
        y 0
        w 200
        h 100
        endScreenProperties

        object activeMessageButtonClass
        beginObjectProperties
        major 4
        minor 0
        release 0
        x 10
        y 10
        w 80
        h 20
        controlPv "X:BYPASS"
        pressValue "0"
        onLabel "{on_label}"
        offLabel "{off_label}"
        endObjectProperties
    """)
    input_file = tmp_path / "button.edl"
    output_file = tmp_path / "button.ui"
    input_file.write_text(edm_content)

    convert(str(input_file), str(output_file))

    widgets = ET.parse(output_file).getroot().iter("widget")
    assert sum(widget.get("class") == "PyDMPushButton" for widget in widgets) == buttons


def test_convert_warns_when_a_shell_variable_shares_a_macro_name(tmp_path, caplog):
    r"""camac/camac_lu_from_epics_detail.edl: $\{LOCA\} (a shell variable) next to the
    $(LOCA) macro. Both read as ${LOCA}, which PyDM substitutes."""
    source = tmp_path / "shell.edl"
    source.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 200\nh 100\nendScreenProperties\n\n"
        "object shellCmdClass\nbeginObjectProperties\nmajor 4\nminor 2\nrelease 0\nx 10\ny 10\nw 100\nh 30\n"
        'numCmds 1\ncommand {\n  0 "luCWRestart $\\{LOCA\\} $(LOCA) $\\{HOME\\}"\n}\nendObjectProperties\n'
    )
    convert(str(source), str(tmp_path / "shell.ui"))
    assert "luCWRestart ${LOCA} ${LOCA} ${HOME}" in (tmp_path / "shell.ui").read_text()
    (warning,) = [r.getMessage() for r in caplog.records if "shares its name with a macro" in r.getMessage()]
    assert warning.endswith(": LOCA")


NESTED_VISIBILITY = textwrap.dedent("""\
    4 0 1
    beginScreenProperties
    major 4
    minor 0
    release 1
    x 0
    y 0
    w 200
    h 200
    endScreenProperties

    object activeGroupClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 10
    y 10
    w 100
    h 100

    beginGroup

    object activeGroupClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 20
    y 20
    w 50
    h 50

    beginGroup

    object activeRectangleClass
    beginObjectProperties
    major 4
    minor 0
    release 0
    x 30
    y 30
    w 20
    h 20
    lineColor index 14
    visPv "$(P):OWN"
    visMin "1"
    visMax "2"
    endObjectProperties

    endGroup

    visPv "$(P):INNER"
    visInvert
    endObjectProperties

    endGroup

    visPv "$(P):OUTER"
    endObjectProperties
    """)


def test_rule_order_does_not_depend_on_hash_seed(tmp_path):
    """A rectangle inside two groups with visPvs has three Visible terms. Converted in
    fresh interpreters with different string hash seeds, they keep one order: the
    outer group's, the inner group's, then the rectangle's own."""
    source = tmp_path / "nested.edl"
    source.write_text(NESTED_VISIBILITY)
    # The tree under test, not whatever pydmconverter the interpreter would find first.
    package_root = str(Path(pydmconverter.__file__).resolve().parents[1])
    code = "import sys; from pydmconverter.edm.converter import convert; convert(sys.argv[1], sys.argv[2])"
    rules_by_seed = {}
    for seed in ("1", "2", "3", "4"):
        output = tmp_path / f"nested_{seed}.ui"
        env = dict(os.environ, PYTHONHASHSEED=seed, QT_QPA_PLATFORM="offscreen")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH")]))
        result = subprocess.run(
            [sys.executable, "-c", code, str(source), str(output)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        rectangle = next(
            w for w in ET.parse(output).getroot().iter("widget") if w.get("class") == "PyDMDrawingRectangle"
        )
        rules_by_seed[seed] = json.loads(rectangle.find("property[@name='rules']/string").text)

    (visible,) = [r for r in rules_by_seed["1"] if r["property"] == "Visible"]
    assert [c["channel"] for c in visible["channels"]] == ["${P}:OUTER", "${P}:INNER", "${P}:OWN"]
    assert visible["expression"] == "(ch[0]==1) and (ch[1]!=1) and (float(ch[2]) >= 1.0 and float(ch[2]) < 2.0)"
    assert all(rules == rules_by_seed["1"] for rules in rules_by_seed.values())
