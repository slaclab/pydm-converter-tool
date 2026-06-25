"""The shared IR builder.

Consumes a :class:`~pydmconverter.ir.source.SourceNode` tree (produced by any
front-end adapter) and emits a :class:`~pydmconverter.ir.model.ScreenIR`. This is
the re-pointed core: where the old ``traverse_group`` instantiated PyDM widget
objects and ``setattr`` Qt attributes, the builder resolves each node's registry
id, walks the widget's ``qtPropMap`` to translate props, and writes IR nodes.

It is source-agnostic: it knows registry ids, ``qtPropMap``, transforms, geometry,
ids, and z-order — nothing about EDM or Qt XML. Both the EDM and ``.ui`` front-ends
build into the same IR through it.

Scope (Phase 1): structural conversion — type, props, absolute geometry, children
order (D14), unknown-widget fallback (D11), screen metadata, and macro collection.
Rules, calc/Fox formulas, and dynamic colour are later phases.
"""

from __future__ import annotations

from typing import Any

from pydmconverter.ir.fox import parse_calc_url
from pydmconverter.ir.ids import FormulaPool, IdAllocator
from pydmconverter.ir.macros import find_macro_references
from pydmconverter.ir.model import (
    Geometry,
    MacroDeclaration,
    Metadata,
    Number,
    Rule,
    RuleCondition,
    RulePV,
    ScreenIR,
    Size,
    Source,
    WidgetNode,
)
from pydmconverter.ir.registry import RegistryClient, WidgetDefinition
from pydmconverter.ir.source import RuleSpec, SourceNode
from pydmconverter.ir.transforms import DROP, apply_transform

ROOT_CANVAS_TYPE = "absolute-canvas"
UNKNOWN_WIDGET_TYPE = "unknown-widget"


class IRBuilder:
    """Builds one :class:`ScreenIR` from a SourceNode tree. One instance per screen
    (the id allocator restarts at ``001`` so output is deterministic)."""

    def __init__(self, registry: RegistryClient, *, root_type: str = ROOT_CANVAS_TYPE) -> None:
        self.registry = registry
        self.ids = IdAllocator()
        self.formulas = FormulaPool(self.ids)
        self.root_type = root_type

    def build_screen(
        self,
        *,
        screen_id: str,
        title: str,
        source_type: str,
        size: tuple[Number, Number],
        top_level: list[SourceNode],
        macros: list[MacroDeclaration] | None = None,
    ) -> ScreenIR:
        """Assemble a screen: an ``absolute-canvas`` root wrapping the top-level nodes.

        If ``macros`` is not supplied, declare every ``${VAR}`` referenced in props
        (default ``""``), so the screen is self-consistent (macros design M2/M9).
        """
        width, height = size
        root = WidgetNode(
            id=self.ids.widget(),
            type=self.root_type,
            props={"width": width, "height": height},
            geometry=Geometry(x=0, y=0, width=width, height=height),
            children=[self._build_node(node) for node in top_level],
        )
        declared = macros if macros is not None else self._collect_macros(root)
        return ScreenIR(
            id=screen_id,
            kind="screen",
            metadata=Metadata(
                title=title,
                source=Source(type=source_type),
                size=Size(width=width, height=height),
            ),
            macros=declared,
            formulas=self.formulas.declarations,
            root=root,
        )

    def _build_node(self, node: SourceNode) -> WidgetNode:
        definition = self.registry.by_qt_class(node.qt_class) if node.qt_class else None
        if definition is None:
            return self._unknown_node(node)
        return WidgetNode(
            id=self.ids.widget(),
            type=definition.id,
            props=self._map_props(node.qt_props, definition),
            geometry=self._geometry(node.geometry),
            rules=self._build_rules(node.rules),
            children=[self._build_node(child) for child in node.children],
            warnings=list(node.warnings),
        )

    def _map_props(self, qt_props: dict[str, Any], definition: WidgetDefinition) -> dict[str, Any]:
        """Translate Qt props to IR props via the widget's ``qtPropMap`` (the allowlist).

        Props with no ``qtPropMap`` entry are dropped; a transform returning
        :data:`~pydmconverter.ir.transforms.DROP` omits that prop.
        """
        out: dict[str, Any] = {}
        for qt_prop, spec in definition.qt_prop_map.items():
            if qt_prop not in qt_props:
                continue
            value = qt_props[qt_prop]
            transform = spec.get("transform")
            if transform:
                value = apply_transform(transform, value)
                if value is DROP:
                    continue
            out[spec["to"]] = value
        return self._hoist_formulas(out)

    def _hoist_formulas(self, props: dict[str, Any]) -> dict[str, Any]:
        """Lower any ``calc://`` channel value to a screen-level Fox formula + ``fox://`` ref."""
        for key, value in props.items():
            if isinstance(value, str) and value.startswith("calc://"):
                parsed = parse_calc_url(value)
                if parsed:
                    expression, bindings = parsed
                    props[key] = f"fox://{self.formulas.intern(expression, bindings)}"
        return props

    def _unknown_node(self, node: SourceNode) -> WidgetNode:
        """A D11 placeholder — nothing disappears silently."""
        original = node.original_class
        warnings = list(node.warnings)
        warnings.append(f"No registry entry for {original}; rendering placeholder")
        return WidgetNode(
            id=self.ids.widget(),
            type=UNKNOWN_WIDGET_TYPE,
            props={"originalClass": original, "originalProps": node.raw_props or node.qt_props},
            geometry=self._geometry(node.geometry),
            rules=self._build_rules(node.rules),
            children=[self._build_node(child) for child in node.children],
            warnings=warnings,
        )

    def _build_rules(self, specs: list[RuleSpec]) -> list[Rule]:
        """Turn id-less RuleSpecs into Rules with allocated ``r-NNN`` ids."""
        rules: list[Rule] = []
        for spec in specs:
            rules.append(
                Rule(
                    id=self.ids.rule(),
                    name=spec.name,
                    target_property=spec.target_property,
                    pvs=[RulePV(name=name, trigger=trigger) for name, trigger in spec.pvs],
                    conditions=[RuleCondition(expression=expr, value=value) for expr, value in spec.conditions],
                    default=spec.default,
                )
            )
        return rules

    @staticmethod
    def _geometry(geom: tuple[Number, Number, Number, Number]) -> Geometry:
        x, y, width, height = geom
        return Geometry(x=x, y=y, width=width, height=height)

    def _collect_macros(self, root: WidgetNode) -> list[MacroDeclaration]:
        """Declare every ``${VAR}`` referenced in any string prop, default ``""``."""
        names: dict[str, None] = {}

        def note(value: object) -> None:
            for ref in find_macro_references(value):
                names.setdefault(ref, None)

        def visit(node: WidgetNode) -> None:
            for value in node.props.values():
                note(value)
            for rule in node.rules:
                for pv in rule.pvs:
                    note(pv.name)
                for condition in rule.conditions:
                    note(condition.expression)
                note(rule.default)
            for child in node.children:
                visit(child)

        visit(root)
        # Macros also hide in hoisted formula bindings (the PV side of a calc).
        for formula in self.formulas.declarations:
            for binding in formula.bindings.values():
                note(binding)
        return [MacroDeclaration(name=name, default="") for name in sorted(names)]
