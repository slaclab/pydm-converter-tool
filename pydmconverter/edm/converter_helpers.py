from typing import Union, List, Optional
from parser import EDMObject, EDMGroup, EDMFileParser
from pydmconverter.widgets import (PyDMDrawingRectangle, PyDMDrawingEllipse, PyDMDrawingLine, 
PyDMLabel, PyDMLineEdit, PyDMPushButton, PyDMRelatedDisplayButton, PyDMShellCommand, PyDMFrame)
from pydmconverter.widgets_helpers import Brush
from parser_helpers import convert_fill_property_to_qcolor, search_color_list, parse_colors_list
import logging



EDM_TO_PYDM_WIDGETS = {
    # Graphics widgets
    "activerectangleclass": PyDMDrawingRectangle,
    "circle": PyDMDrawingEllipse,  
    "activelineclass": PyDMDrawingLine,
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
    "shell_command": PyDMShellCommand
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
    "fill" : "brushFill",
    'fillColor' : "brushColor",

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

def transform_edm_to_pydm(edm_x, edm_y, edm_width, edm_height,
                          container_height, scale=1.0, offset_x=0, offset_y=0):
    """
    Transform coordinates from an EDM coordinate system (bottom-left origin)
    to a PyDM coordinate system (top-left origin) at the root level.
    """
    pydm_x = offset_x + edm_x * scale
    pydm_width = edm_width * scale
    pydm_height = edm_height * scale
    pydm_y = offset_y + (container_height - ((edm_y + edm_height) * scale))
    return int(pydm_x), int(pydm_y), int(pydm_width), int(pydm_height)


def transform_nested_widget(parent_x, parent_y, parent_height,
                            child_edm_x, child_edm_y, child_edm_width, child_edm_height,
                            scale=1.0):
    """
    Transform child widget coordinates relative to its parent.
    
    Assumes:
      - The child's EDM coordinates are relative to the parent's EDM coordinate system,
      - The parent's PyDM geometry has been computed so that its (x, y) is the top-left
        corner and its height is the scaled height.
    
    Returns:
      Tuple of integers (child_x, child_y, child_width, child_height) in PyDM coordinates.
    """
    # Convert the x coordinate directly.
    child_x = parent_x + child_edm_x * scale
    # For y, the child's top edge is computed by taking the parent's top (parent_y)
    # and adding the parent's height, then subtracting the child's offset plus its height.
    child_y = parent_y + (parent_height - (child_edm_y + child_edm_height) * scale)
    child_width = child_edm_width * scale
    child_height = child_edm_height * scale
    return int(child_x), int(child_y), int(child_width), int(child_height)


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
        offset_y: float = 0
    ):
        if pydm_widgets is None:
            pydm_widgets = []

        for obj in edm_group.objects:
            if isinstance(obj, EDMGroup):
                # Determine geometry for the group.
                if parent_pydm_group is None:
                    # At the root, use the provided container_height.
                    x, y, width, height = transform_edm_to_pydm(
                        obj.x, obj.y, obj.width, obj.height,
                        container_height=container_height,
                        scale=scale,
                        offset_x=offset_x,
                        offset_y=offset_y
                    )
                else:
                    # For a nested group, use the parent's PyDM geometry.
                    x, y, width, height = transform_nested_widget(
                        parent_pydm_group.x, parent_pydm_group.y, parent_pydm_group.height,
                        obj.x, obj.y, obj.width, obj.height,
                        scale=scale
                    )
                pydm_group = PyDMFrame(
                    name=obj.name if hasattr(obj, "name") else f"group_{id(obj)}",
                    x=x,
                    y=y,
                    width=width,
                    height=height
                )
                logger.info(f"Created PyDMFrame: {pydm_group.name}")

                if parent_pydm_group:
                    parent_pydm_group.add_child(pydm_group)
                else:
                    pydm_widgets.append(pydm_group)

                used_classes.add(type(pydm_group).__name__)

                # For nested children, use this group's (transformed) height as the container height.
                traverse_group(obj, color_list_dict, pydm_group, pydm_widgets,
                            container_height=height, scale=scale, offset_x=0, offset_y=0)

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
                    if not pydm_attr:
                        continue

                    if edm_attr == "font":
                        value = parse_font_string(value)
                    if edm_attr == "fillColor":
                        value = convert_fill_property_to_qcolor(value, color_data=color_list_dict)
                    if edm_attr == "value":
                        value = str(value[0])

                    try:
                        setattr(widget, pydm_attr, value)
                        logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                    except Exception as e:
                        logger.error(f"Failed to set attribute {pydm_attr} on {widget.name}: {e}")

                # Transform widget geometry.
                if parent_pydm_group is None:
                    x, y, width, height = transform_edm_to_pydm(
                        obj.x, obj.y, obj.width, obj.height,
                        container_height=container_height,
                        scale=scale,
                        offset_x=offset_x,
                        offset_y=offset_y
                    )
                else:
                    x, y, width, height = transform_nested_widget(
                        parent_pydm_group.x, parent_pydm_group.y, parent_pydm_group.height,
                        obj.x, obj.y, obj.width, obj.height,
                        scale=scale
                    )

                widget.x = x
                widget.y = y
                widget.width = width
                widget.height = height

                if parent_pydm_group:
                    parent_pydm_group.add_child(widget)
                else:
                    pydm_widgets.append(widget)
            else:
                logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

        return pydm_widgets

    pydm_widgets = traverse_group(parser.ui, color_list_dict, None, pydm_widgets, parser.ui.height)
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