"""Tests for Phoebus group handling in ``pydmconverter.bob.groups``.

A Phoebus ``group`` offsets its children by its own origin plus a style-dependent
inset derived from the group's font size (``GroupRepresentation.updateChanges``).
"""

from __future__ import annotations

import pytest

from pydmconverter.bob.groups import child_geometry, group_font_size, group_node, group_style
from pydmconverter.bob.parser import BobWidget, parse_bob


def _group(style: int | None = None, *, font: float | None = None, children: str = "", x: int = 100, y: int = 100):
    style_xml = "" if style is None else f"<style>{style}</style>"
    font_xml = (
        "" if font is None else f'<font><font family="Liberation Sans" style="REGULAR" size="{font}"></font></font>'
    )
    xml = (
        '<display version="2.0.0"><name>d</name>'
        f'<widget type="group" version="2.0.0"><name>Box</name><x>{x}</x><y>{y}</y>'
        f"{style_xml}{font_xml}{children}</widget></display>"
    )
    return parse_bob(xml.encode()).widgets[0]


_CHILD = (
    '<widget type="label" version="2.0.0"><name>c</name><x>10</x><y>10</y><width>50</width><height>20</height></widget>'
)


# --- child_geometry: one row per style, default font ---------------------------


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (0, (128, 128, 50, 20)),
        (1, (111, 129, 50, 20)),
        (2, (111, 111, 50, 20)),
        (3, (110, 110, 50, 20)),
        (None, (128, 128, 50, 20)),  # absent <style> is GROUP_BOX
        (9, (128, 128, 50, 20)),  # unknown style falls back to style 0
    ],
)
def test_child_geometry_per_style(style, expected):
    group = _group(style, children=_CHILD)
    assert child_geometry(group, group.children[0]) == expected


def test_child_geometry_returns_ints():
    group = _group(0, children=_CHILD)
    assert all(isinstance(v, int) for v in child_geometry(group, group.children[0]))


# --- font size ----------------------------------------------------------------


def test_group_font_size_default_when_absent():
    assert group_font_size(_group(0)) == 14


def test_group_font_size_read_from_font_element():
    assert group_font_size(_group(0, font=20.0)) == 20


def test_child_geometry_uses_group_font():
    # i = 2 + int(1.2 * 20) = 26
    group = _group(0, font=20.0, children=_CHILD)
    assert child_geometry(group, group.children[0])[:2] == (136, 136)


def test_child_geometry_explicit_font_size_overrides_group_font():
    group = _group(0, font=20.0, children=_CHILD)
    assert child_geometry(group, group.children[0], 14)[:2] == (128, 128)


def test_fractional_font_size():
    # i = 2 + int(1.2 * 10.5) = 2 + 12 = 14
    group = _group(1, font=10.5, children=_CHILD)
    assert child_geometry(group, group.children[0])[:2] == (111, 125)


# --- child size ---------------------------------------------------------------


def test_child_without_size_uses_default_size():
    group = _group(3, children='<widget type="led" version="2.0.0"><name>l</name><x>5</x><y>6</y></widget>')
    assert child_geometry(group, group.children[0]) == (105, 106, 20, 20)


def test_child_without_position_sits_at_inset():
    group = _group(0, children='<widget type="label" version="2.0.0"><name>l</name></widget>')
    assert child_geometry(group, group.children[0]) == (118, 118, 100, 20)


def test_float_coordinates_are_truncated_to_ints():
    child = '<widget type="label" version="2.0.0"><name>c</name><x>10.0</x><y>10.7</y><width>50.0</width></widget>'
    group = _group(3, children=child)
    assert child_geometry(group, group.children[0]) == (110, 110, 50, 20)


def test_hand_built_widgets_without_x_y():
    group = BobWidget(type="group", name="g", props={"style": "3"})
    child = BobWidget(type="label", name="c", props={"x": "4", "y": "5"})
    assert child_geometry(group, child) == (4, 5, 100, 20)


# --- nesting ------------------------------------------------------------------


def test_nested_style0_groups_add_inset_twice():
    inner = (
        f'<widget type="group" version="2.0.0"><name>Inner</name><x>10</x><y>10</y><style>0</style>{_CHILD}</widget>'
    )
    outer = _group(0, children=inner)
    inner_widget = outer.children[0]
    ix, iy, iw, ih = child_geometry(outer, inner_widget)
    assert (ix, iy, iw, ih) == (128, 128, 300, 200)
    grandchild = child_geometry(inner_widget, inner_widget.children[0], origin=(ix, iy))
    # 100 + 18 + 10 + 18 + 10 on each axis
    assert grandchild == (156, 156, 50, 20)


def test_nested_groups_compose_mixed_styles():
    inner = (
        f'<widget type="group" version="2.0.0"><name>Inner</name><x>10</x><y>10</y><style>1</style>{_CHILD}</widget>'
    )
    outer = _group(3, children=inner)
    inner_widget = outer.children[0]
    origin = child_geometry(outer, inner_widget)[:2]
    assert origin == (110, 110)
    assert child_geometry(inner_widget, inner_widget.children[0], origin=origin)[:2] == (121, 139)


# --- group_style / group_node ------------------------------------------------


@pytest.mark.parametrize(("style", "expected"), [(None, 0), (0, 0), (1, 1), (2, 2), (3, 3)])
def test_group_style(style, expected):
    assert group_style(_group(style)) == expected


def test_group_style_non_numeric_falls_back_to_zero():
    assert group_style(BobWidget(type="group", name="g", props={"style": "bogus"})) == 0


@pytest.mark.parametrize("style", [0, 1, None])
def test_group_node_group_box_carries_title(style):
    assert group_node(_group(style)) == ("QGroupBox", "group-box", {"title": "Box"})


@pytest.mark.parametrize("style", [2, 3])
def test_group_node_plain_group_has_no_title(style):
    assert group_node(_group(style)) == (None, "group", {})


def test_group_node_unknown_style_is_group_box():
    assert group_node(_group(7)) == ("QGroupBox", "group-box", {"title": "Box"})
