"""The shared gates (``pydmconverter.bob.gates``) every ``.bob`` sink calls."""

from __future__ import annotations

import pytest

from pydmconverter.bob import gates
from pydmconverter.bob.formula_pv import lower_formula_pv
from pydmconverter.bob.rules import syntax_check
from pydmconverter.ir.ids import FormulaPool, IdAllocator


class _Ctx:
    def __init__(self) -> None:
        self.builder = type("B", (), {"formulas": FormulaPool(IdAllocator())})()
        self.warnings: list[str] = []


@pytest.mark.parametrize(
    "expression, ok",
    [
        ("{0} * 2 + abs({1})", True),
        ("floor({0}) == 1 and not {1}", True),
        ("(1 if {0} > 0 else 2) == 1", True),
        ("{0} == ${M}", False),
        ("{0} == '$(M)'", False),
        ("__import__('os').system('x') == 0", False),
        ("{0}.real", False),
        ("{0} // 2", False),
    ],
)
def test_rule_conditions_and_formula_pvs_share_one_gate(expression, ok):
    assert gates.expression_allowed(expression, 2) is ok
    assert syntax_check(expression, 2) is ok


@pytest.mark.parametrize(
    "text, lowered",
    [
        ('=pv("$(P):A") * 2', True),  # a macro inside a PV name is a binding, not code
        ('=pv("A") * ${GAIN}', False),
        ('=pv("A") * $(GAIN)', False),
        ('=pv("A") == "${M}"', False),  # a substituted value could close the literal
        ('=pv("A").real', False),
    ],
)
def test_formula_pvs_pass_the_expression_gate(text, lowered):
    ctx = _Ctx()
    assert (lower_formula_pv(text, ctx) is not None) is lowered
    assert (ctx.warnings == []) is lowered


@pytest.mark.parametrize(
    "text, reference",
    [
        ("a.png", "a.png"),
        ("../x/$(DEV).bob", "../x/${DEV}.bob"),
        ("/opt/ops/${IOC}", "/opt/ops/${IOC}"),
        ("sub\\panel.bob", "sub/panel.bob"),
        (" \tdocs/manual.pdf\n", "docs/manual.pdf"),
    ],
)
def test_file_references_that_pass(text, reference):
    assert gates.file_reference(text) == reference


@pytest.mark.parametrize(
    "text",
    [
        "//evil.example/x.bob",
        "\\\\evil.example\\share\\x.bob",
        "/\\evil.example/x.bob",
        "\\/evil.example/x.bob",
        " //evil.example/x.bob",
        "/\t/evil.example/x.bob",
        "https://evil.example/x.bob",
        "file:///etc/passwd",
        "C:\\data\\x.bob",
        "${F}",
        "$(DIR)/x.bob",
    ],
)
def test_file_references_that_are_refused(text):
    assert gates.file_reference(text) is None


@pytest.mark.parametrize(
    "text, url",
    [
        ("https://${HOST}/x", "https://${HOST}/x"),
        ("//cdn.example/a", "//cdn.example/a"),
        ("docs/a.html", "docs/a.html"),
    ],
)
def test_web_urls_that_pass(text, url):
    assert gates.web_url(text) == url


@pytest.mark.parametrize("text", ["javascript:alert(1)", "java\tscript:alert(1)", "data:text/html,x", "${BASE}/x"])
def test_web_urls_that_are_refused(text):
    assert gates.web_url(text) is None
