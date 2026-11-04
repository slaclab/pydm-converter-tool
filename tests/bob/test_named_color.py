"""Tests for named colours becoming scheme roles (``pydmconverter.colors.named_color``).

The parity rule: a Phoebus colour name the scheme imports becomes ``{"$role", "fallback"}``
only when the role's light value equals the hex the converter writes today; otherwise the
literal is kept and one aggregated ``parity: `` note per (name, saved RGB, role light) is
prepended to the first non-declarer child of root. All panels and schemes are synthetic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS, coerce, color_from_element, color_from_text
from pydmconverter.colors import ColorContext, named_color
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.react import convert_bytes
from pydmconverter.scheme import SchemeResult, load_scheme


def _bob_ir(data: bytes, **kwargs):
    """Convert ``.bob`` bytes through the public bytes entry point."""
    return convert_bytes(data, kind="bob", **kwargs)


# Synthetic scheme: Text keeps Phoebus black; Grid is overridden; Display_Background is white.
_ROLES = {
    "Text": "#000000",
    "Grid": "#c6c6c6",
    "Display_Background": "#ffffff",
    "Transparent": "#ffffff00",
    "Read_Background": "#f0f0f0",
}
_IMPORTS = {
    "phoebus": {name: name for name in _ROLES} | {"Ghost": "NoSuchRole"},
    "edm": {"GLOBAL canvas": "Display_Background"},
}


def _scheme() -> SchemeResult:
    roles = list(_ROLES)
    flat = {"roles": roles, "light": [_ROLES[r] for r in roles], "dark": ["#101010"] * len(roles)}
    return SchemeResult(flat=flat, imports=_IMPORTS, meta={})


def _ctx(**kwargs) -> ColorContext:
    return ColorContext.from_scheme(_scheme(), dict(BUILTIN_NAMED_COLORS), **kwargs)


def _color(name: str | None = None, rgb: tuple[int, int, int] | None = None, tag: str = "foreground_color"):
    attrs = "" if name is None else f' name="{name}"'
    if rgb is not None:
        attrs += f' red="{rgb[0]}" green="{rgb[1]}" blue="{rgb[2]}"'
    return ET.fromstring(f"<{tag}><color{attrs}/></{tag}>")


# --------------------------------------------------------------------------
# named_color: the rule itself
# --------------------------------------------------------------------------
def test_mapped_and_equal_gives_role():
    ctx = _ctx()
    assert named_color("Text", (0, 0, 0, 255), "foreground_color", ctx) == {"$role": "Text", "fallback": "#000000"}
    assert ctx.parity_notes() == []


def test_mapped_transparent_compares_alpha():
    ctx = _ctx()
    assert named_color("Transparent", (255, 255, 255, 0), "background_color", ctx) == {
        "$role": "Transparent",
        "fallback": "#ffffff00",
    }


def test_mapped_and_different_gives_literal_and_one_aggregated_note():
    ctx = _ctx()
    for slot in ("foreground_color", "background_color", "foreground_color"):
        assert named_color("Grid", (128, 128, 128, 255), slot, ctx) == "#808080"
    notes = ctx.parity_notes()
    assert len(notes) == 1
    note = notes[0]
    assert note.startswith("parity: ")
    assert "'Grid'" in note and "#808080" in note and "#c6c6c6" in note
    assert "3 uses" in note
    assert "foreground_color, background_color" in note


def test_parity_notes_keyed_by_saved_rgb():
    ctx = _ctx()
    named_color("Grid", (128, 128, 128, 255), "a", ctx)
    named_color("Grid", (1, 2, 3, 255), "a", ctx)
    named_color("Grid", (1, 2, 3, 255), "b", ctx)
    notes = ctx.parity_notes()
    assert len(notes) == 2
    assert "1 use:" in notes[0] and "#808080" in notes[0]
    assert "2 uses" in notes[1] and "#010203" in notes[1]


@pytest.mark.parametrize("name", ["Background", "Ghost", None])
def test_unmapped_gives_literal(name):
    # Background is not imported; Ghost is imported to a role the scheme lacks; None is unnamed.
    ctx = _ctx()
    assert named_color(name, (255, 255, 255, 255), "background_color", ctx) == "#ffffff"
    assert ctx.parity_notes() == []


def test_no_context_gives_literal():
    assert named_color("Text", (0, 0, 0, 255), "foreground_color", None) == "#000000"


def test_import_kind_selects_the_map():
    ctx = _ctx(import_kind="edm")
    assert named_color("GLOBAL canvas", (255, 255, 255, 255), "bg", ctx) == {
        "$role": "Display_Background",
        "fallback": "#ffffff",
    }
    assert named_color("Text", (0, 0, 0, 255), "fg", ctx) == "#000000"


# --------------------------------------------------------------------------
# coercion routed through named_color
# --------------------------------------------------------------------------
def test_color_from_element_named_maps_to_role():
    assert color_from_element(_color("Text", (9, 9, 9)), ctx=_ctx()) == {"$role": "Text", "fallback": "#000000"}


def test_color_from_element_unknown_name_uses_saved_rgb_for_parity():
    # Display_Background is not a Phoebus built-in, so today's hex is the saved RGB.
    ctx = _ctx()
    assert color_from_element(_color("Display_Background", (255, 255, 255)), ctx=ctx) == {
        "$role": "Display_Background",
        "fallback": "#ffffff",
    }
    assert color_from_element(_color("Display_Background", (250, 250, 250)), ctx=ctx) == "#fafafa"
    assert len(ctx.parity_notes()) == 1


def test_color_from_element_slot_is_the_property_tag():
    ctx = _ctx()
    color_from_element(_color("Grid", tag="line_color"), ctx=ctx)
    assert "line_color" in ctx.parity_notes()[0]


def test_color_from_element_unnamed_stays_literal():
    assert color_from_element(_color(rgb=(0, 0, 0)), ctx=_ctx()) == "#000000"


@pytest.mark.parametrize(
    "elem",
    [
        _color("Text", (9, 9, 9)),
        _color("Grid", (1, 2, 3)),
        _color("Display_Background", (255, 255, 255)),
        _color("NotAName", (10, 20, 30)),
        _color("NotAName"),
        _color(rgb=(1, 2, 3)),
        _color(),
    ],
)
def test_no_scheme_is_identical_to_today(elem):
    plain_warnings: list[str] = []
    ctx_warnings: list[str] = []
    assert color_from_element(elem, None, ctx_warnings, None) == color_from_element(elem, None, plain_warnings)
    assert ctx_warnings == plain_warnings


def test_color_from_text_name_maps_and_hex_stays_literal():
    ctx = _ctx()
    assert color_from_text("Text", ctx=ctx) == {"$role": "Text", "fallback": "#000000"}
    assert color_from_text("#000000", ctx=ctx) == "#000000"
    assert color_from_text("#00000080", ctx=ctx) == "#000000"  # today's 6-digit truncation kept
    assert color_from_text("0,0,0", ctx=ctx) == "#000000"


def test_coerce_with_ctx_maps_a_named_string():
    assert coerce("color", " Text ", ctx=_ctx()) == {"$role": "Text", "fallback": "#000000"}
    assert coerce("color", "Text") == "#000000"
    assert coerce("color", "Grid", ctx=_ctx()) == "#808080"


def test_context_named_table_used_when_no_explicit_table():
    ctx = ColorContext.from_scheme(_scheme(), {"Text": (0, 0, 0, 255), "Custom": (0, 0, 0, 255)})
    # "Custom" is in the context's table but not imported by the scheme: literal.
    assert color_from_text("Custom", ctx=ctx) == "#000000"
    assert color_from_text("Text", ctx=ctx) == {"$role": "Text", "fallback": "#000000"}


# --------------------------------------------------------------------------
# Whole panels through _bob_ir(scheme=...)
# --------------------------------------------------------------------------
_DECLARER_BUTTON = """
<widget type="action_button" version="3.0.0">
  <name>B</name>
  <pv_name>loc://flag&lt;VLong&gt;(0)</pv_name>
  <actions><action type="write_pv"><pv_name>$(pv_name)</pv_name><value>1</value>
  <description>Go</description></action></actions>
