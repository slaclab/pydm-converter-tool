"""Tests for the data tables in ``pydmconverter.bob.bob_qt``."""

from __future__ import annotations

import pytest

from pydmconverter.bob import bob_qt
from pydmconverter.ir.registry import VendoredRegistry


# --- default sizes: one row per table entry ------------------------------------


@pytest.mark.parametrize(
    ("widget_type", "expected"),
    [
        ("label", (100, 20)),
        ("textupdate", (100, 20)),
        ("textentry", (100, 20)),
        ("rectangle", (100, 20)),
        ("ellipse", (100, 50)),
        ("action_button", (100, 30)),
        ("bool_button", (100, 30)),
        ("led", (20, 20)),
        ("group", (300, 200)),
        ("embedded", (400, 300)),
        ("xyplot", (400, 300)),
        ("tabs", (400, 300)),
        ("combo", (100, 20)),  # anything else falls back to 100x20
    ],
)
def test_default_size(widget_type, expected):
    assert bob_qt.default_size(widget_type) == expected


def test_every_default_size_row_is_tested():
    tested = {
        "label", "textupdate", "textentry", "rectangle", "ellipse", "action_button",
        "bool_button", "led", "group", "embedded", "xyplot", "tabs",
    }  # fmt: skip
    assert set(bob_qt.DEFAULT_SIZES) == tested


def test_display_default_size():
    assert bob_qt.default_size(None) == (800, 600)
    assert bob_qt.default_size("display") == (800, 600)


# --- group inset -------------------------------------------------------------


def test_inset_style0_default_font():
    assert bob_qt.inset(0, 14) == (18, 18)


def test_inset_style1_default_font():
    assert bob_qt.inset(1, 14) == (1, 19)


def test_inset_style2_and_3():
    assert bob_qt.inset(2, 14) == (1, 1)
    assert bob_qt.inset(3, 14) == (0, 0)


def test_inset_font_size_scales_and_defaults():
    assert bob_qt.inset(0, 20) == (26, 26)
    assert bob_qt.inset(0) == (18, 18)
    assert bob_qt.inset(0, None) == (18, 18)


# --- class table ---------------------------------------------------------------


def test_every_class_table_registry_id_exists():
    registry = VendoredRegistry()
    ids = set(registry.widget_ids)
    for widget_type, (qt_class, registry_id) in bob_qt.BOB_TO_QT_CLASS.items():
        assert registry_id in ids, widget_type
        assert registry.by_id(registry_id).qt_class == qt_class, widget_type
    for style, (qt_class, registry_id) in bob_qt.GROUP_STYLE_TO_ID.items():
        assert registry_id in ids, style
        assert registry.by_id(registry_id).qt_class == qt_class, style


def test_class_table_covers_milestones_and_excludes_tabs():
    assert bob_qt.MILESTONE_TYPES <= set(bob_qt.BOB_TO_QT_CLASS)
    assert "tabs" not in bob_qt.BOB_TO_QT_CLASS
    assert bob_qt.qt_class_for("tabs") is None


@pytest.mark.parametrize(
    ("widget_type", "registry_id"),
    [
        ("action_button", "regular-button"),
        ("bool_button", "pv-button"),
        ("label", "text-label"),
        ("textupdate", "pv-label"),
        ("textentry", "pv-text-input"),
        ("led", "pv-led"),
        ("embedded", "embedded-display"),
        ("rectangle", "rectangle"),
        ("ellipse", "ellipse"),
        ("polygon", "polygon"),
        ("polyline", "line"),
        ("xyplot", "xy-plot"),
        ("group", "group-box"),
        ("picture", "image-view"),
    ],
)
def test_pinned_class_mapping(widget_type, registry_id):
    assert bob_qt.qt_class_for(widget_type)[1] == registry_id


def test_group_style_ids():
    assert bob_qt.GROUP_STYLE_TO_ID[0][1] == "group-box"
    assert bob_qt.GROUP_STYLE_TO_ID[1][1] == "group-box"
    assert bob_qt.GROUP_STYLE_TO_ID[2][1] == "group"
    assert bob_qt.GROUP_STYLE_TO_ID[3][1] == "group"


