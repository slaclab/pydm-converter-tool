"""Text colours and their ground become roles together or stay literal together (pydmconverter.pairing)."""

from __future__ import annotations

from pydmconverter.colors import ColorContext
from pydmconverter.ir.source import RuleSpec, SourceNode
from pydmconverter.pairing import MIN_CONTRAST, TRANSPARENT, contrast, pair_text_colors
from pydmconverter.scheme import SchemeResult

# Text's light value is not Phoebus black (as in canopy-default), so parity keeps it literal.
_LIGHT = {"Text": "#161616", "Display_Background": "#ffffff", "Read_Background": "#f4f4f4", "Background": "#ffffff"}
_DARK = {"Text": "#f4f4f4", "Display_Background": "#161616", "Read_Background": "#262626", "Background": "#161616"}


def _ctx() -> ColorContext:
    roles = list(_LIGHT)
    flat = {"roles": roles, "light": [_LIGHT[r] for r in roles], "dark": [_DARK[r] for r in roles]}
    scheme = SchemeResult(flat=flat, imports={"phoebus": {r: r for r in roles}}, meta={})
    return ColorContext.from_scheme(scheme, {"Text": (0, 0, 0, 255), "Read_Background": (240, 240, 240, 255)})


def _role(role: str, fallback: str) -> dict:
    return {"$role": role, "fallback": fallback}


_BG_ROLE = _role("Display_Background", "#ffffff")
_TEXT = ("Text", (0, 0, 0, 255), "foreground_color")
_READ = ("Read_Background", (240, 240, 240, 255), "background_color")


def _label(fg, geometry=(10, 10, 50, 20), qt_class="QLabel", **props) -> SourceNode:
    return SourceNode(qt_class=qt_class, qt_props={"foregroundColor": fg, **props}, geometry=geometry)


def _named(table: dict) -> callable:
    return lambda node, prop: table.get((id(node), prop))


def test_contrast_ratio():
    assert round(contrast("#000000", "#ffffff"), 1) == 21.0
    assert contrast("#000000", "#161616") < MIN_CONTRAST
    assert contrast("#f4f4f4", "#161616") > MIN_CONTRAST
    assert contrast("#000000", TRANSPARENT) is None


def test_named_text_on_a_role_ground_becomes_its_role_and_its_parity_note_goes():
    ctx = _ctx()
    label = _label("#000000")
    ctx.parity.record("Text", (0, 0, 0, 255), "#161616", "Text", "#000000", "foreground_color")
    background = pair_text_colors([label], _BG_ROLE, ctx, _named({(id(label), "foregroundColor"): _TEXT}))
    assert background == _BG_ROLE
    assert label.qt_props["foregroundColor"] == _role("Text", "#000000")
    notes = ctx.parity_notes()
    assert not any(n.startswith("parity: ") for n in notes)
    assert any(n.startswith("pair: color 'Text' written as scheme role 'Text'") for n in notes)


def test_named_text_on_a_literal_ground_stays_literal():
    ctx = _ctx()
    label = _label("#000000")
    assert pair_text_colors([label], "#ffffff", ctx, _named({(id(label), "foregroundColor"): _TEXT})) == "#ffffff"
    assert label.qt_props["foregroundColor"] == "#000000"


def test_unnamed_dark_text_on_a_role_display_background_keeps_the_background_literal():
    ctx = _ctx()
    label = _label("#000000")
    assert pair_text_colors([label], _BG_ROLE, ctx) == "#ffffff"
    assert label.qt_props["foregroundColor"] == "#000000"
    assert any("'Display_Background' of the display background kept as #ffffff" in n for n in ctx.parity_notes())


def test_unnamed_light_text_readable_on_the_dark_value_leaves_the_role():
    ctx = _ctx()
    label = _label("#ffff00")  # yellow reads on #161616
    assert pair_text_colors([label], _BG_ROLE, ctx) == _BG_ROLE


def test_demoted_display_background_takes_named_text_back_to_literal():
    # One literal black label keeps the canvas light, so the Text label next to it stays black too.
    ctx = _ctx()
    named, plain = _label("#000000"), _label("#000000", geometry=(100, 10, 50, 20))
    background = pair_text_colors([named, plain], _BG_ROLE, ctx, _named({(id(named), "foregroundColor"): _TEXT}))
    assert background == "#ffffff"
    assert named.qt_props["foregroundColor"] == "#000000"


def test_role_text_on_a_literal_light_panel_goes_literal():
    ctx = _ctx()
    panel = SourceNode(
        qt_class="PyDMDrawingRectangle",
        qt_props={"brushFill": True, "brushColor": "#e0e0e0"},
        geometry=(0, 0, 200, 100),
    )
    label = _label(_role("Text", "#000000"))
    pair_text_colors([panel, label], _BG_ROLE, ctx)
    assert label.qt_props["foregroundColor"] == "#000000"
    assert panel.qt_props["brushColor"] == "#e0e0e0"


def test_text_beside_a_panel_uses_the_display_background():
    ctx = _ctx()
    panel = SourceNode(
        qt_class="PyDMDrawingRectangle", qt_props={"brushFill": True, "brushColor": "#e0e0e0"}, geometry=(0, 0, 5, 5)
    )
    label = _label(_role("Text", "#000000"))
    pair_text_colors([panel, label], _BG_ROLE, ctx)
    assert label.qt_props["foregroundColor"] == _role("Text", "#000000")


def test_own_named_text_and_background_become_a_role_pair():
    ctx = _ctx()
    readback = _label("#000000", qt_class="PyDMLabel", backgroundColor="#f0f0f0")
    table = {(id(readback), "foregroundColor"): _TEXT, (id(readback), "backgroundColor"): _READ}
    pair_text_colors([readback], "#ffffff", ctx, _named(table))
    assert readback.qt_props["foregroundColor"] == _role("Text", "#000000")
    assert readback.qt_props["backgroundColor"] == _role("Read_Background", "#f0f0f0")


def test_rule_default_follows_the_static_colour():
    ctx = _ctx()
    label = _label("#000000")
    label.rules = [RuleSpec(target_property="foregroundColor", name="r", default="#000000")]
    pair_text_colors([label], _BG_ROLE, ctx, _named({(id(label), "foregroundColor"): _TEXT}))
    assert label.rules[0].default == _role("Text", "#000000")


def test_readback_without_a_background_gets_a_transparent_one_with_or_without_a_scheme():
    for ctx in (None, _ctx()):
        readback = _label("#000000", qt_class="PyDMLabel")
        static = _label("#000000")
        pair_text_colors([readback, static], "#bbbbbb", ctx)
        assert readback.qt_props["backgroundColor"] == TRANSPARENT
        assert "backgroundColor" not in static.qt_props
