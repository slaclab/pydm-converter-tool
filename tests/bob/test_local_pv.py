"""Tests for Phoebus local-PV URL handling (``pydmconverter.bob.local_pv``)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from pydmconverter.bob.local_pv import is_gateway_channel, local_pv_key, rewrite_local_pv


def _rewrite(url: str, **kw) -> tuple[str, list[str]]:
    warnings: list[str] = []
    out = rewrite_local_pv(url, warnings.append, **kw)
    return out, warnings


# --- local_pv_key -----------------------------------------------------------------


@pytest.mark.parametrize(
    "url, key",
    [
        ("loc://MEM_USED", "loc://MEM_USED"),
        ("loc://MEM_USED<VDouble>", "loc://MEM_USED"),
        ("loc://MEM_USED<VDouble>(0)", "loc://MEM_USED"),
        ("loc://x(5)", "loc://x"),
        ("loc://x?type=int&init=1", "loc://x"),
        ("loc://$(P):MEM_FREE<VDouble>(0)", "loc://${P}:MEM_FREE"),
        ("loc://${P}:MEM_FREE", "loc://${P}:MEM_FREE"),
        ('loc://s<VString>("a?b(c)")', "loc://s"),
        ("  loc://x<VLong>(1)  ", "loc://x"),
        ("sim://noise", "sim://noise"),
        ("$(P):SIG", "${P}:SIG"),
    ],
)
def test_local_pv_key_strips_type_init_and_query(url, key):
    assert local_pv_key(url) == key


@pytest.mark.parametrize(
    "url, key",
    [
        ("loc://a(b)c(d)", "loc://a"),  # from the first "(" to the final ")"
        ("loc://a(b", "loc://a(b"),  # no final ")": nothing cut
        ("loc://a<x<y>z", "loc://az"),
        ("loc://a<x", "loc://a<x"),  # unclosed "<" stays
    ],
)
def test_local_pv_key_span_edges(url, key):
    assert local_pv_key(url) == key


def test_local_pv_key_is_linear_on_pathological_input():
    code = (
        "from pydmconverter.bob.local_pv import local_pv_key\n"
        "for url in ['loc://' + '(' * 200000 + 'x', 'loc://' + '<' * 200000]:\n"
        "    local_pv_key(url)\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


def test_local_pv_key_typed_and_bare_spelling_are_one_pv():
    assert local_pv_key("loc://MEM_USED<VDouble>") == local_pv_key("loc://MEM_USED")
    assert local_pv_key("loc://$(HOST):A") == local_pv_key("loc://${HOST}:A<VLong>(3)")


# --- rewrite_local_pv: typed ------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("loc://a<VLong>(1)", "loc://a?type=int&init=1"),
        ("loc://a<VInt>(-7)", "loc://a?type=int&init=-7"),
        ("loc://a<VDouble>(1.5)", "loc://a?type=float&init=1.5"),
        ("loc://a<VDouble>(0)", "loc://a?type=float&init=0"),
        ('loc://a<VString>("hello")', "loc://a?type=str&init=hello"),
        ("loc://a<VString>('hello')", "loc://a?type=str&init=hello"),
        ("loc://a<VString>(hello)", "loc://a?type=str&init=hello"),
        ('loc://a<VString>("")', "loc://a?type=str&init="),
        ("loc://a<VLong>", "loc://a?type=int"),
        ("loc://a<VDouble>", "loc://a?type=float"),
        ("loc://a<VString>", "loc://a?type=str"),
        ("loc://testtriggercolorcode<VLong>(1)", "loc://testtriggercolorcode?type=int&init=1"),
    ],
)
def test_rewrite_typed_local_pv(url, expected):
    out, warnings = _rewrite(url)
    assert out == expected
    assert warnings == []


# --- rewrite_local_pv: typeless inference ----------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("loc://a(1)", "loc://a?type=int&init=1"),
        ("loc://a(-3)", "loc://a?type=int&init=-3"),
        ("loc://a(2.5)", "loc://a?type=float&init=2.5"),
        ("loc://a(1e3)", "loc://a?type=float&init=1e3"),
        ('loc://a("text")', "loc://a?type=str&init=text"),
        ('loc://a("12")', "loc://a?type=str&init=12"),
        ("loc://a(abc)", "loc://a?type=str&init=abc"),
    ],
)
def test_rewrite_typeless_infers_type_from_literal(url, expected):
    out, warnings = _rewrite(url)
    assert out == expected
    assert warnings == []


# --- macros -----------------------------------------------------------------------


def test_rewrite_normalizes_macros_in_name():
    out, warnings = _rewrite("loc://$(P):MEM_FREE<VDouble>(0)")
    assert out == "loc://${P}:MEM_FREE?type=float&init=0"
    assert warnings == []


def test_rewrite_keeps_macro_in_init_literal():
    out, _ = _rewrite('loc://a<VString>("${DEV}")')
    assert out == "loc://a?type=str&init=${DEV}"


def test_rewrite_encodes_query_breaking_characters_in_init():
    out, _ = _rewrite('loc://a<VString>("x&y z")')
    assert out == "loc://a?type=str&init=x%26y%20z"


# --- passthrough ------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "loc://plain",
        "loc://${P}:plain",
        "loc://x?type=int&init=1",
        "sim://noise",
        "sim://sine(0, 10, 0.1)",
        "SR:C01:BPM:X",
        "pva://SR:X",
        "calc://c",
        "",
    ],
)
def test_rewrite_passes_through_non_typed_urls(url):
    out, warnings = _rewrite(url)
    assert out == url
    assert warnings == []


# --- warnings ---------------------------------------------------------------------


@pytest.mark.parametrize("vtype", ["VTable", "VEnum", "VDoubleArray", "VBoolean", "VFoo"])
def test_unmapped_vtype_warns_and_emits_bare_name(vtype):
    out, warnings = _rewrite(f"loc://t<{vtype}>(1)")
    assert out == "loc://t"
    assert warnings == [f"local PV type {vtype} not supported"]


def test_unmapped_vtype_without_value_warns():
    out, warnings = _rewrite("loc://t<VEnum>")
    assert out == "loc://t"
    assert warnings == ["local PV type VEnum not supported"]


def test_warning_is_prefixed_with_widget_name_when_given():
    out, warnings = _rewrite("loc://t<VTable>", widget="Table_1")
    assert out == "loc://t"
    assert warnings == ["Table_1: local PV type VTable not supported"]


@pytest.mark.parametrize(
    "url",
    ["loc://arr<VDouble>(1, 2, 3)", "loc://arr(1,2)", 'loc://arr<VString>("a", "b")'],
)
def test_array_initializer_warns_and_emits_bare_name(url):
    out, warnings = _rewrite(url, widget="W")
    assert out == "loc://arr"
    assert warnings == ["W: array local PV initializer not supported"]


def test_comma_inside_quoted_string_is_not_an_array():
    out, warnings = _rewrite('loc://s<VString>("a,b")')
    assert out == "loc://s?type=str&init=a%2Cb"
    assert warnings == []


# --- postcondition ----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "loc://a<VLong>(1)",
        "loc://a<VDouble>",
        "loc://a<VTable>",
        "loc://a<VEnum>(0)",
        "loc://a<VDoubleArray>(1,2)",
        "loc://a<VString>(1,2)",
        'loc://a<VString>("<V")',
        "loc://$(P)<VInt>(2)",
        "loc://a<vlong>(1)",
    ],
)
def test_no_output_contains_vtype_marker(url):
    out, _ = _rewrite(url)
    assert "<V" not in out
    assert "<v" not in out


# --- is_gateway_channel -----------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("SR:C01:BPM:X", True),
        ("${P}:MEM_MAX", True),
        ("ca://SR:X", True),
        ("pva://SR:X", True),
        ("loc://x", False),
        ("loc://x<VLong>(1)", False),
        ("LOC://x", False),
        ("sim://noise", False),
        ("calc://c", False),
        ("formula://f-001", False),
        ("formula://x", False),
        ("=`a`+1", False),
        ("", False),
    ],
)
def test_is_gateway_channel(url, expected):
    assert is_gateway_channel(url) is expected
