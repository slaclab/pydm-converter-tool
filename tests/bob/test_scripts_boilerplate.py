"""Tests for matcher (a): the EDM alarm-colour boilerplate script -> severity rule.

The EDM-to-Phoebus converter stamps one fixed Jython script onto every alarm-sensitive
widget, in two textual variants that differ only in the target property
(``background_color`` / ``line_color``). Each one lowers to a rule on the target prop bound to ``<pv>.SEVR`` with the Phoebus palette.
"""

from __future__ import annotations

import pytest

from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS, rgba_to_hex
from pydmconverter.bob.parser import BobScript, BobWidget, parse_bob
from pydmconverter.bob.rules import RuleContext
from pydmconverter.bob.scripts import match_alarm_boilerplate

# --- fixtures ---

# Verbatim converter output, variant 1.
BACKGROUND_BOILERPLATE = """# EDM Alarm-sensitive color
from org.csstudio.display.builder.runtime.script import PVUtil
from org.csstudio.display.builder.model.persist import WidgetColorService
sevr = PVUtil.getSeverity(pvs[0])
cn = ( 'OK', 'MINOR', 'MAJOR', 'INVALID', 'DISCONNECTED' )[sevr]
widget.setPropertyValue('background_color', WidgetColorService.getColor(cn))"""

# Verbatim converter output, variant 2.
LINE_BOILERPLATE = BACKGROUND_BOILERPLATE.replace("'background_color'", "'line_color'")

# Same statements, reformatted: no comment, other quotes, other spacing, trailing
# comment, blank lines, CRLF. Normalisation must see through all of it.
REFORMATTED_BOILERPLATE = (
    "\r\n"
    "from org.csstudio.display.builder.runtime.script import  PVUtil\r\n"
    "\r\n"
    "from org.csstudio.display.builder.model.persist import WidgetColorService\r\n"
    "sevr=PVUtil.getSeverity( pvs[ 0 ] )   # read severity\r\n"
    'cn = ("OK","MINOR","MAJOR","INVALID","DISCONNECTED")[ sevr ]\r\n'
    'widget.setPropertyValue( "background_color" , WidgetColorService.getColor( cn ) )\r\n'
)


def _widget(script_text: str | None, pv: str, *, wtype: str = "rectangle", name: str = "R1") -> BobWidget:
    script = BobScript(name="", file="EmbeddedPy", text=script_text, pvs=[(pv, True)])
    return BobWidget(type=wtype, name=name, props={}, scripts=[script])


def _hex(name: str) -> str:
    return rgba_to_hex(BUILTIN_NAMED_COLORS[name])


EXPECTED_CONDITIONS = [
    ("{0}==1", _hex("MINOR")),
    ("{0}==2", _hex("MAJOR")),
    ("{0}>=3", _hex("INVALID")),
]


# --- matching variants ---


@pytest.mark.parametrize(
    ("text", "wtype", "target"),
    [
        (BACKGROUND_BOILERPLATE, "rectangle", "fillColor"),
        (LINE_BOILERPLATE, "rectangle", "lineColor"),
        (REFORMATTED_BOILERPLATE, "rectangle", "fillColor"),
    ],
    ids=["background_color", "line_color", "reformatted"],
)
def test_boilerplate_variant_lowers_to_severity_rule(text: str, wtype: str, target: str) -> None:
    widget = _widget(text, "SR10C___SHD2___BM02", wtype=wtype)
    ctx = RuleContext()
    rule = match_alarm_boilerplate(widget.scripts[0], widget, ctx)
    assert rule is not None
    assert rule.target_property == target
    assert rule.pvs == [("SR10C___SHD2___BM02.SEVR", True)]
    assert rule.conditions == EXPECTED_CONDITIONS
    assert rule.default == _hex("OK")
    assert ctx.warnings == []


def test_boilerplate_parsed_from_bob_xml() -> None:
    xml = f"""<display version="2.0.0">
  <widget type="rectangle" version="2.0.0">
    <name>EDM activeRectangleClass_1</name>
    <scripts>
      <script file="EmbeddedPy">
        <text><![CDATA[{LINE_BOILERPLATE}]]></text>
        <pv_name>$(P):STATUS</pv_name>
      </script>
    </scripts>
  </widget>
</display>""".encode()
    widget = parse_bob(xml).widgets[0]
    rule = match_alarm_boilerplate(widget.scripts[0], widget, RuleContext())
    assert rule is not None
    assert rule.target_property == "lineColor"
    assert rule.pvs == [("${P}:STATUS.SEVR", True)]


