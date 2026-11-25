"""Text and the ground it sits on, coloured as a pair the theme can flip together.

A scheme turns some colours into roles (:mod:`pydmconverter.colors`) and leaves the
rest literal, one colour at a time. Text is readable only against what is painted
under it, so the two have to agree: a literal black label on a ``Display_Background``
role turns black-on-near-black in a dark theme, and a ``Text`` role on a literal white
panel turns white-on-white. This pass looks at every piece of text after lowering and
makes the text and its *ground* both roles or both literal wherever mixing them would
make the text unreadable in the dark theme.

The ground of a text widget is its own painted background, else the topmost painted
widget below it (earlier in paint order) that holds the text's centre, else the display
background. Then:

* A text colour the source names (``Text``, by default or authored) whose ground is a
  role becomes its role even when the parity rule kept it literal (the light values
  differ): the theme restyles the pair together. Likewise a widget whose own text and
  background are both named colours (a Phoebus ``textupdate``'s defaults) gets both
  roles or neither.
* A literal text colour the source does not name, whose ground is a role it cannot be
  read on in the dark theme, demotes that ground to its literal fallback.
* A role text colour on a literal ground it cannot be read on in the dark theme is
  written as its literal fallback.

"Cannot be read" is a contrast ratio below :data:`MIN_CONTRAST` (WCAG) between the two
dark values. Every change is counted in a ``pair:`` note, aggregated per document with
the parity notes.

Independently of any scheme, a ``pv-label`` (``PyDMLabel``) that paints no background
of its own gets an explicit transparent one: the source shows what is under it (Phoebus
``transparent``, EDM ``useDisplayBg`` or an unfilled ``Textupdate``), and a viewer must
not substitute its own readback field under a foreground chosen for that ground.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from pydmconverter.colors import RGBA, ColorContext, ColorValue, rgba_to_hex
from pydmconverter.ir.source import SourceNode

__all__ = ["MAX_RESTYLE", "MIN_CONTRAST", "TRANSPARENT", "NamedColor", "contrast", "pair_text_colors"]

#: The background a non-painting readback gets: fully transparent.
TRANSPARENT = "#00000000"
#: WCAG contrast ratio below which text counts as unreadable on its ground.
MIN_CONTRAST = 3.0
#: Largest per-channel change between a literal and its role's light value that pairing may apply.
MAX_RESTYLE = 32
#: Qt classes whose ``foregroundColor`` is text drawn straight onto the ground.
_TEXT_CLASSES = frozenset({"QLabel", "PyDMLabel", "QGroupBox"})
#: Qt classes a viewer paints a field under when no background is given.
_READBACK_CLASSES = frozenset({"PyDMLabel"})

#: ``(source name, resolved RGBA, source slot)`` of a named colour prop.
NamedColor = tuple[str, RGBA, str]
NamedOf = Callable[[SourceNode, str], "NamedColor | None"]


def _rgb(value: str) -> tuple[float, float, float, float] | None:
    digits = value.strip().lstrip("#")
    if len(digits) not in (6, 8):
        return None
    try:
        parts = [int(digits[i : i + 2], 16) for i in range(0, len(digits), 2)]
    except ValueError:
        return None
    alpha = parts[3] / 255 if len(parts) == 4 else 1.0
    return parts[0], parts[1], parts[2], alpha


def _luminance(rgb: tuple[float, float, float, float]) -> float:
    def channel(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b, _a = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float | None:
    """WCAG contrast ratio of two hex colours; ``None`` when either is not an opaque-enough hex."""
    a, b = _rgb(fg), _rgb(bg)
    if a is None or b is None or a[3] < 0.5 or b[3] < 0.5:
        return None
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _is_role(value: Any) -> bool:
    return isinstance(value, dict) and "$role" in value


def _dark(value: ColorValue, ctx: ColorContext) -> str:
    """The value shown in the dark theme: a role's dark value, else the literal itself."""
    if _is_role(value):
        return value.get("fallbackDark") or ctx.dark.get(value["$role"]) or value["fallback"]
    return value


