"""EDM -> Qt class and prop name maps for the IR adapter (P0 widgets).

The shared IR builder resolves widgets and props by Qt vocabulary (the keys
Beaver's ``qtMapping``/``qtPropMap`` use). The EDM front-end therefore translates
EDM class names -> Qt class names and EDM attribute names -> Qt prop names here;
value coercion lives in ``ir_adapter.py``.

Reuses the EDM coverage knowledge from ``EDM_TO_PYDM_WIDGETS``/``EDM_TO_PYDM_ATTRIBUTES``
but re-points the targets from PyDM dataclass attributes to Qt prop names.
"""

from __future__ import annotations

from typing import Any

# EDM class (lowercased) -> Qt class the registry knows. P0 subset; everything
# else falls through to an unknown-widget node (D11).
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
    # P1
    "byteclass": "PyDMByteIndicator",
    "relateddisplayclass": "PyDMRelatedDisplayButton",
}

# EDM attributes that name a PV channel.
EDM_CHANNEL_ATTRS = ("controlPv", "indicatorPv", "readPv", "alarmPv", "pv", "filePv", "nullPv")

# EDM attribute name -> Qt prop name (the key Beaver's qtPropMap consumes).
EDM_TO_QT_PROP: dict[str, str] = {
    # channels (all funnel to "channel"; Beaver maps channel -> pv via stripProtocol)
    "controlPv": "channel",
    "indicatorPv": "channel",
    "readPv": "channel",
    "alarmPv": "channel",
    "pv": "channel",
    "filePv": "channel",
    "nullPv": "channel",
    # text / labels (Beaver maps "text" -> text/label per widget)
    "value": "text",
    "label": "text",
    "buttonLabel": "text",
    # display formatting
    "precision": "precision",
    "showUnits": "showUnits",
    "displayFormat": "displayFormat",
    # alarm sensitivity
    "fgAlarm": "alarmSensitiveContent",
    "alarmSensitiveContent": "alarmSensitiveContent",
    "alarmSensitiveBorder": "alarmSensitiveBorder",
    # button values
    "pressValue": "pressValue",
    "releaseValue": "releaseValue",
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
    # related display (P1): a list of target files -> "filenames" (firstOf -> file)
    "displayFileName": "filenames",
    # byte indicator (P1)
    "numBits": "numBits",
    "shift": "shift",
    # alignment
    "fontAlign": "alignment",
}


def has_pv(properties: dict[str, Any]) -> bool:
    """True if the EDM object carries any PV channel attribute."""
    return any(attr in properties for attr in EDM_CHANNEL_ATTRS)


def resolve_qt_class(name_lower: str, properties: dict[str, Any]) -> str | None:
    """Resolve an EDM class to a Qt class, or ``None`` (-> unknown-widget).

    A static ``activeXTextClass`` (no PV) is a label with fixed text, so it maps to
    ``QLabel`` (-> ``text-label``, which has a ``text`` prop). With a PV it is a live
    value display, so it maps to ``PyDMLabel`` (-> ``pv-label``).
    """
    if name_lower == "activextextclass" and not has_pv(properties):
        return "QLabel"
    return EDM_TO_QT_CLASS.get(name_lower)
