"""Canopy Screen IR data model (Pydantic v2).

Mirrors the locked Screen IR design (D1-D17) plus the additive ``formulas[]``
section from the converter handoff. Field names are snake_case in Python and
camelCase on the wire (see :mod:`pydmconverter.ir.base`).

Key decisions encoded here:

* D1  single root node (``ScreenIR.root``), children form subtrees.
* D2  ``WidgetNode.type`` is a Canopy registry id (``"pv-label"``), never a Qt class.
* D3  ids are short, stable, prefixed (``w-001``, ``r-001``, ``f-001``).
* D4  geometry is absolute-only (``x, y, width, height``).
* D6  macros declared at screen level; ``${VAR}`` syntax.
* D7/D15 rules stored in author form keyed by ``targetProperty`` (the REVISED
  2026-06-16 shape: ``pvs`` + ordered ``conditions`` + ``default``).
* D11 unknown widgets are explicit ``unknown-widget`` nodes carrying ``warnings``.
* D14 z-order is ``children`` array order.
* D17 per-node ``meta`` is preserved on round-trip, ignored by the runtime.
* formulas[] hoists ``calc://`` expressions to screen-level Fox formula
  declarations, referenced from a channel prop as ``fox://<name>``.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import Field, model_validator

from pydmconverter.ir.base import IRModel

# Absolute geometry/size coordinates. A smart union so EDM integer pixels stay
# ints in the JSON while scaled/computed values may be floats.
Number = Union[int, float]

SchemaVersion = Literal["1.0"]
ScreenKind = Literal["screen", "template"]
FormulaKind = Literal["scalar", "timeseries", "waveform"]

# Macro names: uppercase letters/digits/underscores, must start with a letter
# (Canopy macros design M2). ``${VAR}`` references resolve frontend-side.
MACRO_NAME_PATTERN = r"^[A-Z][A-Z0-9_]*$"


class Geometry(IRModel):
    """Absolute-only geometry (D4). Origin is the parent's top-left."""

    x: Number
    y: Number
    width: Number
    height: Number


class Source(IRModel):
    """Provenance of the screen. ``type`` is e.g. ``"edl-converter"``."""

    type: str
    saved_at: str | None = None


class Size(IRModel):
    width: Number
    height: Number


class Metadata(IRModel):
    title: str
    source: Source
    size: Size


class MacroDeclaration(IRModel):
    """A screen-level macro (D6 / macros design M2).

    ``default`` is required for ``kind: "screen"`` and forbidden for
    ``kind: "template"`` — enforced on :class:`ScreenIR`.
    """

    name: str = Field(pattern=MACRO_NAME_PATTERN)
    default: str | None = None
    description: str | None = None


class RulePV(IRModel):
    """A PV referenced by a rule. ``trigger`` marks it as a re-eval input."""

    name: str
    trigger: bool = True


class RuleCondition(IRModel):
    """One ordered condition -> value pair.

    ``expression`` references the rule's PVs by 0-based index (``{0}``, ``{1}``)
    so it stays stable across PV renames. ``value`` is the value written to the
    target property when the condition holds.
    """

    expression: str
    value: Any


class Rule(IRModel):
    """A property rule in author form (D7/D15, REVISED 2026-06-16).

    The runtime ``FormulaSpec`` is derived client-side at subscribe time and is
    never stored here. Any bindable (scalar/enum, non ``pv-channel``) property
    may be targeted.
    """

    id: str
    name: str
    target_property: str
    pvs: list[RulePV] = Field(default_factory=list)
    conditions: list[RuleCondition] = Field(default_factory=list)
    default: Any = None


class FormulaDeclaration(IRModel):
    """A screen-level Fox formula (converter handoff 6.3).

    Shape-compatible with ``canopy.contracts.formula.FormulaSpec`` plus a
    ``name``. ``calc://`` expressions are hoisted here (deduped) and referenced
    from a widget channel prop as ``fox://<name>``.
    """

    name: str
    kind: FormulaKind = "scalar"
    expression: str
    bindings: dict[str, str] = Field(default_factory=dict)


class NodeMeta(IRModel):
    """Editor annotations preserved on round-trip, ignored by the runtime (D17)."""

    comment: str | None = None


class WidgetNode(IRModel):
    """A single widget in the tree (D1, D2, D3, D7, D11, D14, D17)."""

    id: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    geometry: Geometry
    rules: list[Rule] = Field(default_factory=list)
    children: list[WidgetNode] = Field(default_factory=list)
    meta: NodeMeta | None = None
    # D11: populated on unknown-widget nodes (and any other convert-time note
    # that belongs with a specific node). Screen-level diagnostics travel
    # out-of-band, not in the IR (D12).
    warnings: list[str] = Field(default_factory=list)


class ScreenIR(IRModel):
    """The canonical screen representation — the converter's single output seam."""

    schema_version: SchemaVersion = "1.0"
    kind: ScreenKind = "screen"
    id: str
    metadata: Metadata
    macros: list[MacroDeclaration] = Field(default_factory=list)
    formulas: list[FormulaDeclaration] = Field(default_factory=list)
    root: WidgetNode

    @model_validator(mode="after")
    def _check_macro_defaults(self) -> ScreenIR:
        """Macros need defaults on screens, must omit them on templates (M2)."""
        for macro in self.macros:
            if self.kind == "screen" and macro.default is None:
                raise ValueError(f"macro {macro.name!r} needs a default on a screen (kind='screen')")
            if self.kind == "template" and macro.default is not None:
                raise ValueError(f"macro {macro.name!r} must not declare a default on a template")
        return self


# Resolve the WidgetNode self-reference (children).
WidgetNode.model_rebuild()
