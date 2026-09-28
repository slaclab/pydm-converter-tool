"""colors.list rule colours (EDM color_pkg.cc semantics).

A ``rule N name { <cond> : "colour" ... }`` index is a dynamic colour: EDM paints
it with the colour of the first condition that holds for a PV value, and with
the FIRST condition's colour when none holds (that colour is also the rule's
static pixel).
"""

from pydmconverter.edm.ir_adapter import _alarm_palette, _object_to_source
from pydmconverter.edm.parser import EDMObject
from pydmconverter.edm.parser_helpers import (
    get_color_by_index,
    parse_color_rule_condition,
    parse_colors_list,
)

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
