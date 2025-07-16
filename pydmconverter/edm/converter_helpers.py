from typing import Optional, List
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
    PyDMTabWidget,
)
from pydmconverter.edm.parser_helpers import convert_color_property_to_qcolor, search_color_list, parse_colors_list
import logging
import math
import os

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
    "activextextdspclass": PyDMLabel,
    "activepipclass": PyDMEmbeddedDisplay,
    "activeexitbuttonclass": QPushButton,
    "shellcmdclass": QPushButton,  # may need to change
    "textupdateclass": PyDMLabel,
    "relateddisplayclass": PyDMRelatedDisplayButton,  # QPushButton,
    "activexregtextclass": PyDMLabel,
    "activebuttonclass": PyDMPushButton,
    "activechoicebuttonclass": PyDMTabWidget,
    "activecircleclass": PyDMDrawingEllipse,
    "activepngclass": PyDMLabel,
    "activeslacbarclass": PyDMDrawingRectangle,
    "activeradiobuttonclass": PyDMEnumButton,
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
    "visPv": "channel",
    "colorPv": "channel",
    "readPv": "channel",
    "nullPv": "channel",  # TODO: Add xpv and yPv
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
    # Related display attributes
    "fileName": "filename",
    "macro": "macro",
    "file": "filename",
    "useDisplayBg": "useDisplayBg",
    # Scatter plot attributes
    "xChannel": "x_channel",
    "yChannel": "y_channel",
    "xRange": "x_range",
    "yRange": "y_range",
    "markerStyle": "marker_style",
    # Alarm sensitivity
    "alarmSensitiveContent": "alarmSensitiveContent",
    "alarmSensitiveBorder": "alarmSensitiveBorder",
    # Push Button attributes
    "pressValue": "press_value",
    "releaseValue": "release_value",
    "onLabel": "text",  # TODO: may need to change later to accomidate for offLabel (but in all examples so far they are the same)
    "arrows": "arrows",
    "fontAlign": "alignment",
}

# Configure logging
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

    pip_objects = find_objects(parser.ui, "activepipclass")

    for pip_object in pip_objects:
        print(pip_object.name)
    print(len(pip_objects))
    breakpoint()

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
    ):
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
                pydm_group = PyDMFrame(
                    name=obj.name if hasattr(obj, "name") else f"group_{id(obj)}",
                    x=0,
                    y=0,
                    width=parser.ui.width,
                    height=parser.ui.height,
                )
                logger.info(f"Created PyDMFrame: {pydm_group.name}")

                if parent_pydm_group:
                    parent_pydm_group.add_child(pydm_group)
                else:
                    pydm_widgets.append(pydm_group)

                used_classes.add(type(pydm_group).__name__)

                traverse_group(
                    obj,
                    color_list_dict,
                    pydm_group,
                    pydm_widgets=None,
                    container_height=height,
                    scale=scale,
                    offset_x=0,
                    offset_y=0,
                    central_widget=central_widget,
                )

            elif isinstance(obj, EDMObject):
                widget_type = EDM_TO_PYDM_WIDGETS.get(obj.name.lower())
                if not widget_type:
                    logger.warning(f"Unsupported widget type: {obj.name}. Skipping.")
                    log_unsupported_widget(obj.name)
                    continue

                widget = widget_type(name=obj.name + str(id(obj)) if hasattr(obj, "name") else f"widget_{id(obj)}")
                used_classes.add(type(widget).__name__)
                logger.info(f"Creating widget: {widget_type.__name__} ({widget.name})")

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
                    color_attributes: set = {
                        "fgColor",
                        "bgColor",
                        "lineColor",
                        "offColor",
                        "onColor",
                        "topShadowColor",
                        "botShadowColor",
                    }
                    if edm_attr in color_attributes:
                        value = convert_color_property_to_qcolor(value, color_data=color_list_dict)

                    try:
                        setattr(widget, pydm_attr, value)
                        logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                    except Exception as e:
                        logger.error(f"Failed to set attribute {pydm_attr} on {widget.name}: {e}")

                """if (
                    obj.name.lower() == "activepipclass"
                ):
                    create_embedded_tabs(obj, central_widget)"""

                if obj.name.lower() == "activelineclass" and isinstance(widget, PyDMDrawingPolyline):
                    if "xPoints" in obj.properties and "yPoints" in obj.properties:
                        x_points = obj.properties["xPoints"]
                        y_points = obj.properties["yPoints"]
                        abs_pts = [(int(x), int(y)) for x, y in zip(x_points, y_points)]
                        pen = int(obj.properties.get("lineWidth", 1))
                        geom, point_strings = geom_and_local_points(abs_pts, pen)

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

                if isinstance(widget, (PyDMDrawingLine, PyDMDrawingPolyline)):
                    pad = widget.pen_width or 1
                    widget.width = int(widget.width) + pad
                    widget.height = int(widget.height) + pad

                if obj.properties.get("autoSize", False):
                    widget.autoSize = True

                if parent_pydm_group:
                    parent_pydm_group.add_child(widget)
                    logger.info(f"Added {widget.name} to parent {parent_pydm_group.name}")
                else:
                    pydm_widgets.append(widget)
                    logger.info(f"Added {widget.name} to root")
            else:
                logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

        return pydm_widgets

    pydm_widgets = traverse_group(parser.ui, color_list_dict, None, None, parser.ui.height, central_widget=parser.ui)
    return pydm_widgets, used_classes


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


def create_embedded_tabs(obj: EDMObject, central_widget: EDMGroup) -> None:
    """
    If needed, creates tabs from local variables of this embedded display.

    Parameters
    ----------
    obj : EDMObject
        The activePipClass EDMFileObject instance that will be used to generate tabs and embedded displays. (This object is an activePipClass).
    """
    searched_arr = None
    for prop_name, prop_val in obj.properties.items():
        if prop_val is str and prop_val.startswith(
            "LOC\\"
        ):  # TODO: is it possible to have multiple loc\\ in the same embedded display?
            searched_arr = prop_val.split("=")
    if int(obj.num_disps) <= 1 or searched_arr is None or not searched_arr[1].startswith("e"):
        return None
    channel_name, channel_value = searched_arr

    tab_widget = search_group(central_widget, "activeChoiceButton", channel_name, "Pv")
    if tab_widget is None:
        return None
    # tab_names = channel_value.split(",")[1:]
    # tab_widget.properties[]


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
                    if value is not None and value == prop_val:
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
    print("fonts", font_str)
    parts = font_str.split("-")
    family = parts[0].capitalize()
    bold = "bold" in parts[1].lower()
    italic = "i" in parts[2].lower() or "o" in parts[2].lower()
    size_str = parts[-1]
    pointsize = math.floor(convert_pointsize(float(size_str), 100))

    return {
        "family": family,
        "pointsize": pointsize,
        "bold": bold,
        "italic": italic,
        "weight": 50,
    }


def convert_pointsize(pixel_size, dpi: float = 96):
    """
    Convert the edm pizelsize to pydm pointsize (default is 96)
    """
    point_size = pixel_size * 72 / dpi
    return point_size


def geom_and_local_points(abs_points, pen_width: int = 1):
    xs, ys = zip(*abs_points)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    geom = {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x + pen_width,
        "height": max_y - min_y + pen_width,
    }

    rel = [(x - min_x, y - min_y) for x, y in abs_points]
    return geom, [f"{x}, {y}" for x, y in rel]
