from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
COLORS = FIXTURES / "colors.list"


def _convert(name: str):
    return edm_file_to_ir(FIXTURES / name, color_list_path=COLORS)


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------


def test_rectangle_line_and_fill_props():
    rect = _convert("graphics_rect.edl").root.children[0]
    assert rect.type == "rectangle"
    assert rect.props == {
        "lineColor": "#ffff00",
        "fillColor": "#0000ff",
        "fill": True,
        "lineWidth": 2,
        "lineStyle": "dashed",
    }
    assert rect.geometry.model_dump() == {"x": 20, "y": 20, "width": 100, "height": 50}


def test_rectangle_invisible_becomes_opacity_100():
    rect = _convert("graphics_rect.edl").root.children[1]
    assert rect.type == "rectangle"
    assert rect.props["opacity"] == 100


def test_rectangle_zero_width_promoted_and_alarm_rules():
    rect = _convert("graphics_rect.edl").root.children[2]
    assert rect.props["lineWidth"] == 1
    # alarmPv + lineAlarm/fillAlarm now become alarm-color rules, not a warning.
    assert rect.warnings == []
    assert [rule.target_property for rule in rect.rules] == ["lineColor", "fillColor"]
    assert all(rule.pvs[0].name.endswith(":STAT.SEVR") for rule in rect.rules)
    assert all(rule.default == "#00c000" for rule in rect.rules)


# ---------------------------------------------------------------------------
# Ellipse (activeCircleClass)
# ---------------------------------------------------------------------------


def test_ellipse_maps_from_circle_class():
    ellipse = _convert("graphics_circle.edl").root.children[0]
    assert ellipse.type == "ellipse"
    assert ellipse.props["lineColor"] == "#0000ff"
    assert ellipse.props["fill"] is True
    assert ellipse.props["fillColor"] == "#ffff00"


# ---------------------------------------------------------------------------
# Line (activeLineClass)
# ---------------------------------------------------------------------------


def test_line_bbox_geometry_beats_header_and_points_are_relative():
    line = _convert("graphics_line.edl").root.children[0]
    assert line.type == "line"
    geom = line.geometry.model_dump()
    assert (geom["x"], geom["y"], geom["width"], geom["height"]) == (100, 50, 100, 30)
    assert line.props["points"] == [{"x": 0, "y": 0}, {"x": 50, "y": 30}, {"x": 100, "y": 0}]
    assert line.props["arrowStart"] is False
    assert line.props["arrowEnd"] is True
    assert line.props["lineWidth"] == 1
    assert line.props["lineStyle"] == "dashed"


def test_line_without_arrows_prop_gets_explicit_false_both_ends():
    """No ``arrows`` prop at all still yields explicit booleans (the Line component
    defaults arrowEnd to TRUE when the prop is absent, so both must always be written)."""
    line = _convert("graphics_line.edl").root.children[1]
    assert line.props["arrowStart"] is False
    assert line.props["arrowEnd"] is False
    assert "arrowStart" in line.props
    assert "arrowEnd" in line.props


def test_line_filled_closed_polygon_becomes_polygon_widget():
    polygon = _convert("graphics_line.edl").root.children[2]
    assert polygon.type == "polygon"
    assert not any("open polyline" in w for w in polygon.warnings)
    assert polygon.props["fill"] is True
    assert polygon.props["fillColor"]
    assert polygon.props["closed"] is True
    assert [(p["x"], p["y"]) for p in polygon.props["points"]] == [(0, 0), (30, 40), (60, 0)]


# ---------------------------------------------------------------------------
# Arc (activeArcClass)
# ---------------------------------------------------------------------------


def test_arc_angle_convention_pin():
    """Pins the shared angle convention: 0 deg = east, CCW-positive, direct pass-through.

    A converter that flipped signs or offset by 90 deg would fail this test —
    startAngle -90 / totalAngle 180 must come through unchanged as startAngle -90 /
    spanAngle 180, not e.g. 0/180 or 90/-180.
    """
    arc = _convert("graphics_arc.edl").root.children[0]
    assert arc.type == "arc"
    assert arc.props["startAngle"] == -90
    assert arc.props["spanAngle"] == 180
    assert arc.props["fill"] is True
    assert arc.props["fillColor"] == "#0000ff"


