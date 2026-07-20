"""Regression tests for the MC-batch unknown-widget reduction.

Each previously-unmapped Qt/PyDM ``.ui`` class must now resolve to a concrete IR
type (never ``unknown-widget``). Most go through the adapter's class-alias table
(``_QT_CLASS_ALIASES``); ``PyDMSpinbox`` goes through a dedicated ``pv-spinbox``
registry entry.
"""

from __future__ import annotations

from pydmconverter.ui.ir_adapter import ui_file_to_ir


def _one_widget_ui(inner: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0"><widget class="QWidget" name="Form">
 <property name="geometry"><rect><x>0</x><y>0</y><width>400</width><height>300</height></rect></property>
 {inner}
</widget></ui>"""


def _first(ir):
    return ir.root.children[0]


def _convert(tmp_path, inner: str):
    path = tmp_path / "w.ui"
    path.write_text(_one_widget_ui(inner))
    return ui_file_to_ir(path)


def test_edm_display_button_maps_to_related_display_button(tmp_path):
    inner = """<widget class="PyDMEDMDisplayButton" name="b">
      <property name="geometry"><rect><x>0</x><y>0</y><width>64</width><height>24</height></rect></property>
      <property name="text"><string>IN20</string></property>
      <property name="filenames" stdset="0"><stringlist><string>mc_in20</string></stringlist></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "related-display-button"
    assert node.props["label"] == "IN20"
    assert node.props["file"] == "mc_in20.screen.json"  # screenRef: extensionless target -> .screen.json


def test_pydm_frame_maps_to_frame_container_with_children(tmp_path):
    inner = """<widget class="PyDMFrame" name="fr">
      <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
      <widget class="QLabel" name="l">
        <property name="geometry"><rect><x>5</x><y>5</y><width>50</width><height>20</height></rect></property>
        <property name="text"><string>Inside</string></property>
      </widget>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "frame"
    assert [c.type for c in node.children] == ["text-label"]
    assert node.children[0].props["text"] == "Inside"


def test_qt_line_maps_to_line(tmp_path):
    inner = """<widget class="Line" name="line">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>3</height></rect></property>
      <property name="orientation"><enum>Qt::Horizontal</enum></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "line"


def test_pydm_drawing_line_maps_to_line(tmp_path):
    inner = """<widget class="PyDMDrawingLine" name="dl">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>3</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "line"


def test_pydm_spinbox_maps_to_pv_spinbox(tmp_path):
    inner = """<widget class="PyDMSpinbox" name="sp">
      <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>28</height></rect></property>
      <property name="channel" stdset="0"><string>ca://${P}${M}.VAL</string></property>
      <property name="showStepExponent" stdset="0"><bool>false</bool></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "pv-spinbox"
    assert node.props["pv"] == "${P}${M}.VAL"  # ca:// stripped
    assert node.props["showStepExponent"] is False


def test_text_widgets_map_to_text_label(tmp_path):
    for klass in ("QTextEdit", "QTextBrowser", "QLineEdit"):
        inner = f"""<widget class="{klass}" name="t">
          <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>40</height></rect></property>
        </widget>"""
        node = _first(_convert(tmp_path, inner))
        assert node.type == "text-label", klass


def test_qlineedit_carries_its_text(tmp_path):
    inner = """<widget class="QLineEdit" name="le">
      <property name="geometry"><rect><x>0</x><y>0</y><width>120</width><height>24</height></rect></property>
      <property name="text"><string>Copper target controls</string></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "text-label"
    assert node.props["text"] == "Copper target controls"


def test_stacked_toolbox_pydmtab_map_to_tabs(tmp_path):
    for klass in ("QStackedWidget", "QToolBox", "PyDMTabWidget"):
        inner = f"""<widget class="{klass}" name="c">
          <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>150</height></rect></property>
          <widget class="QLabel" name="l">
            <property name="geometry"><rect><x>5</x><y>5</y><width>50</width><height>20</height></rect></property>
            <property name="text"><string>Page</string></property>
          </widget>
        </widget>"""
        node = _first(_convert(tmp_path, inner))
        assert node.type == "tabs", klass
        assert node.children[0].type == "text-label"  # children survive


def test_pydm_drawing_pie_maps_to_arc(tmp_path):
    inner = """<widget class="PyDMDrawingPie" name="pie">
      <property name="geometry"><rect><x>0</x><y>0</y><width>40</width><height>40</height></rect></property>
      <property name="spanAngle"><double>180.0</double></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "arc"
    assert node.props["spanAngle"] == 180.0


def test_pydm_drawing_triangle_maps_to_polygon(tmp_path):
    inner = """<widget class="PyDMDrawingTriangle" name="tri">
      <property name="geometry"><rect><x>0</x><y>0</y><width>20</width><height>20</height></rect></property>
      <property name="rotation"><double>135.0</double></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "polygon"


def test_pydm_drawing_circle_maps_to_ellipse(tmp_path):
    inner = """<widget class="PyDMDrawingCircle" name="c">
      <property name="geometry"><rect><x>0</x><y>0</y><width>40</width><height>40</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "ellipse"


def test_pydm_time_plot_maps_to_waveform_plot(tmp_path):
    inner = """<widget class="PyDMTimePlot" name="tp">
      <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>120</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "waveform-plot"


def test_pydm_event_plot_maps_to_waveform_plot(tmp_path):
    inner = """<widget class="PyDMEventPlot" name="ep">
      <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>120</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "waveform-plot"


def test_qcombobox_maps_to_pv_enum_combobox(tmp_path):
    inner = """<widget class="QComboBox" name="cb">
      <property name="geometry"><rect><x>0</x><y>0</y><width>120</width><height>28</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "pv-enum-combobox"


def test_qspinbox_maps_to_pv_spinbox(tmp_path):
    inner = """<widget class="QSpinBox" name="sb">
      <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>28</height></rect></property>
      <property name="minimum"><number>0</number></property>
      <property name="maximum"><number>100</number></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "pv-spinbox"


def test_template_repeater_stays_unknown_placeholder(tmp_path):
    """PyDMTemplateRepeater is not trivially mappable (external template + data
    source, no inline children) — it remains an unknown-widget placeholder
    (nothing disappears silently) and is flagged needs-human."""
    inner = """<widget class="PyDMTemplateRepeater" name="tr">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
    </widget>"""
    node = _first(_convert(tmp_path, inner))
    assert node.type == "unknown-widget"
    assert node.props["originalClass"] == "PyDMTemplateRepeater"
