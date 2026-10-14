"""EDM -> Qt class and prop name maps for the IR adapter.

The shared IR builder resolves widgets and props by Qt vocabulary (the keys
the registry's ``qtMapping``/``qtPropMap`` use). The EDM front-end therefore translates
EDM class names -> Qt class names and EDM attribute names -> Qt prop names here;
value coercion lives in ``ir_adapter.py``.

Reuses the EDM coverage knowledge from ``EDM_TO_PYDM_WIDGETS``/``EDM_TO_PYDM_ATTRIBUTES``
but re-points the targets from PyDM dataclass attributes to Qt prop names.

The PV roles per EDM class (``EDM_CHANNEL_ROLES``) live here too, and the .ui
target reads them as well.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# EDM class (lowercased) -> Qt class the registry knows; everything
# else falls through to an unknown-widget node.
EDM_TO_QT_CLASS: dict[str, str] = {
    "activextextclass": "PyDMLabel",  # split to QLabel (text-label) when static, see resolve_qt_class
    "textupdateclass": "PyDMLabel",
    "multilinetextupdateclass": "PyDMLabel",
    "activexregtextclass": "PyDMLabel",
    "regtextupdateclass": "PyDMLabel",
    # Text Control: an input only when "editable" is set; read-only ones resolve to
    # PyDMLabel (resolve_qt_class).
    "activextextdspclass": "PyDMLineEdit",
    "textentryclass": "PyDMLineEdit",
    "activebuttonclass": "PyDMPushButton",
    "activemessagebuttonclass": "PyDMPushButton",
    "activemenubuttonclass": "PyDMPushButton",
    "activemotifsliderclass": "PyDMSlider",
    "activesliderclass": "PyDMSlider",
    "activetriumfsliderclass": "PyDMSlider",
    # EDM choice button IS a radio set: every state visible, current one lit
    # (a dropdown hides the alternatives and, closed, showed only the ordinal).
    "activechoicebuttonclass": "PyDMEnumButton",
    "activepipclass": "PyDMEmbeddedDisplay",
    # byte indicator / related display
    "byteclass": "PyDMByteIndicator",
    "relateddisplayclass": "PyDMRelatedDisplayButton",
    "xygraphclass": "PyDMWaveformPlot",
    # graphics
    "activerectangleclass": "PyDMDrawingRectangle",
    "activecircleclass": "PyDMDrawingEllipse",
    "activelineclass": "PyDMDrawingPolyline",
    "activearcclass": "PyDMDrawingArc",
    "activebarclass": "PyDMScaleIndicator",
    "activeslacbarclass": "PyDMScaleIndicator",
    "activevsbarclass": "PyDMScaleIndicator",
    # text / buttons / indicators
    "activextextdspclassnoedit": "PyDMLabel",  # the parser strips the colon from activeXTextDspClass:noedit
    "shellcmdclass": "QPushButton",
    "activeexitbuttonclass": "QPushButton",
    "activepngclass": "PyDMDrawingImage",
    "activemeterclass": "PyDMAnalogIndicator",
    "activeindicatorclass": "PyDMScaleIndicator",
    "activeradiobuttonclass": "PyDMEnumButton",
    "activefreezebuttonclass": "QPushButton",  # corpus: 0/102 samples carry a controlPv (freeze/unfreeze is local-only)
    "activerampbuttonclass": "PyDMPushButton",
    "activeupdownbuttonclass": "PyDMPushButton",
    "mmvclass": "PyDMSlider",
    "multilinetextentryclass": "PyDMLineEdit",
    # menuMuxClass deliberately absent: macro-muxing needs a design; stays unknown-widget.
}


@dataclass(frozen=True)
class ChannelRoles:
    """What each PV tag of an EDM class does, from EDM's C++ source.

    EDM has no single "channel": each class gives each PV tag a fixed role, and
    one tag means different things on different classes. An indicatorPv is the
    value a bar shows but a button's readback; a nullPv is a colour condition on
    a text control but an offset on a bar. Both targets read this table
    (converter_helpers.apply_channel_roles, ir_adapter._apply_channel_attrs), so
    neither keeps whichever tag the file happens to list last.

    data: the PV the widget shows and writes, the first one present.
    readback: the PV the widget shows its state from while writing the data PV
        (the button family's indicatorPv). With no data PV it is the only PV the
        widget shows, so it takes the data PV's place.
    color: the PVs whose value picks a colors.list rule colour, the first one
        present. They are never shown.
    alarm: the PV whose alarm severity colours the widget. It is never shown.
    null: the PV a text control compares under its nullCondition to draw its
        text in nullColor. It is never shown.
    """

    data: tuple[str, ...] = ("controlPv",)
    readback: str | None = None
    color: tuple[str, ...] = ()
    alarm: str | None = None
    null: str | None = None

    def data_attr(self, properties: dict[str, Any]) -> str | None:
        """The tag of the object's data PV, or ``None`` for none."""
        for attr in (*self.data, self.readback):
            if attr and properties.get(attr):
                return attr
        return None

    def readback_attr(self, properties: dict[str, Any]) -> str | None:
        """The tag of the object's readback, when it has a data PV besides."""
        if self.readback and properties.get(self.readback) and self.data_attr(properties) != self.readback:
            return self.readback
        return None

    def color_attr(self, properties: dict[str, Any]) -> str | None:
        """The tag of the PV that picks the object's rule colours, or ``None``."""
        return next((attr for attr in self.color if properties.get(attr)), None)


# Static text and drawings show no PV; their alarmPv's value also picks their
# rule colours (x_text_obj.cc, rectangle_obj.cc and the other drawings).
_STATIC_ROLES = ChannelRoles(data=(), color=("alarmPv",), alarm="alarmPv")
# The button family writes its controlPv. Button labels and a menu's or choice
# button's selection follow the indicatorPv when there is one (button.cc,
# menu_button.cc, choice_button.cc).
_BUTTON_ROLES = ChannelRoles(readback="indicatorPv", color=("colorPv",))
# Bars and indicators have no controlPv; a bar's nullPv is an offset subtracted
# from the value (bar.cc), not a colour condition.
_BAR_ROLES = ChannelRoles(data=("indicatorPv",))
# xTextDsp: colorPv picks the fg and bg rule colours, with no fallback to the
# controlPv; nullPv switches the fg to nullColor (x_text_dsp_obj.cc).
_TEXT_CONTROL_ROLES = ChannelRoles(color=("colorPv",), null="nullPv")
# Textupdate's fg rule colour follows its colorPv, else its controlPv (textupdate.cc).
_TEXTUPDATE_ROLES = ChannelRoles(color=("colorPv", "controlPv"))

# EDM class (lowercased) -> its PV roles. A class not listed reads its controlPv
# and nothing else.
EDM_CHANNEL_ROLES: dict[str, ChannelRoles] = {
    "activextextdspclass": _TEXT_CONTROL_ROLES,
    "activextextdspclassnoedit": _TEXT_CONTROL_ROLES,
    "textupdateclass": _TEXTUPDATE_ROLES,
    "regtextupdateclass": _TEXTUPDATE_ROLES,
    "textentryclass": ChannelRoles(color=("colorPv",)),
    # The multi-line classes spell it colourPv.
    "multilinetextupdateclass": ChannelRoles(color=("colourPv",)),
    "multilinetextentryclass": ChannelRoles(color=("colourPv",)),
    "activextextclass": _STATIC_ROLES,
    "activexregtextclass": _STATIC_ROLES,
    "activerectangleclass": _STATIC_ROLES,
    "activecircleclass": _STATIC_ROLES,
    "activearcclass": _STATIC_ROLES,
    "activelineclass": _STATIC_ROLES,
    "activebuttonclass": _BUTTON_ROLES,
    "activemenubuttonclass": _BUTTON_ROLES,
    "activechoicebuttonclass": _BUTTON_ROLES,
    # The slider draws a second pointer and a readback value from its indicatorPv.
    "activesliderclass": ChannelRoles(readback="indicatorPv"),
    # A message button only writes its controlPv (message_button.cc never monitors it).
    "activemessagebuttonclass": ChannelRoles(color=("colorPv",)),
    "activeupdownbuttonclass": ChannelRoles(color=("colorPv",)),
    "activerampbuttonclass": ChannelRoles(color=("colorPv",)),
    "activebarclass": _BAR_ROLES,
    "activeslacbarclass": _BAR_ROLES,
    "activevsbarclass": _BAR_ROLES,
    "activeindicatorclass": _BAR_ROLES,
    "activemeterclass": ChannelRoles(data=("readPv",)),
    # ctrl2Pv drives a second slider (converter_helpers.create_multi_sliders).
    "mmvclass": ChannelRoles(data=("ctrl1Pv",)),
    "activecoeftableclass": ChannelRoles(data=("pv",)),
    # The filePv names the file shown, or picks a menu entry (pip.cc).
    "activepipclass": ChannelRoles(data=("filePv",)),
    # Its pv[] are written with literal value[] when a display opens.
    "relateddisplayclass": ChannelRoles(data=(), color=("colorPv",)),
    # Its pv's string value names the file the table reads (table.cc).
    "activetableclass": ChannelRoles(data=("pv",)),
}
_DEFAULT_ROLES = ChannelRoles()

# Tags that are a data PV on some class. An object carrying one its class does
# not read (a related display's pv[]) drops it.
EDM_DATA_PV_ATTRS = ("controlPv", "readPv", "indicatorPv", "pv", "filePv", "ctrl1Pv")

# xyGraph PVs besides its traces' xPv/yPv, which neither target carries, and
# what each does (xygraph.cc). nPv is one per trace.
XY_GRAPH_UNMAPPED_PVS = {
    "nPv": "how many points each trace plots",
    "traceCtlPv": "a bitmask that hides traces",
    "resetPv": "clears the plot",
    "triggerPv": "when trigger-mode traces update",
}


def channel_roles(name_lower: str) -> ChannelRoles:
    """The PV roles of an EDM class (lowercased name)."""
    return EDM_CHANNEL_ROLES.get(name_lower, _DEFAULT_ROLES)


# EDM attribute name -> Qt prop name (the key the registry's qtPropMap consumes).
# Channel attrs are absent on purpose: the adapter routes them itself.
EDM_TO_QT_PROP: dict[str, str] = {
    # text / labels (the registry maps "text" -> text/label per widget)
    "value": "text",
    "label": "text",
    "buttonLabel": "text",
    # display formatting
    "precision": "precision",
    "showUnits": "showUnits",
    "displayFormat": "displayFormat",
    "format": "displayFormat",  # activeXTextDspClass(:noedit) EDM format string
    # alarm sensitivity
    "fgAlarm": "alarmSensitiveContent",
    "alarmSensitiveContent": "alarmSensitiveContent",
    "alarmSensitiveBorder": "alarmSensitiveBorder",
    # button values / state labels / behavior
    "pressValue": "pressValue",
    "releaseValue": "releaseValue",
    "onLabel": "onLabel",
    "offLabel": "offLabel",
    "buttonType": "buttonType",
    # state colors (buttons and byte indicators share the attr names)
    "onColor": "onColor",
    "offColor": "offColor",
    # typography: EDM font strings ("helvetica-bold-r-12.0") -> pixel size.
    # Without this every label rendered at the theme default and overflowed
    # its EDM-sized box (ellipsis, or silently clipped digits).
    "font": "fontSize",
    # slider
    "scaleMin": "userMinimum",
    "scaleMax": "userMaximum",
    "orientation": "orientation",
    "showValue": "showValueLabel",
    # embedded display
    "file": "filename",
    "fileName": "filename",
    "symbols": "macros",
    "macro": "macros",
    # related display: a list of target files -> "filenames" (firstOf -> file)
    "displayFileName": "filenames",
    # byte indicator
    "numBits": "numBits",
    "shift": "shift",
    # alignment
    "fontAlign": "alignment",
    # colors (resolved to hex by the adapter)
    "fgColor": "foregroundColor",
    "bgColor": "backgroundColor",
    # British-spelled EDM keys emitted by some classes (multiLineTextEntryClass, mmvClass et al.)
    "fgColour": "foregroundColor",
    "bgColour": "backgroundColor",
    # drawing
    "lineColor": "penColor",
    "fillColor": "brushColor",
    "lineWidth": "penWidth",
    "lineStyle": "penStyle",
    "fill": "brushFill",
    "startAngle": "startAngle",
    "totalAngle": "spanAngle",
    # bar/scale range
    "min": "userMinimum",
    "max": "userMaximum",
}


def has_pv(properties: dict[str, Any]) -> bool:
    """True if the EDM object carries a DATA channel attribute.

    alarmPv does not count: it only feeds alarm-color rules, so e.g. a static
    label with an alarmPv stays a static label (previously it converted to a
    live pv-label bound to the alarm PV and displayed that PV's value).
    """
    return any(attr in properties for attr in EDM_DATA_PV_ATTRS)


def resolve_qt_class(name_lower: str, properties: dict[str, Any]) -> str | None:
    """Resolve an EDM class to a Qt class, or ``None`` (-> unknown-widget).

    A static ``activeXTextClass`` (no data PV: its alarmPv is never shown, see
    ``EDM_CHANNEL_ROLES``) is a label with fixed text, so it maps to ``QLabel``
    (-> ``text-label``, which has a ``text`` prop).

    ``activeXTextDspClass`` is read-only unless its ``editable`` flag is set (EDM
    ``x_text_dsp_obj.cc`` loads it with a default of 0 and refuses input when it is
    clear), so only an editable one maps to ``PyDMLineEdit`` (-> ``pv-text-input``);
    otherwise it is a value display, ``PyDMLabel`` (-> ``pv-label``), like
    ``activeXTextDspClass:noedit`` and ``TextupdateClass``.

    A closed or filled ``activeLineClass`` is a polygon, not a polyline — the
    polyline widget has no fill, so EDM's filled shapes (triangles, flow arrows)
    rendered as empty outlines.
    """
    if name_lower == "activextextclass" and channel_roles(name_lower).data_attr(properties) is None:
        return "QLabel"
    if name_lower == "activextextdspclass" and not properties.get("editable"):
        return "PyDMLabel"
    if name_lower == "activelineclass" and (properties.get("fill") or properties.get("closePolygon")):
        return "PyDMDrawingIrregularPolygon"
    return EDM_TO_QT_CLASS.get(name_lower)
