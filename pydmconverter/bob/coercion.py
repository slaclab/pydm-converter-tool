"""Value coercion for Phoebus Display Builder (``.bob``) properties.

Turns the raw text / ``ET.Element`` property values the parser keeps into the
plain Python values the IR stores: colours as ``"#rrggbb"``, font sizes as
numbers, alignment as the Qt flag strings the ``qtAlignment`` transform reads,
polygon points as ``(x, y)`` tuples, and rule arm values per target kind
(``bool`` / ``number`` / ``color`` / ``str``).

Named colours follow Phoebus's ``NamedWidgetColors``: the built-in table below,
optionally overlaid by a site ``color.def`` file (:func:`load_color_def`). Like
every front-end helper here, nothing raises on unmapped input; problems are
appended to a caller-supplied ``warnings`` list and a fallback value is used.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union

from pydmconverter.colors import RGBA, ColorContext, ColorValue, named_color, rgba_to_hex
from pydmconverter.ir.macros import normalize_macro_syntax

__all__ = [
    "BUILTIN_NAMED_COLORS",
    "RGBA",
    "alignment",
    "coerce",
    "color_from_element",
    "color_from_text",
    "font_size",
    "load_color_def",
    "normalize_macro_syntax",
    "parse_rgba_list",
    "points",
    "rgba_to_hex",
]

Number = Union[int, float]

# Ported from org.phoebus.ui.color.NamedWidgetColors (defineDefaultColors).
BUILTIN_NAMED_COLORS: dict[str, RGBA] = {
    "Transparent": (255, 255, 255, 0),
    "OK": (0, 255, 0, 255),
    "MINOR": (255, 128, 0, 255),
    "MAJOR": (255, 0, 0, 255),
    "INVALID": (255, 0, 255, 255),
    "DISCONNECTED": (200, 0, 200, 200),
    "Text": (0, 0, 0, 255),
    "ActiveText": (255, 255, 0, 255),
    "Background": (255, 255, 255, 255),
    "Read_Background": (240, 240, 240, 255),
    "Write_Background": (128, 255, 255, 255),
    "Button_Background": (210, 210, 210, 255),
    "Grid": (128, 128, 128, 255),
}

FALLBACK_COLOR = "#000000"

# Phoebus HorizontalAlignment / VerticalAlignment (ordinal or enum name) -> Qt flag.
_HORIZONTAL_QT: dict[str, str] = {
    "0": "Qt::AlignLeft",
    "1": "Qt::AlignHCenter",
    "2": "Qt::AlignRight",
    "LEFT": "Qt::AlignLeft",
    "CENTER": "Qt::AlignHCenter",
    "RIGHT": "Qt::AlignRight",
}
_VERTICAL_QT: dict[str, str] = {
    "0": "Qt::AlignTop",
    "1": "Qt::AlignVCenter",
    "2": "Qt::AlignBottom",
    "TOP": "Qt::AlignTop",
    "MIDDLE": "Qt::AlignVCenter",
    "BOTTOM": "Qt::AlignBottom",
}


def _warn(warnings: list[str] | None, message: str) -> None:
    if warnings is not None:
        warnings.append(message)


def parse_rgba_list(text: str) -> RGBA | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) not in (3, 4):
        return None
    try:
        values = [int(p) for p in parts]
    except ValueError:
        return None
    if len(values) == 3:
        values.append(255)
    return (values[0], values[1], values[2], values[3])


def load_color_def(path: str | Path, warnings: list[str] | None = None) -> dict[str, RGBA]:
    """Parse a Phoebus ``color.def`` and return the built-ins overlaid by its entries.

    Grammar (Phoebus ``examples/color.def``): ``Name = r, g, b [, a]`` |
    ``Name = PreviouslyDefinedName`` | ``Name = alias(PreviouslyDefinedName)``;
    ``#`` starts a comment line. Both reference forms resolve to the referenced
    colour's RGBA here, since the IR only stores concrete colours. Lines that do
    not parse, or reference an undefined name, are skipped with a warning.
    """
    named = dict(BUILTIN_NAMED_COLORS)
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            _warn(warnings, f"color.def:{lineno}: cannot parse '{line}'")
            continue
        name, value = (s.strip() for s in line.split("=", 1))
        if not name:
            _warn(warnings, f"color.def:{lineno}: cannot parse '{line}'")
            continue
        ref = None
        if value.startswith("alias"):
            rest = value[5:].strip()
            if rest.startswith("(") and rest.endswith(")"):
                ref = rest[1:-1].strip()
            else:
                _warn(warnings, f"color.def:{lineno}: cannot parse color '{name}' from '{value}'")
                continue
        elif value in named:
            ref = value
        if ref is not None:
            if ref not in named:
                _warn(warnings, f"color.def:{lineno}: color '{name}' references undefined '{ref}'")
                continue
            named[name] = named[ref]
            continue
        rgba = parse_rgba_list(value)
        if rgba is None:
            _warn(warnings, f"color.def:{lineno}: cannot parse color '{name}' from '{value}'")
            continue
        named[name] = rgba
    return named


def _table(named: dict[str, RGBA] | None, ctx: ColorContext | None) -> dict[str, RGBA]:
    """The colour-name table: ``named``, else the context's, else the built-ins."""
    if named is not None:
        return named
    if ctx is not None and ctx.named is not None:
        return ctx.named
    return BUILTIN_NAMED_COLORS


