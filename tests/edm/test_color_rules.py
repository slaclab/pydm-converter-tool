"""colors.list rule colours (EDM color_pkg.cc semantics).

A ``rule N name { <cond> : "colour" ... }`` index is a dynamic colour: EDM paints
it with the colour of the first condition that holds for a PV value, and with
the FIRST condition's colour when none holds (that colour is also the rule's
static pixel).
"""

from pydmconverter.edm.ir_adapter import _alarm_palette, _object_to_source, edm_file_to_ir
from pydmconverter.edm.parser import EDMObject
from pydmconverter.edm.parser_helpers import (
    get_color_by_index,
    parse_color_rule_condition,
    parse_colors_list,
)
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.registry import VendoredRegistry
from pydmconverter.ir.schema import validate_screen_json

_PALETTE = """4 0 0
max=0x10000

static 0 "Disconn/Invalid" { 65535 65535 65535 }
static 15 "Monitor: NORMAL" { 0 65535 0 }
static 20 "Monitor: MAJOR" { 65535 0 0 }
static 25 "Controller" { 0 0 65535 }
static 30 "Controller/alt" { 0 65535 65535 }
static 35 "Monitor: MINOR" { 65535 65535 0 }
static 46 "purple-46" { 32896 0 32896 }
static 81 "red-blink" { 65535 0 0 32762 0 0 }

rule 84 alarm {
 = -1 	: "purple-46"
 = 2 	: "Monitor: MAJOR"
 = 1 	: "Monitor: MINOR"
}
rule 86 rf_ilck_led {
 = 30	:"Controller/alt"
 = 30	:"Controller/alt"
 = 3	:"Controller"
}
rule 110 rfb_alarm {
 >=0 && < 1  : purple-46   # trailing comment
 >=1 && < 2  : "Monitor: NORMAL"
}
rule 111 joined {
 > 0 : &&
 < 5 : "Controller"
 default : "red-blink"
}

alarm {
  disconnected : "Disconn/Invalid"
  invalid      : "Disconn/Invalid"
  minor        : "Monitor: MINOR"
  major        : "Monitor: MAJOR"
  noalarm      : *
}
"""


def _palette(tmp_path):
    path = tmp_path / "colors.list"
    path.write_text(_PALETTE, encoding="utf-8")
    return parse_colors_list(str(path))


def test_result_names_with_colons_are_kept(tmp_path):
    """'= 2 : "Monitor: MAJOR"' has two colons; splitting on every colon dropped it."""
    rule = _palette(tmp_path)["rules"][84]
    assert [(c["terms"], c["color"]) for c in rule["conditions"]] == [
        ([("==", -1.0)], "purple-46"),
        ([("==", 2.0)], "Monitor: MAJOR"),
        ([("==", 1.0)], "Monitor: MINOR"),
    ]


def test_alarm_block_keeps_colour_names_with_colons(tmp_path):
    alarm = _palette(tmp_path)["alarm"]
    assert alarm["minor"] == "Monitor: MINOR"
    assert alarm["major"] == "Monitor: MAJOR"
    assert alarm["noalarm"] == "*"


def test_connector_and_unquoted_result_and_comment(tmp_path):
    first = _palette(tmp_path)["rules"][110]["conditions"][0]
    assert first["terms"] == [(">=", 0.0), ("<", 1.0)]
    assert first["connector"] == "&&"
    assert first["color"] == "purple-46"


def test_join_and_default(tmp_path):
    joined, closing, fallback = _palette(tmp_path)["rules"][111]["conditions"]
    assert joined["join"] == "&&" and joined["color"] is None
    assert closing["color"] == "Controller"
    assert fallback["default"] and fallback["color"] == "red-blink"


def test_condition_grammar_rejects_garbage():
    assert parse_color_rule_condition("banana") is None
    assert parse_color_rule_condition("= : red") is None
    assert parse_color_rule_condition("> 3") is None


def test_rule_index_resolves_to_first_condition_colour(tmp_path):
    """The rule's static pixel is its first result colour (was: 'Color index N not found')."""
    colors = _palette(tmp_path)
    assert get_color_by_index(colors, "index 84")["rgb"] == [32896, 0, 32896]
    assert get_color_by_index(colors, "index 86")["rgb"] == [0, 65535, 65535]
    # A leading join condition names no colour: the first result-bearing one counts.
    assert get_color_by_index(colors, "index 111")["rgb"] == [0, 0, 65535]
    assert get_color_by_index(colors, "index 86")["rule"] == 86


def test_undefined_index_is_still_none(tmp_path):
    assert get_color_by_index(_palette(tmp_path), "index 150") is None


# ── alarm rules follow the palette's alarm block ─────────────────────────────


def _obj(name, properties, w=10, h=10):
    obj = EDMObject.__new__(EDMObject)
    obj.name = name
    obj.properties = properties
    obj.x, obj.y, obj.width, obj.height = 0, 0, w, h
    return obj


