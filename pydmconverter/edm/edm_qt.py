"""EDM -> Qt class and prop name maps for the IR adapter.

The shared IR builder resolves widgets and props by Qt vocabulary (the keys
Beaver's ``qtMapping``/``qtPropMap`` use). The EDM front-end therefore translates
EDM class names -> Qt class names and EDM attribute names -> Qt prop names here;
value coercion lives in ``ir_adapter.py``.

Reuses the EDM coverage knowledge from ``EDM_TO_PYDM_WIDGETS``/``EDM_TO_PYDM_ATTRIBUTES``
but re-points the targets from PyDM dataclass attributes to Qt prop names.
"""

from __future__ import annotations

from typing import Any

# EDM class (lowercased) -> Qt class the registry knows; everything
# else falls through to an unknown-widget node.
EDM_TO_QT_CLASS: dict[str, str] = {
    "activextextclass": "PyDMLabel",  # split to QLabel (text-label) when static, see resolve_qt_class
    "textupdateclass": "PyDMLabel",
    "multilinetextupdateclass": "PyDMLabel",
    "activexregtextclass": "PyDMLabel",
    "regtextupdateclass": "PyDMLabel",
    "activextextdspclass": "PyDMLineEdit",
    "textentryclass": "PyDMLineEdit",
    "activebuttonclass": "PyDMPushButton",
    "activemessagebuttonclass": "PyDMPushButton",
    "activemenubuttonclass": "PyDMPushButton",
    "activemotifsliderclass": "PyDMSlider",
    "activesliderclass": "PyDMSlider",
    "activetriumfsliderclass": "PyDMSlider",
    "activechoicebuttonclass": "PyDMEnumComboBox",
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

# EDM attributes that name a data-PV channel, in PRIMARY-channel priority order.
# When an object carries several (EDM buttons pair controlPv with indicatorPv),
# controlPv wins: it is the write/primary channel; readPv/indicatorPv are
# readbacks; the rest only ever appear alone. The adapter picks primary +
# readback explicitly (ir_adapter._apply_channel_attrs) — funneling them all to
# the single "channel" prop kept only the last attr parsed and re-pointed
# widgets at the wrong PV.
EDM_PRIMARY_CHANNEL_ORDER = ("controlPv", "readPv", "indicatorPv", "pv", "filePv", "nullPv", "ctrl1Pv")
# Readback preference when a second data channel is present.
EDM_READBACK_CHANNEL_ORDER = ("indicatorPv", "readPv")
# alarmPv is deliberately NOT a data channel: it names the alarm-severity source
# for alarm-color rules (ir_adapter._alarm_rules) and must never steal the
# widget's channel (nor make a static label "live" — see has_pv).
EDM_CHANNEL_ATTRS = EDM_PRIMARY_CHANNEL_ORDER + ("alarmPv",)

# EDM attribute name -> Qt prop name (the key Beaver's qtPropMap consumes).
# Channel attrs are absent on purpose: the adapter routes them itself.
EDM_TO_QT_PROP: dict[str, str] = {
    # text / labels (Beaver maps "text" -> text/label per widget)
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
    return any(attr in properties for attr in EDM_PRIMARY_CHANNEL_ORDER)


def resolve_qt_class(name_lower: str, properties: dict[str, Any]) -> str | None:
    """Resolve an EDM class to a Qt class, or ``None`` (-> unknown-widget).

    A static ``activeXTextClass`` (no PV) is a label with fixed text, so it maps to
    ``QLabel`` (-> ``text-label``, which has a ``text`` prop). With a PV it is a live
    value display, so it maps to ``PyDMLabel`` (-> ``pv-label``).

    A closed or filled ``activeLineClass`` is a polygon, not a polyline — the
    polyline widget has no fill, so EDM's filled shapes (triangles, flow arrows)
    rendered as empty outlines.
    """
    if name_lower == "activextextclass" and not has_pv(properties):
        return "QLabel"
    if name_lower == "activelineclass" and (properties.get("fill") or properties.get("closePolygon")):
        return "PyDMDrawingIrregularPolygon"
    return EDM_TO_QT_CLASS.get(name_lower)
