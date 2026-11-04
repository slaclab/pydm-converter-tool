"""Tests for local-PV declarer planning (``pydmconverter.bob.local_pv.plan_declarers``).

A Phoebus ``loc://name<VType>(v)`` initializer on a widget with no channel (an
``action_button``) must still reach Canopy's page-scoped ``LocalPVService``, which
initialises only on a declaring subscribe. The adapter emits a hidden 0x0
``pv-label`` declarer for it, first among the root children.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import pytest

from pydmconverter.bob.local_pv import plan_declarers
from pydmconverter.bob.parser import parse_bob
from pydmconverter.ir.registry import VendoredRegistry


@pytest.fixture(scope="module")
def registry():
    return VendoredRegistry()


def _display(body: str):
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0"><name>t</name>{body}</display>'
    return parse_bob(xml.encode())


_BUTTON_XML = """
<widget type="action_button" version="3.0.0">
  <name>{name}</name>
  <pv_name>{pv}</pv_name>
  <actions>
    <action type="write_pv">
      <pv_name>$(pv_name)</pv_name>
      <value>1</value>
      <description>Go</description>
    </action>
  </actions>
</widget>
"""

_READER_XML = """
<widget type="textupdate" version="2.0.0">
  <name>{name}</name>
  <pv_name>{pv}</pv_name>
</widget>
"""


class _Template:
    """``str.format`` with the substituted values XML-escaped (``<VLong>`` -> ``&lt;VLong&gt;``)."""

    def __init__(self, text: str):
        self.text = text

    def format(self, **values: str) -> str:
        return self.text.format(**{k: escape(v) for k, v in values.items()})


_BUTTON = _Template(_BUTTON_XML)
_READER = _Template(_READER_XML)


def _plan(body: str, registry):
    display = _display(body)
    return display, plan_declarers(display.widgets, registry)


def _assert_declarer(node, widget: str, url: str):
    assert node.registry_id == "pv-label"
    assert node.qt_class == "PyDMLabel"
    assert node.qt_props == {"channel": url}
    assert "visible" not in node.qt_props
    assert tuple(node.geometry) == (0, 0, 0, 0)
    assert node.raw_props.get("name") == f"{widget}.init"
    assert node.warnings == []
    assert node.children == []


# --- action_button initializer ------------------------------------------------


def test_action_button_initializer_with_in_file_reader(registry):
    body = _BUTTON.format(name="Btn", pv="loc://trig<VLong>(1)") + _READER.format(name="Rd", pv="loc://trig")
    display, declarers = _plan(body, registry)
    assert len(declarers) == 1
    _assert_declarer(declarers[0], "Btn", "loc://trig?type=int&init=1")
    # the reader is untouched: still short-form
    assert display.widgets[1].props["pv_name"] == "loc://trig"


def test_action_button_initializer_without_reader(registry):
    body = _BUTTON.format(name="Action Button_7", pv="loc://testtriggercolorcode<VLong>(1)")
    _display_, declarers = _plan(body, registry)
    assert len(declarers) == 1
    _assert_declarer(declarers[0], "Action Button_7", "loc://testtriggercolorcode?type=int&init=1")


def test_macro_initializer_normalised(registry):
    body = _BUTTON.format(name="B", pv="loc://$(P):X<VDouble>(0.5)")
    _d, declarers = _plan(body, registry)
    assert [d.qt_props["channel"] for d in declarers] == ["loc://${P}:X?type=float&init=0.5"]


# --- widgets with a channel keep their initializer ------------------------------


def test_textupdate_initializer_yields_no_declarer(registry):
    body = _READER.format(name="Rd", pv="loc://x<VDouble>(3)")
    _d, declarers = _plan(body, registry)
    assert declarers == []


# --- non-initializers -----------------------------------------------------------


@pytest.mark.parametrize("pv", ["loc://x", "loc://x<VDouble>", "PLAIN:PV", "sim://noise", ""])
def test_action_button_without_initializer_yields_no_declarer(registry, pv):
    _d, declarers = _plan(_BUTTON.format(name="B", pv=pv), registry)
    assert declarers == []


# --- de-duplication and ordering -------------------------------------------------


def test_two_buttons_declaring_same_local_yield_one_declarer(registry):
    body = _BUTTON.format(name="A", pv="loc://s<VLong>(1)") + _BUTTON.format(name="B", pv="loc://s<VLong>(1)")
    _d, declarers = _plan(body, registry)
    assert len(declarers) == 1
    _assert_declarer(declarers[0], "A", "loc://s?type=int&init=1")


def test_declarers_follow_document_order_including_nested(registry):
    body = (
        '<widget type="group" version="2.0.0"><name>G</name>'
        + _BUTTON.format(name="Inner", pv="loc://a<VLong>(1)")
        + "</widget>"
        + _BUTTON.format(name="Outer", pv="loc://b<VLong>(2)")
    )
    _d, declarers = _plan(body, registry)
    assert [d.raw_props["name"] for d in declarers] == ["Inner.init", "Outer.init"]
    assert [d.qt_props["channel"] for d in declarers] == ["loc://a?type=int&init=1", "loc://b?type=int&init=2"]


def test_direct_action_target_initializer_is_declared(registry):
    body = """
    <widget type="action_button" version="3.0.0">
      <name>W</name>
      <actions>
        <action type="write_pv">
          <pv_name>loc://m&lt;VString&gt;("hi")</pv_name>
          <value>x</value>
        </action>
      </actions>
    </widget>
    """
    _d, declarers = _plan(body, registry)
    assert [d.qt_props["channel"] for d in declarers] == ["loc://m?type=str&init=hi"]


def test_parser_output_not_mutated(registry):
    display, _decl = _plan(_BUTTON.format(name="B", pv="loc://k<VLong>(4)"), registry)
    button = display.widgets[0]
    assert button.props["pv_name"] == "loc://k<VLong>(4)"
    assert button.actions[0].fields["pv_name"] == "loc://k<VLong>(4)"


def test_unsupported_vtype_is_not_declared_and_warns_via_callback(registry):
    warnings: list[str] = []
    display = _display(_BUTTON.format(name="B", pv="loc://e<VEnum>(0)"))
    declarers = plan_declarers(display.widgets, registry, warn=warnings.append)
    assert declarers == []
    assert warnings and warnings[0].startswith("B: ")
