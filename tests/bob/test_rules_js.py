"""Table-driven tests for js_to_python, the port of Phoebus RuleToScript.javascriptToPythonLogic.

The first block mirrors Phoebus ``RuleToScript_ReplacementTests.java`` verbatim, so the
spacing produced around ``and``/``or``/``not`` matches what Phoebus itself generates.
"""

from __future__ import annotations

import pytest

from pydmconverter.bob.rules import js_to_python

PHOEBUS_CASES = [
    # testTrueFalse
    (" true ", " True "),
    (" ! false ", "  not  False "),
    ('  "false"  ', '  "false"  '),
    # testEqual
    ("pv0!=3", "pv0!=3"),
    ("pv0=3", "pv0==3"),
    ("pv0>=0", "pv0>=0"),
    # testAndOr
    ("x && y", "x  and  y"),
    ("x || y", "x  or  y"),
    ('a < 1 && y != "a && b"', 'a < 1  and  y != "a && b"'),
    ('y != "a && b" && a < 1', 'y != "a && b"  and  a < 1'),
    ('a < 1 || y != "a || b"', 'a < 1  or  y != "a || b"'),
    # testBitwise: single-character bitwise operators are left alone
    ("pvInt2 & 4", "pvInt2 & 4"),
    ("pvInt2 | 4", "pvInt2 | 4"),
    ("pvInt2 ^ 4", "pvInt2 ^ 4"),
    # testNot
    ("x != y", "x != y"),
    ("!(x+y > 1)", " not (x+y > 1)"),
    ('!(a==b) && x != "!"', ' not (a==b)  and  x != "!"'),
    ("Hello World!", "Hello World not "),
    ('"Hello World !"', '"Hello World !"'),
    ("'Hello World !'", "'Hello World !'"),
    # testAll
    ('a == "a" || x != "\\"" && y == "b!"', 'a == "a"  or  x != "\\""  and  y == "b!"'),
    ("pv0>=0) && (pv0<=10)", "pv0>=0)  and  (pv0<=10)"),
]

CORPUS_CASES = [
    ('pv0==1 && pvStr1=="a&&b"', 'pv0==1  and  pvStr1=="a&&b"'),
    ("!pvInt0", " not pvInt0"),
    ("pv0 = 1", "pv0 == 1"),
    ("Math.abs(pv0) > 2", "abs(pv0) > 2"),
    ("pvSev0<=1 || true", "pvSev0<=1  or  True"),
]

EDGE_CASES = [
    ("", ""),
    ("pv0==1", "pv0==1"),
    ("pv0<=1", "pv0<=1"),
    ("false", "False"),
    ("'a=b' == pvStr0", "'a=b' == pvStr0"),
    ('"true" == pvStr0', '"true" == pvStr0'),
    ('"Math.abs"', '"Math.abs"'),
    ("Math.max(pv0, pv1)", "max(pv0, pv1)"),
]


@pytest.mark.parametrize(("js", "expected"), PHOEBUS_CASES)
def test_js_to_python_matches_phoebus_unit_tests(js: str, expected: str) -> None:
    assert js_to_python(js) == expected


@pytest.mark.parametrize(("js", "expected"), CORPUS_CASES)
def test_js_to_python_corpus_forms(js: str, expected: str) -> None:
    assert js_to_python(js) == expected


@pytest.mark.parametrize(("js", "expected"), EDGE_CASES)
def test_js_to_python_edge_cases(js: str, expected: str) -> None:
    assert js_to_python(js) == expected


@pytest.mark.parametrize("js", ['pv0 == "abc', "pvStr0 == 'abc", 'x && "', "'"])
def test_js_to_python_unmatched_quote_returns_input_unchanged(js: str) -> None:
    # Phoebus returns the original text on an unmatched quote (and would throw when
    # the quote is the last character); the port returns the input in both cases.
    assert js_to_python(js) == js
