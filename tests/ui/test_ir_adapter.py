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


def test_button_text_double_ampersand_unescaped(tmp_path):
    """Issue #157: the .ui emitter writes `&&` for button text so Qt doesn't treat
    a lone `&` as a mnemonic marker; the react/IR path has no mnemonic concept and
    must show the user's literal `&` (button text lands in IR as `label`)."""
    ui = tmp_path / "button.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMRelatedDisplayButton" name="btn">
  <property name="geometry"><rect><x>0</x><y>0</y><width>150</width><height>30</height></rect></property>
  <property name="text"><string>PLC &amp;&amp; UPS Diagnostics</string></property>
  <property name="filenames"><stringlist><string>plc.ui</string></stringlist></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    button = ir.root.children[0]
    assert button.props["label"] == "PLC & UPS Diagnostics"


def test_related_display_titles_unescaped():
    """`titles` (plural) isn't in related-display-button's qtPropMap, so it never
    surfaces into IR props (builder._map_props drops anything not in qtPropMap) —
    but the SourceNode-level unescaping must still happen (defense in depth /
    future-proofing), so assert directly on the SourceNode qt_props."""
    import xml.etree.ElementTree as ET

    from pydmconverter.ui.ir_adapter import _widget_to_sources

    widget_xml = """<widget class="PyDMRelatedDisplayButton" name="btn">
      <property name="geometry"><rect><x>0</x><y>0</y><width>150</width><height>30</height></rect></property>
      <property name="titles"><stringlist><string>Sub &amp;&amp; Menu</string></stringlist></property>
    </widget>"""
    widget = ET.fromstring(widget_xml)
    nodes = _widget_to_sources(widget, None)
    assert nodes[0].qt_props["titles"] == ["Sub & Menu"]


def test_label_text_ampersand_untouched(tmp_path):
    """Regression guard: QLabel/PyDMLabel text is never unescaped (PyQt5 renders
    `&` in a QLabel literally, so there is no mnemonic to undo)."""
    ui = tmp_path / "label_amp.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="centralwidget">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMLabel" name="lbl_dbl">
  <property name="geometry"><rect><x>0</x><y>0</y><width>80</width><height>20</height></rect></property>
  <property name="text"><string>A &amp;&amp; B</string></property>
 </widget>
 <widget class="PyDMLabel" name="lbl_single">
  <property name="geometry"><rect><x>0</x><y>30</y><width>80</width><height>20</height></rect></property>
  <property name="text"><string>A &amp; B</string></property>
 </widget>
</widget></ui>"""
    )
    ir = ui_file_to_ir(ui)
    lbl_dbl, lbl_single = ir.root.children[0], ir.root.children[1]
    assert lbl_dbl.props["text"] == "A && B"
    assert lbl_single.props["text"] == "A & B"


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


def _centralwidget_ui(tmp_path, central: tuple[int, int], label: tuple[int, int, int, int]):
    """A legacy-converter-shaped .ui: a 400x300 Form wrapping a layout-less
    centralwidget with an explicit geometry and one label."""
    x, y, w, h = label
    ui = tmp_path / "central.ui"
    ui.write_text(
        f"""<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="Form">
 <property name="geometry"><rect><x>0</x><y>0</y><width>400</width><height>300</height></rect></property>
 <widget class="QWidget" name="centralwidget">
  <property name="geometry"><rect><x>0</x><y>0</y><width>{central[0]}</width><height>{central[1]}</height></rect></property>
  <widget class="QLabel" name="lbl">
   <property name="geometry"><rect><x>{x}</x><y>{y}</y><width>{w}</width><height>{h}</height></rect></property>
   <property name="text"><string>hi</string></property>
  </widget>
 </widget>