def _transparent(value: Any) -> bool:
    if _is_role(value):
        return value["$role"] == "Transparent"
    rgb = _rgb(value) if isinstance(value, str) else None
    return rgb is not None and rgb[3] == 0


@dataclass
class _Ground:
    """A painted colour: a node's prop, or the display background (``node is None``)."""

    node: SourceNode | None
    prop: str


def _preorder(nodes: list[SourceNode]) -> Iterator[SourceNode]:
    for node in nodes:
        yield node
        yield from _preorder(node.children)


def _painted_prop(node: SourceNode) -> str | None:
    """The prop holding the colour ``node`` paints its box with, or ``None`` when it paints none."""
    props = node.qt_props
    if props.get("brushFill") and props.get("brushColor") is not None and not _transparent(props["brushColor"]):
        return "brushColor"
    bg = props.get("backgroundColor")
    if bg is not None and not props.get("flat") and not _transparent(bg) and "brushFill" not in props:
        return "backgroundColor"
    return None


def _contains(node: SourceNode, point: tuple[float, float]) -> bool:
    try:
        x, y, w, h = (float(v) for v in node.geometry)
    except (TypeError, ValueError):
        return False
    return x <= point[0] <= x + w and y <= point[1] <= y + h


def _centre(node: SourceNode) -> tuple[float, float] | None:
    try:
        x, y, w, h = (float(v) for v in node.geometry)
    except (TypeError, ValueError):
        return None
    return x + w / 2, y + h / 2


def _set(node: SourceNode, prop: str, value: ColorValue) -> None:
    """Set a static colour and the default of every rule on it that fell back to the old value."""
    old = node.qt_props.get(prop)
    node.qt_props[prop] = value
    for rule in node.rules:
        if rule.target_property == prop and rule.default == old:
            rule.default = value


def _role_value(named: NamedColor, ctx: ColorContext) -> dict | None:
    """The role a named colour is imported as, when the role only slightly restyles its literal.

    "Slightly": every channel of the role's light value within :data:`MAX_RESTYLE` of the
    literal (canopy-default's ``Text`` #161616 for Phoebus black), so the light theme looks
    as before; a bigger restyle stays with the parity rule.
    """
    name, rgb, slot = named
    role = ctx.role_for(name, slot)
    if role is None:
        return None
    light = _rgb(ctx.light.get(role, ""))
    if light is None or max(abs(a - b) for a, b in zip(light[:3], rgb[:3])) > MAX_RESTYLE:
        return None
    return {"$role": role, "fallback": rgba_to_hex(rgb)}


