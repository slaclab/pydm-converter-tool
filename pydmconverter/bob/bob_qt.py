"""Phoebus Display Builder (``.bob``) -> Qt class and prop tables for the IR adapter.

The shared IR builder resolves widgets and props by Qt vocabulary (the keys
the widget registry's ``qtMapping``/``qtPropMap`` use). The ``.bob`` front-end therefore
translates Phoebus widget types -> Qt classes and Phoebus property names -> Qt
prop names here, mirroring ``pydmconverter/edm/edm_qt.py``. Everything in this
module is data; value coercion and lowering live in ``ir_adapter.py`` and the
rule/local-PV modules.

Tables:

* :data:`BOB_TO_QT_CLASS` -- Phoebus type -> (Qt class, registry id).
* :data:`BOB_TO_QT_PROP` / :data:`BOB_TO_QT_PROP_BY_TYPE` -- Phoebus prop -> Qt prop.
* :data:`BOB_DEFAULTS` / :data:`DISPLAY_BACKGROUND_DEFAULT` -- values Phoebus does
  not serialise because they equal the widget constructor defaults.
* :data:`DEFAULT_SIZES` -- width/height when ``<width>``/``<height>`` are absent.
* :data:`GROUP_INSET` -- child-origin inset per group style.
* :data:`BOOL_BUTTON_MODE` -- ``bool_button`` ``<mode>`` -> ``pv-button`` props.
* :data:`RULE_DIRECT_TARGETS` / :data:`RULE_TARGET_COERCION` -- rule targets.
"""

from __future__ import annotations

from typing import Any, Callable

# --------------------------------------------------------------------------
# Class table: Phoebus widget type -> (Qt class, registry id).
#
# ``tabs`` is deliberately absent: the registry has no qtPropMap for tabs
# (``tabs[]``), so a Phoebus tabs widget stays an unknown-widget node with the
# warning in :data:`TABS_WARNING`. ``group`` maps to ``group-box`` here; styles
# 2/3 (no border / no title) switch to the plain ``group`` id via
# :data:`GROUP_STYLE_TO_ID`.
# --------------------------------------------------------------------------
BOB_TO_QT_CLASS: dict[str, tuple[str | None, str]] = {
    # milestone types
    "action_button": ("QPushButton", "regular-button"),  # the only registry entry carrying `actions`
    "bool_button": ("PyDMPushButton", "pv-button"),
    "label": ("QLabel", "text-label"),
    "textupdate": ("PyDMLabel", "pv-label"),
    "textentry": ("PyDMLineEdit", "pv-text-input"),
    "led": ("PyDMSymbol", "pv-led"),
    "embedded": ("PyDMEmbeddedDisplay", "embedded-display"),
    "rectangle": ("PyDMDrawingRectangle", "rectangle"),
    "ellipse": ("PyDMDrawingEllipse", "ellipse"),
    "polygon": ("PyDMDrawingIrregularPolygon", "polygon"),
    "polyline": ("PyDMDrawingPolyline", "line"),
    "xyplot": ("PyDMScatterPlot", "xy-plot"),
    "group": ("QGroupBox", "group-box"),
    # secondary types with registry matches
    "combo": ("PyDMEnumComboBox", "pv-enum-combobox"),
    "choice": ("PyDMEnumButton", "pv-radio-group"),
    "radio": ("PyDMEnumButton", "pv-radio-group"),
    "checkbox": ("PyDMCheckbox", "pv-checkbox"),
    "spinner": ("PyDMSpinbox", "pv-spinbox"),
    "byte_monitor": ("PyDMByteIndicator", "pv-byte-led"),
    "picture": ("PyDMDrawingImage", "image-view"),
    "progressbar": ("PyDMScaleIndicator", "pv-progress-bar"),
    "meter": ("PyDMAnalogIndicator", "pv-meter"),
    "scaledslider": ("PyDMSlider", "pv-slider"),
}

# The Phoebus types the milestone set exercises (pinned; see PROPOSAL.md).
MILESTONE_TYPES: frozenset[str] = frozenset(
    {
        "action_button",
        "bool_button",
        "label",
        "textupdate",
        "textentry",
        "led",
        "embedded",
        "rectangle",
        "ellipse",
        "polygon",
        "polyline",
        "xyplot",
        "group",
    }
)

# Phoebus group ``<style>``: 0 GROUP_BOX, 1 TITLE, 2 LINE, 3 NONE.
GROUP_STYLE_TO_ID: dict[int, tuple[str | None, str]] = {
    0: ("QGroupBox", "group-box"),
    1: ("QGroupBox", "group-box"),
    2: (None, "group"),
    3: (None, "group"),
}

