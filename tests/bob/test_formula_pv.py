"""Tests for Phoebus formula-PV lowering (``pydmconverter.bob.formula_pv``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from pydmconverter.bob.formula_pv import FORMULA_NOT_LOWERED_WARNING, lower_formula_pv
from pydmconverter.ir.ids import FormulaPool, IdAllocator


@dataclass
class _Ctx:
    """Minimal lowering context: a builder exposing ``formulas`` and a warnings list."""

    builder: SimpleNamespace = field(default_factory=lambda: SimpleNamespace(formulas=FormulaPool(IdAllocator())))
    warnings: list[str] = field(default_factory=list)


def _lower(text: str, **kw) -> tuple[str | None, _Ctx]:
    ctx = _Ctx()
    return lower_formula_pv(text, ctx, **kw), ctx


def _decl(ctx: _Ctx, url: str):
    name = url.removeprefix("formula://")
    (decl,) = [d for d in ctx.builder.formulas.declarations if d.name == name]
    return decl


# --- the dominant corpus forms ----------------------------------------------------


@pytest.mark.parametrize(
    "text, expression, bindings",
    [
        ('=(pv("SR02C_TSP2_TTF")*60)', "({0}*60)", {"0": "SR02C_TSP2_TTF"}),
        ("=pv('SR02C_TSP2_TTF')*60", "{0}*60", {"0": "SR02C_TSP2_TTF"}),
        ("=abs(`A:X`-`B:Y`) <= 0.25", "abs({0}-{1}) <= 0.25", {"0": "A:X", "1": "B:Y"}),
        (
            "=abs(`A`+`B`-`C`) <= 0.28",
            "abs({0}+{1}-{2}) <= 0.28",
            {"0": "A", "1": "B", "2": "C"},
        ),
        ("=`A`&&`B`", "{0} and {1}", {"0": "A", "1": "B"}),
        ("=`A`||!`B`", "{0} or not {1}", {"0": "A", "1": "B"}),
        ("=`LN:STATE`==14", "{0}==14", {"0": "LN:STATE"}),
        ("=`X`/3600", "{0}/3600", {"0": "X"}),
        ("='FE01:SR:VacOK' && 'FE01BL4:IG001:OK'", "{0} and {1}", {"0": "FE01:SR:VacOK", "1": "FE01BL4:IG001:OK"}),
        ("=`A` != `B`", "{0} != {1}", {"0": "A", "1": "B"}),
    ],
)
def test_dominant_forms_lower(text, expression, bindings):
    url, ctx = _lower(text)
    assert url is not None and url.startswith("formula://")
    decl = _decl(ctx, url)
    assert decl.expression == expression
    assert decl.bindings == bindings
    assert ctx.warnings == []


def test_macro_syntax_normalised_and_duplicates_shared():
    url, ctx = _lower("=abs(`$(P):AC`-`$(P):AM`) <= 0.2 && `$(P):AC` > 0")
    decl = _decl(ctx, url)
    assert decl.bindings == {"0": "${P}:AC", "1": "${P}:AM"}
    assert decl.expression == "abs({0}-{1}) <= 0.2 and {0} > 0"


def test_mixed_quote_forms_share_one_binding():
    url, ctx = _lower("=`A` + 'A' + pv(\"A\")")
    decl = _decl(ctx, url)
    assert decl.bindings == {"0": "A"}
    assert decl.expression == "{0} + {0} + {0}"


def test_identical_formulas_intern_once():
    ctx = _Ctx()
    a = lower_formula_pv("=`A`&&`B`", ctx)
    b = lower_formula_pv("=`A`&&`B`", ctx)
    assert a == b == "formula://f-001"
    assert len(ctx.builder.formulas.declarations) == 1


def test_warn_callable_preferred():
    seen: list[str] = []
    ctx = SimpleNamespace(builder=SimpleNamespace(formulas=FormulaPool(IdAllocator())), warn=seen.append)
    assert lower_formula_pv("=concat(`A`,`B`)", ctx, widget="W") is None
    assert seen == ["W: formula PV not lowered: =concat(`A`,`B`)"]


# --- rejections --------------------------------------------------------------------


def test_concat_returns_none_with_warning():
    text = "=concat($(P)$(R)MainEventTextStr,$(P)$(R)MainEventTextStr2)"
    url, ctx = _lower(text, widget="Text Update_3")
    assert url is None
    assert ctx.warnings == [f"Text Update_3: formula PV not lowered: {text}"]
    assert ctx.builder.formulas.declarations == []


def test_warning_constant_shape():
    assert FORMULA_NOT_LOWERED_WARNING.format(widget="W", text="=x") == "W: formula PV not lowered: =x"


@pytest.mark.parametrize(
    "text",
    [
        "=elementAt(`A`, $(IDX)-1)",
        "=`A``B`S(`A`-`B`)",  # mangled corpus form, fails ast.parse
        "=",
        "=   ",
        "=abs(`A`-`B`) <=",  # truncated
        "=max(`A`, `B`)",  # function other than abs
        "=`A` ? 1 : 0",
        "=`A` ^ 2",  # Phoebus power, Python xor: never lower silently
        "=42",  # no PV binding: the Formula Engine rejects token-less formulas
        "=`A` + foo",  # bare unquoted name
        "=`A`.real",
        "=`A`[0]",
    ],
)
def test_unlowerable_returns_none_with_warning(text):
    url, ctx = _lower(text)
    assert url is None
    assert ctx.warnings == [f"formula PV not lowered: {text}"]
    assert ctx.builder.formulas.declarations == []


def test_non_formula_text_is_not_lowered():
    url, ctx = _lower("SR:PV")
    assert url is None
    assert len(ctx.warnings) == 1