def test_arc_missing_total_angle_defaults_to_full_ellipse():
    arc = _convert("graphics_arc.edl").root.children[1]
    assert arc.props["spanAngle"] == 360


def test_arc_fill_mode_warns():
    arc = _convert("graphics_arc.edl").root.children[2]
    assert any("fillMode" in w for w in arc.warnings)


# ---------------------------------------------------------------------------
# Bars (activeBarClass / activeSlacBarClass / activeVsBarClass)
# ---------------------------------------------------------------------------


def test_bar_class_maps_to_pv_progress_bar():
    bar = _convert("graphics_bars.edl").root.children[0]
    assert bar.type == "pv-progress-bar"
    assert bar.props["pv"] == "${P}:PRESSURE"
    assert bar.props["min"] == 0
    assert bar.props["max"] == 25
    assert bar.props["orientation"] == "vertical"
    assert any("indicatorColor" in w for w in bar.warnings)


def test_slac_bar_class_horizontal():
    bar = _convert("graphics_bars.edl").root.children[1]
    assert bar.props["orientation"] == "horizontal"
    assert any("label" in w and "showScale" in w for w in bar.warnings)


def test_vs_bar_defaults_to_vertical():
    bar = _convert("graphics_bars.edl").root.children[2]
    assert bar.props["orientation"] == "vertical"
    assert any("maxPv" in w for w in bar.warnings)


# ---------------------------------------------------------------------------
# Group materialization
# ---------------------------------------------------------------------------


def test_group_materializes_as_group_node():
    root = _convert("graphics_group.edl").root
    group = root.children[0]
    assert group.type == "group"
    assert group.props == {"layoutMode": "absolute"}
    assert group.geometry.model_dump() == {"x": 10, "y": 10, "width": 200, "height": 120}

    assert len(group.rules) == 1
    rule = group.rules[0]
    assert rule.target_property == "visible"
    assert [pv.name for pv in rule.pvs] == ["${P}:SHOW"]
    assert rule.conditions[0].expression == "{0} != 0"
    assert rule.default is False


def test_group_children_keep_absolute_geometry_with_no_inherited_rules():
    group = _convert("graphics_group.edl").root.children[0]
    label, nested_group = group.children

    assert label.type == "text-label"
    assert label.rules == []
    assert label.geometry.model_dump() == {"x": 20, "y": 20, "width": 100, "height": 18}

    assert nested_group.type == "group"
    assert nested_group.rules == []
    assert nested_group.geometry.model_dump() == {"x": 30, "y": 50, "width": 100, "height": 60}

    rectangle = nested_group.children[0]
    assert rectangle.type == "rectangle"
    assert rectangle.geometry.model_dump() == {"x": 40, "y": 60, "width": 60, "height": 30}


def test_top_level_widget_after_group_has_its_own_range_rule():
    root = _convert("graphics_group.edl").root
    text_input = root.children[1]
    assert text_input.type == "pv-text-input"
    assert len(text_input.rules) == 1
    rule = text_input.rules[0]
    assert [pv.name for pv in rule.pvs] == ["${P}:MODE"]
    assert rule.conditions[0].expression == "({0} >= 1.0) and ({0} < 3.0)"


# ---------------------------------------------------------------------------
# Schema validation + determinism across every fixture in this module
# ---------------------------------------------------------------------------

GRAPHICS_FIXTURES = [
    "graphics_rect.edl",
    "graphics_circle.edl",
    "graphics_line.edl",
    "graphics_arc.edl",
    "graphics_bars.edl",
    "graphics_group.edl",
]


def test_every_fixture_validates_against_schema():
    for name in GRAPHICS_FIXTURES:
        screen = _convert(name)
        assert validate_screen_json(to_wire_dict(screen)) == [], f"{name} failed schema validation"


def test_group_fixture_conversion_is_deterministic():
    """Same input -> byte-identical IR (D3 round-trip stability across runs)."""
    assert to_json(_convert("graphics_group.edl")) == to_json(_convert("graphics_group.edl"))
