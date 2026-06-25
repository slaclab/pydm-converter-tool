"""Deterministic id allocation for the Screen IR (D3).

Ids are short, prefixed, and stable across re-runs: ``w-001`` for widgets,
``r-001`` for rules, ``f-001`` for formulas. Because the converter walks each
source tree in a deterministic order, sequential allocation yields identical ids
on every run of the same input — which is what makes round-trip output stable.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydmconverter.ir.model import FormulaDeclaration, FormulaKind


class IdAllocator:
    """Per-screen sequential id allocator.

    One counter per prefix. Construct a fresh allocator per screen so ids restart
    at ``001`` and stay deterministic.
    """

    def __init__(self, width: int = 3) -> None:
        self._counters: dict[str, int] = {}
        self._width = width

    def next(self, prefix: str) -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}-{n:0{self._width}d}"

    def widget(self) -> str:
        return self.next("w")

    def rule(self) -> str:
        return self.next("r")

    def formula(self) -> str:
        return self.next("f")


def _formula_key(kind: str, expression: str, bindings: Mapping[str, str]) -> tuple:
    """Order-independent identity for a formula (handoff 6.3 dedupe)."""
    return (kind, expression, tuple(sorted(bindings.items())))


class FormulaPool:
    """Interns Fox formulas so identical ``calc://`` expressions share one decl.

    A calc used by N widgets becomes a single screen-level declaration; every
    widget references it by the same ``fox://<name>``. Allocation order is
    preserved so the emitted ``formulas[]`` is deterministic.
    """

    def __init__(self, allocator: IdAllocator) -> None:
        self._alloc = allocator
        self._by_key: dict[tuple, str] = {}
        self._decls: list[FormulaDeclaration] = []

    def intern(self, expression: str, bindings: Mapping[str, str], kind: FormulaKind = "scalar") -> str:
        """Return the formula name for this expression, allocating on first sight."""
        key = _formula_key(kind, expression, bindings)
        name = self._by_key.get(key)
        if name is None:
            name = self._alloc.formula()
            self._by_key[key] = name
            self._decls.append(FormulaDeclaration(name=name, kind=kind, expression=expression, bindings=dict(bindings)))
        return name

    @property
    def declarations(self) -> list[FormulaDeclaration]:
        """The interned formulas, in allocation order — assign to ``ScreenIR.formulas``."""
        return list(self._decls)
