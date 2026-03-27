import re
from typing import Optional, List, Tuple
from pydmconverter.edm.parser import EDMObject, EDMGroup, EDMFileParser
from pydmconverter.widgets import (
    PyDMDrawingRectangle,
    PyDMDrawingEllipse,
    PyDMDrawingLine,
    PyDMDrawingPolyline,
    PyDMDrawingIrregularPolygon,
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
    PyDMDrawingPie,
    PyDMWaveformPlot,
    PyDMScaleIndicator,
    PyDMSlider,
    PyDMWaveformTable,
)
from pydmconverter.edm.parser_helpers import convert_color_property_to_qcolor, search_color_list, parse_colors_list
from pydmconverter.edm.menumux import generate_menumux_file
from pydmconverter.exceptions import AttributeConversionError
import logging
import math
import os
import copy
import json

EDM_TO_PYDM_WIDGETS = {  # missing PyDMFrame,  QComboBox
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
    "commandLabel": "titles",
    "menuLabel": "titles",
    # Related display attributes
    "fileName": "filename",
    "macro": "macros",
    "symbols": "macros",  # EDM related display buttons use "symbols" for macros
    "file": "filename",
    "useDisplayBg": "useDisplayBg",
    "invisible": "flat",
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


def _has_fill_properties(obj: EDMObject) -> tuple:
    """Return (has_fill, has_fill_color) for an EDM object."""
    has_fill = obj.properties.get("fill") is True or "fill" in obj.properties
    has_fill_color = "fillColor" in obj.properties
    return has_fill, has_fill_color


def _compute_geometry(obj, parent_pydm_group, container_height, scale, offset_x, offset_y):
    """Dispatch to the appropriate geometry transform based on whether we have a parent group."""
    if parent_pydm_group is None:
        return transform_edm_to_pydm(
            obj.x, obj.y, obj.width, obj.height,
            container_height=container_height, scale=scale,
            offset_x=offset_x, offset_y=offset_y,
        )
    else:
        return transform_nested_widget(
            obj.x, obj.y, obj.width, obj.height,
            parent_pydm_group.x, parent_pydm_group.y, parent_pydm_group.height,
            scale=scale,
        )


def get_polyline_widget_type(obj: EDMObject) -> type:
    """
    Determine if an activelineclass should be PyDMDrawingPolyline or PyDMDrawingIrregularPolygon.

    Returns PyDMDrawingIrregularPolygon if the polyline is:
    - Closed (first point == last point OR closePolygon is set) AND
    - Has fill color

    Otherwise returns PyDMDrawingPolyline.

    Parameters
    ----------
    obj : EDMObject
        The EDM object to analyze

    Returns
    -------
    type
        Either PyDMDrawingIrregularPolygon or PyDMDrawingPolyline
    """
    has_fill, has_fill_color = _has_fill_properties(obj)
    is_closed = obj.properties.get("closePolygon") is True

    if not is_closed and "xPoints" in obj.properties and "yPoints" in obj.properties:
        x_pts = obj.properties["xPoints"]
        y_pts = obj.properties["yPoints"]
        if len(x_pts) > 1 and len(y_pts) > 1:
            is_closed = x_pts[0] == x_pts[-1] and y_pts[0] == y_pts[-1]

    if (has_fill or has_fill_color) and is_closed:
        logger.info("Converting closed filled polyline to PyDMDrawingIrregularPolygon")
        return PyDMDrawingIrregularPolygon
    else:
        return PyDMDrawingPolyline


def get_arc_widget_type(obj: EDMObject) -> type:
    """
    Determine if an activearcclass should be PyDMDrawingPie or PyDMDrawingArc.

    Returns PyDMDrawingPie if the arc has fill enabled.
    Otherwise returns PyDMDrawingArc.

    Parameters
    ----------
    obj : EDMObject
        The EDM object to analyze

    Returns
    -------
    type
        Either PyDMDrawingPie or PyDMDrawingArc
    """
    has_fill, has_fill_color = _has_fill_properties(obj)

    if has_fill or has_fill_color:
        logger.info("Converting filled arc to PyDMDrawingPie")
        return PyDMDrawingPie
    else:
        return PyDMDrawingArc


def widgets_overlap(widget1, widget2) -> bool:
    """
    Check if two widgets overlap based on their geometry (x, y, width, height).

    Parameters
    ----------
    widget1, widget2 : PyDM widget instances
        Widgets with x, y, width, height attributes

    Returns
    -------
    bool
        True if widgets overlap, False otherwise
    """
    x1, y1 = widget1.x, widget1.y
    w1, h1 = widget1.width, widget1.height

    x2, y2 = widget2.x, widget2.y
    w2, h2 = widget2.width, widget2.height

    if x1 + w1 <= x2 or x2 + w2 <= x1:
        return False
    if y1 + h1 <= y2 or y2 + h2 <= y1:
        return False

    return True


def handle_button_polygon_overlaps(pydm_widgets):
    """
    Detect when PyDMRelatedDisplayButton overlaps with PyDMDrawingIrregularPolygon.
    Set the button's flat property to True to make it transparent, and ensure
    the button is placed after the polygon in the widget list (on top in z-order).

    Parameters
    ----------
    pydm_widgets : List
        List of PyDM widget instances

    Returns
    -------
    List
        Updated list of PyDM widgets with proper ordering and flat property set
    """
    from pydmconverter.widgets import PyDMRelatedDisplayButton, PyDMDrawingIrregularPolygon

    buttons = [(i, w) for i, w in enumerate(pydm_widgets) if isinstance(w, PyDMRelatedDisplayButton)]
    polygons = [(i, w) for i, w in enumerate(pydm_widgets) if isinstance(w, PyDMDrawingIrregularPolygon)]

    buttons_to_move = []

    for btn_idx, button in buttons:
        for poly_idx, polygon in polygons:
            if widgets_overlap(button, polygon):
                logger.info(f"Detected overlap: {button.name} overlaps with {polygon.name}")
                button.flat = True

                if btn_idx < poly_idx:
                    buttons_to_move.append((btn_idx, button))
                    logger.info(f"Button {button.name} will be moved after polygon {polygon.name}")
                break

    if buttons_to_move:
        buttons_to_move.sort(key=lambda x: x[0], reverse=True)

        for btn_idx, button in buttons_to_move:
            pydm_widgets.pop(btn_idx)

        for _, button in reversed(buttons_to_move):
            pydm_widgets.append(button)

    return pydm_widgets


def resolve_widget_type(obj: EDMObject):
    """
    Determine the PyDM widget type for a given EDM object.

    Returns the widget type class, or None if unsupported.
    May mutate obj.properties for special cases (e.g. activechoicebuttonclass without tabs).
    """
    name = obj.name.lower()

    if name == "activelineclass":
        return get_polyline_widget_type(obj)
    if name == "activearcclass":
        return get_arc_widget_type(obj)

    widget_type = EDM_TO_PYDM_WIDGETS.get(name)
    if not widget_type:
        return None

    if name == "activechoicebuttonclass" and ("tabs" not in obj.properties or not obj.properties["tabs"]):
        channel = search_for_edm_attr(obj, "channel")
        if not channel:
            logger.warning(f"Could not find channel in object: {obj.name}")
        else:
            widget_type = PyDMEnumButton
            obj.properties["tab_names"] = None
            obj.properties["hide_on_disconnect_channel"] = channel

    return widget_type


def convert_attribute_value(edm_attr, value, widget, obj, color_list_dict):
    """
    Convert a single EDM attribute value to its PyDM equivalent.

    Returns the converted value, or None to signal the attribute should be skipped.
    """
    if obj.name.lower() == "activelineclass" and edm_attr in ["xPoints", "yPoints", "numPoints"]:
        return None

    if edm_attr == "font":
        value = parse_font_string(value)
    elif edm_attr in ("macro", "symbols"):
        if isinstance(value, list):
            if isinstance(widget, PyDMEmbeddedDisplay) and len(value) == 1:
                macro_dict = parse_edm_macros(value[0])
                value = macro_dict
                logger.info(f"Converted single macro to dict: {value}")
            else:
                parsed_macros = []
                for macro_str in value:
                    macro_dict = parse_edm_macros(macro_str)
                    parsed_macros.append(json.dumps(macro_dict))
                value = "\n".join(parsed_macros) if parsed_macros else None
                logger.info(f"Converted macro list to: {value}")
        elif isinstance(value, str):
            macro_dict = parse_edm_macros(value)
            if isinstance(widget, PyDMEmbeddedDisplay):
                value = macro_dict
            else:
                value = json.dumps(macro_dict) if macro_dict else None
            logger.info(f"Converted macro string to: {value}")
    elif edm_attr == "fillColor":
        original_value = value
        color_tuple = convert_color_property_to_qcolor(value, color_data=color_list_dict)
        logger.info(f"Color conversion: {original_value} -> {color_tuple}")
        if color_tuple:
            value = color_tuple
            logger.info(f"Setting fillColor/brushColor to: {value}")
        else:
            logger.warning(f"Could not convert color {value}, skipping")
            return None
    elif edm_attr == "value":
        value = get_string_value(value)
    elif edm_attr in COLOR_ATTRIBUTES:
        value = convert_color_property_to_qcolor(value, color_data=color_list_dict)
    elif edm_attr == "plotColor":
        color_list = []
        for color in value:
            color_list.append(convert_color_property_to_qcolor(color, color_data=color_list_dict))
        value = color_list
    elif edm_attr in ("menuLabel", "commandLabel"):
        # EDM uses \x18 (CAN character) as a placeholder meaning "use the filename".
        # Strip these so PyDM falls back to its default title behavior.
        if isinstance(value, list):
            value = [v for v in value if v != "\x18"]
            if not value:
                return None
        elif value == "\x18":
            return None

    return value


def apply_widget_post_processing(
    widget, obj, pydm_widgets, scale, offset_x, offset_y, container_height, parent_pydm_group
):
    """
    Apply widget-specific post-processing after attribute mapping.

    Handles geometry transformation, polyline points, button variants,
    embedded display filenames, dimension padding, and minimum sizes.
    """
    # Tab bar population
    if obj.name.lower() == "activechoicebuttonclass" and isinstance(widget, QTabWidget):
        populate_tab_bar(obj, widget)

    # Polyline/polygon point calculation and geometry
    if obj.name.lower() == "activelineclass" and isinstance(widget, (PyDMDrawingPolyline, PyDMDrawingIrregularPolygon)):
        if "xPoints" in obj.properties and "yPoints" in obj.properties:
            x_points = obj.properties["xPoints"]
            y_points = obj.properties["yPoints"]
            abs_pts = [(int(float(x) * scale), int(float(y) * scale)) for x, y in zip(x_points, y_points)]
            pen = int(obj.properties.get("lineWidth", 1))

            arrow_size = 0
            if "arrows" in obj.properties and obj.properties["arrows"] in ("to", "from", "both"):
                arrow_size = int(15 * scale)

            startCoord = (obj.x, obj.y)
            geom, point_strings = geom_and_local_points(abs_pts, startCoord, pen, arrow_size)

            if not geom:
                logger.warning(f"Skipping {type(widget).__name__} with no valid points for {obj.name}")
                return

            widget.points = point_strings
            widget.penWidth = pen
            if widget.penColor is None:
                widget.penColor = (0, 0, 0, 255)

            if isinstance(widget, PyDMDrawingIrregularPolygon):
                if widget.brushColor is not None:
                    widget.brushFill = True
                    logger.info(f"IrregularPolygon has explicit brushColor: {widget.brushColor}")
                else:
                    widget.brushColor = (255, 255, 255, 255)
                    widget.brushFill = True
                    logger.info("Setting default white fill color for IrregularPolygon (no fillColor specified)")

                widget.alarm_sensitive_content = True
                logger.info("Enabled alarm_sensitive_content for IrregularPolygon to ensure fill is visible")

            widget.x = int(geom["x"] + offset_x)
            widget.y = int(geom["y"] + offset_y)
            widget.width = int(geom["width"])
            widget.height = int(geom["height"])
    elif not (
        obj.name.lower() == "activelineclass" and isinstance(widget, (PyDMDrawingPolyline, PyDMDrawingIrregularPolygon))
    ):
        x, y, width, height = _compute_geometry(obj, parent_pydm_group, container_height, scale, offset_x, offset_y)
        widget.x = int(x)
        widget.y = int(y)
        widget.width = max(1, int(width))
        widget.height = max(1, int(height))

    # PushButton off/on handling
    if isinstance(widget, PyDMPushButton) and ("offLabel" in obj.properties and "onLabel" not in obj.properties):
        widget.text = obj.properties["offLabel"]
    elif isinstance(widget, PyDMPushButton) and (
        (
            ("offLabel" in obj.properties and obj.properties["offLabel"] != obj.properties["onLabel"])
            or ("offColor" in obj.properties and obj.properties["offColor"] != obj.properties["onColor"])
        )
        and hasattr(widget, "channel")
        and widget.channel is not None
    ):
        off_button = create_off_button(widget)
        pydm_widgets.append(off_button)

    # Embedded display filename handling
    if isinstance(widget, PyDMEmbeddedDisplay) and obj.name.lower() == "activepipclass":
        if "displayFileName" in obj.properties and obj.properties["displayFileName"]:
            display_filenames = obj.properties["displayFileName"]
            filename_to_set = None
            if isinstance(display_filenames, (list, tuple)) and len(display_filenames) > 0:
                filename_to_set = display_filenames[0]
            elif isinstance(display_filenames, dict) and len(display_filenames) > 0:
                filename_to_set = display_filenames[0]
            elif isinstance(display_filenames, str):
                filename_to_set = display_filenames

            if isinstance(filename_to_set, str):
                if filename_to_set.endswith(".edl"):
                    filename_to_set = filename_to_set[:-4] + ".ui"
                widget.filename = filename_to_set
                logger.info(f"Set PyDMEmbeddedDisplay filename to: {widget.filename}")

        # Make LOC variables unique if they had $(!W) marker
        if hasattr(widget, "channel") and widget.channel and "__UNIQUE__" in widget.channel:
            widget_id = str(id(widget))[-6:]
            widget.channel = widget.channel.replace("__UNIQUE__", widget_id)
            logger.info(f"Made LOC variable unique: {widget.channel}")

    # Freeze button handling
    if obj.name.lower() == "activefreezebuttonclass":
        freeze_button = create_freeze_button(widget)
        pydm_widgets.append(freeze_button)

    # Multi-slider handling
    if obj.name.lower() == "mmvclass":
        generated_sliders = create_multi_sliders(widget, obj)
        pydm_widgets.extend(generated_sliders)

    # Drawing shape dimension padding
    if isinstance(widget, (PyDMDrawingLine, PyDMDrawingPolyline, PyDMDrawingIrregularPolygon)):
        pad = widget.penWidth or 1

        if isinstance(widget, PyDMDrawingIrregularPolygon):
            alarm_border_pad = 4 if hasattr(widget, "alarm_sensitive_border") and widget.alarm_sensitive_border else 0
            pad = pad + alarm_border_pad

        min_dim = max(pad * 2, 3)

        if widget.width < min_dim:
            widget.width = min_dim
        else:
            widget.width = int(widget.width) + pad

        if widget.height < min_dim:
            widget.height = min_dim
        else:
            widget.height = int(widget.height) + pad

    # Label minimum sizing
    if isinstance(widget, PyDMLabel):
        widget.width = max(widget.width, 20)
        widget.height = max(widget.height, 14)

    # Drawing shape alarm sensitivity
    if isinstance(widget, (PyDMDrawingArc, PyDMDrawingPie, PyDMDrawingRectangle, PyDMDrawingEllipse)):
        if hasattr(widget, "brushColor") and widget.brushColor is not None:
            widget.alarm_sensitive_content = True
            logger.info(f"Enabled alarm_sensitive_content for {type(widget).__name__} to ensure fill is visible")

    # Auto-size
    if obj.properties.get("autoSize", False) and hasattr(widget, "autoSize"):
        widget.autoSize = True


def traverse_group(
    edm_group: EDMGroup,
    color_list_dict,
    used_classes: set,
    skip_widgets: set = None,
    parent_pydm_group: Optional[PyDMFrame] = None,
    pydm_widgets=None,
    container_height: float = None,
    scale: float = 1.0,
    offset_x: float = 0,
    offset_y: float = 0,
    central_widget: EDMGroup = None,
    parent_vispvs: Optional[List[Tuple[str, int, int]]] = None,
):
    """
    Recursively traverse an EDM group and convert each object to a PyDM widget.

    Parameters
    ----------
    edm_group : EDMGroup
        The EDM group to traverse.
    color_list_dict : dict
        Parsed color list data for color conversion.
    used_classes : set
        Accumulator for tracking which PyDM widget classes are used.
    skip_widgets : set, optional
        Set of widget class names (lowercase) to skip during conversion.
    """
    menu_mux_buttons = []
    if pydm_widgets is None:
        pydm_widgets = []
    if skip_widgets is None:
        skip_widgets = set()

    for obj in edm_group.objects:
        if isinstance(obj, EDMGroup):
            x, y, width, height = _compute_geometry(
                obj, parent_pydm_group, container_height, scale, offset_x, offset_y
            )

            logger.debug("Skipped pydm_group")

            if "visPv" in obj.properties and "visMin" in obj.properties and "visMax" in obj.properties:
                curr_vispv = [(obj.properties["visPv"], obj.properties["visMin"], obj.properties["visMax"])]
            elif "visPv" in obj.properties:
                curr_vispv = [(obj.properties["visPv"], None, None)]
            else:
                curr_vispv = []

            if "symbolMin" in obj.properties and "symbolMax" in obj.properties and "symbolChannel" in obj.properties:
                symbol_vispv = [
                    (obj.properties["symbolChannel"], obj.properties["symbolMin"], obj.properties["symbolMax"])
                ]
            else:
                symbol_vispv = []

            traverse_group(
                obj,
                color_list_dict,
                used_classes,
                skip_widgets=skip_widgets,
                pydm_widgets=pydm_widgets,
                container_height=height,
                scale=scale,
                offset_x=0,
                offset_y=0,
                central_widget=central_widget,
                parent_vispvs=(parent_vispvs or []) + curr_vispv + symbol_vispv,
            )

        elif isinstance(obj, EDMObject):
            # Skip widgets based on site rules
            if obj.name.lower() in skip_widgets:
                logger.info(f"Skipping {obj.name} (site rule)")
                continue

            # 1. Resolve widget type
            widget_type = resolve_widget_type(obj)

            if obj.name.lower() == "menumuxclass":
                menu_mux_buttons.append(obj)
            if not widget_type:
                logger.warning(f"Unsupported widget type: {obj.name}. Skipping.")
                log_unsupported_widget(obj.name)
                continue

            # 2. Create widget instance
            widget = widget_type(name=obj.name + str(id(obj)) if hasattr(obj, "name") else f"widget_{id(obj)}")
            used_classes.add(type(widget).__name__)
            logger.info(f"Creating widget: {widget_type.__name__} ({widget.name})")

            if parent_vispvs:
                widget.visPvList = list(parent_vispvs)

            # TextupdateClass widgets always show units in EDM
            if obj.name.lower() in ("textupdateclass", "multilinetextupdateclass", "regtextupdateclass"):
                if "showUnits" not in obj.properties:
                    widget.show_units = True
                    logger.info(f"Set show_units=True for {obj.name} (implicit EDM behavior)")

            # 3. Map and convert attributes
            for edm_attr, value in obj.properties.items():
                pydm_attr = EDM_TO_PYDM_ATTRIBUTES.get(edm_attr)
                if not pydm_attr:
                    continue

                value = convert_attribute_value(edm_attr, value, widget, obj, color_list_dict)
                if value is None:
                    continue

                try:
                    setattr(widget, pydm_attr, value)
                    logger.info(f"Set {pydm_attr} to {value} for {widget.name}")
                except Exception as e:
                    raise AttributeConversionError(edm_attr, value, widget.name, cause=e) from e

            # 4. Post-processing (geometry, button variants, dimension padding, etc.)
            apply_widget_post_processing(
                widget,
                obj,
                pydm_widgets,
                scale,
                offset_x,
                offset_y,
                container_height,
                parent_pydm_group,
            )

            pydm_widgets.append(widget)
            logger.info(f"Added {widget.name} to root")
        else:
            logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

    return pydm_widgets, menu_mux_buttons


def convert_edm_to_pydm_widgets(parser: EDMFileParser, site=None):
    """
    Converts an EDMFileParser object into a collection of PyDM widget instances.

    Parameters
    ----------
    parser : EDMFileParser
        The EDMFileParser instance containing parsed EDM objects and groups.

    Returns
    -------
    Tuple[List, set]
        A tuple of (pydm_widgets, used_classes).
    """
    from pydmconverter.sites import get_skip_widgets

    skip_widgets = get_skip_widgets(site)

    used_classes = set()
    color_list_filepath = search_color_list()
    color_list_dict = parse_colors_list(color_list_filepath)

    # Pre-process: populate embedded tab bars
    pip_objects = find_objects(parser.ui, "activepipclass")
    for pip_object in pip_objects:
        create_embedded_tabs(pip_object, parser.ui)

    # Pre-process: remove overlapping text labels on related display buttons
    text_objects = find_objects(parser.ui, "activextextclass")
    for text_object in text_objects:
        if should_delete_overlapping(parser.ui, text_object, "relateddisplayclass"):
            delete_object_in_group(parser.ui, text_object)

    # Traverse and convert
    pydm_widgets, menu_mux_buttons = traverse_group(
        parser.ui,
        color_list_dict,
        used_classes,
        skip_widgets=skip_widgets,
        container_height=parser.ui.height,
        central_widget=parser.ui,
    )

    pydm_widgets = handle_button_polygon_overlaps(pydm_widgets)

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


def create_button_variant(
    widget: PyDMPushButton, suffix: str, variant_type: str, attr_mappings: list, original_mappings: list = None
):
    """
    Clone a PyDMPushButton into a variant (e.g. "off" or "freeze") with remapped attributes.

    Parameters
    ----------
    widget : PyDMPushButton
        The original button to clone.
    suffix : str
        Name suffix for the variant (e.g. "_off", "_freeze").
    variant_type : str
        Type label for the variant flag (e.g. "off", "freeze").
    attr_mappings : list of (src, dst) tuples
        Copies widget.src → variant.dst for each pair.
    original_mappings : list of (src, dst) tuples, optional
        Copies widget.src → widget.dst on the original widget for each pair.
    """
    variant = copy.deepcopy(widget)
    variant.name = widget.name + suffix
    for src, dst in attr_mappings:
        if hasattr(widget, src):
            setattr(variant, dst, getattr(widget, src))
    setattr(variant, f"is_{variant_type}_button", True)
    setattr(widget, f"is_{variant_type}_button", False)
    if original_mappings:
        for src, dst in original_mappings:
            if hasattr(widget, src):
                setattr(widget, dst, getattr(widget, src))
    logger.info(f"Created {variant_type}-button: {variant.name} based on {widget.name}")
    return variant


def create_off_button(widget: PyDMPushButton):
    """Create an 'off' variant of a push button with distinct off/on states."""
    return create_button_variant(
        widget,
        "_off",
        "off",
        attr_mappings=[("off_color", "on_color"), ("off_label", "on_label"), ("off_label", "text")],
        original_mappings=[("on_label", "text")],
    )


def create_freeze_button(widget: PyDMPushButton):
    """Create a 'freeze' variant of an activefreezebuttonclass button."""
    return create_button_variant(
        widget,
        "_freeze",
        "freeze",
        attr_mappings=[("frozenLabel", "text"), ("frozen_background_color", "background_color")],
    )


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
        widget.height = widget.height // len(ctrl_attributes)
        widget.channel = ctrl_attributes[0][0]
        widget.indicatorColor = ctrl_attributes[0][1]
        for j in range(1, len(ctrl_attributes)):
            curr_slider = copy.deepcopy(widget)
            curr_slider.name = widget.name + f"_{j}"
            curr_slider.y = curr_slider.y + curr_slider.height * j
            curr_slider.channel = ctrl_attributes[j][0]
            curr_slider.indicatorColor = ctrl_attributes[j][1]
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
            widget_name = re.sub(r"[^a-zA-Z0-9_]", "_", tab_name)
            child_widget = QWidget(title=tab_name)
            widget.add_child(child_widget)
            embedded_widget = PyDMEmbeddedDisplay(
                name=f"{widget_name}_embedded",
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


def count_loc_variable_instances(group: EDMGroup, channel_name: str) -> int:
    """
    Count how many times a location variable channel appears in the widget tree.

    Parameters
    ----------
    group : EDMGroup
        The group to search within
    channel_name : str
        The channel name to search for (e.g., "loc://myVar")

    Returns
    -------
    int
        Number of instances found
    """
    count = 0

    def search_recursive(g: EDMGroup):
        nonlocal count
        for obj in g.objects:
            if isinstance(obj, EDMGroup):
                search_recursive(obj)
            elif hasattr(obj, "properties"):
                # Check all properties for the channel
                for key, value in obj.properties.items():
                    if isinstance(value, str) and channel_name in value:
                        count += 1
                        break  # Count this object once

    search_recursive(group)
    return count


def create_hidden_frame_for_loc_variable(loc_variable: str, central_widget: EDMGroup) -> None:
    """
    Create a hidden PyDMFrame with the location variable to satisfy
    the minimum 2-instance requirement for embedded tabs.

    The frame is invisible and positioned at (0,0) with 0 size so it
    doesn't interfere with clicks or disrupt the UI.

    Parameters
    ----------
    loc_variable : str
        The location variable (e.g., "loc://myVar?init=['tab1', 'tab2']")
    central_widget : EDMGroup
        The central widget group to add the hidden frame to
    """
    channel_name = loc_variable.split("?")[0]

    hidden_frame = EDMObject(
        name="Group",
        properties={
            "visPv": channel_name,
            "visInvert": True,
            "visMin": 0,
            "visMax": 1,
        },
        x=0,
        y=0,
        width=0,
        height=0,
    )

    central_widget.add_object(hidden_frame)
    logger.info(f"Created hidden PyDMFrame for location variable: {channel_name}")


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
    loc_variable = None
    channel_name = None

    logger.debug(f"Object properties: {dict(obj.properties.items())}")
    for prop_name, prop_val in obj.properties.items():
        if isinstance(prop_val, str) and (
            "loc://" in prop_val or "LOC\\" in prop_val
        ):  # TODO: is it possible to have multiple loc\\ in the same embedded display?
            searched_arr = prop_val.split("=")
            loc_variable = prop_val  # Save full location variable string
            channel_name = prop_val.split("?")[0]

    if int(obj.properties["numDsps"]) <= 1 or searched_arr is None:
        return False

    if loc_variable and channel_name:
        instance_count = count_loc_variable_instances(central_widget, channel_name)

        if instance_count < 2:
            logger.info(f"Location variable {channel_name} only appears {instance_count} time(s)")
            logger.info("Creating hidden PyDMFrame to satisfy minimum instance requirement")
            create_hidden_frame_for_loc_variable(loc_variable, central_widget)

    string_list = searched_arr[-1]

    if string_list.startswith("[") and string_list.endswith("]"):
        channel_list = string_list[1:-1].split(", ")
        tab_names = [item.strip("'") for item in channel_list]
    else:
        tab_names = [string_list.strip("'")]

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


def _split_macro_pairs(macro_string: str) -> list[str]:
    """Split macro string on commas, respecting ${...} nesting."""
    pairs = []
    current = []
    depth = 0
    for char in macro_string:
        if char == "{" and depth >= 0:
            depth += 1
            current.append(char)
        elif char == "}" and depth > 0:
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            pairs.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        pairs.append("".join(current))
    return pairs


def parse_edm_macros(macro_string: str) -> dict:
    """
    Parse an EDM macro string into a dictionary for PyDM widgets.

    EDM macros are in the format: "KEY1=value1,KEY2=value2,KEY3=value3"
    This function converts them to a Python dict: {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}

    Parameters
    ----------
    macro_string : str
        The EDM macro string to parse (e.g., "P=CAMR:LI20:110,R=:ASYN")

    Returns
    -------
    dict
        A dictionary containing the parsed macro key-value pairs.
        Returns an empty dict if the input is empty or None.

    Examples
    --------
    >>> parse_edm_macros("P=CAMR:LI20:110,R=:ASYN")
    {'P': 'CAMR:LI20:110', 'R': ':ASYN'}
    >>> parse_edm_macros("DEVICE=IOC:SYS0:1")
    {'DEVICE': 'IOC:SYS0:1'}
    >>> parse_edm_macros("")
    {}
    """
    if not macro_string or not isinstance(macro_string, str):
        return {}

    macro_dict = {}
    macro_string = macro_string.strip()

    if not macro_string:
        return {}

    pairs = _split_macro_pairs(macro_string)

    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            key, value = pair.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            macro_dict[key] = value
        else:
            logger.warning(f"Invalid macro pair format: '{pair}' in macro string: '{macro_string}'")

    return macro_dict


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


def geom_and_local_points(abs_points, startCoord, pen_width: int = 1, arrow_size: int = 0):
    if not abs_points:
        logger.warning("abs_points is empty for PyDMDrawingPolyLine")  # TODO: Fix this
        return {}, []
    xs, ys = zip(*abs_points)
    min_x, max_x = min(list(xs)), max(xs)  # TODO: Comeback and resolve which to use
    min_y, max_y = min(list(ys)), max(ys)

    width = max_x - min_x + pen_width
    height = max_y - min_y + pen_width

    if arrow_size > 0:
        width += arrow_size * 2
        height += arrow_size * 2

    geom = {
        "x": min_x - (arrow_size if arrow_size > 0 else 0),
        "y": min_y - (arrow_size if arrow_size > 0 else 0),
        "width": width,
        "height": height,
    }

    offset_x = arrow_size if arrow_size > 0 else 0
    offset_y = arrow_size if arrow_size > 0 else 0
    rel = [(x - min_x + offset_x, y - min_y + offset_y) for x, y in abs_points]
    return geom, [f"{x}, {y}" for x, y in rel]
