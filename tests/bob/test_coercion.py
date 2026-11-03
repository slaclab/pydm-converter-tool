"""Tests for pydmconverter.bob.coercion (Phoebus .bob value coercion)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pydmconverter.bob import coercion
from pydmconverter.bob.coercion import (
    BUILTIN_NAMED_COLORS,
    alignment,
    coerce,
    color_from_element,
    font_size,
    load_color_def,
    normalize_macro_syntax,
    points,
)
from pydmconverter.ir.transforms import qt_alignment

COLOR_DEF = Path(__file__).parent / "fixtures" / "color.def"


def _xml(text: str) -> ET.Element:
    return ET.fromstring(text)


# --- named colours / color.def -------------------------------------------


def test_builtin_named_colors_match_phoebus_defaults():
    assert BUILTIN_NAMED_COLORS["MAJOR"] == (255, 0, 0, 255)
    assert BUILTIN_NAMED_COLORS["MINOR"] == (255, 128, 0, 255)
    assert BUILTIN_NAMED_COLORS["DISCONNECTED"] == (200, 0, 200, 200)
    assert BUILTIN_NAMED_COLORS["Button_Background"] == (210, 210, 210, 255)
    assert len(BUILTIN_NAMED_COLORS) == 13


def test_color_def_copy_reference_resolves_stop_to_major():
    named = load_color_def(COLOR_DEF)
    elem = _xml('<color name="STOP" red="1" green="2" blue="3"/>')
    assert color_from_element(elem, named) == "#ff0000"


def test_color_def_alias_resolves():
    named = load_color_def(COLOR_DEF)
    assert named["Halt"] == named["MAJOR"]
    assert named["On"] == BUILTIN_NAMED_COLORS["OK"]


def test_color_def_overrides_builtin_and_keeps_others():
    named = load_color_def(COLOR_DEF)
    assert named["Background"] == (250, 250, 250, 255)
    assert named["Grid"] == BUILTIN_NAMED_COLORS["Grid"]
    assert named["Semi"] == (10, 20, 30, 128)
    assert named["Header_Background"] == (77, 77, 77, 255)


def test_color_def_bad_lines_warn_and_are_skipped():
    warnings: list[str] = []
    named = load_color_def(COLOR_DEF, warnings)
    assert "Broken" not in named
    assert "Dangling" not in named
    assert any("Broken" in w for w in warnings)
    assert any("NoSuchColour" in w for w in warnings)


def test_load_color_def_does_not_mutate_builtins(tmp_path):
    path = tmp_path / "color.def"
    path.write_text("MAJOR = 1, 2, 3\n")
    assert load_color_def(path)["MAJOR"] == (1, 2, 3, 255)
    assert BUILTIN_NAMED_COLORS["MAJOR"] == (255, 0, 0, 255)


# --- color_from_element -----------------------------------------------------


def test_color_from_rgb_attributes():
    assert color_from_element(_xml('<color red="18" green="52" blue="86" alpha="255"/>')) == "#123456"


def test_color_from_rgb_attributes_keeps_partial_alpha():
    assert color_from_element(_xml('<color red="18" green="52" blue="86" alpha="128"/>')) == "#12345680"


def test_color_from_rgb_attributes_keeps_zero_alpha():
    assert color_from_element(_xml('<color red="18" green="52" blue="86" alpha="0"/>')) == "#12345600"


def test_rgba_to_hex_alpha():
    assert coercion.rgba_to_hex((18, 52, 86)) == "#123456"
    assert coercion.rgba_to_hex((18, 52, 86, 255)) == "#123456"
    assert coercion.rgba_to_hex((18, 52, 86, 128)) == "#12345680"
    assert coercion.rgba_to_hex((18, 52, 86, -5)) == "#12345600"


def test_color_from_property_wrapper_element():
    elem = _xml('<foreground_color><color red="255" green="0" blue="0"/></foreground_color>')
    assert color_from_element(elem) == "#ff0000"


def test_named_color_wins_over_saved_rgb():
    elem = _xml('<color name="OK" red="1" green="1" blue="1"/>')
    assert color_from_element(elem) == "#00ff00"


def test_unknown_named_color_uses_saved_rgb_silently():
    warnings: list[str] = []
    elem = _xml('<color name="Mystery" red="16" green="32" blue="48"/>')
    assert color_from_element(elem, BUILTIN_NAMED_COLORS, warnings) == "#102030"
    assert warnings == []


def test_unknown_named_color_without_rgb_falls_back_to_black():
    warnings: list[str] = []
    assert color_from_element(_xml('<color name="Mystery"/>'), None, warnings) == "#000000"
    assert warnings


def test_color_from_element_without_color_returns_none():
    assert color_from_element(None) is None
    assert color_from_element(_xml("<background_color/>")) is None


# --- font / alignment / points / macros ------------------------------------


def test_font_size_from_property_element():
    elem = _xml('<font><font name="Default" family="Liberation Sans" style="REGULAR" size="14.0"/></font>')
    assert font_size(elem) == 14
    assert isinstance(font_size(elem), int)


def test_font_size_inner_element_and_fractional():
    assert font_size(_xml('<font family="Sans" size="10.5"/>')) == 10.5


def test_font_size_missing_returns_none():
    assert font_size(None) is None
    assert font_size(_xml("<font/>")) is None
    assert font_size(_xml('<font><font size="big"/></font>')) is None


@pytest.mark.parametrize(
    ("horizontal", "vertical", "qt", "expected"),
    [
        ("0", None, "Qt::AlignLeft", "left"),
        ("1", None, "Qt::AlignHCenter", "center"),
        ("2", None, "Qt::AlignRight", "right"),
        ("RIGHT", "1", "Qt::AlignRight|Qt::AlignVCenter", "right"),
        ("1", "0", "Qt::AlignHCenter|Qt::AlignTop", "center"),
        ("0", "2", "Qt::AlignLeft|Qt::AlignBottom", "left"),
        (None, None, "Qt::AlignLeft", "left"),
    ],
)
def test_alignment_maps_to_qt_values_qt_alignment_reads(horizontal, vertical, qt, expected):
    result = alignment(horizontal, vertical)
    assert result == qt
    assert qt_alignment(result) == expected


def test_normalize_macro_syntax_reexported():
    assert normalize_macro_syntax("$(P):$(R)CALC") == "${P}:${R}CALC"
    assert coercion.normalize_macro_syntax is normalize_macro_syntax


def test_points():
    elem = _xml('<points><point x="0.0" y="10.0"/><point x="2.5" y="3"/><point x="bad" y="1"/></points>')
    assert points(elem) == [(0, 10), (2.5, 3)]
    assert points(None) == []


# --- coerce -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("bool", True),
        ("bool", False),
        ("number", 3),
        ("number", -2.5),
        ("color", "#12abef"),
        ("str", "hello world"),
    ],
)
def test_coerce_round_trips(kind, value):
    text = str(value).lower() if isinstance(value, bool) else str(value)
    result = coerce(kind, text)
    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize(
    ("kind", "text", "expected"),
    [
        ("bool", " TRUE ", True),
        ("bool", "0", False),
        ("number", "4.0", 4),
        ("number", "1e3", 1000),
        ("color", "255, 0, 0", "#ff0000"),
        ("color", "#ABC", "#aabbcc"),
        ("color", "MINOR", "#ff8000"),
        ("color", "#11223344", "#112233"),
        ("str", "$(P):SET", "${P}:SET"),
    ],
)
def test_coerce_accepts_variants(kind, text, expected):
    assert coerce(kind, text) == expected


def test_coerce_color_uses_color_def_names():
    named = load_color_def(COLOR_DEF)
    assert coerce("color", "STOP", named) == "#ff0000"


@pytest.mark.parametrize(("kind", "text"), [("bool", "maybe"), ("number", "abc"), ("color", "chartreuse-ish")])
def test_coerce_invalid_warns_and_keeps_text(kind, text):
    warnings: list[str] = []
    assert coerce(kind, text, warnings=warnings) == text
    assert len(warnings) == 1 and kind in warnings[0]


def test_coerce_unknown_kind_warns_and_keeps_text():
    warnings: list[str] = []
    assert coerce("widget", "$(P)", warnings=warnings) == "${P}"
    assert warnings
