from typing import Optional
from parser import EDMObject, EDMGroup, EDMFileParser
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
)
from parser_helpers import convert_fill_property_to_qcolor, search_color_list, parse_colors_list
import logging


EDM_TO_PYDM_WIDGETS = {
    # Graphics widgets
    "activerectangleclass": PyDMDrawingRectangle,
    "circle": PyDMDrawingEllipse,
    "activelineclass": PyDMDrawingPolyline,
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
    "tooltip": "PyDMToolTip",
    "visible": "visible",
    "enabled": "enabled",
    "precision": "precision",
    "showUnits": "show_units",
    "alarmPv": "channel",
    "controlPv": "channel",
    "indicatorPv": "channel",
    "value": "text",
    "fill": "brushFill",
    "fillColor": "brushColor",
    "autoSize": "autoSize",
    # Graphics attributes
    "lineWidth": "line_width",
    "lineStyle": "line_style",
    "radius": "radius",
    "color": "color",
    # Image and display attributes
    "file": "image_file",
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
    # Command-related attributes
    "cmd": "command",
    "args": "arguments",
    # Related display attributes
    "fileName": "filename",
    "macro": "macro",
    # Scatter plot attributes
    "xChannel": "x_channel",
    "yChannel": "y_channel",
    "xRange": "x_range",
    "yRange": "y_range",
    "markerStyle": "marker_style",
    # Alarm sensitivity
    "alarmSensitiveContent": "alarmSensitiveContent",
    "alarmSensitiveBorder": "alarmSensitiveBorder",
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
    relative_x = parent_edm_x + (child_edm_x * scale)
    relative_y = parent_edm_y + (child_edm_y * scale)
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

    def traverse_group(
        edm_group: EDMGroup,
        color_list_dict,
        parent_pydm_group: Optional[PyDMFrame] = None,
        pydm_widgets=None,
        container_height: float = None,
        scale: float = 1.0,
        offset_x: float = 0,
        offset_y: float = 0,
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
                    name=obj.name if hasattr(obj, "name") else f"group_{id(obj)}", x=x, y=y, width=width, height=height
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
                )

            elif isinstance(obj, EDMObject):
                widget_type = EDM_TO_PYDM_WIDGETS.get(obj.name.lower())
                if not widget_type:
                    logger.warning(f"Unsupported widget type: {obj.name}. Skipping.")
                    continue

                widget = widget_type(name=obj.name if hasattr(obj, "name") else f"widget_{id(obj)}")
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
                        color_tuple = convert_fill_property_to_qcolor(value, color_data=color_list_dict)
                        logger.info(f"Color conversion: {original_value} -> {color_tuple}")
                        if color_tuple:
                            value = color_tuple
                            logger.info(f"Setting fillColor/brushColor to: {value}")
                        else:
                            logger.warning(f"Could not convert color {value}, skipping")
                            continue
                    if edm_attr == "value":
                        value = str(value[0])

                    try:
                        setattr(widget, pydm_attr, value)
                        logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                    except Exception as e:
                        logger.error(f"Failed to set attribute {pydm_attr} on {widget.name}: {e}")

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

                if isinstance(widget, PyDMLabel):
                    widget.width += 8.0  # don't like this....

                if parent_pydm_group:
                    parent_pydm_group.add_child(widget)
                    logger.info(f"Added {widget.name} to parent {parent_pydm_group.name}")
                else:
                    pydm_widgets.append(widget)
                    logger.info(f"Added {widget.name} to root")
            else:
                logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

        return pydm_widgets

    pydm_widgets = traverse_group(parser.ui, color_list_dict, None, None, parser.ui.height)
    return pydm_widgets, used_classes


def parse_font_string(font_str: str) -> dict:
    """
    Parse an EDM font string like 'helvetica-bold-r-12.0'
    into a dictionary for a PyDM widget.
    This is just an example parser—adjust as needed.
    """
    parts = font_str.split("-")
    bold = "bold" in parts[1].lower()
    italic = "i" in parts[1].lower()
    size_str = parts[-1]
    pointsize = int(float(size_str))

    return {
        "pointsize": pointsize,
        "bold": bold,
        "italic": italic,
        "weight": 50,
    }


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
