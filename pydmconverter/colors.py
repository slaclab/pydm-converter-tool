"""Named colours to scheme roles: the parity rule shared by every colour emitter.

Used by the ``.bob`` and ``.edl`` front-ends. A named colour (a Phoebus ``color.def``
name such as ``<color name="Text" .../>``, or an EDM ``colors.list`` name) that the
colour scheme imports (``import.phoebus`` / ``import.edm``) can be written as a scheme
role, ``{"$role": role, "fallback": hex}``, so a viewer re-colours it with the scheme
and its light/dark mode. The converter does that only when it changes nothing today:
the role's light value must equal the hex the converter would write anyway (the
*fallback*). Otherwise the literal fallback is kept and a ``parity:`` note is recorded,
aggregated per document.

A role that restyles a Phoebus colour declares the value it replaces (its ``phoebus``
source, :attr:`SchemeResult.sources`). For such a role the fallback is compared with
that source instead of the light value, so the restyle is applied while a screen whose
``color.def`` drifted from the declared value is still caught.

An import entry may be an object ``{"role": default, "<slot>": role, ...}``: the colour
then becomes a different role depending on the Phoebus property it colours (``slot``),
e.g. ``Grid`` as a ``background_color`` is ``Grid_Fill`` and as a ``line_color`` ``Grid``.

With no :class:`ColorContext` (no scheme) every call returns the fallback, so output
is identical to the converter's output before schemes existed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from pydmconverter.scheme import canonical_hex

if TYPE_CHECKING:
    from pydmconverter.scheme import SchemeResult

__all__ = [
    "RGBA",
    "ColorContext",
    "ParityNotes",
    "named_color",
    "rgba_to_hex",
]

RGBA = tuple[int, int, int, int]

#: A colour value the IR stores: a literal hex, or a ``{"$role", "fallback"}`` role.
ColorValue = str | dict


def rgba_to_hex(rgba: tuple[int, ...]) -> str:
    """``(r, g, b[, a])`` -> ``"#rrggbb"``, or ``"#rrggbbaa"`` when alpha < 255 (components clamped)."""
    r, g, b, a = (max(0, min(255, int(c))) for c in (*rgba[:4], 255)[:4])
    return f"#{r:02x}{g:02x}{b:02x}" if a == 255 else f"#{r:02x}{g:02x}{b:02x}{a:02x}"


@dataclass
class _Mismatch:
    role: str
    fallback: str
    count: int = 0
    slots: dict[str, int] = field(default_factory=dict)


@dataclass
class ParityNotes:
    """Per-document aggregate of parity mismatches, keyed by ``(name, saved RGB, role, compared value)``.

    The compared value is the role's ``phoebus`` source when it declares one, else its light value;
    ``basis`` (``"phoebus"`` or ``"light"``) names which, in the note.
    """

    entries: dict[tuple[str, RGBA, str, str, str], _Mismatch] = field(default_factory=dict)

    def record(
        self, name: str, rgb: RGBA, value: str, role: str, fallback: str, slot: str, basis: str = "light"
    ) -> None:
        """Count one literal kept because ``role``'s ``basis`` value ``value`` differs from ``fallback``."""
        key = (name, tuple(rgb), role, basis, value)
        entry = self.entries.setdefault(key, _Mismatch(role=role, fallback=fallback))
        entry.count += 1
        entry.slots[slot] = entry.slots.get(slot, 0) + 1

    def waive(self, name: str, rgb: RGBA, role: str, slot: str) -> None:
        """Take back one :meth:`record` of ``name`` as ``role`` for ``slot``: the colour became the role after all."""
        for key, entry in list(self.entries.items()):
            if key[0] != name or key[1] != tuple(rgb) or key[2] != role or slot not in entry.slots:
                continue
            entry.count -= 1
            entry.slots[slot] -= 1
            if entry.slots[slot] <= 0:
                del entry.slots[slot]
            if entry.count <= 0:
                del self.entries[key]
            return

    def notes(self) -> list[str]:
        """One ``parity: `` message per key, in first-seen order, with its count."""
        out: list[str] = []
        for (name, _rgb, _role, basis, value), entry in self.entries.items():
            uses = "use" if entry.count == 1 else "uses"
            out.append(
                f"parity: color '{name}' kept as {entry.fallback}, scheme role '{entry.role}' has {basis} {value} "
                f"({entry.count} {uses}: {', '.join(entry.slots)})"
            )
        return out


