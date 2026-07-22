"""Iteration-3 WS2 regressions (converter side): CALC visibility PVs hoist to
fox:// formulas (including reuse without short-form leaks), named calcs resolve
via a sibling calc.list, LOC args survive as loc:// bindings, and EPICS calc
function names lower to the Fox namespace."""

from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.fox import to_fox_expression

FIXTURES = Path(__file__).parent / "fixtures"


def _convert():
    # calc.list resolution: the fixture dir holds a calc.list defining `sum`.
    return edm_file_to_ir(FIXTURES / "calc_rules.edl")


def test_calc_vis_pvs_hoist_to_fox_formulas():
    screen = _convert()
    rects = screen.root.children
    for rect in rects[:2]:
        rule = rect.rules[0]
        assert rule.pvs[0].name.startswith("fox://")
    # Identical calcs intern to ONE formula; no calc:// short forms survive.
    assert rects[0].rules[0].pvs[0].name == rects[1].rules[0].pvs[0].name
    assert len(screen.formulas) == 2  # MAX pair + sum


def test_calc_function_names_lower_to_fox_namespace():
    screen = _convert()
    max_formula = next(f for f in screen.formulas if "max(" in f.expression)
    assert "MAX(" not in max_formula.expression
    assert sorted(max_formula.bindings.values()) == ["SIG:ONE.SEVR", "SIG:TWO.SEVR"]


def test_named_calc_resolves_via_sibling_calc_list_with_loc_bindings():
    screen = _convert()
    sum_formula = next(f for f in screen.formulas if f.expression == "{A}+{B}" or f.expression == "A+B")
    values = sorted(sum_formula.bindings.values())
    assert all(value.startswith("loc://") for value in values)
    assert any("posVis" in value for value in values)


def test_no_raw_calc_or_short_calc_urls_survive_in_ir():
    import json

    from pydmconverter.ir.emit import to_wire_dict

    wire = json.dumps(to_wire_dict(_convert()))
    assert "CALC\\" not in wire.replace("\\\\", "\\")
    assert "calc://" not in wire


def test_to_fox_expression_lowering():
    assert to_fox_expression("MAX(A,B)") == "max(A,B)"
    assert to_fox_expression("SQR(A)+LN(B)") == "sqrt(A)+log(B)"
    # Single-letter variables named like function initials stay untouched.
    assert to_fox_expression("A + B") == "A + B"
    # Idempotent on already-lowered input.
    assert to_fox_expression("max(A,B)") == "max(A,B)"
