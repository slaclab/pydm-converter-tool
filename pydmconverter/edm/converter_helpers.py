from typing import Optional, List, Tuple
from pydmconverter.edm.parser import EDMObject, EDMGroup, EDMFileParser
from pydmconverter.widgets import (
    PyDMDrawingRectangle,
    PyDMDrawingEllipse,
    PyDMDrawingLine,
    PyDMDrawingPolyline,
    PyDMLabel,
    PyDMLineEdit,
    PyDMPushButton,
    PyDMRelatedDisplayButton,
    PyDMShellCommand,
    PyDMFrame,
    PyDMEmbeddedDisplay,
    QPushButton,
    PyDMEnumButton,
    QTabWidget,
    QWidget,
    QTableWidget,
    PyDMByteIndicator,
    PyDMDrawingArc,
    PyDMWaveformPlot,
    PyDMScaleIndicator,
    PyDMSlider,
    PyDMWaveformTable,
)
from pydmconverter.edm.parser_helpers import convert_color_property_to_qcolor, search_color_list, parse_colors_list
from pydmconverter.edm.menumux import generate_menumux_file
import logging
import math
import os
import copy

EDM_TO_PYDM_WIDGETS = {  # missing PyDMFrame, QPushButton, QComboBox, PyDMDrawingLine
    # Graphics widgets
    "activerectangleclass": PyDMDrawingRectangle,
    "circle": PyDMDrawingEllipse,
    "activelineclass": PyDMDrawingPolyline,
    "line": PyDMDrawingLine,
    # "image": PyDMImageView,
    "activextextclass": PyDMLabel,
    # Monitors
    # "meter": PyDMMeter,
    # "bar": PyDMBar,
    # "xy_graph": PyDMScatterPlot,
    # "byte_indicator": PyDMByteIndicator,
    # Controls
    "text_input": PyDMLineEdit,
    # "slider": PyDMSlider,
    "button": PyDMPushButton,
    # "menu_button": PyDMMenuButton,
    # "choice_button": PyDMChoiceButton,
    # "radio_box": PyDMRadioButtonGroup,
    "related_display_button": PyDMRelatedDisplayButton,
    "shell_command": PyDMShellCommand,
    # "activemessagebuttonclass": PyDMEnumComboBox,  # and more: activeMenuButtonClass, activeButtonClass
    # "": PyDMEnumButton
    "activemenubuttonclass": PyDMPushButton,  # "activemenubuttonclass": PyDMEnumComboBox,
    "activemessagebuttonclass": PyDMPushButton,
    "activextextdspclass": PyDMLineEdit,
    "activepipclass": PyDMEmbeddedDisplay,
    "activeexitbuttonclass": QPushButton,
    # "shellcmdclass": QPushButton,  # may need to change
    "shellcmdclass": PyDMShellCommand,
    "textupdateclass": PyDMLabel,
    "multilinetextupdateclass": PyDMLabel,
    "relateddisplayclass": PyDMRelatedDisplayButton,  # QPushButton,
    "activexregtextclass": PyDMLabel,
    "activebuttonclass": PyDMPushButton,
    "activechoicebuttonclass": QTabWidget,
    "activecircleclass": PyDMDrawingEllipse,
    "activepngclass": PyDMLabel,
    "activebarclass": PyDMDrawingRectangle,
    "activeslacbarclass": PyDMDrawingRectangle,
    "activeradiobuttonclass": PyDMEnumButton,
    "activetableclass": QTableWidget,
    # "activecoeftableclass": PyDMWaveformTable,
    "byteclass": PyDMByteIndicator,
    "textentryclass": PyDMLineEdit,
    "multilinetextentryclass": PyDMLineEdit,
    "activextextdspclassnoedit": PyDMLabel,
    "activearcclass": PyDMDrawingArc,
    "xygraphclass": PyDMWaveformPlot,  # TODO: Going to need to add PyDMScatterplot for when there are xPvs and yPvs
    # "xygraphclass": PyDMScatterPlot
    "activeindicatorclass": PyDMScaleIndicator,
    "activesymbolclass": PyDMEmbeddedDisplay,
    "anasymbolclass": PyDMEmbeddedDisplay,
    "activefreezebuttonclass": PyDMPushButton,
    "activesliderclass": PyDMSlider,
    "activemotifsliderclass": PyDMSlider,
    "mzxygraphclass": PyDMWaveformPlot,
    "regtextupdateclass": PyDMLabel,
    "activetriumfsliderclass": PyDMSlider,
    "activeupdownbuttonclass": PyDMPushButton,  # TODO: Need to find a more exact mapping but can't find a good edm screen to test with (all updown buttons are hidden)
    "activecoeftableclass": PyDMWaveformTable,
    "activerampbuttonclass": PyDMPushButton,  # TODO: Same here
    "mmvclass": PyDMSlider,  # TODO: Find a better mapping for multiple indicators in one slider
}