</widget>
"""


def _panel(body: str, background: str = "") -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0"><name>t</name>{background}{body}</display>'
    ).encode()


def _textupdate(name: str, color_xml: str) -> str:
    return (
        f'<widget type="textupdate" version="2.0.0"><name>{name}</name><pv_name>sim://x</pv_name>'
        f"<foreground_color>{color_xml}</foreground_color></widget>"
    )


_PANEL = _panel(
    _DECLARER_BUTTON
    + _textupdate("T1", '<color name="Text" red="0" green="0" blue="0"/>')
    + _textupdate("T2", '<color name="Grid" red="128" green="128" blue="128"/>')
    + _textupdate("T3", '<color name="Grid" red="128" green="128" blue="128"/>'),
    '<background_color><color name="Display_Background" red="255" green="255" blue="255"/></background_color>',
)


def _children(wire: dict) -> list[dict]:
    return wire["root"]["children"]


def test_no_scheme_panel_output_identical_to_today():
    assert to_json(_bob_ir(_PANEL, scheme=None)) == to_json(_bob_ir(_PANEL))


def test_named_display_background_becomes_role():
    wire = to_wire_dict(_bob_ir(_PANEL, scheme=_scheme()))
    assert wire["root"]["props"]["backgroundColor"] == {"$role": "Display_Background", "fallback": "#ffffff"}


def test_named_display_background_with_default_scheme_becomes_role():
    wire = to_wire_dict(_bob_ir(_PANEL, scheme=load_scheme(None)))
    assert wire["root"]["props"]["backgroundColor"] == {"$role": "Display_Background", "fallback": "#ffffff"}


def test_widget_props_map_and_keep_literals():
    children = _children(to_wire_dict(_bob_ir(_PANEL, scheme=_scheme())))
    colors = [c["props"].get("foregroundColor") for c in children if c["props"].get("pv") == "sim://x"]
    assert colors == [{"$role": "Text", "fallback": "#000000"}, "#808080", "#808080"]


def test_parity_notes_land_on_first_non_declarer_child():
    children = _children(to_wire_dict(_bob_ir(_PANEL, scheme=_scheme())))
    declarer, first = children[0], children[1]
    # Declarers come first in top_level: a hidden 0x0 pv-label for the loc:// initializer.
    assert declarer["type"] == "pv-label"
    assert (declarer["geometry"]["width"], declarer["geometry"]["height"]) == (0, 0)
    assert not [w for w in declarer.get("warnings", []) if w.startswith("parity: ")]

    parity = [w for w in first.get("warnings", []) if w.startswith("parity: ")]
    assert len(parity) == 1
    assert "'Grid'" in parity[0] and "2 uses" in parity[0]
    assert first["warnings"][0] == parity[0]  # prepended
    for child in children[2:]:
        assert not [w for w in child.get("warnings", []) if w.startswith("parity: ")]


def test_parity_notes_are_per_document():
    scheme = _scheme()
    first = _children(to_wire_dict(_bob_ir(_PANEL, scheme=scheme)))[1]
    second = _children(to_wire_dict(_bob_ir(_PANEL, scheme=scheme)))[1]
    assert first["warnings"] == second["warnings"]
    assert "2 uses" in next(w for w in second["warnings"] if w.startswith("parity: "))


def test_no_parity_note_when_everything_maps():
    panel = _panel(_DECLARER_BUTTON + _textupdate("T1", '<color name="Text" red="0" green="0" blue="0"/>'))
    children = _children(to_wire_dict(_bob_ir(panel, scheme=_scheme())))
    for child in children:
        assert not [w for w in child.get("warnings", []) if w.startswith("parity: ")]


# --------------------------------------------------------------------------
# C1/C2: slot-aware imports and declared Phoebus source values
# --------------------------------------------------------------------------
# Grid splits by use: as a box background it is Grid_Fill (a restyle declaring the Phoebus
# value it replaces), as a line it stays Grid. OK is a restyle of Phoebus green; Text has no
# source and keeps the light rule.
_SLOT_ROLES = {"Grid": "#808080", "Grid_Fill": "#c6c6c6", "OK": "#006e00", "Text": "#000000"}
_SLOT_SOURCES = {"Grid_Fill": "#808080", "OK": "#00ff00"}
_SLOT_IMPORTS = {
    "phoebus": {
        "Grid": {"role": "Grid", "background_color": "Grid_Fill"},
        "OK": "OK",
        "Text": "Text",
        "Ghost": {"role": "Text", "line_color": "NoSuchRole"},
    },
}


def _slot_scheme(sources: dict[str, str] | None = None) -> SchemeResult:
    roles = list(_SLOT_ROLES)
    flat = {"roles": roles, "light": [_SLOT_ROLES[r] for r in roles], "dark": ["#101010"] * len(roles)}
    return SchemeResult(
        flat=flat, imports=_SLOT_IMPORTS, meta={}, sources=_SLOT_SOURCES if sources is None else sources
    )


def _slot_ctx(**kwargs) -> ColorContext:
    return ColorContext.from_scheme(_slot_scheme(**kwargs), dict(BUILTIN_NAMED_COLORS))


_GRAY = (128, 128, 128, 255)


def test_from_scheme_copies_sources():
    ctx = _slot_ctx()
    assert ctx.sources == _SLOT_SOURCES
    assert ColorContext.from_scheme(_scheme()).sources == {}


def test_role_for_without_slot_is_the_default_role():
    ctx = _slot_ctx()
    assert ctx.role_for("Grid") == "Grid"
    assert ctx.role_for("OK") == "OK"


def test_role_for_slot_named_by_the_entry():
    ctx = _slot_ctx()
    assert ctx.role_for("Grid", "background_color") == "Grid_Fill"
    assert ctx.role_for("Grid", "line_color") == "Grid"
    assert ctx.role_for("Grid", "foreground_color") == "Grid"
    assert ctx.role_for("OK", "background_color") == "OK"  # string entry: every slot


def test_role_for_slot_role_missing_from_scheme_is_none():
    ctx = _slot_ctx()
    assert ctx.role_for("Ghost", "line_color") is None
    assert ctx.role_for("Ghost", "background_color") == "Text"


def test_grid_as_background_gives_grid_fill():
    ctx = _slot_ctx()
    assert named_color("Grid", _GRAY, "background_color", ctx) == {"$role": "Grid_Fill", "fallback": "#808080"}
    assert ctx.parity_notes() == []


def test_grid_as_line_gives_grid():
    ctx = _slot_ctx()
    assert named_color("Grid", _GRAY, "line_color", ctx) == {"$role": "Grid", "fallback": "#808080"}
    assert ctx.parity_notes() == []


def test_restyled_role_emitted_for_its_source_value():
    ctx = _slot_ctx()
    # OK's light (#006e00) differs from the screen's #00ff00, but #00ff00 is the declared source.
    assert named_color("OK", (0, 255, 0, 255), "foreground_color", ctx) == {"$role": "OK", "fallback": "#00ff00"}
    assert ctx.parity_notes() == []


def test_restyled_role_drifted_value_gives_literal_and_note_naming_the_source():
    ctx = _slot_ctx()
    assert named_color("OK", (0, 254, 0, 255), "foreground_color", ctx) == "#00fe00"
    notes = ctx.parity_notes()
    assert len(notes) == 1
    note = notes[0]
    assert note.startswith("parity: ")
    assert "'OK'" in note and "#00fe00" in note
    assert "phoebus #00ff00" in note  # the compared value is the source, not the light
    assert "#006e00" not in note


def test_restyled_role_matching_its_light_but_not_its_source_is_literal():
    ctx = _slot_ctx()
    assert named_color("OK", (0, 110, 0, 255), "foreground_color", ctx) == "#006e00"
    assert len(ctx.parity_notes()) == 1


def test_source_compare_is_canonical():
    scheme = _slot_scheme(sources={"OK": "#0F0", "Grid_Fill": "#808080FF"})
    ctx = ColorContext.from_scheme(scheme)
    assert named_color("OK", (0, 255, 0, 255), "foreground_color", ctx) == {"$role": "OK", "fallback": "#00ff00"}
    assert named_color("Grid", _GRAY, "background_color", ctx) == {"$role": "Grid_Fill", "fallback": "#808080"}


def test_role_without_source_keeps_the_light_rule():
    ctx = _slot_ctx()
    assert named_color("Text", (0, 0, 0, 255), "foreground_color", ctx) == {"$role": "Text", "fallback": "#000000"}
    assert named_color("Text", (1, 1, 1, 255), "foreground_color", ctx) == "#010101"
    note = ctx.parity_notes()[0]
    assert "light #000000" in note


def test_without_sources_the_slot_role_uses_its_light():
    ctx = _slot_ctx(sources={})
    # Grid_Fill's light #c6c6c6 differs from Phoebus Grid #808080: literal and a note.
    assert named_color("Grid", _GRAY, "background_color", ctx) == "#808080"
    assert named_color("OK", (0, 255, 0, 255), "foreground_color", ctx) == "#00ff00"
    notes = ctx.parity_notes()
    assert len(notes) == 2
    assert "'Grid_Fill'" in notes[0] and "light #c6c6c6" in notes[0]


def test_slot_mismatch_notes_are_kept_apart_per_role():
    ctx = _slot_ctx(sources={})
    named_color("Grid", (1, 2, 3, 255), "background_color", ctx)
    named_color("Grid", (1, 2, 3, 255), "line_color", ctx)
    notes = ctx.parity_notes()
    assert len(notes) == 2
    assert "'Grid_Fill'" in notes[0] and "background_color" in notes[0]
    assert "'Grid'" in notes[1] and "line_color" in notes[1]


def test_no_scheme_ignores_slots_and_sources():
    assert named_color("Grid", _GRAY, "background_color", None) == "#808080"
    assert named_color("OK", (0, 255, 0, 255), "foreground_color", None) == "#00ff00"


def test_color_from_element_uses_the_property_tag_as_slot():
    ctx = _slot_ctx()
    assert color_from_element(_color("Grid", tag="background_color"), ctx=ctx) == {
        "$role": "Grid_Fill",
        "fallback": "#808080",
    }
    assert color_from_element(_color("Grid", tag="line_color"), ctx=ctx) == {"$role": "Grid", "fallback": "#808080"}


def test_with_slot_names_the_slot_of_a_generic_element_and_shares_parity():
    ctx = _slot_ctx(sources={})
    view = ctx.with_slot("background_color")
    assert view.parity is ctx.parity
    # A rule arm's <value> element and a bare name do not say which property they colour.
    value_elem = ET.fromstring('<value><color name="Grid" red="1" green="2" blue="3"/></value>')
    assert color_from_element(value_elem, ctx=view) == "#808080"
    assert color_from_text("Grid", ctx=view) == "#808080"
    notes = ctx.parity_notes()
    assert len(notes) == 1 and "'Grid_Fill'" in notes[0] and "2 uses: background_color" in notes[0]


def test_generic_element_without_slot_hint_keeps_its_tag():
    ctx = _slot_ctx(sources={})
    value_elem = ET.fromstring('<value><color name="Grid" red="1" green="2" blue="3"/></value>')
    # Without a slot hint the <value> wrapper is no property: the import's default role.
    assert color_from_element(value_elem, ctx=ctx) == {"$role": "Grid", "fallback": "#808080"}
    assert ctx.parity_notes() == []


def _rule_widget(prop: str, color_xml: str) -> str:
    return (
        f'<widget type="rectangle" version="2.0.0"><name>R</name>'
        f'<rules><rule name="r" prop_id="{prop}" out_exp="false">'
        f'<exp bool_exp="pv0 &gt; 0"><value>{color_xml}</value></exp>'
        f"<pv_name>sim://x</pv_name></rule></rules></widget>"
    )


def _rule_conditions(panel: bytes, scheme: SchemeResult | None) -> list:
    children = _children(to_wire_dict(_bob_ir(panel, scheme=scheme)))
    rules = [r for c in children for r in c.get("rules", [])]
    assert rules, children
    return [arm[1] if isinstance(arm, list) else arm.get("value") for rule in rules for arm in rule["conditions"]]


@pytest.mark.parametrize(
    ("prop", "role"),
    [("background_color", "Grid_Fill"), ("line_color", "Grid")],
)
def test_rule_arm_uses_the_rule_property_as_slot(prop, role):
    panel = _panel(_rule_widget(prop, '<color name="Grid" red="128" green="128" blue="128"/>'))
    assert _rule_conditions(panel, _slot_scheme()) == [{"$role": role, "fallback": "#808080"}]


def test_rule_arm_without_scheme_is_literal():
    panel = _panel(_rule_widget("background_color", '<color name="Grid" red="128" green="128" blue="128"/>'))
    assert _rule_conditions(panel, None) == ["#808080"]


def test_panel_grid_background_and_line_split_by_slot():
    widget = (
        '<widget type="rectangle" version="2.0.0"><name>R</name>'
        '<background_color><color name="Grid" red="128" green="128" blue="128"/></background_color>'
        '<line_color><color name="Grid" red="128" green="128" blue="128"/></line_color></widget>'
    )
    children = _children(to_wire_dict(_bob_ir(_panel(widget), scheme=_slot_scheme())))
    props = children[0]["props"]
    colors = {v["$role"] for v in props.values() if isinstance(v, dict) and "$role" in v}
    assert colors == {"Grid_Fill", "Grid"}


def test_default_scheme_grid_background_keeps_todays_parity():
    # canopy-default declares no sources: Grid_Fill's light differs from Phoebus Grid, so literal.
    ctx = ColorContext.from_scheme(load_scheme(None), dict(BUILTIN_NAMED_COLORS))
    assert ctx.role_for("Grid", "background_color") == "Grid_Fill"
    assert named_color("Grid", _GRAY, "background_color", ctx) == "#808080"
    assert "'Grid_Fill'" in ctx.parity_notes()[0]
