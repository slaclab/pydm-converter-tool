"""Dropped-prop recording for the ``.bob`` front-end.

A ``.bob`` prop the prop table has no Qt name for used to vanish without trace. The
adapter now records each such prop on the widget's ``dropped_props``, except the ones
another module consumes (a group's ``style`` feeds ``groups.group_style``). The IR
builder adds the Qt props its ``qtPropMap`` cannot place. ``dropped_props`` is never
emitted on the wire, so the goldens are unaffected.
"""

from __future__ import annotations


from pydmconverter.ir.emit import to_json
from pydmconverter.ir.model import WidgetNode
from pydmconverter.react import convert_bytes


def _bob_ir(data: bytes, **kwargs):
    """Convert ``.bob`` bytes through the public bytes entry point."""
    return convert_bytes(data, kind="bob", **kwargs)


def _display(body: str) -> bytes:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0">\n<name>D</name>\n{body}\n</display>'.encode()


def _walk(node: WidgetNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def _nodes(data: bytes) -> list[WidgetNode]:
    return list(_walk(_bob_ir(data).root))[1:]


def _only(data: bytes) -> WidgetNode:
    nodes = _nodes(data)
    assert len(nodes) == 1, [n.id for n in nodes]
    return nodes[0]


def test_embedded_resize_is_recorded():
    node = _only(
        _display(
            '<widget type="embedded" version="2.0.0"><name>E</name><file>other.bob</file>'
            "<resize>2</resize><width>100</width><height>50</height></widget>"
        )
    )
    assert "resize" in node.dropped_props


def test_action_button_tooltip_and_border_alarm_sensitive_are_recorded():
    node = _only(
        _display(
            '<widget type="action_button" version="2.0.0"><name>B</name><pv_name>X:Y</pv_name>'
            "<text>Go</text><tooltip>hint</tooltip><border_alarm_sensitive>false</border_alarm_sensitive></widget>"
        )
    )
    assert "tooltip" in node.dropped_props
    assert "border_alarm_sensitive" in node.dropped_props


def test_xyplot_show_legend_and_x_axis_are_consumed_not_dropped():
    node = _only(
        _display(
            '<widget type="xyplot" version="2.0.0"><name>P</name><title>T</title>'
            "<show_legend>false</show_legend>"
            "<x_axis><title>t</title><autoscale>true</autoscale></x_axis></widget>"
        )
    )
    assert "show_legend" not in node.dropped_props
    assert "x_axis" not in node.dropped_props
    assert "title" not in node.dropped_props


def test_xyplot_uncarried_sub_elements_are_not_recorded():
    node = _only(
        _display(
            '<widget type="xyplot" version="2.0.0"><name>P</name>'
            '<x_axis><title>t</title><title_font><font></font></title_font><color><color red="1" green="2" blue="3"/></color></x_axis>'
            "<y_axes><y_axis><title>y</title><on_right>true</on_right></y_axis></y_axes>"
            "<traces><trace><name>n</name><y_pv>A:B</y_pv><err_pv>A:E</err_pv></trace></traces></widget>"
        )
    )
    assert node.dropped_props == []


def test_group_style_is_consumed_not_dropped():
    nodes = _nodes(
        _display(
            '<widget type="group" version="2.0.0"><name>G</name><style>2</style>'
            "<width>200</width><height>100</height></widget>"
        )
    )
    assert nodes
    for node in nodes:
        assert node.dropped_props == [], (node.id, node.dropped_props)


def test_dropped_props_never_reach_the_wire():
    screen = _bob_ir(
        _display(
            '<widget type="action_button" version="2.0.0"><name>B</name><pv_name>X:Y</pv_name>'
            "<tooltip>hint</tooltip></widget>"
        )
    )
    assert "dropped_props" not in to_json(screen)
    assert "droppedProps" not in to_json(screen)