TABS_WARNING = "{widget}: Phoebus tabs need a registry qtPropMap for tabs[]"

# --------------------------------------------------------------------------
# Prop table: Phoebus prop -> Qt prop (as used by the registry qtPropMaps).
#
# Generic entries apply to every type; BOB_TO_QT_PROP_BY_TYPE overrides them
# per type, where ``None`` means "deliberately not mapped". Props needing
# structural lowering (``transparent`` -> ``brushFill = not transparent``,
# ``actions``, ``traces``/``y_axes``, ``rules``, ``scripts``) are handled in
# the adapter, not here.
# --------------------------------------------------------------------------
BOB_TO_QT_PROP: dict[str, str] = {
    "pv_name": "channel",
    "text": "text",
    "foreground_color": "foregroundColor",
    "background_color": "backgroundColor",
    "line_color": "penColor",
    "line_width": "penWidth",
    "font": "fontSize",  # font size only
    "horizontal_alignment": "alignment",
    "format": "displayFormat",
    "precision": "precision",
    "show_units": "showUnits",
    "points": "points",
    "file": "filename",
    "macros": "macros",
    "on_label": "onLabel",
    "off_label": "offLabel",
    "on_color": "onColor",
    "off_color": "offColor",
    "title": "title",
    "minimum": "userMinimum",
    "maximum": "userMaximum",
    "horizontal": "orientation",
    "label": "text",  # checkbox label
}

BOB_TO_QT_PROP_BY_TYPE: dict[str, dict[str, str | None]] = {
    # action_button pv_name is tooltip/alarm-border metadata in Phoebus; the
    # local-PV declarer (adapter) is the only consumer.
    "action_button": {"pv_name": None},
    # bool_button: the runtime derives on/off from the readback alone, so the
    # adapter also copies `channel` to `readbackChannel`.
    "bool_button": {},
    # shapes: background is the brush, not a widget background
    "rectangle": {"background_color": "brushColor"},
    "ellipse": {"background_color": "brushColor"},
    "polygon": {"background_color": "brushColor"},
    "polyline": {},
    # led: Phoebus draws a border in line_color; the registry has no slot for it
    "led": {"line_color": None},
    "byte_monitor": {"line_color": None, "numBits": "numBits", "startBit": "shift"},
    "picture": {"file": "filename"},
}

# Qt prop that stands for the widget's primary PV readback when one exists.
READBACK_COPY: dict[str, tuple[str, str]] = {
    "bool_button": ("channel", "readbackChannel"),
}

# --------------------------------------------------------------------------
# Per-type defaults for props Phoebus does not serialise (widget constructor
# defaults). Keys are Phoebus prop names; the adapter applies them whenever the
# element is absent, before the prop table.
#
# A colour default Phoebus takes from a named widget colour is written as that
# name ("Text", "Read_Background"), so it follows a configured ``color.def`` (as in
# Phoebus) and can become a scheme role; with neither it is the built-in RGB.
# Colours with no Phoebus name (shape fills and lines, LED and bool_button on/off)
# stay literal hex.
# --------------------------------------------------------------------------
BOB_DEFAULTS: dict[str, dict[str, Any]] = {
    "rectangle": {
        "transparent": False,
        "line_width": 3,
        "line_color": "#0000ff",
        "background_color": "#1e90ff",
    },
    "ellipse": {
        "transparent": False,
        "line_width": 3,
        "line_color": "#0000ff",
        "background_color": "#1e90ff",
    },
    "polygon": {
        "transparent": False,
        "line_width": 3,
        "line_color": "#0000ff",
        "background_color": "#3232ff",
    },
    "polyline": {"line_width": 3},
    "label": {"transparent": True, "foreground_color": "Text"},
    "textupdate": {
        "transparent": False,
        "foreground_color": "Text",
        "background_color": "Read_Background",
    },
    "bool_button": {
        "on_label": "On",
        "off_label": "Off",
        "on_color": "#3cff3c",
        "off_color": "#3c643c",
    },
    "led": {"on_color": "#00ff00", "off_color": "#3c643c"},
}

# The display ``<background_color>`` default, passed to build_screen(background=).
DISPLAY_BACKGROUND_DEFAULT = "#ffffff"

# --------------------------------------------------------------------------
# Default sizes (width, height) when ``<width>``/``<height>`` are absent.
# polyline/polygon derive their box from the points' bounding box in the
# adapter; the table entry is the fallback for an empty point list.
# --------------------------------------------------------------------------
FALLBACK_SIZE: tuple[int, int] = (100, 20)
DISPLAY_DEFAULT_SIZE: tuple[int, int] = (800, 600)

