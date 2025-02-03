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
        pydm_widgets = None):
        """
        Recursively traverse an EDMGroup and convert EDMObjects to PyDM widgets.

        Parameters
        ----------
        edm_group : EDMGroup
            The current EDMGroup to traverse.
        parent_pydm_group : Optional[PyDMFrame]
            The parent PyDMFrame to which widgets should be added. None if root.
        pydm_widgets : Optional[List[PyDMWidget]]
            A list to collect the converted PyDM widgets.

        Returns
        -------
        List[PyDMWidget]
            A list of all PyDM widgets converted from EDM objects.
        """
        if pydm_widgets is None:
            pydm_widgets = []

        for obj in edm_group.objects:
            if isinstance(obj, EDMGroup):
                # Create a PyDM container widget (Frame)
                pydm_group = PyDMFrame(
                    name=obj.name if hasattr(obj, "name") else f"group_{id(obj)}",
                    x=obj.x,
                    y=obj.y,
                    width=obj.width,
                    height=obj.height
                )
                logger.info(f"Created PyDMFrame: {pydm_group.name}")

                if parent_pydm_group:
                    parent_pydm_group.add_child(pydm_group)
                else:
                    pydm_widgets.append(pydm_group)
                
                used_classes.add(type(pydm_group).__name__)

                # Recursively traverse the subgroup
                traverse_group(obj, color_list_dict, pydm_group, pydm_widgets)

            elif isinstance(obj, EDMObject):
                widget_type = EDM_TO_PYDM_WIDGETS.get(obj.name.lower())
                if not widget_type:
                    logger.warning(f"Unsupported widget type: {obj.name}. Skipping.")
                    continue

                # Instantiate the widget
                widget = widget_type(name=obj.name if hasattr(obj, "name") else f"widget_{id(obj)}")
                used_classes.add(type(widget).__name__)
                logger.info(f"Creating widget: {widget_type.__name__} ({widget.name})")

                # Map and set attributes
                for edm_attr, value in obj.properties.items():
                    pydm_attr = EDM_TO_PYDM_ATTRIBUTES.get(edm_attr)
                    if not pydm_attr:
                        logger.debug(f"Attribute '{edm_attr}' not mapped. Skipping.")
                        continue

                    if edm_attr == "font":
                        value = parse_font_string(value)
                    
                    if edm_attr == 'fillColor':
                        value = convert_fill_property_to_qcolor(value, color_data=color_list_dict)

                    if edm_attr == "value":
                        value = str(value[0]) 
                        print(widget, pydm_attr, value)

                    try:
                        setattr(widget, pydm_attr, value)
                        logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                    except Exception as e:
                        logger.error(f"Failed to set attribute {pydm_attr} on {widget.name}: {e}")

                # Set widget geometry
                widget.x = obj.x
                widget.y = obj.y
                widget.width = obj.width
                widget.height = obj.height

                # Add to parent group or root
                if parent_pydm_group:
                    parent_pydm_group.add_child(widget)
                else:
                    pydm_widgets.append(widget)
            else:
                logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

        return pydm_widgets

    pydm_widgets = traverse_group(parser.ui, color_list_dict, None, pydm_widgets)
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