def test_noalarm_star_keeps_the_static_colour_at_no_alarm(tmp_path):
    """colors.list "noalarm : *": NO_ALARM shows the part's own colour, not green."""
    colors = _palette(tmp_path)
    obj = _obj(
        "activeRectangleClass",
        {"lineColor": "index 25", "fillColor": "index 30", "fill": True, "alarmPv": "X:STAT", "lineAlarm": True},
    )
    (rule,) = _object_to_source(obj, colors).rules
    assert rule.target_property == "lineColor"
    assert rule.default == "#0000ff"
    assert rule.conditions == [("{0} == 1", "#ffff00"), ("{0} == 2", "#ff0000"), ("{0} >= 3", "#ffffff")]


def test_named_noalarm_and_missing_entries(tmp_path):
    colors = _palette(tmp_path)
    colors["alarm"] = {"noalarm": "Monitor: NORMAL", "major": "purple-46"}
    conditions, no_alarm = _alarm_palette(colors)
    assert no_alarm == "#00ff00"
    # An entry the block leaves out is palette index 0 (EDM specialIndex default).
    assert conditions == [("{0} == 1", "#ffffff"), ("{0} == 2", "#800080"), ("{0} >= 3", "#ffffff")]


def test_no_alarm_block_keeps_the_fixed_palette():
    conditions, no_alarm = _alarm_palette({"static": {}})
    assert no_alarm == "#00c000"
    assert conditions[1] == ("{0} == 2", "#ff0000")


# ── rule colours become value-driven IR rules ────────────────────────────────


def test_drawing_rule_colour_is_driven_by_alarm_pv(tmp_path):
    """rectangle_obj.cc: evalRule(fillColor, alarmPv->get_double())."""
    obj = _obj("activeRectangleClass", {"fillColor": "index 84", "fill": True, "alarmPv": "CRYO:STAT"})
    node = _object_to_source(obj, _palette(tmp_path))
    assert node.qt_props["brushColor"] == "#800080"  # static = first result colour
    (rule,) = node.rules
    assert rule.target_property == "fillColor"
    assert rule.pvs == [("CRYO:STAT", True)]
    assert rule.conditions == [("{0} == -1", "#800080"), ("{0} == 2", "#ff0000"), ("{0} == 1", "#ffff00")]
    assert rule.default == "#800080"


def test_text_control_rule_colour_follows_color_pv_and_dedupes(tmp_path):
    """x_text_dsp_obj.cc: colorPv's value callback re-evaluates fg and bg rules."""
    obj = _obj(
        "activeXTextDspClassnoedit",
        {"controlPv": "RF:VAL", "colorPv": "RF:ILCK", "fgColor": "index 86", "bgColor": "index 25"},
    )
    node = _object_to_source(obj, _palette(tmp_path))
    (rule,) = node.rules
    assert rule.target_property == "foregroundColor"
    assert rule.pvs == [("RF:ILCK", True)]
    # The repeated "= 30" collapses: only the first can ever match.
    assert rule.conditions == [("{0} == 30", "#00ffff"), ("{0} == 3", "#0000ff")]
    assert rule.default == "#00ffff"
    assert not any("dynamic color" in w for w in node.warnings)


def test_text_control_alarm_border_keeps_the_static_rule_colour(tmp_path):
    """With useAlarmBorder + fgAlarm EDM draws the text with fgColor.pixelIndex()."""
    props = {"controlPv": "RF:VAL", "colorPv": "RF:ILCK", "fgColor": "index 86", "fgAlarm": True}
    node = _object_to_source(_obj("activeXTextDspClassnoedit", {**props, "useAlarmBorder": True}), _palette(tmp_path))
    assert node.qt_props["foregroundColor"] == "#00ffff"
    assert node.rules == []


def test_rule_colour_without_a_driving_pv_stays_static(tmp_path):
    obj = _obj("activeXTextDspClassnoedit", {"controlPv": "RF:VAL", "fgColor": "index 86"})
    node = _object_to_source(obj, _palette(tmp_path))
    assert node.qt_props["foregroundColor"] == "#00ffff"
    assert node.rules == []


def test_textupdate_fg_uses_control_pv_and_fill_is_evaluated_at_zero(tmp_path):
    """textupdate.cc: the text colour takes colorPv, else the main PV; the fill
    ColorHelper is never given a value, so its rule is evalRule(index, 0)."""
    obj = _obj(
        "TextupdateClass",
        {"controlPv": "BCS:SUM", "fgColor": "index 110", "bgColor": "index 84", "fill": True},
    )
    node = _object_to_source(obj, _palette(tmp_path))
    (rule,) = node.rules
    assert rule.target_property == "foregroundColor"
    assert rule.pvs == [("BCS:SUM", True)]
    assert rule.conditions == [
        ("({0} >= 0) and ({0} < 1)", "#800080"),
        ("({0} >= 1) and ({0} < 2)", "#00ff00"),
    ]
    # Rule 84 at value 0: no condition holds -> its static (first) colour.
    assert node.qt_props["backgroundColor"] == "#800080"


