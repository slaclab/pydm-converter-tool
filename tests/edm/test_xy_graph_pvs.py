"""An xyGraph's PVs besides its traces' xPv/yPv: nPv[i] (how many points trace i
plots), traceCtlPv (a bitmask that hides traces), resetPv (clears the plot) and
triggerPv (when trigger-mode traces update). Neither target carries them, so
each is dropped with a warning naming its PVs (xygraph.cc)."""

import json
import logging
import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import edm_file_to_ir

GRAPH = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 300
h 200
endScreenProperties

object {cls}
beginObjectProperties
major 4
minor 10
release 0
x 4
y 4
w 280
h 180
border
plotAreaBorder
fgColor index 13
bgColor index 3
gridColor index 6
font "helvetica-bold-r-12.0"
nPts 0
{pvs}
showXAxis
xAxisSrc "AutoScale"
showYAxis
yAxisSrc "AutoScale"
numTraces 2
xPv {{
  0 "DEMO:TIME"
  1 "DEMO:TIME"
}}
yPv {{
  0 "DEMO:WAVE_A"
  1 "DEMO:WAVE_B"
}}
{n_pv}
plotUpdateMode {{
  0 "xOrY"
  1 "trigger"
}}
opMode {{
  0 "plot"
  1 "plot"
}}
plotColor {{
  0 index 20
  1 index 25
}}
endObjectProperties
"""

PVS = """resetPv "DEMO:RESET"
traceCtlPv "DEMO:HIDE_MASK"
triggerPv "DEMO:TRIGGER\""""
N_PV = """nPv {
  0 "DEMO:WAVE_A_COUNT"
  1 "DEMO:WAVE_B_COUNT"
}"""

DROPPED = {
    "nPv": "DEMO:WAVE_A_COUNT, DEMO:WAVE_B_COUNT",
    "traceCtlPv": "DEMO:HIDE_MASK",
    "resetPv": "DEMO:RESET",
    "triggerPv": "DEMO:TRIGGER",
}


def _write(tmp_path, cls="xyGraphClass", pvs=PVS, n_pv=N_PV):
    source = tmp_path / "xy.edl"
    source.write_text(GRAPH.format(cls=cls, pvs=pvs, n_pv=n_pv), encoding="utf-8")
    return source


def _ui_warnings(tmp_path, source, caplog):
    with caplog.at_level(logging.WARNING):
        convert(str(source), str(tmp_path / "xy.ui"))
    return [record.getMessage() for record in caplog.records if "has no place in the .ui" in record.getMessage()]


def test_ir_warns_about_each_xy_graph_pv_it_drops(tmp_path):
    [graph] = edm_file_to_ir(_write(tmp_path)).root.children
    assert graph.type == "waveform-plot"
    assert [curve["y_channel"] for curve in graph.props["curves"]] == ["DEMO:WAVE_A", "DEMO:WAVE_B"]
    assert [w for w in graph.warnings if w.startswith("EDM xyGraph")] == [
        "EDM xyGraph nPv not mapped (how many points each trace plots): DEMO:WAVE_A_COUNT, DEMO:WAVE_B_COUNT",
        "EDM xyGraph traceCtlPv not mapped (a bitmask that hides traces): DEMO:HIDE_MASK",
        "EDM xyGraph resetPv not mapped (clears the plot): DEMO:RESET",
        "EDM xyGraph triggerPv not mapped (when trigger-mode traces update): DEMO:TRIGGER",
    ]


@pytest.mark.parametrize("cls", ["xyGraphClass", "mzxyGraphClass"])
def test_ui_warns_about_each_xy_graph_pv_it_drops(tmp_path, caplog, cls):
    warnings = _ui_warnings(tmp_path, _write(tmp_path, cls=cls), caplog)
    assert len(warnings) == len(DROPPED)
    for (tag, pvs), warning in zip(DROPPED.items(), warnings):
        assert warning.startswith(f"{cls}: {tag} {pvs} (")
    [plot] = [w for w in ET.parse(tmp_path / "xy.ui").iter("widget") if w.get("class") == "PyDMWaveformPlot"]
    curves = [json.loads(curve.text) for curve in plot.findall("property[@name='curves']/stringlist/string")]
    assert [curve["y_channel"] for curve in curves] == ["DEMO:WAVE_A", "DEMO:WAVE_B"]


def test_graph_without_these_pvs_warns_about_none(tmp_path, caplog):
    blank_n_pv = 'nPv {\n  0 ""\n}'
    source = _write(tmp_path, pvs="", n_pv=blank_n_pv)
    [graph] = edm_file_to_ir(source).root.children
    assert not [w for w in graph.warnings if w.startswith("EDM xyGraph")]
    assert _ui_warnings(tmp_path, source, caplog) == []
