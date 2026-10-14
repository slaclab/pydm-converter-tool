"""Which EDM alarm flags make a .ui widget follow its channel's alarm severity
(edm_qt.EDM_ALARM_PROPS, converter_helpers.apply_alarm_flags).

EDM colours a part of a widget for alarms only where a flag says so: fgAlarm the
text (x_text_dsp_obj.cc, textupdate.cc, x_text_obj.cc) or a button's label
(button.cc), bgAlarm a menu or choice button's face (menu_button.cc,
choice_button.cc), fillAlarm and lineAlarm a drawing's fill and line, from its
alarmPv (rectangle_obj.cc and the other drawings). An object without them never
changes colour. A flag whose part the .ui widget can't colour is dropped with a
warning.
"""

import logging
import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert

HEADER = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 200
h 100
endScreenProperties
"""
POLYGON_POINTS = """numPoints 4
xPoints {
0 10
1 60
2 35
3 10
}
yPoints {
0 40
1 40
2 10
3 40
}"""
OPEN_LINE_POINTS = """numPoints 3
xPoints {
0 10
1 60
2 35
}
yPoints {
0 40
1 40
2 10
}"""


def convert_object(tmp_path, edm_class: str, body: str, version: str = "major 4\nminor 0") -> ET.Element:
    """The one widget the converter writes for a single EDM object."""
    edl = tmp_path / "screen.edl"
    edl.write_text(
        HEADER + f"object {edm_class}\nbeginObjectProperties\n{version}\nrelease 0\n"
        f"x 10\ny 10\nw 50\nh 30\n{body}\nendObjectProperties\n"
    )
    convert(str(edl), str(tmp_path / "screen.ui"))
    (widget,) = ET.parse(tmp_path / "screen.ui").getroot().find(".//widget[@name='centralwidget']").findall("widget")
    return widget


def _prop(widget: ET.Element, name: str):
    element = widget.find(f"property[@name='{name}']")
    return None if element is None else element[0].text


TEXT_CONTROL = ("activeXTextDspClass:noedit", "major 4\nminor 7")


@pytest.mark.parametrize(
    "edm_class, version, body, widget_class, content, border",
    [
        pytest.param(*TEXT_CONTROL, 'controlPv "X:VAL"\nfgAlarm', "PyDMLabel", True, False, id="text control fgAlarm"),
        pytest.param(*TEXT_CONTROL, 'controlPv "X:VAL"', "PyDMLabel", False, False, id="text control"),
        # x_text_dsp_obj.cc: the border takes the alarm colour and the text keeps its own.
        pytest.param(
            *TEXT_CONTROL,
            'controlPv "X:VAL"\nfgAlarm\nuseAlarmBorder',
            "PyDMLabel",
            False,
            True,
            id="text control useAlarmBorder",
        ),
        pytest.param(
            *TEXT_CONTROL, 'controlPv "X:VAL"\nuseAlarmBorder', "PyDMLabel", False, False, id="useAlarmBorder alone"
        ),
        pytest.param(
            "activeXTextDspClass",
            "major 4\nminor 7",
            'controlPv "X:VAL"\neditable\nfgAlarm',
            "PyDMLineEdit",
            True,
            False,
            id="text entry fgAlarm",
        ),
        pytest.param(
            "TextupdateClass",
            "major 10\nminor 0",
            'controlPv "X:VAL"\nfgAlarm\nlineAlarm',
            "PyDMLabel",
            True,
            True,
            id="text update lineAlarm",
        ),
        pytest.param(
            "activeButtonClass",
            "major 4\nminor 0",
            'controlPv "X:BTN"\nfgAlarm',
            "PyDMPushButton",
            True,
            False,
            id="button fgAlarm",
        ),
        pytest.param(
            "activeButtonClass", "major 4\nminor 0", 'controlPv "X:BTN"', "PyDMPushButton", False, False, id="button"
        ),
        pytest.param(
            "activeMenuButtonClass",
            "major 4\nminor 0",
            'controlPv "X:MENU"\nbgAlarm',
            "PyDMEnumComboBox",
            True,
            False,
            id="menu button bgAlarm",
        ),
        pytest.param(
            "activeRectangleClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfill\nfillAlarm',
            "PyDMDrawingRectangle",
            True,
            False,
            id="rectangle fillAlarm",
        ),
        # Nothing to colour: PyDM would paint a fill EDM never draws.
        pytest.param(
            "activeRectangleClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfillAlarm',
            "PyDMDrawingRectangle",
            False,
            False,
            id="rectangle fillAlarm without fill",
        ),
        pytest.param(
            "activeRectangleClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfill\nlineAlarm',
            "PyDMDrawingRectangle",
            False,
            True,
            id="rectangle lineAlarm",
        ),
        pytest.param(
            "activeRectangleClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfill',
            "PyDMDrawingRectangle",
            False,
            False,
            id="rectangle with an alarmPv and no flag",
        ),
        pytest.param(
            "activeRectangleClass", "major 4\nminor 0", "fill", "PyDMDrawingRectangle", False, False, id="rectangle"
        ),
        pytest.param(
            "activeLineClass",
            "major 4\nminor 0",
            f'alarmPv "X:STAT"\nfill\nfillAlarm\n{POLYGON_POINTS}',
            "PyDMDrawingIrregularPolygon",
            True,
            False,
            id="filled polygon fillAlarm",
        ),
        pytest.param(
            "activeLineClass",
            "major 4\nminor 0",
            f'alarmPv "X:STAT"\nfill\n{POLYGON_POINTS}',
            "PyDMDrawingIrregularPolygon",
            False,
            False,
            id="filled polygon",
        ),
        # An open line has no fill in the .ui; PyDM would colour its arrowheads.
        pytest.param(
            "activeLineClass",
            "major 4\nminor 0",
            f'alarmPv "X:STAT"\nfill\nfillAlarm\nlineAlarm\n{OPEN_LINE_POINTS}',
            "PyDMDrawingPolyline",
            False,
            True,
            id="open line fillAlarm lineAlarm",
        ),
        pytest.param(
            "activeCircleClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfill\nfillAlarm',
            "PyDMDrawingEllipse",
            True,
            False,
            id="circle fillAlarm",
        ),
        pytest.param(
            "activeArcClass",
            "major 4\nminor 0",
            'alarmPv "X:STAT"\nfill\nfillAlarm',
            "PyDMDrawingPie",
            True,
            False,
            id="filled arc fillAlarm",
        ),
        pytest.param(
            "RegTextupdateClass",
            "major 10\nminor 0",
            'controlPv "X:VAL"\nfgAlarm\nlineAlarm',
            "PyDMLabel",
            True,
            True,
            id="regexp text update lineAlarm",
        ),
    ],
)
def test_alarm_flags_pick_what_follows_the_alarm(tmp_path, edm_class, version, body, widget_class, content, border):
    widget = convert_object(tmp_path, edm_class, body, version)

    assert widget.get("class") == widget_class
    assert _prop(widget, "alarmSensitiveContent") == str(content).lower()
    assert _prop(widget, "alarmSensitiveBorder") == str(border).lower()


def test_static_text_takes_its_alarm_pv_severity(tmp_path):
    widget = convert_object(
        tmp_path, "activeXTextClass", 'alarmPv "X:STAT"\nfgAlarm\nvalue {\n  "Status"\n}', "major 4\nminor 1"
    )

    assert _prop(widget, "channel") == "X:STAT"
    assert _prop(widget, "displayLabelText") == "true"
    assert _prop(widget, "text") == "Status"
    assert _prop(widget, "alarmSensitiveContent") == "true"


def test_text_bg_alarm_is_dropped_loudly(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        widget = convert_object(tmp_path, *TEXT_CONTROL[:1], 'controlPv "X:VAL"\nbgAlarm', TEXT_CONTROL[1])

    assert _prop(widget, "alarmSensitiveContent") == "false"
    assert any("bgAlarm" in record.message for record in caplog.records)


def _alarm_warnings(caplog) -> list[str]:
    return [record.message for record in caplog.records if "Alarm has no place" in record.message]


@pytest.mark.parametrize(
    "edm_class, version, body, widget_class, flag",
    [
        # motifSlider.cc colours the slider's background; PyDM colours only its value label.
        pytest.param(
            "activeMotifSliderClass",
            "major 2\nminor 0",
            'controlPv "X:VAL"\nbgAlarm 1',
            "PyDMSlider",
            "bgAlarm",
            id="motif slider bgAlarm",
        ),
        pytest.param(
            "activeBarClass",
            "major 4\nminor 1",
            'indicatorPv "X:VAL"\nindicatorAlarm',
            "PyDMDrawingRectangle",
            "indicatorAlarm",
            id="bar indicatorAlarm",
        ),
        pytest.param(
            "activeMeterClass",
            "major 4\nminor 0",
            'readPv "X:VAL"\nfgAlarm',
            "PyDMAnalogIndicator",
            "fgAlarm",
            id="meter fgAlarm",
        ),
    ],
)
def test_alarm_flag_the_ui_cannot_colour_is_dropped_loudly(
    tmp_path, caplog, edm_class, version, body, widget_class, flag
):
    with caplog.at_level(logging.WARNING):
        widget = convert_object(tmp_path, edm_class, body, version)

    assert widget.get("class") == widget_class
    assert _prop(widget, "alarmSensitiveContent") == "false"
    assert _prop(widget, "alarmSensitiveBorder") == "false"
    assert [message for message in _alarm_warnings(caplog) if flag in message]


@pytest.mark.parametrize(
    "edm_class, version, body",
    [
        # EDM draws no fill to colour either.
        pytest.param(
            "activeRectangleClass", "major 4\nminor 0", 'alarmPv "X:STAT"\nfillAlarm', id="fillAlarm without fill"
        ),
        pytest.param(*TEXT_CONTROL, 'controlPv "X:VAL"\nfgAlarm\nuseAlarmBorder', id="text control useAlarmBorder"),
        pytest.param("TextupdateClass", "major 10\nminor 0", 'controlPv "X:VAL"\nfgAlarm\nlineAlarm', id="text update"),
        pytest.param("activeMenuButtonClass", "major 4\nminor 0", 'controlPv "X:MENU"\nbgAlarm', id="menu button"),
    ],
)
def test_alarm_flag_the_ui_carries_is_not_warned_about(tmp_path, caplog, edm_class, version, body):
    with caplog.at_level(logging.WARNING):
        convert_object(tmp_path, edm_class, body, version)

    assert _alarm_warnings(caplog) == []
