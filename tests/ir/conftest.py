import pytest

from pydmconverter.ir import (
    ScreenIR,
    WidgetNode,
    Geometry,
    Metadata,
    Source,
    Size,
    MacroDeclaration,
    Rule,
    RuleCondition,
    RulePV,
    FormulaDeclaration,
    NodeMeta,
)


@pytest.fixture
def sample_screen() -> ScreenIR:
    """A small but representative screen exercising macros, rules, formulas,
    nesting, meta, and an unknown-widget node with warnings."""
    return ScreenIR(
        id="vacuum-system",
        metadata=Metadata(
            title="Vacuum System",
            source=Source(type="edl-converter"),
            size=Size(width=800, height=600),
        ),
        macros=[MacroDeclaration(name="PREFIX", default="", description="Device prefix")],
        formulas=[
            FormulaDeclaration(name="f-001", expression="A + B", bindings={"A": "${PREFIX}:V1", "B": "${PREFIX}:V2"})
        ],
        root=WidgetNode(
            id="w-001",
            type="absolute-canvas",
            props={"width": 800, "height": 600},
            geometry=Geometry(x=0, y=0, width=800, height=600),
            children=[
                WidgetNode(
                    id="w-002",
                    type="pv-label",
                    props={"pv": "${PREFIX}:PRESSURE", "precision": "fromPV", "alarmSensitive": True},
                    geometry=Geometry(x=10, y=20, width=200, height=30),
                    rules=[
                        Rule(
                            id="r-001",
                            name="Border color from severity",
                            target_property="borderColor",
                            pvs=[RulePV(name="${PREFIX}:STATUS:SEV")],
                            conditions=[
                                RuleCondition(expression="{0} > 1", value="red"),
                                RuleCondition(expression="{0} == 1", value="orange"),
                            ],
                            default="green",
                        )
                    ],
                    meta=NodeMeta(comment="DO NOT MOVE — fault response reference"),
                ),
                WidgetNode(
                    id="w-003",
                    type="unknown-widget",
                    props={"originalClass": "activeMysteryClass", "originalProps": {"foo": 1}},
                    geometry=Geometry(x=10, y=60, width=100, height=20),
                    warnings=["No registry entry for activeMysteryClass; rendering placeholder"],
                ),
            ],
        ),
    )