EDM_TO_PYDM_ATTRIBUTES = {
    # Common attributes
    "x": "x",
    "y": "y",
    "w": "width",
    "h": "height",
    "bgColor": "background_color",
    "fgColor": "foreground_color",
    "font": "font",
    "label": "text",
    "buttonLabel": "text",
    "frozenLabel": "frozenLabel",
    "frozenBgColor": "frozen_background_color",
    "tooltip": "PyDMToolTip",
    "visible": "visible",
    "noScroll": "noscroll",
    "enabled": "enabled",
    "precision": "precision",
    "showUnits": "show_units",
    "alarmPv": "channel",
    "controlPv": "channel",
    "indicatorPv": "channel",
    "filePv": "channel",
    "visPv": "visPv",
    "colorPv": "channel",
    "readPv": "channel",
    "nullPv": "channel",
    "pv": "channel",
    "visInvert": "visInvert",
    "value": "text",
    "fill": "brushFill",
    "fillColor": "brushColor",
    "autoSize": "autoSize",
    "lineColor": "penColor",
    # Graphics attributes
    "lineWidth": "line_width",
    "lineStyle": "penStyle",
    "radius": "radius",
    "color": "color",
    # Image and display attributes
    # "file": "image_file", #TODO: find where this image file is used
    "aspectRatio": "aspect_ratio_mode",
    "scale": "scale_contents",
    # Slider, meter, and bar attributes
    "scaleMin": "min",
    "scaleMax": "max",
    "orientation": "orientation",
    "barColor": "bar_color",
    "scaleColor": "scale_color",
    # Byte indicator attributes
    "bitPattern": "bits",
    "onColor": "on_color",
    "offColor": "off_color",
    "topShadowColor": "top_shadow_color",
    "botShadowColor": "bottom_shadow_color",
    # Command-related attributes
    "cmd": "command",
    "args": "arguments",
    "command": "command",
    "numCmds": "numCmds",
    "commandLabel": "command_label",
    # Related display attributes
    "fileName": "filename",
    "macro": "macro",
    "file": "filename",
    "useDisplayBg": "useDisplayBg",
    # Scatter plot attributes
    "xChannel": "x_channel",
    "yChannel": "y_channel",
    "xPv": "x_channel",
    "yPv": "y_channel",
    "xRange": "x_range",
    "yRange": "y_range",
    "markerStyle": "marker_style",
    "graphTitle": "plot_name",
    "xMin": "minXRange",
    "xMax": "maxXRange",
    "yMin": "minYRange",
    "yMax": "maxYRange",
    "yLabel": "yLabel",
    "xLabel": "xLabel",
    "gridColor": "axisColor",
    "yAxisSrc": "yAxisSrc",
    "xAxisSrc": "xAxisSrc",
    # Alarm sensitivity
    "alarmSensitiveContent": "alarmSensitiveContent",
    "alarmSensitiveBorder": "alarmSensitiveBorder",
    "fgAlarm": "alarmSensitiveContent",
    "lineAlarm": "alarmSensitiveContent",
    # Push Button attributes
    "pressValue": "press_value",
    "releaseValue": "release_value",
    # Misc attributes
    "onLabel": "on_label",
    "offLabel": "off_label",
    "arrows": "arrows",
    "fontAlign": "alignment",
    "displayFileName": "displayFileName",
    "embeddedHeight": "embeddedHeight",
    "embeddedWidth": "embeddedWidth",
    "numBits": "numBits",
    "startAngle": "startAngle",
    "totalAngle": "spanAngle",
    "visMin": "visMin",
    "visMax": "visMax",
    "symbolMin": "symbolMin",
    "symbolMax": "symbolMax",
    "symbolChannel": "symbolChannel",
    "tab_names": "tab_names",
    "hide_on_disconnect_channel": "hide_on_disconnect_channel",
    "flipScale": "flipScale",
    "indicatorColor": "indicatorColor",
    "majorTicks": "majorTicks",
    "minorTicks": "minorTicks",
    "plotColor": "plotColor",
    "nullColor": "nullColor",
    "closePolygon": "closePolygon",
    "secretId": "secretId",
    "isSymbol": "isSymbol",
    "limitsFromDb": "limitsFromDb",
    "showValue": "showValueLabel",
    "showLimits": "showLimitLabels",
    "labels": "rowLabels",
}

