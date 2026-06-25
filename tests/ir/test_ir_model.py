import pytest
from pydantic import ValidationError

from pydmconverter.ir import (
    ScreenIR,
    WidgetNode,
    Geometry,
    Metadata,
    Source,
    Size,
    MacroDeclaration,
)


def _screen(**kwargs) -> dict:
    base = dict(
        id="s",
        metadata=Metadata(title="t", source=Source(type="edl-converter"), size=Size(width=1, height=1)),
        root=WidgetNode(id="w-001", type="absolute-canvas", geometry=Geometry(x=0, y=0, width=1, height=1)),
    )
    base.update(kwargs)
    return base


def test_screen_defaults():
    """A minimal screen carries the locked defaults."""
    screen = ScreenIR(**_screen())
    assert screen.schema_version == "1.0"
    assert screen.kind == "screen"
    assert screen.macros == []
    assert screen.formulas == []


def test_camel_case_on_the_wire():
    """snake_case attributes serialize as camelCase (D2/D7 wire shape)."""
    node = WidgetNode(
        id="w-002",
        type="pv-label",
        geometry=Geometry(x=0, y=0, width=1, height=1),
    )
    wire = node.model_dump(by_alias=True)
    assert "type" in wire
    # targetProperty / schemaVersion checked via a rule-bearing screen below
    screen = ScreenIR(**_screen())
    assert "schemaVersion" in screen.model_dump(by_alias=True)


def test_int_geometry_preserved():
    """EDM integer pixels stay ints in the model (clean golden output)."""
    g = Geometry(x=10, y=20, width=200, height=30)
    dumped = g.model_dump()
    assert dumped["x"] == 10 and isinstance(dumped["x"], int)


def test_float_geometry_allowed():
    """Scaled/computed coordinates may be floats."""
    g = Geometry(x=10.5, y=0, width=1, height=1)
    assert isinstance(g.model_dump()["x"], float)


def test_macro_name_pattern_enforced():
    """Macro names must match ^[A-Z][A-Z0-9_]*$ (M2)."""
    MacroDeclaration(name="PREFIX", default="")
    with pytest.raises(ValidationError):
        MacroDeclaration(name="lowercase", default="")
    with pytest.raises(ValidationError):
        MacroDeclaration(name="1BAD", default="")


def test_screen_macro_requires_default():
    """kind='screen' macros need a default (M2)."""
    with pytest.raises(ValidationError):
        ScreenIR(**_screen(macros=[MacroDeclaration(name="PREFIX")]))


def test_template_macro_forbids_default():
    """kind='template' macros must not declare a default (M2)."""
    with pytest.raises(ValidationError):
        ScreenIR(**_screen(kind="template", macros=[MacroDeclaration(name="PREFIX", default="x")]))
    # A template with a defaultless macro is fine.
    ScreenIR(**_screen(kind="template", macros=[MacroDeclaration(name="PREFIX")]))


def test_accepts_camel_or_snake_input(sample_screen):
    """The model round-trips its own camelCase output back into a model."""
    wire = sample_screen.model_dump(by_alias=True)
    reloaded = ScreenIR.model_validate(wire)
    assert reloaded == sample_screen