@dataclass
class ColorContext:
    """What :func:`named_color` needs from one document's conversion.

    ``imports`` is the scheme's merged import maps (``{"phoebus": {...}, "edm": {...}}``);
    ``import_kind`` picks the one this front end uses. An entry is a role name or a
    slot object ``{"role": default, "<slot>": role}``. ``light`` maps each role to its
    light value and ``sources`` each restyled role to the Phoebus value it replaces.
    ``named`` is the colour-name table in force (built-ins or ``color.def``).
    ``dark`` maps each role to its dark value (read by the text/ground pairing,
    :mod:`pydmconverter.pairing`), and ``pairs`` aggregates that pass's notes.
    ``parity`` aggregates the document's mismatches. ``slot``, when set, is the property
    coloured by an element that does not name it (a rule arm's ``<value>``, a bare name);
    see :meth:`with_slot`.
    """

    imports: dict[str, dict[str, str | dict[str, str]]]
    light: dict[str, str]
    named: dict[str, RGBA] | None = None
    import_kind: str = "phoebus"
    parity: ParityNotes = field(default_factory=ParityNotes)
    sources: dict[str, str] = field(default_factory=dict)
    slot: str | None = None
    dark: dict[str, str] = field(default_factory=dict)
    pairs: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_scheme(
        cls, scheme: SchemeResult, named: dict[str, RGBA] | None = None, *, import_kind: str = "phoebus"
    ) -> ColorContext:
        """Build the context of one document from a flattened scheme."""
        flat = scheme.flat
        light = dict(zip(flat.get("roles", []), flat.get("light", [])))
        dark = dict(zip(flat.get("roles", []), flat.get("dark", [])))
        imports = {kind: dict(table or {}) for kind, table in (scheme.imports or {}).items()}
        sources = dict(scheme.sources or {})
        return cls(imports=imports, light=light, named=named, import_kind=import_kind, sources=sources, dark=dark)

    def with_slot(self, slot: str) -> ColorContext:
        """This context for colours of property ``slot``; it shares the document's parity notes."""
        return replace(self, slot=slot)

    def role_for(self, name: str, slot: str | None = None) -> str | None:
        """The role ``name`` is imported as (for property ``slot``), when that role exists in the scheme.

        A slot object gives the role it names for ``slot``, else its ``role``; without a
        slot (the survey) the default ``role``. A string entry is the role for every slot.
        """
        entry = (self.imports.get(self.import_kind) or {}).get(name)
        if isinstance(entry, dict):
            role = entry.get(slot) if slot is not None and slot != "role" else None
            if role is None:
                role = entry.get("role")
        else:
            role = entry
        return role if isinstance(role, str) and role in self.light else None

    def compared_value(self, role: str) -> tuple[str, str]:
        """``(basis, canonical hex)`` a fallback must equal for ``role``: its ``phoebus`` source, else its light."""
        source = self.sources.get(role)
        if source is not None:
            return "phoebus", canonical_hex(source)
        return "light", canonical_hex(self.light[role])

    def parity_notes(self) -> list[str]:
        """The aggregated ``parity: `` notes of this document, then its ``pair: `` notes."""
        pairs = [f"{note} ({count} {'use' if count == 1 else 'uses'})" for note, count in self.pairs.items()]
        return self.parity.notes() + pairs

    def note_pair(self, note: str) -> None:
        """Count one ``pair: `` note (aggregated per document like the parity notes)."""
        self.pairs[note] = self.pairs.get(note, 0) + 1


def named_color(name: str | None, rgb: RGBA, slot: str, ctx: ColorContext | None) -> ColorValue:
    """The IR value of a colour the converter would write as ``rgba_to_hex(rgb)``.

    ``name`` is the colour's source name (``None`` for an unnamed colour), ``rgb`` the
    RGBA the converter resolves today, ``slot`` the property being coloured (Phoebus
    ``background_color``, ``line_color``, ...; EDM ``fgColor``, ...): it picks the role of a slot-aware import
    and is listed in the parity note. A name the scheme imports gives
    ``{"$role": role, "fallback": hex}`` when ``hex`` equals the role's ``phoebus`` source,
    or its light value when it declares none; when it differs, ``hex`` is returned and a
    parity note naming the compared value is recorded on ``ctx``. Anything else returns ``hex``.
    """
    fallback = rgba_to_hex(rgb)
    if ctx is None or name is None:
        return fallback
    role = ctx.role_for(name, slot)
    if role is None:
        return fallback
    basis, value = ctx.compared_value(role)
    if value == canonical_hex(fallback):
        return {"$role": role, "fallback": fallback}
    ctx.parity.record(name, rgb, value, role, fallback, slot, basis)
    return fallback
