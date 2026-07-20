from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ui.ir_adapter import ui_file_to_ir

FIXTURE = Path(__file__).parent / "fixtures" / "basic_widgets.ui"
NEWLY_SUPPORTED = Path(__file__).parent / "fixtures" / "newly_supported.ui"
EDM_FIXTURE = Path(__file__).parents[1] / "edm" / "fixtures" / "basic_widgets.edl"


def _convert():
    return ui_file_to_ir(FIXTURE)


def test_screen_metadata():
    screen = _convert()
    assert screen.id == "basic_widgets"
    assert screen.metadata.title == "basic_widgets"  # from windowTitle
    assert screen.metadata.source.type == "ui-converter"
    assert (screen.metadata.size.width, screen.metadata.size.height) == (400, 300)


def test_widget_types_in_order():
    children = _convert().root.children
    assert [c.type for c in children] == ["text-label", "pv-text-input", "pv-button", "unknown-widget"]


def test_qlabel_to_text_label():
    label = _convert().root.children[0]
    assert label.type == "text-label"
    assert label.props == {"text": "Label ${PREFIX}"}


def test_channel_protocol_stripped():
    text_input = _convert().root.children[1]
    assert text_input.props == {"pv": "${PREFIX}:SETPOINT"}  # ca:// dropped by stripProtocol


def test_button_props():
    button = _convert().root.children[2]
    assert button.props["pv"] == "${PREFIX}:GO"
    assert button.props["label"] == "Go"
    assert button.props["pressValue"] == "1"


def test_unknown_pydm_class():
    unknown = _convert().root.children[3]
    assert unknown.type == "unknown-widget"
    assert unknown.props["originalClass"] == "PyDMMysteryGauge"
    assert unknown.warnings == ["No registry entry for PyDMMysteryGauge; rendering placeholder"]


def test_macros_collected():
    assert [(m.name, m.default) for m in _convert().macros] == [("PREFIX", "")]


def test_validates_and_deterministic():
    screen = _convert()
    assert validate_screen_json(to_wire_dict(screen)) == []
    assert to_json(ui_file_to_ir(FIXTURE)) == to_json(screen)


def test_layout_child_without_rect_warns(tmp_path):
    """A widget in a Qt layout (no geometry rect) is kept with a warning (D4 trust-and-warn)."""
    ui = """<?xml version="1.0"?>
    <ui version="4.0"><widget class="QWidget" name="screen">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
      <layout class="QVBoxLayout"><item>
        <widget class="QLabel" name="lbl"><property name="text"><string>hi</string></property></widget>
      </item></layout>
    </widget></ui>"""
    path = tmp_path / "layout.ui"
    path.write_text(ui, encoding="utf-8")
    label = ui_file_to_ir(path).root.children[0]
    assert label.type == "text-label"
    assert label.geometry.model_dump() == {"x": 0, "y": 0, "width": 0, "height": 0}
    assert label.warnings and "no geometry rect" in label.warnings[0]


def test_channelless_pydmlabel_keeps_static_text(tmp_path):
    """A PyDMLabel with `text` and no `channel` is a static label: the text must survive.

    Regression for Defect A — pv-label dropped `text`, rendering a blank box.
    """
    ui = """<?xml version="1.0"?>
    <ui version="4.0"><widget class="QWidget" name="screen">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
      <widget class="PyDMLabel" name="static_lbl">
        <property name="geometry"><rect><x>5</x><y>5</y><width>80</width><height>20</height></rect></property>
        <property name="text"><string>Hello</string></property>
      </widget>
    </widget></ui>"""
    path = tmp_path / "static_label.ui"
    path.write_text(ui, encoding="utf-8")
    label = ui_file_to_ir(path).root.children[0]
    assert label.type == "pv-label"
    assert label.props.get("text") == "Hello"
    assert "pv" not in label.props


