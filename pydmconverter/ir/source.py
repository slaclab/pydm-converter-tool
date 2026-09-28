"""SourceNode — the neutral hand-off between a front-end and the IR builder.

Both front-ends normalize their parsed widgets into ``SourceNode`` trees:

* the EDM adapter maps EDM class/props -> Qt class/props (``pydmconverter/edm/ir_adapter.py``),
* the (future) ``.ui`` adapter reads Qt class/props straight from the XML.

The :class:`~pydmconverter.ir.builder.IRBuilder` consumes ``SourceNode`` trees and
knows nothing about EDM or Qt XML — it only resolves ``qt_class`` against the
registry and walks ``qt_props`` through the widget's ``qtPropMap``. This is what
lets all downstream code be written once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydmconverter.ir.model import Number


@dataclass
class RuleSpec:
    """An author-form rule without an id, produced by a front-end.

    The :class:`~pydmconverter.ir.builder.IRBuilder` allocates the ``r-NNN`` id and
    turns this into a :class:`~pydmconverter.ir.model.Rule`. ``pvs`` are
    ``(name, trigger)`` pairs; ``conditions`` are ``(expression, value)`` pairs whose
    expressions reference the pvs positionally (``{0}``, ``{1}``).
    """

    target_property: str
    name: str
    pvs: list[tuple[str, bool]] = field(default_factory=list)
    conditions: list[tuple[str, Any]] = field(default_factory=list)
    default: Any = None


@dataclass
class SourceNode:
    """One source widget, normalized to Qt vocabulary.

    Attributes
    ----------
    qt_class:
        Qt/PyDM class to resolve against the registry (``"PyDMLabel"``). ``None``
        for a node with no widget mapping (forces an ``unknown-widget``).
    qt_props:
        Prop values keyed by Qt property name (the keys Beaver's ``qtPropMap``
        expects). The builder selects and transforms these.
    registry_id:
        Direct registry id to resolve (bypasses Qt-class lookup) — for source
        concepts with no Qt analog, e.g. EDM groups -> the ``"group"`` definition.
        When set, it wins over ``qt_class``.
    geometry:
        Absolute ``(x, y, width, height)``.
    children:
        Child source nodes, in z-order (D14).
    raw_class:
        Original source class (EDM/Qt) for the ``unknown-widget`` ``originalClass``
        and warnings. Defaults to ``qt_class`` when omitted.
    raw_props:
        Original source props, surfaced verbatim on ``unknown-widget`` nodes.
    warnings:
        Convert-time notes to attach to the resulting node (D11).
    placeholder_reason:
        When set, the builder emits an ``unknown-widget`` placeholder with this
        warning instead of resolving the node (a front-end failed to convert it).
    """

    qt_class: str | None
    qt_props: dict[str, Any] = field(default_factory=dict)
    registry_id: str | None = None
    geometry: tuple[Number, Number, Number, Number] = (0, 0, 0, 0)
    children: list["SourceNode"] = field(default_factory=list)
    rules: list[RuleSpec] = field(default_factory=list)
    raw_class: str | None = None
    raw_props: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    placeholder_reason: str | None = None

    @property
    def original_class(self) -> str | None:
        return self.raw_class or self.qt_class


def conversion_failure(source_class: str | None, exc: BaseException) -> str:
    """The placeholder warning for a widget whose conversion raised ``exc``."""
    detail = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else ""
    return f"Conversion of {source_class} failed ({type(exc).__name__}: {detail}); rendering placeholder"
