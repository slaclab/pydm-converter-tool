from pydmconverter.ir.fox import parse_calc_url, to_fox_expression


def test_to_fox_expression_operators():
    assert to_fox_expression("A^2") == "A**2"
    assert to_fox_expression("A#B") == "A!=B"
    assert to_fox_expression("A**2") == "A**2"  # idempotent


def test_parse_basic_calc():
    expr, bindings = parse_calc_url("calc://f?A=channel://X:1&B=ca://X:2&expr=A+B")
    assert expr == "A+B"
    assert bindings == {"A": "X:1", "B": "X:2"}  # protocols stripped


def test_parse_preserves_plus_operator():
    """A '+' in expr stays an operator (manual query split, not parse_qs)."""
    expr, _ = parse_calc_url("calc://f?A=channel://X&expr=A+1")
    assert expr == "A+1"


def test_macros_in_bindings_normalized():
    _, bindings = parse_calc_url("calc://f?A=channel://$(PREFIX):V&expr=A*2")
    assert bindings == {"A": "${PREFIX}:V"}


def test_numeric_constant_inlined_not_bound():
    expr, bindings = parse_calc_url("calc://g?A=channel://X:1&B=2&expr=A*B")
    assert expr == "A*2"
    assert bindings == {"A": "X:1"}


def test_epics_operators_in_calc():
    expr, _ = parse_calc_url("calc://h?A=channel://X&expr=A^2#0")
    assert expr == "A**2!=0"


def test_non_calc_returns_none():
    assert parse_calc_url("ca://X:1") is None
    assert parse_calc_url("calc://no-query") is None
    assert parse_calc_url(None) is None
