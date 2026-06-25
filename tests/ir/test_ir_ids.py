from pydmconverter.ir.ids import FormulaPool, IdAllocator


def test_sequential_and_prefixed():
    """Ids are prefixed and zero-padded, counted per prefix (D3)."""
    a = IdAllocator()
    assert a.widget() == "w-001"
    assert a.widget() == "w-002"
    assert a.rule() == "r-001"
    assert a.formula() == "f-001"
    assert a.widget() == "w-003"  # widget counter independent of rule/formula


def test_fresh_allocator_restarts():
    """A new allocator (new screen) restarts ids — deterministic per screen."""
    assert IdAllocator().widget() == "w-001"


def test_formula_pool_dedupes_identical_calcs():
    """Identical calcs (binding order-insensitive) share one declaration."""
    pool = FormulaPool(IdAllocator())
    n1 = pool.intern("A + B", {"A": "X:1", "B": "X:2"})
    n2 = pool.intern("A + B", {"B": "X:2", "A": "X:1"})
    n3 = pool.intern("A * B", {"A": "X:1", "B": "X:2"})
    assert n1 == n2
    assert n1 != n3
    assert [d.name for d in pool.declarations] == [n1, n3]
    assert len(pool.declarations) == 2


def test_formula_pool_preserves_expression_and_bindings():
    pool = FormulaPool(IdAllocator())
    name = pool.intern("A / 2", {"A": "${PREFIX}:RAW"})
    decl = pool.declarations[0]
    assert decl.name == name
    assert decl.kind == "scalar"
    assert decl.expression == "A / 2"
    assert decl.bindings == {"A": "${PREFIX}:RAW"}
