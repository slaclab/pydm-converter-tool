"""PyDMTemplateRepeater -> N embedded-display materialization (.ui adapter).

PyDM renders a template ``.ui`` once per record in a JSON dataSource, laid out
horizontally/vertically. The adapter fans the repeater out into one
embedded-display IR node per record (reusing the embedded-display path), each
referencing the converted template screen and carrying the record as its macros.
Missing/malformed dataSource falls back to the unknown-widget placeholder.
"""

import json
from pathlib import Path

from pydmconverter.ui.ir_adapter import ui_file_to_ir

TEMPLATE_UI = """<?xml version="1.0"?>
<ui version="4.0"><widget class="QWidget" name="Widget">
  <property name="geometry"><rect><x>0</x><y>0</y><width>50</width><height>40</height></rect></property>
</widget></ui>
"""

REPEATER_UI = """<?xml version="1.0"?>
<ui version="4.0"><widget class="QWidget" name="screen">
  <property name="geometry"><rect><x>0</x><y>0</y><width>500</width><height>300</height></rect></property>
  <widget class="PyDMTemplateRepeater" name="rep">
    <property name="geometry"><rect><x>10</x><y>20</y><width>400</width><height>40</height></rect></property>
    <property name="layoutType" stdset="0"><enum>PyDMTemplateRepeater::Horizontal</enum></property>
    <property name="layoutSpacing" stdset="0"><number>0</number></property>
    <property name="countShownInDesigner" stdset="0"><number>10</number></property>
    <property name="templateFilename" stdset="0"><string>{template}</string></property>
    <property name="dataSource" stdset="0"><string>{data}</string></property>
  </widget>
</widget></ui>
"""

RECORDS = [
    {"Name": "A", "Prefix": "DEV:A"},
    {"Name": "B", "Prefix": "DEV:B"},
    {"Name": "C", "Prefix": "DEV:C"},
]


def _write_screen(tmp_path: Path, *, template: str, data: str, records=RECORDS) -> Path:
    (tmp_path / "Widget.ui").write_text(TEMPLATE_UI)
    if records is not None:
        (tmp_path / "data.json").write_text(json.dumps(records))
    ui = tmp_path / "screen.ui"
    ui.write_text(REPEATER_UI.format(template=template, data=data))
    return ui


def test_repeater_expands_to_embedded_displays(tmp_path):
    ui = _write_screen(tmp_path, template="Widget.ui", data="data.json")
    children = ui_file_to_ir(ui).root.children

    embeds = [c for c in children if c.type == "embedded-display"]
    assert len(embeds) == len(RECORDS)
    assert all(c.type != "unknown-widget" for c in children)

    # Each embed references the converted template screen and carries its record.
    for embed, record in zip(embeds, RECORDS):
        assert embed.props["file"] == "Widget.screen.json"
        assert embed.props["macros"] == record

    # Horizontal layout: stepped x by template width (50) + spacing (0); y constant.
    xs = [c.geometry.x for c in embeds]
    ys = [c.geometry.y for c in embeds]
    assert xs == [10, 60, 110]
    assert ys == [20, 20, 20]
    # Instance geometry uses the template's footprint.
    assert (embeds[0].geometry.width, embeds[0].geometry.height) == (50, 40)


def test_repeater_vertical_and_spacing(tmp_path):
    (tmp_path / "Widget.ui").write_text(TEMPLATE_UI)
    (tmp_path / "data.json").write_text(json.dumps(RECORDS))
    ui = tmp_path / "screen.ui"
    ui.write_text(
        """<?xml version="1.0"?>
<ui version="4.0"><widget class="QWidget" name="screen">
  <property name="geometry"><rect><x>0</x><y>0</y><width>500</width><height>300</height></rect></property>
  <widget class="PyDMTemplateRepeater" name="rep">
    <property name="geometry"><rect><x>10</x><y>20</y><width>60</width><height>200</height></rect></property>
    <property name="layoutSpacing" stdset="0"><number>4</number></property>
    <property name="templateFilename" stdset="0"><string>Widget.ui</string></property>
    <property name="dataSource" stdset="0"><string>data.json</string></property>
  </widget>
</widget></ui>
"""
    )
    embeds = [c for c in ui_file_to_ir(ui).root.children if c.type == "embedded-display"]
    assert len(embeds) == 3
    # layoutType absent -> Vertical (PyDM default): stepped y by height (40) + spacing (4).
    assert [c.geometry.y for c in embeds] == [20, 64, 108]
    assert [c.geometry.x for c in embeds] == [10, 10, 10]


def test_missing_datasource_falls_back_to_unknown(tmp_path):
    ui = _write_screen(tmp_path, template="Widget.ui", data="nope.json", records=None)
    children = ui_file_to_ir(ui).root.children
    assert [c.type for c in children] == ["unknown-widget"]
    node = children[0]
    assert node.props["originalClass"] == "PyDMTemplateRepeater"
    assert any("missing/unreadable" in w for w in node.warnings)


def test_malformed_datasource_falls_back_to_unknown(tmp_path):
    (tmp_path / "Widget.ui").write_text(TEMPLATE_UI)
    (tmp_path / "data.json").write_text("{not valid json")
    ui = tmp_path / "screen.ui"
    ui.write_text(REPEATER_UI.format(template="Widget.ui", data="data.json"))
    children = ui_file_to_ir(ui).root.children
    assert [c.type for c in children] == ["unknown-widget"]
    assert any("missing/unreadable" in w for w in children[0].warnings)


def test_datasource_not_a_list_falls_back(tmp_path):
    (tmp_path / "Widget.ui").write_text(TEMPLATE_UI)
    (tmp_path / "data.json").write_text(json.dumps({"Name": "A"}))  # object, not list
    ui = tmp_path / "screen.ui"
    ui.write_text(REPEATER_UI.format(template="Widget.ui", data="data.json"))
    children = ui_file_to_ir(ui).root.children
    assert [c.type for c in children] == ["unknown-widget"]
    assert any("not a JSON list" in w for w in children[0].warnings)
