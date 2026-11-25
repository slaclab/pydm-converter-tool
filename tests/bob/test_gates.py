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
        ("docs/a.html", "docs/a.html"),
        ("docs/${X}.html", "docs/${X}.html"),
        ("/abs/path.html", "/abs/path.html"),
        (" \thttp://a.example/x\n", "http://a.example/x"),
    ],
)
def test_web_urls_that_pass(text, url):
    assert gates.web_url(text) == url


@pytest.mark.parametrize(
    "text",
    [
        "javascript:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,x",
        "${BASE}/x",
        # Protocol-relative: a browser reads the authority under the page's scheme.
        "//evil.example/x",
        "\\\\evil.example\\x",
        "/\\evil.example/x",
        "\\/evil.example/x",
        " //evil.example/x",
        "/\t/evil.example/x",
    ],
)
def test_web_urls_that_are_refused(text):
    assert gates.web_url(text) is None


def test_over_deep_expressions_are_refused():
    """A tree too deep for the parser is refused, never raised.

    The length cap turns a 60k-term chain away before any parse; ``PARSE_ERRORS`` also
    covers ``RecursionError`` for whatever ``ast.parse`` cannot build, and the parser's
    own "too many nested parentheses" ``SyntaxError``.
    """
    assert gates.expression_allowed(" + ".join(["{0}"] * 60_000), 1) is False
    assert gates.expression_allowed("(" * 300 + "{0}" + ")" * 300, 1) is False


def test_parse_python_survives_a_deep_chain():
    """A 60k-term chain parses on every platform.

    Python 3.10's parser has no depth guard; on a 1 MB main-thread stack (Windows) this
    text overflowed the C stack and killed the test process. ``parse_python`` runs the
    parser on a thread with :data:`gates.PARSE_STACK_BYTES` of stack instead.
    """
    import ast

    tree = gates.parse_python("x = " + " + ".join(["1"] * 60_000))
    assert isinstance(tree, ast.Module) and len(tree.body) == 1


def test_parse_python_raises_what_the_parser_raises_and_caps_length():
    with pytest.raises(SyntaxError):
        gates.parse_python("x = (")
    with pytest.raises(ValueError):
        gates.parse_python("x" * (gates.MAX_SCRIPT_CHARS + 1))
    assert all(issubclass(exc, gates.PARSE_ERRORS) for exc in (SyntaxError, ValueError))


def test_expressions_over_the_formula_engine_limit_are_refused():
    assert gates.MAX_EXPRESSION_CHARS == 2048
    assert gates.expression_allowed("{0} + " * 300 + "1", 1) is True  # 1801 characters
    assert gates.expression_allowed("{0} + " * 400 + "1", 1) is False  # 2401 characters