def test_field_pv_binds_record_severity() -> None:
    widget = _widget(BACKGROUND_BOILERPLATE, "SR01:BPM:X.VAL")
    rule = match_alarm_boilerplate(widget.scripts[0], widget, RuleContext())
    assert rule is not None
    assert rule.pvs == [("SR01:BPM:X.SEVR", True)]


def test_colours_come_from_named_colour_table() -> None:
    named = dict(BUILTIN_NAMED_COLORS)
    named["MAJOR"] = (10, 20, 30, 255)
    widget = _widget(BACKGROUND_BOILERPLATE, "A:B")
    rule = match_alarm_boilerplate(widget.scripts[0], widget, RuleContext(named_colors=named))
    assert rule is not None
    assert rule.conditions[1] == ("{0}==2", "#0a141e")


# --- loc/sim/calc guard ---


@pytest.mark.parametrize(
    "pv",
    ["loc://alarm_state", "loc://$(P):MEM_LOAD<VDouble>(0)", "sim://sine", "calc://x"],
)
def test_non_gateway_pv_is_skipped_with_warning(pv: str) -> None:
    widget = _widget(BACKGROUND_BOILERPLATE, pv, name="Rect_7")
    ctx = RuleContext()
    assert match_alarm_boilerplate(widget.scripts[0], widget, ctx) is None
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("Rect_7: ")
    assert "alarm-colour" in ctx.warnings[0]


# --- near misses ---


@pytest.mark.parametrize(
    "text",
    [
        # getSeverityString into text (corpus: examples/script_util).
        "from org.csstudio.display.builder.runtime.script import PVUtil\n"
        'widget.setPropertyValue("text", PVUtil.getSeverityString(pvs[0]))',
        # getSeverity into text (corpus: examples/script_util).
        "from org.csstudio.display.builder.runtime.script import PVUtil\n"
        'widget.setPropertyValue("text", str(PVUtil.getSeverity(pvs[0])))',
        # Palette reordered: would silently swap MINOR and MAJOR.
        BACKGROUND_BOILERPLATE.replace("'MINOR', 'MAJOR'", "'MAJOR', 'MINOR'"),
        # Second PV index.
        BACKGROUND_BOILERPLATE.replace("pvs[0]", "pvs[1]"),
        # An extra statement makes it a real script.
        BACKGROUND_BOILERPLATE + "\nwidget.setPropertyValue('visible', False)",
        # Index variable mismatch.
        BACKGROUND_BOILERPLATE.replace(")[sevr]", ")[other]"),
        # A commented-out boilerplate is not a boilerplate.
        "\n".join("# " + line for line in BACKGROUND_BOILERPLATE.splitlines()),
    ],
    ids=["severity-string", "severity-text", "palette-order", "pv-index", "extra-stmt", "index-var", "commented"],
)
def test_near_miss_does_not_match(text: str) -> None:
    widget = _widget(text, "A:B")
    ctx = RuleContext()
    assert match_alarm_boilerplate(widget.scripts[0], widget, ctx) is None
    assert ctx.warnings == []


def test_unreadable_script_does_not_match() -> None:
    widget = _widget(None, "A:B")
    assert match_alarm_boilerplate(widget.scripts[0], widget, RuleContext()) is None


def test_script_without_pv_does_not_match() -> None:
    script = BobScript(name="", file="EmbeddedPy", text=BACKGROUND_BOILERPLATE, pvs=[])
    widget = BobWidget(type="rectangle", name="R", props={}, scripts=[script])
    assert match_alarm_boilerplate(script, widget, RuleContext()) is None


def test_unsupported_target_warns() -> None:
    text = BACKGROUND_BOILERPLATE.replace("'background_color'", "'no_such_prop'")
    widget = _widget(text, "A:B", name="R9")
    ctx = RuleContext()
    assert match_alarm_boilerplate(widget.scripts[0], widget, ctx) is None
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("R9: ")
