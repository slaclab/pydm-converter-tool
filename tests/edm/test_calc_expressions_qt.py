"""PyDM evaluates converted EPICS calc expressions: a ternary nested in
parentheses used to stay in EPICS syntax and raise a SyntaxError on every update."""

import pytest

from pydmconverter.edm.parser_helpers import parse_calc_list, translate_calc_pv_to_pydm

# A named calc, bypass_txt: 1 -> 3, 2 -> 5, anything else -> 0.
CALC_LIST = "CALC1\nbypass_txt\nA=1?3:(A=2?5:0)\n"


def test_nested_ternary_evaluates_in_pydm(qtbot, tmp_path):
    pytest.importorskip("pydm")
    from pydm.data_plugins import plugin_for_address
    from pydm.widgets import PyDMLabel, PyDMLineEdit

    calc_list = tmp_path / "calc.list"
    calc_list.write_text(CALC_LIST)
    # An empty default prefix keeps the argument a loc:// channel, so the test
    # needs no Channel Access.
    url = translate_calc_pv_to_pydm(
        r"CALC\\bypass_txt(LOC\\nestedTernaryIn)", parse_calc_list(str(calc_list)), default_prefix=""
    )

    # The variable is defined (type and initial value) before the calc connects to it.
    source = PyDMLineEdit(init_channel="loc://nestedTernaryIn?type=int&init=0")
    qtbot.addWidget(source)
    connections = plugin_for_address("loc://x").connections
    qtbot.waitUntil(lambda: "nestedTernaryIn" in connections, timeout=10000)

    label = PyDMLabel(init_channel=url)
    qtbot.addWidget(label)
    # The calc subscribes to its input from its own thread. Write the input once it
    # has, as PyDM's own calc test does, rather than rely on the calc picking up the
    # initial value or a write sent before it subscribed.
    calc = url.split("://", 1)[1].split("?", 1)[0]
    calcs = plugin_for_address("calc://x").connections
    qtbot.waitUntil(lambda: calc in calcs and calcs[calc].connected, timeout=10000)

    for value, shown in ((1, "3"), (2, "5"), (3, "0")):
        connections["nestedTernaryIn"].put_value(value)
        qtbot.waitUntil(lambda: label.text() == shown, timeout=10000)