COLOR_ATTRIBUTES: set = {
    "fgColor",
    "bgColor",
    "lineColor",
    "offColor",
    "onColor",
    "topShadowColor",
    "botShadowColor",
    "indicatorColor",
    "frozenBgColor",
    "gridColor",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def transform_edm_to_pydm(edm_x, edm_y, edm_width, edm_height, container_height, scale=1.0, offset_x=0, offset_y=0):
    """
    Transform coordinates from an EDM coordinate system (bottom-left origin)
    to a PyDM coordinate system (top-left origin) at the root level.
    """
    pydm_x = offset_x + int(edm_x * scale)
    pydm_width = edm_width * scale
    pydm_height = edm_height * scale
    pydm_y = offset_y + int(edm_y * scale)

    logger.debug(
        f"Transform: EDM({edm_x}, {edm_y}, {edm_width}, {edm_height}) -> PyDM({pydm_x}, {pydm_y}, {pydm_width}, {pydm_height})"
    )

    return int(pydm_x), int(pydm_y), int(pydm_width), int(pydm_height)


def transform_nested_widget(
    child_edm_x,
    child_edm_y,
    child_edm_width,
    child_edm_height,
    parent_edm_x,
    parent_edm_y,
    parent_edm_height,
    scale=1.0,
):
    """
    Transform child widget coordinates relative to its parent.
    If EDM uses absolute coordinates for nested widgets, subtract parent position.
    """
    # Convert to relative coordinates by subtracting parent position
    relative_x = child_edm_x * scale  # - parent_edm_y
    relative_y = child_edm_y * scale  # - parent_edm_x
    child_width = child_edm_width * scale
    child_height = child_edm_height * scale

    return int(relative_x), int(relative_y), int(child_width), int(child_height)


def convert_edm_to_pydm_widgets(parser: EDMFileParser):
    """
    Converts an EDMFileParser object into a collection of PyDM widget instances.

    Parameters
    ----------
    parser : EDMFileParser
        The EDMFileParser instance containing parsed EDM objects and groups.

    Returns
    -------
    List[Union[widgets.PyDMWidgetBase, widgets.PyDMGroup]]
        A list of PyDM widget instances representing the EDM UI.
    """
    pydm_widgets = []
    used_classes = set()
    color_list_filepath = search_color_list()
    color_list_dict = parse_colors_list(color_list_filepath)

    pip_objects = find_objects(parser.ui, "activepipclass")  # find tabs and populate tab bars with tabs
    for pip_object in pip_objects:
        create_embedded_tabs(pip_object, parser.ui)

    text_objects = find_objects(
        parser.ui, "activextextclass"
    )  # TODO: If this gets too large, make into a helper function
    for text_object in text_objects:
        if should_delete_overlapping(parser.ui, text_object, "relateddisplayclass"):
            delete_object_in_group(parser.ui, text_object)

    def traverse_group(
        edm_group: EDMGroup,
        color_list_dict,
        parent_pydm_group: Optional[PyDMFrame] = None,
        pydm_widgets=None,
        container_height: float = None,
        scale: float = 1.0,
        offset_x: float = 0,
        offset_y: float = 0,
        central_widget: EDMGroup = None,
        parent_vispvs: Optional[List[Tuple[str, int, int]]] = None,
        # parent_vis_range: Optional[Tuple[int, int]] = None,
    ):
        menu_mux_buttons = []
        if pydm_widgets is None:
            pydm_widgets = []

        for obj in edm_group.objects:
            if isinstance(obj, EDMGroup):
                if parent_pydm_group is None:
                    x, y, width, height = transform_edm_to_pydm(
                        obj.x,
                        obj.y,
                        obj.width,
                        obj.height,
                        container_height=container_height,
                        scale=scale,
                        offset_x=offset_x,
                        offset_y=offset_y,
                    )
                else:
                    x, y, width, height = transform_nested_widget(
                        obj.x,
                        obj.y,
                        obj.width,
                        obj.height,
                        parent_pydm_group.x,  # Add parent x
                        parent_pydm_group.y,  # Add parent y
                        parent_pydm_group.height,
                        scale=scale,
                    )

                print("skipped pydm_group")

                if "visPv" in obj.properties and "visMin" in obj.properties and "visMax" in obj.properties:
                    curr_vispv = [(obj.properties["visPv"], obj.properties["visMin"], obj.properties["visMax"])]
                elif "visPv" in obj.properties:
                    curr_vispv = [(obj.properties["visPv"], None, None)]
                else:
                    curr_vispv = []

                if (
                    "symbolMin" in obj.properties
                    and "symbolMax" in obj.properties
                    and "symbolChannel" in obj.properties
                ):
                    symbol_vispv = [
                        (obj.properties["symbolChannel"], obj.properties["symbolMin"], obj.properties["symbolMax"])
                    ]
                else:
                    symbol_vispv = []

                traverse_group(
                    obj,
                    color_list_dict,
                    pydm_widgets=pydm_widgets,
                    container_height=height,
                    scale=scale,
                    offset_x=0,
                    offset_y=0,
                    central_widget=central_widget,
                    parent_vispvs=(parent_vispvs or []) + curr_vispv + symbol_vispv,
                    # parent_vis_range=(parent_vis_range or []) + curr_vis_range,
                )

            elif isinstance(obj, EDMObject):
                widget_type = EDM_TO_PYDM_WIDGETS.get(obj.name.lower())
                if obj.name.lower() == "menumuxclass":
                    menu_mux_buttons.append(obj)
                if not widget_type:
                    logger.warning(f"Unsupported widget type: {obj.name}. Skipping.")
                    log_unsupported_widget(obj.name)
                    continue
                if obj.name.lower() == "activechoicebuttonclass" and (
                    "tabs" not in obj.properties or not obj.properties["tabs"]
                ):
                    channel = search_for_edm_attr(obj, "channel")

                    if not channel:
                        logger.warning("Could not find channel in object: {obj.name}")
                    else:
                        tab_names = None
                        # tab_names = get_channel_tabs(channel)
                        widget_type = PyDMEnumButton
                        obj.properties["tab_names"] = tab_names
                        obj.properties["hide_on_disconnect_channel"] = channel

                widget = widget_type(name=obj.name + str(id(obj)) if hasattr(obj, "name") else f"widget_{id(obj)}")
                used_classes.add(type(widget).__name__)
                logger.info(f"Creating widget: {widget_type.__name__} ({widget.name})")

                if parent_vispvs:
                    setattr(widget, "visPvList", list(parent_vispvs))

                # Set mapped attributes.
                for edm_attr, value in obj.properties.items():
                    pydm_attr = EDM_TO_PYDM_ATTRIBUTES.get(edm_attr)

                    if obj.name.lower() == "activelineclass" and edm_attr in ["xPoints", "yPoints", "numPoints"]:
                        continue

                    if not pydm_attr:
                        continue

                    if edm_attr == "font":
                        value = parse_font_string(value)
                    if edm_attr == "fillColor":
                        original_value = value
                        color_tuple = convert_color_property_to_qcolor(value, color_data=color_list_dict)
                        logger.info(f"Color conversion: {original_value} -> {color_tuple}")
                        if color_tuple:
                            value = color_tuple
                            logger.info(f"Setting fillColor/brushColor to: {value}")
                        else:
                            logger.warning(f"Could not convert color {value}, skipping")
                            continue
                    if edm_attr == "value":
                        value = get_string_value(value)
                    if edm_attr in COLOR_ATTRIBUTES:
                        value = convert_color_property_to_qcolor(value, color_data=color_list_dict)
                    if edm_attr == "plotColor":
                        color_list = []
                        for color in value:
                            color_list.append(convert_color_property_to_qcolor(color, color_data=color_list_dict))
                        value = color_list
                    try:
                        setattr(widget, pydm_attr, value)
                        logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                    except Exception as e:
                        logger.error(f"Failed to set attribute {pydm_attr} on {widget.name}: {e}")

                if obj.name.lower() == "activechoicebuttonclass" and widget_type == QTabWidget:
                    populate_tab_bar(obj, widget)
                if obj.name.lower() == "activelineclass" and isinstance(widget, PyDMDrawingPolyline):
                    if "xPoints" in obj.properties and "yPoints" in obj.properties:
                        x_points = obj.properties["xPoints"]
                        y_points = obj.properties["yPoints"]
                        abs_pts = [(int(float(x)), int(float(y))) for x, y in zip(x_points, y_points)]
                        pen = int(obj.properties.get("lineWidth", 1))
                        startCoord = (obj.x, obj.y)
                        geom, point_strings = geom_and_local_points(abs_pts, startCoord, pen)

                        widget.points = point_strings
                        widget.pen_width = pen
                        widget.pen_color = (0, 0, 0)
                        # widget.x, widget.y = geom["x"], geom["y"]
                        # widget.width       = geom["width"]
                        # widget.height      = geom["height"]

                if parent_pydm_group is None:
                    x, y, width, height = transform_edm_to_pydm(
                        obj.x,
                        obj.y,
                        obj.width,
                        obj.height,
                        container_height=container_height,
                        scale=scale,
                        offset_x=offset_x,
                        offset_y=offset_y,
                    )
                else:
                    x, y, width, height = transform_nested_widget(
                        obj.x,
                        obj.y,
                        obj.width,
                        obj.height,
                        parent_pydm_group.x,  # Add parent x
                        parent_pydm_group.y,  # Add parent y
                        parent_pydm_group.height,
                        scale=scale,
                    )
                widget.x = int(x)
                widget.y = int(y)
                widget.width = max(1, int(width))
                widget.height = max(1, int(height))

                if type(widget).__name__ == "PyDMPushButton" and (
                    "offLabel" in obj.properties and "onLabel" not in obj.properties
                ):
                    setattr(widget, "text", obj.properties["offLabel"])
                elif type(widget).__name__ == "PyDMPushButton" and (
                    (
                        ("offLabel" in obj.properties and obj.properties["offLabel"] != obj.properties["onLabel"])
                        or ("offColor" in obj.properties and obj.properties["offColor"] != obj.properties["onColor"])
                    )
                    and hasattr(widget, "channel")
                    and widget.channel is not None
                ):
                    off_button = create_off_button(widget)
                    pydm_widgets.append(off_button)
                if obj.name.lower() == "activefreezebuttonclass":
                    freeze_button = create_freeze_button(widget)
                    pydm_widgets.append(freeze_button)

                if obj.name.lower() == "mmvclass":
                    generated_sliders = create_multi_sliders(widget, obj)
                    for slider in generated_sliders:
                        pydm_widgets.append(slider)

                if isinstance(widget, (PyDMDrawingLine, PyDMDrawingPolyline)):
                    pad = widget.pen_width or 1
                    widget.width = int(widget.width) + pad
                    widget.height = int(widget.height) + pad

                if obj.properties.get("autoSize", False):
                    widget.autoSize = True

                pydm_widgets.append(widget)
                logger.info(f"Added {widget.name} to root")
            else:
                logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

        return pydm_widgets, menu_mux_buttons

    pydm_widgets, menu_mux_buttons = traverse_group(
        parser.ui, color_list_dict, None, None, parser.ui.height, central_widget=parser.ui
    )
    if menu_mux_buttons:
        generate_menumux_file(menu_mux_buttons, parser.output_file_path)
    return pydm_widgets, used_classes


def should_delete_overlapping(
    group: EDMGroup,
    curr_obj: EDMObject,
    overlapping_name: str = "relateddisplayclass",
    percentage_overlapping: float = 80,
) -> bool:
    overlap_type_widgets = find_objects(group, overlapping_name)
    for widget in (
        overlap_type_widgets
    ):  # maybe need to improve conditional but I wanted to have it skip needless calculations if percent overlap == 100
        if (
            (
                percentage_overlapping == 100
                and widget.x == curr_obj.x
                and widget.y == curr_obj.y
                and widget.width == curr_obj.width
                and widget.height == curr_obj.height
            )
            or (percentage_overlapping != 100 and calculate_widget_overlap(curr_obj, widget) > percentage_overlapping)
            and "value" not in widget.properties
            and "value" in curr_obj.properties
        ):
            widget.properties["value"] = curr_obj.properties["value"]
            return True
    return False


def calculate_widget_overlap(widget1: EDMObject, widget2: EDMObject) -> float:
    overlap_x1 = max(widget1.x, widget2.x)
    overlap_x2 = min(widget1.x + widget1.width, widget2.x + widget2.width)
    overlap_y1 = max(widget1.y, widget2.y)
    overlap_y2 = min(widget1.y + widget1.height, widget2.y + widget2.height)
    if overlap_x1 >= overlap_x2 or overlap_y1 >= overlap_y2:
        return 0
    overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
    widget1_area = widget1.width * widget1.height
    widget2_area = widget2.width * widget2.height
    percent_area_1 = overlap_area / widget1_area * 100
    percent_area_2 = overlap_area / widget2_area * 100
    return min(percent_area_1, percent_area_2)


def delete_object_in_group(group: EDMGroup, deleted: EDMObject):
    for i in range(len(group.objects)):
        if isinstance(group.objects[i], EDMGroup):
            delete_object_in_group(group.objects[i], deleted)
        elif group.objects[i] == deleted:
            group.objects.pop(i)
            return


def find_objects(group: EDMGroup, obj_name: str) -> List[EDMObject]:
    """
    Recursively search through an EDMGroup and its nested groups to find all
    instances of EDMObjects that match a specified name.

    Parameters
    ----------
    group : EDMGroup
        The EDMGroup instance within which to search for objects.
    obj_name : str
        The name of the object to search for (case insensitive)

    Returns
    -------
    List[EDMObject]
        A list of EDMObject instances that match the specified name. If no
        matches are found, an empty list is returned.
    """
    objects = []
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            objects += find_objects(obj, obj_name)
        elif obj.name.lower() == obj_name.lower():
            objects.append(obj)
    return objects


def create_off_button(widget: PyDMPushButton):
    """
    Given a PyDMPushButton with distinct off/on states, clone it into an "off" version.
    Modifies relevant visual attributes and appends a flag to identify it.
    """
    off_button = copy.deepcopy(widget)
    off_button.name = widget.name + "_off"
    if hasattr(widget, "off_color"):
        off_button.on_color = widget.off_color
    if hasattr(widget, "off_label"):
        off_button.on_label = widget.off_label
        off_button.text = widget.off_label
        widget.text = widget.on_label
    setattr(off_button, "is_off_button", True)
    setattr(widget, "is_off_button", False)
    logger.info(f"Created off-button: {off_button.name} based on {widget.name}")

    return off_button


def create_freeze_button(
    widget: PyDMPushButton,
):  # TODO: Can find a way to combine with create_off_button to reduce redundancy
    """
    Given a PyDMPushButton converted from an activefreezebuttonclass, clone it into a "freeze" version.
    Modifies relevant visual attributes and appends a flag to identify it.
    """
    freeze_button = copy.deepcopy(widget)
    freeze_button.name = widget.name + "_freeze"
    if hasattr(widget, "frozenLabel"):
        freeze_button.text = widget.frozenLabel
    if hasattr(widget, "frozen_background_color"):
        freeze_button.background_color = widget.frozen_background_color
    setattr(freeze_button, "is_freeze_button", True)
    setattr(widget, "is_freeze_button", False)
    logger.info(f"Created off-button: {freeze_button.name} based on {widget.name}")

    return freeze_button


def create_multi_sliders(widget: PyDMSlider, object: EDMObject):
    """
    Given a ActiveSlider converted from a mmvclass, create stacked sliders to show each slider indicator.
    Modifies the height and channel of the current slider
    """
    i = 1
    prevColor = None
    ctrl_attributes = []
    extra_sliders = []
    while f"ctrl{i}Pv" in object.properties:
        if f"ctrl{i}Color" in object.properties:
            currColor = object.properties[f"ctrl{i}Color"]
        else:
            currColor = prevColor
        ctrl_attributes.append((object.properties[f"ctrl{i}Pv"], currColor))
        prevColor = currColor
        i += 1
    if ctrl_attributes:
        setattr(widget, "height", widget.height // len(ctrl_attributes))
        setattr(widget, "channel", ctrl_attributes[0][0])
        setattr(widget, "indicatorColor", ctrl_attributes[0][1])
        for j in range(1, len(ctrl_attributes)):
            curr_slider = copy.deepcopy(widget)
            curr_slider.name = widget.name + f"_{j}"
            setattr(curr_slider, "y", curr_slider.y + curr_slider.height * j)
            setattr(curr_slider, "channel", ctrl_attributes[j][0])
            setattr(curr_slider, "indicatorColor", ctrl_attributes[j][1])
            logger.info(f"Created multi-slider: {curr_slider.name} based on {widget.name}")
            extra_sliders.append(curr_slider)
    return extra_sliders


def populate_tab_bar(obj: EDMObject, widget):
    tab_names = obj.properties.get("tabs", [])
    if not tab_names and widget.channel is not None:
        # tab_names = get_channel_tabs(widget.channel)
        tab_names = None
    if not tab_names:
        logger.warning(f"No tab names found in {obj.name}. Skipping.")
        return

    if "displayFileName" in obj.properties and obj.properties["displayFileName"] is not None:
        file_list = obj.properties["displayFileName"]
        for index, tab_name in enumerate(tab_names):
            child_widget = QWidget(title=tab_name)
            widget.add_child(child_widget)
            embedded_widget = PyDMEmbeddedDisplay(
                name=f"{tab_name}_embedded",
                x=0,
                y=0,
                filename=file_list[index],
                visible=True,
                height=500,
                width=500,
            )
            child_widget.add_child(embedded_widget)
    else:
        for tab_name in tab_names:
            child_widget = QWidget(title=tab_name)
            widget.add_child(child_widget)


def get_channel_tabs(channel: str, timeout: float = 0.5) -> List[str]:
    # pv = PV(channel, connection_timeout=timeout)
    # pv = PV(channel)
    # if pv and pv.enum_strs:
    #    return list(pv.enum_strs)
    return None


def create_embedded_tabs(obj: EDMObject, central_widget: EDMGroup) -> bool:
    """
    If needed, creates tabs from local variables of this embedded display.

    Parameters
    ----------
    obj : EDMObject
        The activePipClass EDMFileObject instance that will be used to generate tabs and embedded displays. (This object is an activePipClass).

    Returns
    -------
    bool
        Returns true if embedded tabs added, returns false if unable to create embedded tabs
    """
    searched_arr = None
    print(obj.properties.items())
    for prop_name, prop_val in obj.properties.items():
        if isinstance(prop_val, str) and (
            "loc://" in prop_val or "LOC\\" in prop_val
        ):  # TODO: is it possible to have multiple loc\\ in the same embedded display?
            searched_arr = prop_val.split("=")
            channel_name = prop_val.split("?")[0]
    if int(obj.properties["numDsps"]) <= 1 or searched_arr is None:
        return False
    # channel_name = searched_arr[0]
    string_list = searched_arr[-1]
    channel_list = string_list[1:-1].split(", ")
    tab_names = [item.strip("'") for item in channel_list]
    for i in range(len(tab_names)):
        if not tab_names[i]:
            tab_names.pop(i)
    tab_widget = search_group(central_widget, "activeChoiceButtonClass", channel_name, "Pv")
    if tab_widget is None:
        return False

    tab_widget.properties["tabs"] = tab_names
    tab_widget.properties["displayFileName"] = obj.properties["displayFileName"]
    tab_widget.properties["embeddedHeight"] = obj.height
    tab_widget.properties["embeddedWidth"] = obj.width
    # tab_widget.properties["w"] = tab_widget.properties["w"] + obj.properties["w"] #prob not use
    # tab_widget.properties["height"] = tab_widget.properties["height"] + obj.properties["height"]
    return True


def search_group(
    group: EDMGroup, widget_type: str, prop_val: str, prop_name_suffix: str = "Pv"
) -> EDMObject:  # TODO: May need to check for edgecases with multiple tabs
    """
    Recursively search through all nodes in an EDMGroup for a specified widget type
    and a property-value pair where property names end with a specific suffix.

    Parameters
    ----------
    group : EDMGroup
        The EDMGroup to search within.
    widget_type : str
        The type of widget to search for.
    property_val: str
        The expected value.
    prop_name_suffix : str
        The suffix that property names should end with to be checked.

    Returns
    -------
    Optional[EDMObject]
        Returns the found EDMObject if it matches the criteria, else None.
    """
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            child_object = search_group(obj, widget_type, prop_val, prop_name_suffix)
            if child_object is not None:
                return child_object
        elif obj.name.lower() == widget_type.lower():
            for key, value in obj.properties.items():
                if key.endswith(prop_name_suffix):
                    if value is not None and prop_val in value:  # prop_val == value
                        return obj

    return None


def log_unsupported_widget(widget_type, file_path="unsupported_widgets.txt"):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            existing_widgets = {line.strip() for line in file.readlines()}
    else:
        existing_widgets = set()

    if widget_type.lower() not in existing_widgets:
        with open(file_path, "a") as file:
            file.write(widget_type.lower() + "\n")


def search_for_edm_attr(obj: EDMObject, target_attr: str):
    for edm_attr, value in obj.properties.items():
        pydm_attr = EDM_TO_PYDM_ATTRIBUTES.get(edm_attr)
        if pydm_attr == target_attr:
            return value


def get_string_value(value: list) -> str:
    """
    Takes in a value string and joins each element into a string separated by a new line
    """
    return "\n".join(value)


def parse_font_string(font_str: str) -> dict:
    """
    Parse an EDM font string like 'helvetica-bold-r-12.0'
    into a dictionary for a PyDM widget.
    This is just an example parser—adjust as needed.
    """
    if not font_str:
        font_str = "helvetica-medium-r-12.0"
    parts = font_str.split("-")
    family = parts[0].capitalize()
    bold = "bold" in parts[1].lower()
    italic = "i" in parts[2].lower() or "o" in parts[2].lower()
    size_str = parts[-1]
    # pointsize = convert_pointsize(float(size_str))
    # NOTE: This line is commented because of how I observed fastx displays pointsize. In browser mode, the conversion from pixelsize to pointsize is 0.75. In desktop mode, the conversion is ~0.51
    # TODO: Find which version is accurate to how pydm is used and use that function
    pointsize = convert_pointsize(float(size_str))

    return {
        "family": family,
        "pointsize": pointsize,
        "bold": bold,
        "italic": italic,
        "weight": 50,
    }


def convert_pointsize(pixel_size, dpi: float = 96):
    """
    Convert the edm pizelsize to pydm pointsize (multiply by 0.75)
    """
    point_size = pixel_size * 72 / dpi
    return math.floor(point_size)


def new_convert_pointsize(pixel_size):
    point_size = pixel_size * 37 / 72  # Recieved these numbers from arbitrary test
    return math.floor(point_size)


def geom_and_local_points(abs_points, startCoord, pen_width: int = 1):
    if not abs_points:
        logger.warning("abs_points is empty for PyDMDrawingPolyLine")  # TODO: Fix this
        return {}, []
    xs, ys = zip(*abs_points)
    min_x, max_x = min(list(xs)), max(xs)  # TODO: Comeback and resolve which to use
    min_y, max_y = min(list(ys)), max(ys)

    geom = {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x + pen_width,
        "height": max_y - min_y + pen_width,
    }

    rel = [(x - min_x, y - min_y) for x, y in abs_points]
    return geom, [f"{x}, {y}" for x, y in rel]