def test_alarm_flag_and_rule_colour_merge_into_one_rule(tmp_path):
    """pvColor.cc: MINOR/MAJOR/INVALID paint alarm colours; NO_ALARM (noalarm *)
    paints the evaluated rule colour."""
    obj = _obj("activeRectangleClass", {"lineColor": "index 110", "alarmPv": "X:STAT", "lineAlarm": True})
    (rule,) = _object_to_source(obj, _palette(tmp_path)).rules
    assert rule.pvs == [("X:STAT.SEVR", True), ("X:STAT", True)]
    assert rule.conditions[:3] == [("{0} == 1", "#ffff00"), ("{0} == 2", "#ff0000"), ("{0} >= 3", "#ffffff")]
    assert rule.conditions[3] == ("({1} >= 0) and ({1} < 1)", "#800080")
    assert rule.default == "#800080"


def test_join_default_and_blink_note(tmp_path):
    obj = _obj("activeRectangleClass", {"lineColor": "index 111", "alarmPv": "X:VAL"})
    node = _object_to_source(obj, _palette(tmp_path))
    (rule,) = node.rules
    assert rule.conditions == [("({0} < 5) and ({0} > 0)", "#0000ff")]
    assert rule.default == "#ff0000"  # "default : red-blink", first (steady) state
    assert any("blinking colour 'red-blink'" in w for w in node.warnings)


def test_related_display_rule_colour_has_no_prop_to_drive(tmp_path):
    obj = _obj("relatedDisplayClass", {"bgColor": "index 84", "colorPv": "X:VAL", "displayFileName": ["a.edl"]})
    node = _object_to_source(obj, _palette(tmp_path))
    assert node.rules == []
    assert node.warnings == []


def test_rule_colour_screen_validates(tmp_path):
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE, encoding="utf-8")
    edl = tmp_path / "rules.edl"
    edl.write_text(
        """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 100
h 100
endScreenProperties

object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 110
fill
fillColor index 86
alarmPv "$(P):STAT"
lineAlarm
endObjectProperties
""",
        encoding="utf-8",
    )
    wire = to_wire_dict(edm_file_to_ir(edl, color_list_path=palette))
    validate_screen_json(wire)
    (rect,) = wire["root"]["children"]
    assert rect["props"]["lineColor"] == "#800080"
    assert rect["props"]["fillColor"] == "#00ffff"
    assert [r["targetProperty"] for r in rect["rules"]] == ["lineColor", "fillColor"]


# ── the registry passed in decides the rule targets ──────────────────────────


class _PropMapOverride:
    """A RegistryClient wrapping the vendored one, with one Qt class's qtPropMap
    entry for ``qt_prop`` replaced by ``spec`` (``None`` drops the prop)."""

    def __init__(self, qt_class, qt_prop, spec):
        self._inner = VendoredRegistry()
        self._qt_class, self._qt_prop, self._spec = qt_class, qt_prop, spec

    def by_id(self, widget_id):
        return self._inner.by_id(widget_id)

    def by_qt_class(self, qt_class):
        definition = self._inner.by_qt_class(qt_class)
        if definition is None or qt_class != self._qt_class:
            return definition
        prop_map = {k: v for k, v in definition.qt_prop_map.items() if k != self._qt_prop}
        if self._spec is not None:
            prop_map[self._qt_prop] = self._spec
        return definition.model_copy(update={"qt_prop_map": prop_map})


def test_colour_rule_target_follows_the_passed_registry(tmp_path):
    obj = _obj(
        "activeXTextDspClassnoedit",
        {"controlPv": "RF:VAL", "colorPv": "RF:ILCK", "fgColor": "index 86"},
    )
    colors = _palette(tmp_path)
    (default_rule,) = _object_to_source(obj, colors).rules
    assert default_rule.target_property == "foregroundColor"
    remapped = _PropMapOverride("PyDMLabel", "foregroundColor", {"to": "textColor"})
    (rule,) = _object_to_source(obj, colors, registry=remapped).rules
    assert rule.target_property == "textColor"
    dropped = _PropMapOverride("PyDMLabel", "foregroundColor", None)
    assert _object_to_source(obj, colors, registry=dropped).rules == []


def test_edm_file_to_ir_threads_its_registry_to_colour_rules(tmp_path):
    """A registry that drops the rectangle's fill colour drops its rule too,
    including for an object inside a group."""
    palette = tmp_path / "colors.list"
    palette.write_text(_PALETTE, encoding="utf-8")
    rect = """object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 110
fill
fillColor index 86
alarmPv "X:STAT"
lineAlarm
endObjectProperties
"""
    edl = tmp_path / "rules.edl"
    edl.write_text(
        """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 100
h 100
endScreenProperties

"""
        + rect
        + """
object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20

beginGroup

"""
        + rect
        + """
endGroup

endObjectProperties
""",
        encoding="utf-8",
    )
    registry = _PropMapOverride("PyDMDrawingRectangle", "brushColor", None)
    wire = to_wire_dict(edm_file_to_ir(edl, color_list_path=palette, registry=registry))
    top_rect, group = wire["root"]["children"]
    (nested_rect,) = group["children"]
    for node in (top_rect, nested_rect):
        assert [r["targetProperty"] for r in node["rules"]] == ["lineColor"]