def test_irregular_polygon_maps_to_polygon_with_points(tmp_path):
    """A PyDMDrawingIrregularPolygon becomes a `polygon` node (not unknown-widget),
    carrying its vertices as structured {x, y} points."""
    ui = """<?xml version="1.0"?>
    <ui version="4.0"><widget class="QWidget" name="screen">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
      <widget class="PyDMDrawingIrregularPolygon" name="poly">
        <property name="geometry"><rect><x>5</x><y>5</y><width>20</width><height>20</height></rect></property>
        <property name="penStyle"><enum>Qt::SolidLine</enum></property>
        <property name="penWidth"><double>2.0</double></property>
        <property name="points">
          <stringlist>
            <string>0.0, 0.0</string>
            <string>7.0, 5.0</string>
            <string>14.0, 0.0</string>
            <string>0.0, 0.0</string>
          </stringlist>
        </property>
      </widget>
    </widget></ui>"""
    path = tmp_path / "poly.ui"
    path.write_text(ui, encoding="utf-8")
    node = ui_file_to_ir(path).root.children[0]
    assert node.type == "polygon"
    assert node.props["lineWidth"] == 2.0
    assert node.props["lineStyle"] == "solid"
    assert node.props["points"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 7.0, "y": 5.0},
        {"x": 14.0, "y": 0.0},
        {"x": 0.0, "y": 0.0},
    ]


def test_polyline_line_points_are_structured(tmp_path):
    """A PyDMDrawingPolyline stays a `line` node, and its "x, y" stringlist is
    normalized to structured {x, y} points (regression: raw strings reached the runtime)."""
    ui = """<?xml version="1.0"?>
    <ui version="4.0"><widget class="QWidget" name="screen">
      <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>100</height></rect></property>
      <widget class="PyDMDrawingPolyline" name="pl">
        <property name="geometry"><rect><x>0</x><y>0</y><width>20</width><height>20</height></rect></property>
        <property name="points">
          <stringlist>
            <string>0.0, 1.0</string>
            <string>17.0, 18.0</string>
          </stringlist>
        </property>
      </widget>
    </widget></ui>"""
    path = tmp_path / "polyline.ui"
    path.write_text(ui, encoding="utf-8")
    node = ui_file_to_ir(path).root.children[0]
    assert node.type == "line"
    assert node.props["points"] == [{"x": 0.0, "y": 1.0}, {"x": 17.0, "y": 18.0}]


def _structure(screen):
    return [
        (c.type, c.props.get("pv") or c.props.get("text"), tuple(c.geometry.model_dump().values()))
        for c in screen.root.children
    ]


def test_cross_input_equivalence_with_edm():
    """Milestone: the same screen as .edl and .ui yields structurally-equal IR.

    Scoped to the first 3 children (label/input/button): the 4th diverges by
    design — ``basic_widgets.ui``'s ``PyDMMysteryGauge`` is a fixture-only unknown class
    (see test_unknown_pydm_class), while ``basic_widgets.edl``'s activeRectangleClass
    maps to a supported "rectangle" node (see test_rectangle_maps_with_line_color
    in tests/edm/test_ir_adapter.py).
    """
    assert _structure(ui_file_to_ir(FIXTURE))[:3] == _structure(edm_file_to_ir(EDM_FIXTURE))[:3]


def _all_types(node):
    yield node.type
    for child in node.children:
        yield from _all_types(child)


def test_newly_supported_classes_have_no_unknown_widgets():
    """QWidget panels, shell commands, and waveform plots all resolve now."""
    screen = ui_file_to_ir(NEWLY_SUPPORTED)
    assert "unknown-widget" not in set(_all_types(screen.root))


def test_qwidget_panel_becomes_container_with_child():
    screen = ui_file_to_ir(NEWLY_SUPPORTED)
    panel = next(c for c in screen.root.children if c.type == "qwidget-container")
    assert [child.type for child in panel.children] == ["pv-label"]
    assert panel.children[0].props["pv"] == "${PREFIX}:RBV"  # ca:// stripped


def test_shell_command_maps_label_and_command():
    screen = ui_file_to_ir(NEWLY_SUPPORTED)
    shell = next(c for c in screen.root.children if c.type == "shell-command-button")
    assert shell.props["label"] == "Probe..."
    assert shell.props["command"] == "probe ${PREFIX}"  # firstOf the commands stringlist
    assert shell.props["alarmBorder"] is True


