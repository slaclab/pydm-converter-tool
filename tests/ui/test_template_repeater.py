"""PyDMTemplateRepeater -> N embedded-display materialization (.ui adapter).

PyDM renders a template ``.ui`` once per record in a JSON dataSource, laid out
horizontally/vertically. The adapter fans the repeater out into one
embedded-display IR node per record (reusing the embedded-display path), each
referencing the converted template screen and carrying the record as its macros.
Missing/malformed dataSource falls back to the unknown-widget placeholder.
With ``confine_file_refs`` (untrusted input), refs outside the screen's directory
are not read at all.
"""

import json
from pathlib import Path

import pytest

from pydmconverter.react import convert_bytes
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


# --- confine_file_refs: an untrusted .ui's repeater refs stay in its directory ---

SECRET = "s3cret-do-not-inline"
OUTSIDE = "is outside the screen's directory; not read"


def _secret_beside_screen_dir(tmp_path: Path) -> tuple[Path, Path]:
    """A screen dir, and a JSON list holding SECRET in its parent (outside it)."""
    screen_dir = tmp_path / "screen"
    screen_dir.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps([{"Token": SECRET}]))
    return screen_dir, secret


def test_confined_rejects_datasource_outside_screen_dir(tmp_path):
    screen_dir, secret = _secret_beside_screen_dir(tmp_path)
    for data in (str(secret), "../secret.json"):
        ui = _write_screen(screen_dir, template="Widget.ui", data=data)
        # Unconfined, the repeater inlines the outside JSON as macros.
        assert SECRET in ui_file_to_ir(ui).model_dump_json()

        ir = ui_file_to_ir(ui, confine_file_refs=True)
        assert SECRET not in ir.model_dump_json()
        assert [c.type for c in ir.root.children] == ["unknown-widget"]
        warnings = ir.root.children[0].warnings
        assert any(f"dataSource {data!r} {OUTSIDE}, rendering placeholder" in w for w in warnings)
        assert not any("missing/unreadable" in w for w in warnings)


def test_confined_rejection_does_not_depend_on_outside_files(tmp_path):
    screen_dir, secret = _secret_beside_screen_dir(tmp_path)
    for data in (str(secret), "../secret.json"):
        ui = _write_screen(screen_dir, template="Widget.ui", data=data)
        secret.write_text(json.dumps([{"Token": SECRET}]))
        present = ui_file_to_ir(ui, confine_file_refs=True)
        secret.unlink()
        missing = ui_file_to_ir(ui, confine_file_refs=True)
        # A missing target gets the same warning (nothing outside is probed)...
        assert missing.root.children[0].warnings == present.root.children[0].warnings
        assert missing.model_dump_json() == present.model_dump_json()
        # ...where unconfined, the probe shows through.
        assert any("missing/unreadable" in w for w in ui_file_to_ir(ui).root.children[0].warnings)


def test_confined_outside_datasource_skips_basename_fallback(tmp_path):
    # The basename exists in the screen dir: unconfined falls back to it, confined
    # rejects the absolute ref outright.
    ui = _write_screen(tmp_path, template="Widget.ui", data="/nonexistent/deploy/data.json")
    assert [c.type for c in ui_file_to_ir(ui).root.children] == ["embedded-display"] * len(RECORDS)
    children = ui_file_to_ir(ui, confine_file_refs=True).root.children
    assert [c.type for c in children] == ["unknown-widget"]
    assert any(OUTSIDE in w for w in children[0].warnings)


@pytest.mark.parametrize(
    ("template", "data"),
    [
        ("Widget.ui", "data.json"),
        ("./Widget.ui", "sub/../data.json"),
        ("$PYDM/mc/Widget.ui", "$PYDM/mc/data.json"),  # deploy prefix -> basename fallback
    ],
)
def test_confined_in_dir_refs_expand_as_unconfined(tmp_path, template, data):
    ui = _write_screen(tmp_path, template=template, data=data)
    confined = ui_file_to_ir(ui, confine_file_refs=True)
    assert confined.model_dump_json() == ui_file_to_ir(ui).model_dump_json()
    embeds = confined.root.children
    assert [c.type for c in embeds] == ["embedded-display"] * len(RECORDS)
    assert [c.props["macros"] for c in embeds] == RECORDS
    assert [c.geometry.x for c in embeds] == [10, 60, 110]
    assert (embeds[0].geometry.width, embeds[0].geometry.height) == (50, 40)


def test_confined_template_outside_uses_repeater_rect(tmp_path):
    screen_dir = tmp_path / "screen"
    screen_dir.mkdir()
    outside = tmp_path / "Widget.ui"
    for template in (str(outside), "../Widget.ui"):
        # _write_screen also puts a Widget.ui in the screen dir, which a basename
        # fallback would find.
        ui = _write_screen(screen_dir, template=template, data="data.json")
        outside.write_text(TEMPLATE_UI)
        ir = ui_file_to_ir(ui, confine_file_refs=True)
        embeds = ir.root.children
        assert [c.type for c in embeds] == ["embedded-display"] * len(RECORDS)
        # Instances take the repeater rect (400x40), stepped by its width.
        assert [(c.geometry.x, c.geometry.width, c.geometry.height) for c in embeds] == [
            (10, 400, 40),
            (410, 400, 40),
            (810, 400, 40),
        ]
        assert any(f"template {template!r} {OUTSIDE}" in w for w in embeds[0].warnings)
        # Emitted as written (with "/" separators, as every screen ref is), never
        # rewritten by whether the outside file exists.
        expected = template.replace("\\", "/")[: -len(".ui")] + ".screen.json"
        assert all(c.props["file"] == expected for c in embeds)
        outside.unlink()
        assert ui_file_to_ir(ui, confine_file_refs=True).model_dump_json() == ir.model_dump_json()


def test_unconfined_absolute_datasource_still_read(tmp_path):
    ui = _write_screen(tmp_path, template="Widget.ui", data=str(tmp_path / "data.json"))
    embeds = ui_file_to_ir(ui).root.children
    assert [c.props["macros"] for c in embeds] == RECORDS


def test_convert_bytes_ui_confines_repeater_datasource(tmp_path):
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps([{"Token": SECRET}]))
    ui_bytes = REPEATER_UI.format(template="Widget.ui", data=secret).encode()
    # Unconfined, an uploaded .ui reads any JSON list the process can reach.
    assert SECRET in convert_bytes(ui_bytes, kind="ui", filename="u.ui", confine_file_refs=False).model_dump_json()

    # convert_bytes confines by default.
    for confined in (
        convert_bytes(ui_bytes, kind="ui", filename="u.ui"),
        convert_bytes(ui_bytes, kind="ui", filename="u.ui", confine_file_refs=True),
    ):
        assert SECRET not in confined.model_dump_json()
        assert [c.type for c in confined.root.children] == ["unknown-widget"]
        assert any(OUTSIDE in w for w in confined.root.children[0].warnings)
