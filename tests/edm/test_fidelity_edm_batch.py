"""Regression tests for the fidelity/edm-batch fixes: state-button labels,
xyGraph -> waveform-plot curves, and screen background carry-through."""

import json

from pydmconverter.edm.edm_qt import EDM_TO_QT_CLASS
from pydmconverter.edm.ir_adapter import _fixup_state_button, _fixup_xy_graph
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
    obj = _obj("xyGraphClass", {"yPv": ["0 SIG:ONE", "1 SIG:TWO"], "graphTitle": "Kly Fwd", "xPv": "T:BASE"})
    _fixup_xy_graph(obj, qt_props, warnings)
    curves = [json.loads(c) for c in qt_props["curves"]]
    assert [c["y_channel"] for c in curves] == ["SIG:ONE", "SIG:TWO"]
    # The single xPv pairs with the first trace (waveform-vs-waveform).
    assert curves[0]["x_channel"] == "T:BASE"
    assert "x_channel" not in curves[1]
    assert qt_props["title"] == "Kly Fwd"
    assert warnings == []