# --- prop table ----------------------------------------------------------------


def test_prop_targets_exist_in_registry_qt_prop_map():
    registry = VendoredRegistry()
    for widget_type, (_, registry_id) in bob_qt.BOB_TO_QT_CLASS.items():
        prop_map = registry.by_id(registry_id).qt_prop_map
        for phoebus_prop, qt_prop in bob_qt.BOB_TO_QT_PROP_BY_TYPE.get(widget_type, {}).items():
            if qt_prop is not None:
                assert qt_prop in prop_map, (widget_type, phoebus_prop, qt_prop)


def test_prop_lookup_overrides():
    assert bob_qt.qt_prop_for("textupdate", "pv_name") == "channel"
    assert bob_qt.qt_prop_for("action_button", "pv_name") is None
    assert bob_qt.qt_prop_for("rectangle", "background_color") == "brushColor"
    assert bob_qt.qt_prop_for("label", "background_color") == "backgroundColor"
    assert bob_qt.qt_prop_for("led", "line_color") is None
    assert bob_qt.qt_prop_for("rectangle", "line_color") == "penColor"
    assert bob_qt.qt_prop_for("label", "no_such_prop") is None


# --- defaults table ----------------------------------------------------------


def test_defaults_match_proposal():
    shape = {"transparent": False, "line_width": 3, "line_color": "#0000ff"}
    assert bob_qt.BOB_DEFAULTS["rectangle"] == {**shape, "background_color": "#1e90ff"}
    assert bob_qt.BOB_DEFAULTS["ellipse"] == {**shape, "background_color": "#1e90ff"}
    assert bob_qt.BOB_DEFAULTS["polygon"] == {**shape, "background_color": "#3232ff"}
    assert bob_qt.BOB_DEFAULTS["polyline"] == {"line_width": 3}
    # Phoebus-named widget colours are written as their names (resolved through
    # color.def / the built-ins: Text = #000000, Read_Background = #f0f0f0).
    assert bob_qt.BOB_DEFAULTS["label"] == {"transparent": True, "foreground_color": "Text"}
    assert bob_qt.BOB_DEFAULTS["textupdate"] == {
        "transparent": False,
        "foreground_color": "Text",
        "background_color": "Read_Background",
    }
    assert bob_qt.BOB_DEFAULTS["bool_button"] == {
        "on_label": "On",
        "off_label": "Off",
        "on_color": "#3cff3c",
        "off_color": "#3c643c",
    }
    assert bob_qt.BOB_DEFAULTS["led"] == {"on_color": "#00ff00", "off_color": "#3c643c"}
    assert bob_qt.DISPLAY_BACKGROUND_DEFAULT == "#ffffff"


# --- bool_button mode ------------------------------------------------------------


def test_bool_button_modes():
    assert bob_qt.BOOL_BUTTON_MODE[0] == {"buttonType": "toggle"}
    assert bob_qt.BOOL_BUTTON_MODE[1] == {"buttonType": "push", "pressValue": 1, "releaseValue": 0}
    assert bob_qt.BOOL_BUTTON_MODE[2] == {"buttonType": "push", "pressValue": 0, "releaseValue": 1}


def test_bool_button_mode_props_exist_on_pv_button():
    prop_map = VendoredRegistry().by_id("pv-button").qt_prop_map
    for props in bob_qt.BOOL_BUTTON_MODE.values():
        assert set(props) <= set(prop_map)


# --- rule targets --------------------------------------------------------------


def test_rule_direct_targets():
    assert set(bob_qt.RULE_DIRECT_TARGETS) == {"visible", "x", "y", "width", "height"}


@pytest.mark.parametrize(
    ("target", "kind"),
    [
        ("visible", "bool"),
        ("transparent", "bool"),
        ("x", "number"),
        ("line_width", "number"),
        ("background_color", "color"),
        ("foreground_color", "color"),
        ("text", "str"),
        ("something_else", "str"),
    ],
)
def test_rule_target_coercion(target, kind):
    assert bob_qt.rule_coercion(target) == kind
