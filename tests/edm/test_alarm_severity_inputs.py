"""Alarm-colour rules on a CALC or LOC alarmPv (IR target).

An alarm-sensitive EDM part takes the alarm severity of its alarmPv. A CALC PV's
severity is the highest of its PV arguments' (calc_pv_factory.cc
``CALC_ProcessVariable::recalc``; constant arguments don't count), and a LOC
variable is NO_ALARM once it has a value (loc_pv_factory.cc). Appending
``.SEVR`` to a ``calc://`` or ``loc://`` address named no channel at all.
"""

import itertools

from pydmconverter.edm.ir_adapter import _alarm_rules, _object_to_source, edm_file_to_ir
from pydmconverter.edm.parser import EDMObject
from pydmconverter.edm.parser_helpers import parse_colors_list
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

_PALETTE = """4 0 0
max=0x10000

static 0 "Disconn/Invalid" { 65535 65535 65535 }
static 15 "Monitor: NORMAL" { 0 65535 0 }
static 20 "Monitor: MAJOR" { 65535 0 0 }
static 25 "Controller" { 0 0 65535 }
static 35 "Monitor: MINOR" { 65535 65535 0 }
static 46 "purple-46" { 32896 0 32896 }

rule 110 rfb_alarm {
 >=0 && < 1  : purple-46
 >=1 && < 2  : "Monitor: NORMAL"
}

alarm {
  disconnected : "Disconn/Invalid"
  invalid      : "Disconn/Invalid"
  minor        : "Monitor: MINOR"
  major        : "Monitor: MAJOR"
  noalarm      : *
}
"""


def _obj(name, properties):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, 10, 10
    return obj


def _rect(alarm_pv, **extra):
    return _obj("activeRectangleClass", {"alarmPv": alarm_pv, "lineAlarm": True, **extra})


def _evaluate(rule, severities):
    """The colour the rule paints for these {N} values (first true condition wins)."""
    for expression, value in rule.conditions:
        for index, severity in enumerate(severities):
            expression = expression.replace(f"{{{index}}}", str(severity))
        if eval(expression):
            return value
    return rule.default


def test_calc_alarm_pv_reads_each_pv_argument_severity():
    calc = "calc://c?A=ca://X:ONE&B=ca://X:TWO.STAT&expr=A+B"
    (rule,) = _alarm_rules(_rect(calc))
    # A field reference is stripped as for a plain alarmPv: severity is record-level.
    assert rule.pvs == [("X:ONE.SEVR", True), ("X:TWO.SEVR", True)]


def test_calc_alarm_colour_is_that_of_the_highest_argument_severity():
    calc = "calc://c?A=ca://X:ONE&B=ca://X:TWO&C=ca://X:THREE&expr=A+B+C"
    (rule,) = _alarm_rules(_rect(calc))
    (single,) = _alarm_rules(_rect("X:ONE"))
    assert len(rule.pvs) == 3
    for severities in itertools.product(range(4), repeat=3):
        assert _evaluate(rule, severities) == _evaluate(single, [max(severities)]), severities


def test_constant_and_loc_arguments_have_no_severity():
    # A constant as main writes it (ca://15) and inlined; a LOC argument cut at
    # its own & (unescaped) and percent-escaped; and a junk key from an
    # unescaped & in the expression.
    calcs = [
        "calc://c?A=ca://15&B=ca://X:PV&expr=A*B",
        "calc://c?A=ca://X:PV&B=ca://-1.5e3&expr=A*B",
        "calc://c?A=ca://X:PV&expr=A*15",
        "calc://c?A=ca://loc://q?type=float&init=0.15&B=ca://X:PV&expr=A*B",
        "calc://c?A=loc://q%3Ftype%3Dfloat%26init%3D0.15&B=ca://X:PV&expr=A*B",
        "calc://c?A=ca://X:PV&expr=((A&4)==4)",
    ]
    for calc in calcs:
        (rule,) = _alarm_rules(_rect(calc))
        assert rule.pvs == [("X:PV.SEVR", True)], calc
        assert rule.conditions == [("{0} == 1", "#ffff00"), ("{0} == 2", "#ff0000"), ("{0} >= 3", "#ffffff")]