def test_waveform_plot_parses_curves_and_skips_malformed():
    screen = ui_file_to_ir(NEWLY_SUPPORTED)
    plot = next(c for c in screen.root.children if c.type == "waveform-plot")
    assert plot.props["title"] == "Temps"
    # the malformed second curve string is dropped; the valid one parses to an object
    assert plot.props["curves"] == [{"y_channel": "${PREFIX}:TEMP", "color": "#e00000", "lineWidth": 1}]
    assert plot.props["xLabels"] == ["Time"]


def test_scalar_number_parsing_is_tolerant():
    """A <number> is an int, but a float-formatted or junk value degrades rather than raising."""
    import xml.etree.ElementTree as ET

    from pydmconverter.ui.ir_adapter import _SKIP, _scalar_property

    def prop(tag: str, text: str) -> ET.Element:
        el = ET.Element("property")
        ET.SubElement(el, tag).text = text
        return el

    assert _scalar_property(prop("number", "8")) == 8
    assert _scalar_property(prop("number", "8.0")) == 8.0  # float-formatted number, not a crash
    assert _scalar_property(prop("number", "")) == 0
    assert _scalar_property(prop("number", "nope")) is _SKIP
    assert _scalar_property(prop("double", "1.5")) == 1.5
    assert _scalar_property(prop("double", "nope")) is _SKIP


def test_lowercase_macros_are_declared(tmp_path):
    """Lowercase/mixed-case ${macro} refs in PV channels must be collected into
    the screen's macros[] (convert-fidelity defect G) — not silently dropped."""
    from pydmconverter.ui.ir_adapter import ui_file_to_ir

    ui = tmp_path / "lc.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMLabel" name="l1">
  <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>20</height></rect></property>
  <property name="channel"><string>${dev}:${area}:Value</string></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    names = {m.name for m in ir.macros}
    assert "dev" in names and "area" in names


def test_font_pointsize_becomes_fontsize_px(tmp_path):
    """Qt <font><pointsize> is dropped by the scalar walk (complex kind); the adapter
    must lower it to a px `fontSize` prop so dense text does not overflow at the
    runtime 13px default (convert-fidelity font defect). px = round(pt * 96/72)."""
    from pydmconverter.ui.ir_adapter import ui_file_to_ir

    ui = tmp_path / "font.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMLabel" name="lbl">
  <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>20</height></rect></property>
  <property name="text"><string>Currently:</string></property>
  <property name="font"><font><family>Helvetica</family><pointsize>9</pointsize></font></property>
 </widget>
 <widget class="PyDMPushButton" name="btn">
  <property name="geometry"><rect><x>0</x><y>30</y><width>50</width><height>30</height></rect></property>
  <property name="text"><string>STOP</string></property>
  <property name="font"><font><family>Helvetica</family><pointsize>7</pointsize></font></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    label, button = ir.root.children[0], ir.root.children[1]
    assert label.props["fontSize"] == 12  # 9 * 96/72 == 12
    assert button.props["fontSize"] == 9  # round(7 * 96/72) == 9


def test_font_pixelsize_used_verbatim(tmp_path):
    """A Qt <font><pixelsize> is already in px and is carried through unchanged."""
    from pydmconverter.ui.ir_adapter import ui_file_to_ir

    ui = tmp_path / "px.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMLabel" name="lbl">
  <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>20</height></rect></property>
  <property name="text"><string>Px</string></property>
  <property name="font"><font><family>Helvetica</family><pixelsize>15</pixelsize></font></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    assert ir.root.children[0].props["fontSize"] == 15


def test_font_without_size_emits_nothing(tmp_path):
    """A <font> with no point/pixel size must not add a bogus fontSize prop
    (runtime default stands) and must never crash the conversion."""
    from pydmconverter.ui.ir_adapter import ui_file_to_ir

    ui = tmp_path / "nosize.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMLabel" name="lbl">
  <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>20</height></rect></property>
  <property name="text"><string>NoSize</string></property>
  <property name="font"><font><family>Helvetica</family><bold>true</bold></font></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    assert "fontSize" not in ir.root.children[0].props
