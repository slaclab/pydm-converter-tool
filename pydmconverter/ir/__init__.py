"""Canopy Screen IR — the seam between converter front-ends and Canopy outputs.

This package is the target-agnostic intermediate representation that both the EDM
and (future) Qt .ui front-ends build into, and that the JSON emitter serializes to
``*.screen.json``. It is deliberately self-contained and free of EDM/PyDM/Qt types
so it can be lifted into ``src/canopy/converter/`` as a Canopy backend module with
minimal change (swap the Pydantic base for ``canopy.contracts.base.CanopyModel`` and
the vendored registry for ``canopy.beaver.gateway``).

See the design docs: Screen IR (D1-D17), the converter handoff (formulas[], rules),
and the Canopy macros design.
"""

from pydmconverter.ir.model import (
    ScreenIR,
    WidgetNode,
    Geometry,
    NodeMeta,
    Metadata,
    Source,
    Size,
    MacroDeclaration,
    Rule,
    RuleCondition,
    RulePV,
    FormulaDeclaration,
)

__all__ = [
    "ScreenIR",
    "WidgetNode",
    "Geometry",
    "NodeMeta",
    "Metadata",
    "Source",
    "Size",
    "MacroDeclaration",
    "Rule",
    "RuleCondition",
    "RulePV",
    "FormulaDeclaration",
]