#: Wrapper tags that do not name the property they colour.
_GENERIC_SLOTS = frozenset({"color", "value"})


def _color_elem(elem: ET.Element | None) -> ET.Element | None:
    if elem is None:
        return None
    if elem.tag == "color":
        return elem
    return elem.find("color")


def color_from_element(
    elem: ET.Element | None,
    named: dict[str, RGBA] | None = None,
    warnings: list[str] | None = None,
    ctx: ColorContext | None = None,
) -> ColorValue | None:
    """``<color>`` element (or a property element wrapping one) -> ``"#rrggbb[aa]"``.

    A named colour resolves through ``named`` (default: the built-ins), which wins
    over the RGB attributes saved alongside the name, as in Phoebus. An unknown
    name silently uses the saved RGB, as Phoebus does, and warns only when there
    is no saved RGB to fall back on (black). Returns ``None``
    when there is no ``<color>`` element at all.

    With a scheme context ``ctx``, a named colour goes through
    :func:`~pydmconverter.colors.named_color` and may come back as a role. The
    property tag wrapping the ``<color>`` is the slot; a generic wrapper (a rule arm's
    ``<value>``, a bare ``<color>``) takes ``ctx.slot`` when the caller set one.
    """
    color = _color_elem(elem)
    if color is None:
        return None
    table = _table(named, ctx)
    slot = elem.tag if elem is not None and elem.tag != "color" else "color"
    if slot in _GENERIC_SLOTS and ctx is not None and ctx.slot is not None:
        slot = ctx.slot
    name = color.get("name")
    if name is not None and name in table:
        return named_color(name, table[name], slot, ctx)
    rgb = _rgb_attrs(color)
    if name is not None:
        if rgb is not None:
            # Phoebus saves the RGB beside the name and renders it silently
            # when the name is not in its table; do the same.
            return named_color(name, rgb, slot, ctx)
        _warn(warnings, f"unknown named color '{name}', using {FALLBACK_COLOR}")
        return FALLBACK_COLOR
    if rgb is None:
        _warn(warnings, f"color without name or red/green/blue, using {FALLBACK_COLOR}")
        return FALLBACK_COLOR
    return rgba_to_hex(rgb)


def color_name_of(
    elem: object, named: dict[str, RGBA] | None = None, ctx: ColorContext | None = None
) -> tuple[str, RGBA] | None:
    """``(name, RGBA)`` of a named ``<color>`` (or a property element wrapping one), as
    :func:`color_from_element` resolves it; ``None`` for an unnamed or unresolvable colour."""
    color = _color_elem(elem) if isinstance(elem, ET.Element) else None
    name = color.get("name") if color is not None else None
    if name is None:
        return None
    table = _table(named, ctx)
    rgb = table.get(name) or _rgb_attrs(color)
    return None if rgb is None else (name, rgb)


def _rgb_attrs(color: ET.Element) -> RGBA | None:
    try:
        r, g, b = (int(float(color.get(k, ""))) for k in ("red", "green", "blue"))
    except ValueError:
        return None
    try:
        a = int(float(color.get("alpha", "255")))
    except ValueError:
        a = 255
    return (r, g, b, a)


