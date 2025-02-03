from parser import EDMFileParser, EDMObject
import xml.etree.ElementTree as ET
from converter_helpers import convert_edm_to_pydm_widgets
import logging
from pprint import pprint

logger = logging.getLogger(__name__)

CUSTOM_WIDGET_DEFINITIONS = {
    "PyDMFrame": {"extends": "QFrame", "header": "pydm.widgets.frame", "container": "1"},
    "PyDMDrawingRectangle": {"extends": "QLabel", "header": "pydm.widgets.drawing", "container": ""},
    "PyDMDrawingEllipse": {"extends": "QLabel", "header": "pydm.widgets.drawing", "container": ""},
    "PyDMDrawingLine": {"extends": "QLabel", "header": "pydm.widgets.drawing", "container": ""},
    "PyDMDrawingPolyline": {"extends": "QWidget", "header": "pydm.widgets.drawing", "container": ""},
    "PyDMLabel": {"extends": "QLabel", "header": "pydm.widgets.label", "container": ""},
}


def convert(input_path, output_path):
    try:
        edm_parser = EDMFileParser(input_path)
        pprint(edm_parser.ui, indent=2)
        logger.info(f"Successfully parsed EDM file: {input_path}")
    except FileNotFoundError:
        logger.error("File Not Found")
        return

    # edm_parser.ui, _, _ = replace_calc_and_loc_in_edm_content(edm_parser.ui, input_path)

    pydm_widgets, used_classes = convert_edm_to_pydm_widgets(edm_parser)
    logger.info(f"Converted EDM objects to {len(pydm_widgets)} PyDM widgets.")

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
    ET.SubElement(rect, "width").text = str(edm_parser.ui.width)
    ET.SubElement(rect, "height").text = str(edm_parser.ui.height)

    window_title = ET.SubElement(main_widget, "property", attrib={"name": "windowTitle"})
    title_string = ET.SubElement(window_title, "string")
    title_string.text = "PyDM Screen"

    central_widget = ET.SubElement(
        main_widget,
        "widget",
        attrib={
            "class": "QWidget",
            "name": "centralwidget",
        },
    )

    if isinstance(edm_parser.ui, EDMObject) and "bgColor" in edm_parser.ui.properties:
        bg_color = edm_parser.ui.properties["bgColor"]
        bg_color_prop = ET.SubElement(central_widget, "property", attrib={"name": "styleSheet"})
        style_sheet_elem = ET.SubElement(bg_color_prop, "string")
        style_sheet_elem.text = f"background-color: {bg_color};"

    add_widgets_to_parent(pydm_widgets, central_widget)

    customwidgets_el = build_customwidgets_element(used_classes)
    print(ui_element)
    ui_element.append(customwidgets_el)

    ET.SubElement(ui_element, "resources")
    ET.SubElement(ui_element, "connections")

    ET.indent(ui_element, space="  ", level=0)

    tree = ET.ElementTree(ui_element)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def build_customwidgets_element(used_classes: set) -> ET.Element:
    customwidgets_el = ET.Element("customwidgets")

    for cls_name in sorted(used_classes):
        if cls_name not in CUSTOM_WIDGET_DEFINITIONS:
            continue

        data = CUSTOM_WIDGET_DEFINITIONS[cls_name]

        cw_el = ET.SubElement(customwidgets_el, "customwidget")

        class_el = ET.SubElement(cw_el, "class")
        class_el.text = cls_name

        extends_el = ET.SubElement(cw_el, "extends")
        extends_el.text = data["extends"]

        header_el = ET.SubElement(cw_el, "header")
        header_el.text = data["header"]

        if data["container"]:
            container_el = ET.SubElement(cw_el, "container")
            container_el.text = data["container"]

    return customwidgets_el


def add_widgets_to_parent(widgets, parent_element):
    for widget in widgets:
        widget_element = widget.to_xml()
        parent_element.append(widget_element)

        if hasattr(widget, "children") and widget.children:
            add_widgets_to_parent(widget.children, widget_element)
