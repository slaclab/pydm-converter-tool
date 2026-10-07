"""Regression tests for the fidelity/edm-batch fixes: state-button labels,
xyGraph -> waveform-plot curves, and screen background carry-through."""

import json

from pydmconverter.edm.edm_qt import EDM_TO_QT_CLASS
from pydmconverter.edm.ir_adapter import _fixup_pip, _fixup_shell_cmd, _fixup_state_button, _fixup_xy_graph, _pip_rules
from pydmconverter.edm.parser import EDMObject


def _obj(name, properties):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, 10, 10
    return obj


def test_message_button_falls_back_to_off_label():
    qt_props = {}
    warnings = []
    obj = _obj("activeMessageButtonClass", {"onLabel": "HV Off", "offLabel": "HV Off"})
    _fixup_state_button(obj, qt_props, warnings)
    assert qt_props["text"] == "HV Off"
    assert warnings == []


def test_state_button_notes_differing_labels_and_keeps_resting():
    qt_props = {}
    warnings = []
    obj = _obj("activeButtonClass", {"onLabel": "Running", "offLabel": "Stopped"})
    _fixup_state_button(obj, qt_props, warnings)
    assert qt_props["text"] == "Stopped"
    assert any("resting" in w for w in warnings)


def test_state_button_keeps_existing_text():
    qt_props = {"text": "Authored"}
    obj = _obj("activeMessageButtonClass", {"offLabel": "Ignored"})
    _fixup_state_button(obj, qt_props, [])
    assert qt_props["text"] == "Authored"


def test_xygraph_maps_to_waveform_plot_class():
    assert EDM_TO_QT_CLASS["xygraphclass"] == "PyDMWaveformPlot"


def test_xygraph_traces_become_curve_json():
    qt_props = {}
    warnings = []
    obj = _obj("xyGraphClass", {"yPv": ["SIG:ONE", "SIG:TWO"], "graphTitle": "Kly Fwd", "xPv": "T:BASE"})
    _fixup_xy_graph(obj, qt_props, warnings)
    curves = [json.loads(c) for c in qt_props["curves"]]
    assert [c["y_channel"] for c in curves] == ["SIG:ONE", "SIG:TWO"]
    # The single xPv pairs with the first trace (waveform-vs-waveform).
    assert curves[0]["x_channel"] == "T:BASE"
    assert "x_channel" not in curves[1]
    assert qt_props["title"] == "Kly Fwd"
    assert warnings == []


def test_xygraph_pairs_traces_by_index_across_omitted_entries():
    """buncherPRCIQvstgraph.edl: traces 0 and 1 are unused, so yPv starts at index 2."""
    qt_props = {}
    obj = _obj("xyGraphClass", {"yPv": ["", "", "SIG:C", "SIG:D"], "xPv": ["X:A", "", "X:C"]})
    _fixup_xy_graph(obj, qt_props, [])
    curves = [json.loads(c) for c in qt_props["curves"]]
    assert curves == [
        {"y_channel": "SIG:C", "name": "trace 1", "x_channel": "X:C"},
        {"y_channel": "SIG:D", "name": "trace 2"},
    ]


def test_shell_command_labels_stay_with_their_commands():
    """asta_main.edl: command 0 has no label, so commandLabel starts at index 1."""
    qt_props = {}
    properties = {"command": ["viewer.bash", "firefox grafana", ""], "commandLabel": ["", "Grafana", "Unused"]}
    _fixup_shell_cmd(_obj("shellCmdClass", properties), qt_props, [])
    assert qt_props["actions"] == [
        {"type": "shell_command", "command": "viewer.bash"},
        {"type": "shell_command", "command": "firefox grafana", "label": "Grafana"},
    ]


def test_shell_command_keeps_digit_led_labels():
    qt_props = {}
    _fixup_shell_cmd(_obj("shellCmdClass", {"command": ["run 1"], "commandLabel": ["1 Hz"]}), qt_props, [])
    assert qt_props["actions"][0]["label"] == "1 Hz"


def test_menu_pip_rule_keeps_each_files_selector_value():
    """An omitted displayFileName entry leaves its filePv value showing nothing."""
    properties = {"displaySource": "menu", "filePv": "SEL:PV", "displayFileName": ["a.edl", "", "c.edl"]}
    (rule,) = _pip_rules(_obj("activePipClass", properties))
    assert [value for value, _ in rule.conditions] == ["{0} == 0", "{0} == 2"]
    assert rule.conditions[1][1].startswith("c")


def test_menu_pip_static_file_is_the_first_listed_file():
    qt_props = {}
    properties = {"displaySource": "menu", "filePv": "SEL:PV", "displayFileName": ["", "b.edl"]}
    _fixup_pip(_obj("activePipClass", properties), qt_props, [])
    assert qt_props["filename"] == "b.edl"
