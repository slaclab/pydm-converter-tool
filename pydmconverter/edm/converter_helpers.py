import re
from typing import Optional, List, Tuple
from pydmconverter.edm.parser import EDMObject, EDMGroup, EDMFileParser, block_items
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
    PyDMAnalogIndicator,
)
from pydmconverter.edm.parser_helpers import (
    convert_color_property_to_qcolor,
    search_color_list,
    parse_colors_list,
    parse_edm_macros,
)
from pydmconverter.edm.menumux import generate_menumux_file
from pydmconverter.exceptions import AttributeConversionError
import ast
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
    "activemeterclass": PyDMAnalogIndicator,
    "meter": PyDMAnalogIndicator,
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

# Choice-button property holding the pages of the menu embedded window it
# absorbed (set by pair_menu_pips, read by populate_tab_bar).
TAB_PAGES = "_tab_pages"

# Group property: its visibility rule starts true rather than false.
STARTS_VISIBLE = "_starts_visible"

LOC_NAME_PATTERN = re.compile(r"loc://([^?&\s\"',]+)")

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
    "barColor",
    "scaleColor",
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
        return transform_nested_widget(
            obj.x,
            obj.y,
            obj.width,
            obj.height,
            parent_pydm_group.x,
            parent_pydm_group.y,
            parent_pydm_group.height,
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

    if name == "activechoicebuttonclass" and TAB_PAGES not in obj.properties:
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
            elif isinstance(widget, PyDMEmbeddedDisplay) and is_menu_pip(obj) and value:
                # A menu window has one symbols entry per displayFileName entry: take the shown one's.
                index = shown_display_index(obj)
                value = parse_edm_macros(value[index]) if index < len(value) else {}
                logger.info(f"Converted shown display's macros to dict: {value}")
            elif isinstance(widget, PyDMRelatedDisplayButton) and obj.properties.get("displayFileName"):
                # EDM (related_display.cc) pairs symbols[i] with displayFileName[i] by array
                # index, and a file may skip indices: one macros entry per filename, in
                # filename order, "{}" for a display with no symbols entry.
                symbols = dict(block_items(value))
                parsed_macros = [
                    json.dumps(parse_edm_macros(symbols.get(index, "")))
                    for index, _ in block_items(obj.properties["displayFileName"])
                ]
                value = "\n".join(parsed_macros) if parsed_macros else None
                logger.info(f"Converted related display macros to: {value}")
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
                filename_to_set = display_filenames[shown_display_index(obj)]
            elif isinstance(display_filenames, dict) and len(display_filenames) > 0:
                filename_to_set = display_filenames[0]
            elif isinstance(display_filenames, str):
                filename_to_set = display_filenames

            if isinstance(filename_to_set, str):
                # PyDMEmbeddedDisplay maps the EDM name to its .ui name when serialized.
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

    # Text widget padding — Qt renders fonts slightly wider than EDM,
    # so add a small width buffer to prevent text clipping and button text wrapping.
    if isinstance(widget, (PyDMLabel, PyDMLineEdit, PyDMPushButton, PyDMRelatedDisplayButton, PyDMShellCommand)):
        text_pad = max(int(widget.width * 0.05), 4)
        widget.width = widget.width + text_pad
    if isinstance(widget, (PyDMLabel, PyDMLineEdit)):
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

    if obj.properties.get("showScale") and isinstance(widget, PyDMAnalogIndicator):
        widget.showTicks = True
        widget.showLimits = True
        widget.showUnits = True

    # EDM meter labels become the analog indicator title. pvName and pvLabel
    # types resolve from the PV at runtime, so use the PV name for those.
    if isinstance(widget, PyDMAnalogIndicator):
        label_type = obj.properties.get("labelType", "literal")
        if label_type == "literal":
            title = obj.properties.get("label")
        else:
            title = obj.properties.get("readPv")
        if title:
            widget.title = title


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
    parent_vispvs: Optional[List[Tuple[str, int, int, bool]]] = None,
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
            x, y, width, height = _compute_geometry(obj, parent_pydm_group, container_height, scale, offset_x, offset_y)

            logger.debug("Skipped pydm_group")

            vis_invert = bool(obj.properties.get("visInvert", False))
            if "visPv" in obj.properties and "visMin" in obj.properties and "visMax" in obj.properties:
                curr_vispv = [(obj.properties["visPv"], obj.properties["visMin"], obj.properties["visMax"], vis_invert)]
                if obj.properties.get(STARTS_VISIBLE):
                    curr_vispv = [curr_vispv[0] + (True,)]
            elif "visPv" in obj.properties:
                curr_vispv = [(obj.properties["visPv"], None, None, vis_invert)]
            else:
                curr_vispv = []

            if "symbolMin" in obj.properties and "symbolMax" in obj.properties and "symbolChannel" in obj.properties:
                symbol_vispv = [
                    (
                        obj.properties["symbolChannel"],
                        obj.properties["symbolMin"],
                        obj.properties["symbolMax"],
                        False,
                    )
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

            # ByteClass: EDM defaults to 16 bits and no labels
            if isinstance(widget, PyDMByteIndicator):
                if "numBits" not in obj.properties:
                    widget.numBits = 16
                    logger.info(f"Set numBits=16 for {obj.name} (EDM default)")
                widget.showLabels = False
                logger.info(f"Set showLabels=False for {obj.name} (EDM has no labels)")

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

            # Widgets built inside a container (tab pages) need their classes declared too.
            nested = list(getattr(widget, "children", []))
            while nested:
                child = nested.pop()
                used_classes.add(type(child).__name__)
                nested.extend(getattr(child, "children", []))

            pydm_widgets.append(widget)
            logger.info(f"Added {widget.name} to root")
        else:
            logger.warning(f"Unknown object type: {type(obj)}. Skipping.")

    return pydm_widgets, menu_mux_buttons


def convert_edm_to_pydm_widgets(parser: EDMFileParser, site=None, color_list_file: str | None = None):
    """
    Converts an EDMFileParser object into a collection of PyDM widget instances.

    Parameters
    ----------
    parser : EDMFileParser
        The EDMFileParser instance containing parsed EDM objects and groups.
    color_list_file : str, optional
        Explicit path to an EDM ``colors.list`` palette used to resolve "index N"
        colors. Falls back to ``EDMCOLORFILE``, ``$EDMFILES/colors.list``, then
        ``/etc/edm/colors.list`` when omitted.

    Returns
    -------
    Tuple[List, set]
        A tuple of (pydm_widgets, used_classes).
    """
    from pydmconverter.sites import get_skip_widgets

    skip_widgets = get_skip_widgets(site)

    used_classes = set()
    color_list_filepath = search_color_list(color_list_file)
    color_list_dict = parse_colors_list(color_list_filepath)

    # Pre-process: choice buttons driving menu embedded windows become tabs or switched displays
    pair_menu_pips(parser.ui, color_list_dict, skip_widgets=skip_widgets)

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
        generate_menumux_file(menu_mux_buttons, parser.output_file_path, loc_declarations(parser.ui))
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


def populate_tab_bar(obj: EDMObject, widget: QTabWidget) -> None:
    """Build the pages of a choice button that absorbed a menu embedded window (see pair_menu_pips)."""
    spec = obj.properties.get(TAB_PAGES)
    if spec is None:
        # A choice button without a channel to become a PyDMEnumButton.
        logger.warning(f"No tab names found in {obj.name}. Skipping.")
        return
    # The pages switch on their own, so the tab widget needs no channel.
    widget.channel = None
    widget.tab_bar_height = spec["tab_bar_height"]
    widget.tab_bar_left = spec["tab_bar_left"]
    widget.tab_width = spec["tab_width"]
    widget.border_color = spec["border_color"]
    widget.current_index = spec["current_index"]
    widget.select_color = spec["select_color"]
    for index, page in enumerate(spec["pages"]):
        child_widget = QWidget(title=page["title"])
        child_widget.add_child(
            PyDMEmbeddedDisplay(
                name=f"{widget.name}_page{index}",
                x=spec["page_x"],
                y=spec["page_y"],
                width=spec["page_width"],
                height=spec["page_height"],
                filename=page["filename"],
                macros=page["macros"],
                visible=True,
            )
        )
        widget.add_child(child_widget)


def _loc_names(obj: EDMObject) -> set:
    """Every loc:// variable name the object's properties reference."""
    names = set()
    for value in obj.properties.values():
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str):
                names.update(LOC_NAME_PATTERN.findall(item))
    return names


def _loc_enum_strings(url: str) -> List[str]:
    """States of an enum loc:// URL. parser_helpers.loc_conversion writes them
    last, as a Python list literal (the form PyDM's local plugin reads)."""
    _, found, literal = url.partition("&enum_string=")
    if not found:
        return []
    try:
        return [str(state) for state in ast.literal_eval(literal)]
    except (ValueError, SyntaxError):
        return []


def loc_declarations(root: EDMGroup) -> dict:
    """Map each loc:// variable the converted .ui configures, by its bare
    address (loc://name), to the address that configures it. Menu muxes are
    left out: they become the separate .py screen. When several widgets
    configure a variable differently the richest wins, as in pair_menu_pips:
    most enum strings, then the first in the file."""
    declarations = {}
    for obj, _, _ in _walk_objects(root):
        if isinstance(obj, EDMObject) and obj.name.lower() == "menumuxclass":
            continue
        for value in obj.properties.values():
            for item in _as_list(value):
                if isinstance(item, str) and item.startswith("loc://") and "?" in item:
                    declarations.setdefault(item.split("?", 1)[0], []).append(item)
    return {bare: max(urls, key=lambda url: len(_loc_enum_strings(url))) for bare, urls in declarations.items()}


def _loc_init(url: str) -> int:
    match = re.search(r"[?&]init=(-?\d+)", url)
    return int(match.group(1)) if match else 0


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def is_menu_pip(obj) -> bool:
    """An embedded window whose filePv picks among its displayFileName entries."""
    if not isinstance(obj, EDMObject):
        # Groups carry properties but no class name, so they are never a window.
        return False
    return obj.name.lower() == "activepipclass" and str(obj.properties.get("displaySource", "")).lower() == "menu"


def shown_display_index(obj: EDMObject) -> int:
    """The displayFileName/symbols entry an embedded window shows when it opens:
    a menu window starts at its filePv's initial value, any other at entry 0."""
    if not is_menu_pip(obj):
        return 0
    file_pv = obj.properties.get("filePv")
    index = _loc_init(file_pv) if isinstance(file_pv, str) and file_pv.startswith("loc://") else 0
    count = len(_as_list(obj.properties.get("displayFileName")))
    return index if 0 <= index < count else 0


def _walk_objects(group: EDMGroup, hidden: bool = False):
    """Yield (object, parent group, whether an enclosing group has a visibility PV).

    Groups are yielded alongside their leaves: a group's own visibility PV can
    reference a LOC variable, which makes the group a user of that variable.
    A group is yielded with the enclosing hidden flag, since its own visibility
    PV hides its children rather than itself.
    """
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            yield obj, group, hidden
            group_hidden = hidden or "visPv" in obj.properties or "symbolChannel" in obj.properties
            yield from _walk_objects(obj, group_hidden)
        else:
            yield obj, group, hidden


def _fits_tab_bar(pip: EDMObject, pip_parent: EDMGroup, hidden: bool, choice: EDMObject, choice_parent) -> bool:
    """A horizontal choice button sitting directly on top of the window, sharing
    its group and with no visibility of its own, reads as a tab bar."""
    if choice_parent is not pip_parent or hidden:
        return False
    if "visPv" in pip.properties or "visPv" in choice.properties:
        return False
    # EDM lays a choice button's states out to fill its rect, so a wide box reads
    # horizontally and a tall one vertically; the declared orientation property is
    # optional and unreliable. Same rule as ir_adapter._fixup_choice_button.
    if choice.width < choice.height:
        return False
    gap = pip.y - (choice.y + choice.height)
    inside = pip.x - 8 <= choice.x and choice.x + choice.width <= pip.x + pip.width + 8
    return -4 <= gap <= 12 and inside


def pair_menu_pips(root: EDMGroup, color_list_dict, skip_widgets: set = None) -> None:
    """
    Convert each menu embedded window that a choice button drives.

    In EDM the two are separate widgets sharing a LOC\\ variable: the choice
    button writes it (its states are the variable's enum strings) and the
    window shows displayFileName[value]. When the button sits on top of the
    window and nothing else uses the variable, the pair becomes one QTabWidget:
    the choice button carries the pages and the window is removed. Otherwise
    the button stays a PyDMEnumButton and the window becomes one embedded
    display per file, shown only at its index, so EDM's layout and every other
    user of the variable keep working.

    skip_widgets is the site's set of EDM classes to drop; pairing rewrites both
    widgets together, so a site dropping either one leaves the tree untouched.
    """
    if skip_widgets and {"activechoicebuttonclass", "activepipclass"} & skip_widgets:
        logger.info("Skipping menu embedded window pairing (site rule)")
        return

    # A $(!W) LOC variable is per-screen; the parser leaves a __UNIQUE__ marker
    # (EDMFileParser.modify_text) that apply_widget_post_processing only resolves
    # on an embedded display's own channel. The stacked path instead writes the
    # name into visPv/controlPv strings, so resolve the marker here, once per
    # screen, to the same name for every widget sharing the variable.
    token = str(id(root))[-6:]

    objects = list(_walk_objects(root))
    # objects holds a reference to every walked object, so keying by id is safe.
    loc_names = {id(obj): _loc_names(obj) for obj, _, _ in objects}
    for pip, parent, hidden in objects:
        if not is_menu_pip(pip):
            continue
        file_pv = pip.properties.get("filePv")
        match = LOC_NAME_PATTERN.search(file_pv) if isinstance(file_pv, str) else None
        files = _as_list(pip.properties.get("displayFileName"))
        if not match or not files:
            continue
        # The name as it appears in the tree, marker included: users and the
        # definition are matched on this form, then the marker is resolved.
        marked_name = match.group(1)
        users = [(obj, group) for obj, group, _ in objects if obj is not pip and marked_name in loc_names[id(obj)]]
        choices = [
            (obj, group)
            for obj, group in users
            if isinstance(obj, EDMObject) and obj.name.lower() == "activechoicebuttonclass"
        ]
        if not choices:
            continue

        # The richest reference defines the variable: most enum strings, then any config at all.
        references = [file_pv] + [
            value
            for obj, _ in users
            for value in obj.properties.values()
            if isinstance(value, str) and (value == f"loc://{marked_name}" or value.startswith(f"loc://{marked_name}?"))
        ]
        definition = max(references, key=lambda url: (len(_loc_enum_strings(url)), "?" in url))

        name = marked_name.replace("__UNIQUE__", token)
        if name != marked_name:
            definition = definition.replace("__UNIQUE__", token)

        if len(users) == 1 and len(files) > 1 and _fits_tab_bar(pip, parent, hidden, *choices[0]):
            # Tabs switch on their own and never emit the variable, so the
            # marked name never reaches the output.
            _absorb_pip_into_tabs(pip, parent, choices[0][0], files, definition, color_list_dict)
        else:
            _stack_pip_displays(pip, parent, name, files, definition, users, marked_name)


def _absorb_pip_into_tabs(pip, parent, choice, files, definition, color_list_dict) -> None:
    """Turn the choice button into a tab widget covering both rects, one page per file."""
    enum_strings = _loc_enum_strings(definition)
    labels = _as_list(pip.properties.get("menuLabel"))
    symbols = _as_list(pip.properties.get("symbols"))
    pages = []
    for index, file in enumerate(files):
        # Tab titles are what EDM's choice button shows: the variable's enum strings.
        title = enum_strings[index] if index < len(enum_strings) else ""
        if not title and index < len(labels) and labels[index] != "\x18":
            title = labels[index]
        if not title:
            title = os.path.splitext(os.path.basename(file))[0]
        symbol = symbols[index] if index < len(symbols) else ""
        pages.append({"title": title, "filename": file, "macros": parse_edm_macros(symbol) if symbol else {}})

    left = min(choice.x, pip.x)
    right = max(choice.x + choice.width, pip.x + pip.width)
    gap = max(pip.y - (choice.y + choice.height), 0)
    init = _loc_init(definition)
    colors = {
        key: convert_color_property_to_qcolor(choice.properties[key], color_data=color_list_dict)
        for key in ("selectColor", "botShadowColor")
        if choice.properties.get(key)
    }
    choice.properties[TAB_PAGES] = {
        "pages": pages,
        "tab_bar_height": choice.height,
        "tab_bar_left": choice.x - left,
        "tab_width": choice.width // len(pages),
        "page_x": pip.x - left,
        "page_y": gap,
        "page_width": pip.width,
        "page_height": pip.height,
        "current_index": init if 0 < init < len(files) else None,
        "select_color": colors.get("selectColor"),
        "border_color": colors.get("botShadowColor"),
    }
    choice.x = left
    choice.width = right - left
    choice.height = choice.height + gap + pip.height
    parent.objects.remove(pip)
    logger.info(f"Converted choice button and menu embedded window on {definition} to tabs")


def _stack_pip_displays(pip, parent, name, files, definition, users, marked_name=None) -> None:
    """Replace the window with one embedded display per file, each visible only
    while the variable equals its index (a group visPv in [i, i + 1)).

    name is the resolved variable name, marked_name the form still carrying the
    parser's __UNIQUE__ marker (the same when there is no marker); user
    properties are matched on the marked form and rewritten to the resolved one.
    """
    if marked_name is None:
        marked_name = name
    symbols = _as_list(pip.properties.get("symbols"))
    start = _loc_init(definition)
    if not 0 <= start < len(files):
        start = 0
    shared = {
        key: value
        for key, value in pip.properties.items()
        if key not in ("filePv", "displayFileName", "symbols", "menuLabel", "numDsps")
    }
    stack = []
    for index, file in enumerate(files):
        properties = dict(shared, displayFileName=[file], numDsps="1")
        if index < len(symbols) and symbols[index]:
            properties["symbols"] = [symbols[index]]
        display = EDMObject(name=pip.name, x=pip.x, y=pip.y, width=pip.width, height=pip.height, properties=properties)
        stack.append(
            EDMGroup(
                x=pip.x,
                y=pip.y,
                width=pip.width,
                height=pip.height,
                objects=[display],
                properties={
                    "visPv": f"loc://{name}",
                    "visMin": str(index),
                    "visMax": str(index + 1),
                    # The starting display's rule begins true so it shows as soon as
                    # the screen opens, rather than staying blank until the loc://
                    # channel delivers its first value.
                    STARTS_VISIBLE: index == start,
                },
            )
        )
    position = parent.objects.index(pip)
    parent.objects[position : position + 1] = stack

    # PyDM's local plugin takes a variable's type, initial value and enum
    # strings from the first channel that connects and ignores later ones. The
    # window carried the full definition; hand it to the choice buttons (which
    # need the enum strings for their states) and to every other configured use.
    for obj, _ in users:
        is_choice = isinstance(obj, EDMObject) and obj.name.lower() == "activechoicebuttonclass"
        for key, value in obj.properties.items():
            if not isinstance(value, str):
                continue
            if value.startswith(f"loc://{marked_name}?") or (is_choice and value == f"loc://{marked_name}"):
                obj.properties[key] = definition
            elif marked_name != name:
                # A plain reference carrying no configuration (a label's visPv,
                # say) keeps the marker otherwise, naming a different variable
                # than the displays it is meant to track.
                obj.properties[key] = value.replace(f"loc://{marked_name}", f"loc://{name}")
    logger.info(f"Stacked {len(files)} embedded displays switched by {definition}")


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