</widget></ui>"""
    )
    return ui_file_to_ir(ui)


def test_centralwidget_geometry_keeps_screen_size(tmp_path):
    """A centralwidget sized to the screen is a page wrapper, not content: it must
    not push the canvas out by the overflow margin (400x300 stays 400x300)."""
    ir = _centralwidget_ui(tmp_path, (400, 300), (20, 20, 100, 20))
    assert (ir.metadata.size.width, ir.metadata.size.height) == (400, 300)
    assert (ir.root.geometry.width, ir.root.geometry.height) == (400, 300)


def test_centralwidget_overflow_still_grows_screen(tmp_path):
    """Children past the declared size (centralwidget enlarged to cover them) still
    grow the canvas to their extent plus the margin."""
    ir = _centralwidget_ui(tmp_path, (450, 340), (300, 300, 150, 40))
    assert (ir.metadata.size.width, ir.metadata.size.height) == (458, 348)
    assert (ir.root.geometry.width, ir.root.geometry.height) == (458, 348)


def _related_display_ui(tmp_path, macros_xml):
    ui = tmp_path / "rd.ui"
    ui.write_text(
        f"""<?xml version="1.0"?>
<ui version="4.0"><class>Form</class>
<widget class="QWidget" name="Form">
 <property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>
 <widget class="PyDMRelatedDisplayButton" name="rd">
  <property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>20</height></rect></property>
  <property name="filenames" stdset="0"><stringlist><string>a.ui</string><string>b.ui</string></stringlist></property>
  {macros_xml}
 </widget>
</widget></ui>"""
    )
    (button,) = ui_file_to_ir(ui).root.children
    return button


def test_related_display_macros_stringlist_takes_first_display(tmp_path):
    """macros is a QStringList paired with filenames: the IR button (first file only) gets entry 0 as an object."""
    button = _related_display_ui(
        tmp_path,
        """<property name="macros" stdset="0"><stringlist>
  <string>{"P": "A"}</string><string>{"P": "B"}</string></stringlist></property>""",
    )
    assert button.props["file"] == "a.screen.json"
    assert button.props["macros"] == {"P": "A"}


def test_related_display_macros_string_and_epics_forms(tmp_path):
    """A lone <string> (older single-entry form) in PyDM's NAME=value syntax also becomes an object."""
    button = _related_display_ui(tmp_path, '<property name="macros" stdset="0"><string>P=A, R=B</string></property>')
    assert button.props["macros"] == {"P": "A", "R": "B"}


def test_related_display_empty_first_macros_dropped(tmp_path):
    button = _related_display_ui(
        tmp_path,
        """<property name="macros" stdset="0"><stringlist>
  <string>{}</string><string>{"P": "B"}</string></stringlist></property>""",
    )
    assert "macros" not in button.props


def test_related_display_unparseable_macros_dropped_with_warning(tmp_path):
    button = _related_display_ui(tmp_path, '<property name="macros" stdset="0"><string>not macros</string></property>')
    assert "macros" not in button.props
    assert "rd has unparseable macros; dropped" in button.warnings


def test_related_display_macros_newline_joined_string_takes_first_line(tmp_path):
    """A lone <string> may be the pre-#181 converter's newline-joined list (one JSON object per filename)."""
    button = _related_display_ui(
        tmp_path, '<property name="macros" stdset="0"><string>{"P": "A"}\n{"P": "B"}</string></property>'
    )
    assert button.props["macros"] == {"P": "A"}
    assert not any("unparseable macros" in warning for warning in button.warnings)


def test_related_display_newline_joined_empty_first_entry(tmp_path):
    button = _related_display_ui(
        tmp_path, '<property name="macros" stdset="0"><string>{}\n{"P": "B"}</string></property>'
    )
    assert "macros" not in button.props
    assert not any("unparseable macros" in warning for warning in button.warnings)


def test_related_display_pretty_printed_macros_string(tmp_path):
    """A multi-line <string> that is one JSON object parses whole, before any first-line split."""
    button = _related_display_ui(
        tmp_path, '<property name="macros" stdset="0"><string>{\n "P": "A"\n}</string></property>'
    )
    assert button.props["macros"] == {"P": "A"}
