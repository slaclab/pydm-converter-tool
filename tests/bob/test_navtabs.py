"""Phoebus ``navtabs`` -> one open-display button per tab, each with its own file and macros."""

from __future__ import annotations

from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.react import convert_bytes

_NAVTABS = b"""<?xml version="1.0" encoding="UTF-8"?>
<display version="2.0.0">
  <name>Eng</name>
  <widget type="navtabs" version="2.0.0">
    <name>Stations</name>
    <macros><SYS>ARRF</SYS></macros>
    <tabs>
      <tab>
        <name>Status</name>
        <file>_status.bob</file>
        <macros><P>ARRF:LLRF1:</P></macros>
        <group_name></group_name>
      </tab>
      <tab>
        <name>Configuration</name>
        <file>_config.bob</file>
        <macros><P>ARRF:LLRF1:</P><CH>$(SYS):2</CH></macros>
        <group_name></group_name>
      </tab>
      <tab>
        <name>Waveforms</name>
        <file>sub/_waveforms.bob</file>
        <macros><P>ARRF:LLRF2:</P></macros>
        <group_name></group_name>
      </tab>
    </tabs>
    <x>20</x>
    <y>30</y>
    <width>800</width>
    <height>600</height>
    <direction>0</direction>
    <tab_width>200</tab_width>
    <tab_height>28</tab_height>
    <tab_spacing>4</tab_spacing>
  </widget>
</display>
"""


def _wire(data: bytes) -> dict:
    return to_wire_dict(convert_bytes(data, kind="bob"))


def _buttons(wire: dict) -> list[dict]:
    (group,) = wire["root"]["children"]
    return group["children"]


def test_each_tab_button_keeps_its_own_file_and_macros():
    buttons = _buttons(_wire(_NAVTABS))
    assert [b["type"] for b in buttons] == ["regular-button"] * 3
    assert [b["props"]["label"] for b in buttons] == ["Status", "Configuration", "Waveforms"]
    assert [b["props"]["actions"] for b in buttons] == [
        [{"type": "open_display", "file": "_status.screen.json", "target": "tab",
          "macros": {"SYS": "ARRF", "P": "ARRF:LLRF1:"}}],
        [{"type": "open_display", "file": "_config.screen.json", "target": "tab",
          "macros": {"SYS": "ARRF", "P": "ARRF:LLRF1:", "CH": "${SYS}:2"}}],
        [{"type": "open_display", "file": "sub/_waveforms.screen.json", "target": "tab",
          "macros": {"SYS": "ARRF", "P": "ARRF:LLRF2:"}}],
    ]  # fmt: skip


def test_horizontal_tabs_are_laid_out_from_the_widget_corner():
    buttons = _buttons(_wire(_NAVTABS))
    assert [b["geometry"] for b in buttons] == [
        {"x": 20, "y": 30, "width": 200, "height": 28},
        {"x": 224, "y": 30, "width": 200, "height": 28},
        {"x": 428, "y": 30, "width": 200, "height": 28},
    ]


def test_default_layout_is_a_vertical_column_of_100x30_tabs():
    data = (
        _NAVTABS.replace(b"<direction>0</direction>", b"")
        .replace(b"<tab_width>200</tab_width>", b"")
        .replace(b"<tab_height>28</tab_height>", b"")
        .replace(b"<tab_spacing>4</tab_spacing>", b"")
    )
    buttons = _buttons(_wire(data))
    assert [(b["geometry"]["x"], b["geometry"]["y"]) for b in buttons] == [(20, 30), (20, 62), (20, 94)]
    assert {(b["geometry"]["width"], b["geometry"]["height"]) for b in buttons} == {(100, 30)}


def test_the_tab_row_is_a_frameless_group_that_says_the_body_is_not_embedded():
    (group,) = _wire(_NAVTABS)["root"]["children"]
    assert group["type"] == "group"
    assert any("navigation tabs converted to open-display buttons" in w for w in group.get("warnings", []))


def test_a_tab_without_a_file_gets_no_action_and_a_warning():
    data = _NAVTABS.replace(b"<file>_config.bob</file>", b"")
    wire = _wire(data)
    (group,) = wire["root"]["children"]
    assert "actions" not in group["children"][1]["props"]
    assert any("navigation tab 'Configuration' has no file" in w for w in group.get("warnings", []))


def test_tab_file_that_is_not_a_path_has_no_action():
    data = (
        b'<display version="2.0.0"><name>D</name><widget type="navtabs" version="2.0.0"><name>Tabs</name>'
        b"<tabs><tab><name>Bad</name><file>javascript:alert(1)</file></tab>"
        b"<tab><name>Good</name><file>good.bob</file></tab></tabs></widget></display>"
    )
    node = to_wire_dict(convert_bytes(data, kind="bob"))["root"]["children"][0]
    bad, good = node["children"]
    assert "actions" not in bad["props"]
    assert good["props"]["actions"][0]["file"] == "good.screen.json"
    assert "Tabs: navigation tab 'Bad' 'javascript:alert(1)' is not a file path; dropped" in node["warnings"]