def pair_text_colors(
    nodes: list[SourceNode],
    background: ColorValue | None,
    ctx: ColorContext | None,
    named_of: NamedOf | None = None,
) -> ColorValue | None:
    """Pair every text colour in ``nodes`` with its ground (see the module docstring); return the display background.

    ``background`` is the display background the screen will get (``None``: the
    viewer's default, treated as literal). ``named_of(node, qt_prop)`` gives the source
    name of a colour prop, when the front end has one, so a literal kept by the parity
    rule can still become its role. ``ctx`` ``None`` (no scheme) only adds the
    transparent readback backgrounds. Mutates ``nodes``.
    """
    order = list(_preorder(nodes))
    for node in order:
        if node.qt_class in _READBACK_CLASSES and "backgroundColor" not in node.qt_props:
            node.qt_props["backgroundColor"] = TRANSPARENT
    if ctx is None:
        return background

    named_of = named_of or (lambda _node, _prop: None)
    display = {"value": background}
    texts = [n for n in order if n.qt_class in _TEXT_CLASSES and n.qt_props.get("foregroundColor") is not None]

    def light(value: ColorValue) -> str:
        return ctx.light.get(value["$role"], value["fallback"]) if _is_role(value) else value

    def readable(fg: ColorValue, bg: ColorValue) -> bool:
        """Readable in both themes (an undecidable contrast, e.g. a translucent colour, counts as readable)."""
        for a, b in ((light(fg), light(bg)), (_dark(fg, ctx), _dark(bg, ctx))):
            ratio = contrast(a, b)
            if ratio is not None and ratio < MIN_CONTRAST:
                return False
        return True

    def candidate(node: SourceNode, prop: str) -> dict | None:
        """The role a literal prop could become, or ``None``."""
        named = named_of(node, prop)
        if named is None or _is_role(node.qt_props.get(prop)):
            return None
        return _role_value(named, ctx)

    def promote(node: SourceNode, prop: str, role: dict) -> None:
        name, rgb, slot = named_of(node, prop)
        _set(node, prop, role)
        ctx.parity.waive(name, rgb, role["$role"], slot)
        ctx.note_pair(f"pair: color '{name}' written as scheme role '{role['$role']}' with its ground ({slot})")

    def get(ground: _Ground) -> ColorValue | None:
        return display["value"] if ground.node is None else ground.node.qt_props.get(ground.prop)

    def put(ground: _Ground, value: ColorValue) -> None:
        if ground.node is None:
            display["value"] = value
        else:
            _set(ground.node, ground.prop, value)

    index = {id(node): i for i, node in enumerate(order)}

    def ground_of(node: SourceNode) -> _Ground:
        own = _painted_prop(node)
        if own is not None:
            return _Ground(node, own)
        # Painted earlier and holding the text's centre: an ancestor, or a sibling drawn below it.
        centre = _centre(node)
        if centre is not None:
            for below in reversed(order[: index[id(node)]]):
                prop = _painted_prop(below)
                if prop is not None and _contains(below, centre):
                    return _Ground(below, prop)
        return _Ground(None, "background")

    # 1. A widget's own named text and background (a Phoebus textupdate's defaults): a role pair when both can be.
    for node in texts:
        if _painted_prop(node) != "backgroundColor":
            continue
        fg, bg = node.qt_props["foregroundColor"], node.qt_props["backgroundColor"]
        fg_role = fg if _is_role(fg) else candidate(node, "foregroundColor")
        bg_role = bg if _is_role(bg) else candidate(node, "backgroundColor")
        if fg_role is not None and bg_role is not None and readable(fg_role, bg_role):
            for prop, role in (("backgroundColor", bg_role), ("foregroundColor", fg_role)):
                if not _is_role(node.qt_props[prop]):
                    promote(node, prop, role)

    grounds = {id(node): ground_of(node) for node in texts}

    # 2. Literal text that cannot become a role, unreadable on a role ground in the dark theme: that ground goes literal.
    for node in texts:
        fg = node.qt_props["foregroundColor"]
        ground = grounds[id(node)]
        under = get(ground)
        if _is_role(fg) or not _is_role(under):
            continue
        role = candidate(node, "foregroundColor")
        if role is not None and readable(role, under):
            continue  # becomes its role in step 3
        ratio = contrast(fg, _dark(under, ctx))
        if ratio is not None and ratio < MIN_CONTRAST:
            put(ground, under["fallback"])
            where = "display background" if ground.node is None else f"{ground.prop} of a widget"
            ctx.note_pair(
                f"pair: scheme role '{under['$role']}' of the {where} kept as {under['fallback']}: "
                f"text {fg} on it is unreadable in the dark theme"
            )

    # 3. Text follows its ground: named text on a role becomes its role; a role unreadable on a literal goes literal.
    for node in texts:
        fg = node.qt_props["foregroundColor"]
        under = get(grounds[id(node)])
        if under is None or _transparent(under):
            continue
        if _is_role(under):
            role = candidate(node, "foregroundColor")
            if role is not None and readable(role, under):
                promote(node, "foregroundColor", role)
            continue
        if _is_role(fg):
            ratio = contrast(_dark(fg, ctx), under)
            if ratio is not None and ratio < MIN_CONTRAST:
                _set(node, "foregroundColor", fg["fallback"])
                ctx.note_pair(
                    f"pair: scheme role '{fg['$role']}' of a text kept as {fg['fallback']}: "
                    f"its dark value is unreadable on {under}"
                )
    return display["value"]