def color_from_text(
    text: str,
    named: dict[str, RGBA] | None = None,
    warnings: list[str] | None = None,
    ctx: ColorContext | None = None,
) -> ColorValue | None:
    """``"#rgb"`` / ``"#rrggbb"`` / ``"r,g,b[,a]"`` / colour name -> ``"#rrggbb"``, or ``None``.

    With a scheme context ``ctx``, a colour name goes through
    :func:`~pydmconverter.colors.named_color` and may come back as a role; its slot
    is ``ctx.slot`` when the caller set one, else ``"color"``.
    """
    value = text.strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        if len(digits) in (6, 8):
            try:
                int(digits, 16)
            except ValueError:
                pass
            else:
                return "#" + digits[:6].lower()
    else:
        rgba = parse_rgba_list(value)
        if rgba is not None:
            return rgba_to_hex(rgba)
        table = _table(named, ctx)
        if value in table:
            slot = ctx.slot if ctx is not None and ctx.slot is not None else "color"
            return named_color(value, table[value], slot, ctx)
    _warn(warnings, f"cannot coerce '{text}' to a color")
    return None


def font_size(elem: object) -> Number | None:
    """Font property (``<font><font size=..>``) or inner ``<font>`` -> size, else ``None``.

    Anything that is not an element (an absent or text-only prop) gives ``None``.
    """
    if not isinstance(elem, ET.Element):
        return None
    font = elem if elem.get("size") is not None else elem.find("font")
    if font is None:
        return None
    raw = font.get("size")
    if raw is None:
        return None
    try:
        size = float(raw)
    except ValueError:
        return None
    return int(size) if size.is_integer() else size


def alignment(horizontal: str | None, vertical: str | None = None) -> str:
    """Phoebus horizontal/vertical alignment (ordinal or name) -> Qt alignment flags.

    E.g. ``alignment("1", "1") == "Qt::AlignHCenter|Qt::AlignVCenter"``. Unknown or
    missing horizontal values default to left, matching Phoebus's default.
    """
    h = _HORIZONTAL_QT.get(str(horizontal).strip().upper(), "Qt::AlignLeft")
    if vertical is None:
        return h
    v = _VERTICAL_QT.get(str(vertical).strip().upper())
    return f"{h}|{v}" if v else h


def points(elem: object) -> list[tuple[Number, Number]]:
    """``<points><point x= y=/>...</points>`` -> ``[(x, y), ...]``; bad points are skipped.

    Anything that is not an element (an absent or text-only prop) gives ``[]``.
    """
    if not isinstance(elem, ET.Element):
        return []
    result: list[tuple[Number, Number]] = []
    for point in elem.iter("point"):
        try:
            x, y = float(point.get("x", "")), float(point.get("y", ""))
        except ValueError:
            continue
        result.append((_num(x), _num(y)))
    return result


def _num(value: float) -> Number:
    return int(value) if value.is_integer() else value


def coerce(
    kind: str,
    text: str,
    named: dict[str, RGBA] | None = None,
    warnings: list[str] | None = None,
    *,
    ctx: ColorContext | None = None,
) -> bool | Number | str | dict | None:
    """Coerce a property/rule value's text to ``kind`` (``bool``/``number``/``color``/``str``).

    ``str`` values get ``$(P)`` -> ``${P}`` macro normalisation. A value that does
    not parse as its kind warns and is returned as the (normalised) text; an
    unknown kind is treated as ``str`` with a warning. ``ctx`` (a scheme's
    :class:`~pydmconverter.colors.ColorContext`) lets a named ``color`` become a role.
    """
    raw = text if isinstance(text, str) else str(text)
    value = raw.strip()
    if kind == "bool":
        lowered = value.lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    elif kind == "number":
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return _num(float(value))
        except ValueError:
            pass
    elif kind == "color":
        hexed = color_from_text(value, named, None, ctx)
        if hexed is not None:
            return hexed
    elif kind == "str":
        return normalize_macro_syntax(raw)
    else:
        _warn(warnings, f"unknown coercion kind '{kind}', keeping text")
        return normalize_macro_syntax(raw)
    _warn(warnings, f"cannot coerce '{raw}' to {kind}")
    return normalize_macro_syntax(raw)