DEFAULT_SIZES: dict[str, tuple[int, int]] = {
    "label": (100, 20),
    "textupdate": (100, 20),
    "textentry": (100, 20),
    "rectangle": (100, 20),
    "ellipse": (100, 50),
    "action_button": (100, 30),
    "bool_button": (100, 30),
    "led": (20, 20),
    "group": (300, 200),
    "embedded": (400, 300),
    "xyplot": (400, 300),
    "tabs": (400, 300),
}


def default_size(widget_type: str | None) -> tuple[int, int]:
    """Default (width, height) for a Phoebus type; ``None`` is the display root."""
    if widget_type is None or widget_type == "display":
        return DISPLAY_DEFAULT_SIZE
    return DEFAULT_SIZES.get(widget_type, FALLBACK_SIZE)


# --------------------------------------------------------------------------
# Group inset, ported from Phoebus GroupRepresentation.updateChanges: child
# origins are offset by (dx, dy) depending on the group style, with
# ``i = 2 + int(1.2 * font_size)`` (font size from the group's <font>, else 14,
# so 18 px by default).
# --------------------------------------------------------------------------
GROUP_DEFAULT_FONT_SIZE = 14

GROUP_INSET: dict[int, Callable[[int], tuple[int, int]]] = {
    0: lambda i: (i, i),  # GROUP_BOX
    1: lambda i: (1, i + 1),  # TITLE
    2: lambda i: (1, 1),  # LINE
    3: lambda i: (0, 0),  # NONE
}


def inset(style: int, font_size: float | None = GROUP_DEFAULT_FONT_SIZE) -> tuple[int, int]:
    """Child-origin inset (dx, dy) for a group of ``style``; unknown styles use 0."""
    size = GROUP_DEFAULT_FONT_SIZE if font_size is None else font_size
    i = 2 + int(1.2 * size)
    return GROUP_INSET.get(style, GROUP_INSET[0])(i)


# --------------------------------------------------------------------------
# bool_button <mode> -> pv-button props (absent == 0).
# --------------------------------------------------------------------------
BOOL_BUTTON_MODE: dict[int, dict[str, Any]] = {
    0: {"buttonType": "toggle"},
    1: {"buttonType": "push", "pressValue": 1, "releaseValue": 0},
    2: {"buttonType": "push", "pressValue": 0, "releaseValue": 1},
}

# --------------------------------------------------------------------------
# Rule targets. Direct targets land on the IR rule target as-is; every other
# Phoebus prop goes through the prop table and must then appear in the node's
# registry qtPropMap, else the adapter warns "unsupported rule target".
# RULE_TARGET_COERCION picks the value coercion for a rule's arm values.
# --------------------------------------------------------------------------
RULE_DIRECT_TARGETS: dict[str, str] = {
    "visible": "visible",
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
}

RULE_TARGET_COERCION: dict[str, str] = {
    "visible": "bool",
    "transparent": "bool",
    "enabled": "bool",
    "x": "number",
    "y": "number",
    "width": "number",
    "height": "number",
    "line_width": "number",
    "precision": "number",
    "minimum": "number",
    "maximum": "number",
    "foreground_color": "color",
    "background_color": "color",
    "line_color": "color",
    "on_color": "color",
    "off_color": "color",
    "text": "str",
    "on_label": "str",
    "off_label": "str",
    "file": "str",
    "title": "str",
}

RULE_TARGET_UNSUPPORTED_WARNING = "{widget}: unsupported rule target {target}"
TRANSPARENT_BG_RULE_TYPES: frozenset[str] = frozenset({"label", "textupdate"})
TRANSPARENT_BG_RULE_WARNING = "{widget}: background_color rule ignored on a transparent widget (Phoebus semantics)"


def rule_coercion(target: str) -> str:
    """Coercion kind (``bool``/``number``/``color``/``str``) for a rule target."""
    return RULE_TARGET_COERCION.get(target, "str")


def qt_class_for(widget_type: str) -> tuple[str | None, str] | None:
    """(Qt class, registry id) for a Phoebus type, or ``None`` when unmapped."""
    return BOB_TO_QT_CLASS.get(widget_type)


def qt_prop_for(widget_type: str, prop: str) -> str | None:
    """Qt prop name for a Phoebus prop on ``widget_type``; ``None`` when unmapped."""
    overrides = BOB_TO_QT_PROP_BY_TYPE.get(widget_type, {})
    if prop in overrides:
        return overrides[prop]
    return BOB_TO_QT_PROP.get(prop)