def test_loc_alarm_pv_shows_the_no_alarm_colour():
    for alarm_pv in (
        "loc://flag?type=int&init=0",
        "loc://flag",
        "calc://c?A=ca://15&B=loc://flag&expr=A+B",
    ):
        rect = _rect(alarm_pv, fillAlarm=True, fill=True, lineColor="rgb 0 0 65535", fillColor="rgb 0 0 65535")
        rules = _alarm_rules(rect)
        assert [r.target_property for r in rules] == ["lineColor", "fillColor"]
        for rule in rules:
            assert (rule.pvs, rule.conditions) == ([], [])
        # No severity can change it: the NO_ALARM colour (green without a palette
        # alarm block) becomes the static colour, and no rule is left.
        node = _object_to_source(rect)
        assert node.rules == []
        assert (node.qt_props["penColor"], node.qt_props["brushColor"]) == ("#00c000", "#00c000")


def test_loc_alarm_pv_on_text_keeps_its_own_colour_and_drops_alarm_sensitivity(tmp_path):
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE, encoding="utf-8")
    obj = _obj(
        "activeXTextDspClassnoedit",
        {"controlPv": "X:VAL", "fgColor": "index 25", "alarmPv": "loc://flag?type=int&init=0", "fgAlarm": True},
    )
    node = _object_to_source(obj, parse_colors_list(str(palette)))
    assert node.rules == []
    assert node.qt_props["foregroundColor"] == "#0000ff"  # noalarm : * -> the part's own colour
    # alarmPv, not the widget's own channel, is the alarm source.
    assert "alarmSensitiveContent" not in node.qt_props


def test_loc_alarm_pv_with_a_named_no_alarm_colour_hides_the_colour_rule(tmp_path):
    """pvColor.cc: a named NO_ALARM colour replaces the rule colour while alarm-sensitive."""
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE.replace("noalarm      : *", 'noalarm      : "Monitor: NORMAL"'), encoding="utf-8")
    rect = _rect("loc://flag?type=int&init=0", lineColor="index 110")
    node = _object_to_source(rect, parse_colors_list(str(palette)))
    assert node.rules == []
    assert node.qt_props["penColor"] == "#00ff00"


def test_colour_rule_merges_after_the_calc_severity_channels(tmp_path):
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE, encoding="utf-8")
    colors = parse_colors_list(str(palette))
    calc = "calc://c?A=ca://X:ONE&B=ca://X:TWO&expr=A+B"
    (rule,) = _object_to_source(_rect(calc, lineColor="index 110"), colors).rules
    assert rule.pvs == [("X:ONE.SEVR", True), ("X:TWO.SEVR", True), (calc, True)]
    assert rule.conditions[3:] == [("({2} >= 0) and ({2} < 1)", "#800080"), ("({2} >= 1) and ({2} < 2)", "#00ff00")]
    # A LOC alarmPv has no severity channel: the value ladder alone, on {0}.
    loc = "loc://flag?type=int&init=0"
    (rule,) = _object_to_source(_rect(loc, lineColor="index 110"), colors).rules
    assert rule.pvs == [(loc, True)]
    assert rule.conditions == [("({0} >= 0) and ({0} < 1)", "#800080"), ("({0} >= 1) and ({0} < 2)", "#00ff00")]


_EDL = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 200
h 200
endScreenProperties
"""

_RECT = """
object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x {x}
y 10
w 20
h 20
lineColor index 25
alarmPv "{alarm_pv}"
lineAlarm
endObjectProperties
"""


def test_calc_and_loc_alarm_pvs_in_a_screen(tmp_path):
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE, encoding="utf-8")
    edl = tmp_path / "alarms.edl"
    alarm_pvs = [r"CALC\\{A+B}(X:ONE,X:TWO.STAT)", r"CALC\\{A*B}(15,X:THREE)", r"LOC\\flag=i:0", "X:PLAIN"]
    edl.write_text(
        _EDL + "".join(_RECT.format(x=10 + 30 * i, alarm_pv=pv) for i, pv in enumerate(alarm_pvs)), encoding="utf-8"
    )
    wire = to_wire_dict(edm_file_to_ir(edl, color_list_path=palette))
    assert validate_screen_json(wire) == []
    assert not any(".SEVR" in formula["expression"] for formula in wire.get("formulas", []))
    pvs = [[pv["name"] for rule in rect.get("rules", []) for pv in rule["pvs"]] for rect in wire["root"]["children"]]
    assert pvs == [["X:ONE.SEVR", "X:TWO.SEVR"], ["X:THREE.SEVR"], [], ["X:PLAIN.SEVR"]]
    # The LOC alarmPv's part keeps its own colour (noalarm : *).
    assert wire["root"]["children"][2]["props"]["lineColor"] == "#0000ff"
