"""PyDM evaluates converted EPICS calc expressions: a ternary nested in
parentheses used to stay in EPICS syntax and raise a SyntaxError on every update."""

import pytest

from pydmconverter.edm.parser_helpers import parse_calc_list, translate_calc_pv_to_pydm

# bypass_txt as bcs/config/calc.list defines it: 1 -> 3, 2 -> 5, anything else -> 0.
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
    source = PyDMLineEdit(init_channel="loc://nestedTernaryIn?type=int&init=1")
    label = PyDMLabel(init_channel=url)
    qtbot.addWidget(source)
    qtbot.addWidget(label)
    connections = plugin_for_address("loc://x").connections
    qtbot.waitUntil(lambda: "nestedTernaryIn" in connections, timeout=3000)

    for value, shown in ((1, "3"), (2, "5"), (3, "0")):
        connections["nestedTernaryIn"].put_value(value)
        qtbot.waitUntil(lambda: label.text() == shown, timeout=3000)
