"""CALC PV arguments are read like EDM's get_arg (calc_pv_factory.cc): empty
arguments disappear, an argument ends at the first ")" it did not open, and a
numeric argument is a constant rather than a PV."""

import pytest

from pydmconverter.edm.parser_helpers import get_calc_arguments, parse_calc_pv, translate_calc_pv_to_pydm

CALC_DICT = {"fault_byp_txt": (None, "A=1?B:C")}


def query(url):
    """The calc URL's query pairs, in order."""
    return url.split("?", 1)[1].split("&")


@pytest.mark.parametrize(
    "args, expected",
    [
        ("X,,Y)", ["X", "Y"]),
        ("X,Y,)", ["X", "Y"]),
        ("X) )", ["X"]),
        (" X , Y )", ["X", "Y"]),
        ("MAX(X,Y),Z)", ["MAX(X,Y)", "Z"]),
        ("X", ["X"]),
        (")", []),
    ],
)
def test_get_calc_arguments(args, expected):
    assert get_calc_arguments(args) == expected


def test_empty_argument_is_dropped_and_later_ones_move_up():
    _, args, _ = parse_calc_pv(r"CALC\\\{A-B\}(X,,Y)")
    assert args == ["X", "Y"]


def test_trailing_comma_adds_no_argument():
    # bcs/BCS_LEE.edl: C used to become a channel named "ca://".
    url = translate_calc_pv_to_pydm(r"CALC\\fault_byp_txt(LI04:BCS:1:B1_ILCK,LI04:BCS:1:B1_I_BYP,)", CALC_DICT)
    assert query(url)[:2] == ["A=ca://LI04:BCS:1:B1_ILCK", "B=ca://LI04:BCS:1:B1_I_BYP"]
    assert not any(pair.startswith("C=") for pair in query(url))


def test_stray_closing_parenthesis_is_not_part_of_the_pv():
    url = translate_calc_pv_to_pydm(r"CALC\\fault_byp_txt(LI04:BCS:1:FS6427_B,LI04:BCS:1:6427BBYP) )", CALC_DICT)
    assert query(url)[:2] == ["A=ca://LI04:BCS:1:FS6427_B", "B=ca://LI04:BCS:1:6427BBYP"]


def test_missing_closing_parenthesis_still_gives_the_argument():
    # llrf/INTarcTest.edl
    name, args, inline = parse_calc_pv(r"CALC\\\{(A>>(8))\}(${P}RXCWAD_R")
    assert (name, args, inline) == ("(A>>(8))", ["${P}RXCWAD_R"], True)


@pytest.mark.parametrize(
    "edm_pv, pairs",
    [
        (r"CALC\\\{sqrt(A^2-B^2)\}(WIRE:LI20:3206:XRMS,15)", ["A=ca://WIRE:LI20:3206:XRMS", "expr=sqrt(A**2-15**2)"]),
        (r"CALC\\\{A*B\}(1.5e3, X)", ["B=ca://X", "expr=1.5e3*B"]),
        # A signed constant keeps its sign under any operator.
        (r"CALC\\\{A-B^2\}(X,-5)", ["A=ca://X", "expr=A-(-5)**2"]),
        # A macro may expand to a number, but only at runtime: it stays a channel.
        (r"CALC\\\{A+B\}(X,${N})", ["A=ca://X", "B=ca://${N}", "expr=A+B"]),
    ],
)
def test_numeric_argument_is_a_constant(edm_pv, pairs):
    assert query(translate_calc_pv_to_pydm(edm_pv)) == pairs


def test_constant_argument_evaluates_in_pydm(qtbot):
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.widgets import PyDMLabel, PyDMLineEdit

    # An empty default prefix keeps the variable a loc:// channel, so the test
    # needs no Channel Access.
    url = translate_calc_pv_to_pydm(r"CALC\\\{A+B\}(LOC\\calcConstantIn, 15)", default_prefix="")

    # The variable is defined (type and initial value) before the calc connects to it.
    source = PyDMLineEdit(init_channel="loc://calcConstantIn?type=int&init=2")
    label = PyDMLabel(init_channel=url)
    qtbot.addWidget(source)
    qtbot.addWidget(label)
    qtbot.waitUntil(lambda: label.text() == "17", timeout=3000)
    plugin_for_address("loc://x").connections["calcConstantIn"].put_value(5)
    qtbot.waitUntil(lambda: label.text() == "20", timeout=3000)
