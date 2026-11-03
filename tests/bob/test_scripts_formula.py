"""Tests for the loc-formula script matcher (``pydmconverter.bob.scripts.match_loc_formula``)."""

from __future__ import annotations

import pytest

from pydmconverter.bob.parser import BobAction, BobScript, BobWidget
from pydmconverter.bob.scripts import (
    FormulaCandidate,
    ScriptFileContext,
    build_writer_census,
    match_loc_formula,
    script_written_pvs,
)

# The MEM_LOAD script of controls/hoststats/embedded/_host.bob, verbatim.
HOST_MEM_LOAD = """# Embedded python script
from org.csstudio.display.builder.runtime.script import PVUtil, ScriptUtil

mem_max_pv = pvs[0]
mem_free_pv = pvs[1]
loc_pv = pvs[2]

mem_max_bytes = PVUtil.getDouble(mem_max_pv)
mem_free_bytes = PVUtil.getDouble(mem_free_pv)
mem_load = (mem_max_bytes - mem_free_bytes)/mem_max_bytes
loc_pv.setValue(mem_load*100)
"""

HEADER = "from org.csstudio.display.builder.runtime.script import PVUtil, ScriptUtil\n"


def _script(text: str | None, pvs: list[str], name: str = "s") -> BobScript:
    return BobScript(name=name, file="EmbeddedPy", text=text, pvs=[(p, True) for p in pvs])


def _widget(name: str, *scripts: BobScript, actions: list[BobAction] | None = None, pv: str = "") -> BobWidget:
    props = {"pv_name": pv} if pv else {}
    return BobWidget(type="textupdate", name=name, props=props, scripts=list(scripts), actions=actions or [])


def _match(widget: BobWidget, script: BobScript, others: list[BobWidget] | None = None):
    ctx = ScriptFileContext(writers=build_writer_census([widget, *(others or [])]))
    return match_loc_formula(script, widget, ctx), ctx.warnings


# --- the _host.bob MEM_LOAD script ------------------------------------------------


def test_host_mem_load_verbatim():
    script = _script(HOST_MEM_LOAD, ["$(P):MEM_MAX", "$(P):MEM_FREE", "loc://$(P):MEM_LOAD"])
    widget = _widget("Text Update_25", script, pv="loc://$(P):MEM_LOAD")
    cand, warnings = _match(widget, script)
    assert warnings == []
    assert isinstance(cand, FormulaCandidate)
    assert cand.expression == "({0} - {1}) / {0} * 100"
    assert cand.bindings == {"0": "${P}:MEM_MAX", "1": "${P}:MEM_FREE"}
    assert cand.target_key == "loc://${P}:MEM_LOAD"
    assert cand.actions == []


# --- accepted forms ---------------------------------------------------------------


def test_direct_form():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]) * 2)\n"
    script = _script(text, ["SR:CURRENT", "loc://twice<VDouble>(0)"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "{0} * 2"
    assert cand.bindings == {"0": "SR:CURRENT"}
    assert cand.target_key == "loc://twice"


def test_direct_value_binding_and_write():
    text = HEADER + "v = PVUtil.getLong(pvs[0])\npvs[1].write(v + 1)\n"
    script = _script(text, ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "{0} + 1"
    assert cand.bindings == {"0": "A"}


def test_alias_form():
    text = HEADER + "a = pvs[0]\nout = pvs[2]\nb = pvs[1]\nout.setValue(PVUtil.getInt(a) - PVUtil.getInt(b))\n"
    script = _script(text, ["X", "Y", "loc://diff"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "{0} - {1}"
    assert cand.bindings == {"0": "X", "1": "Y"}


def test_intermediate_form_inlines_chain():
    text = HEADER + ("x = PVUtil.getDouble(pvs[0])\ny = x * 2\nz = y + x\npvs[1].setValue(-z)\n")
    script = _script(text, ["P:X", "loc://Z"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "-({0} * 2 + {0})"
    assert cand.bindings == {"0": "P:X"}


def _doubling(n: int) -> str:
    """``x0 = pvs[0]`` then ``x<i> = x<i-1> + x<i-1>``: the inlined formula doubles each line."""
    lines = "".join(f"x{i} = x{i - 1} + x{i - 1}\n" for i in range(1, n + 1))
    return HEADER + "x0 = PVUtil.getDouble(pvs[0])\n" + lines + f"pvs[1].setValue(x{n})\n"


def test_inlining_below_the_node_cap_is_a_formula():
    script = _script(_doubling(6), ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression.count("{0}") == 64


@pytest.mark.parametrize("n", [7, 12, 64])
def test_inlining_past_the_node_cap_stays_tier_2(n):
    script = _script(_doubling(n), ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings == [f"w: {TIER2}: x0 = PVUtil.getDouble(pvs[0]) (inlined expression exceeds 500 nodes)"]


def test_freed_temporaries_do_not_hide_the_expansion():
    """Node sizes are not remembered across statements: a freed node's id can be reused."""
    lines = ["x0 = PVUtil.getDouble(pvs[0])"]
    for i in range(1, 11):
        lines += [f"t = x{i - 1} + 1", "t = 2", f"x{i} = x{i - 1} + x{i - 1}"]
    script = _script(HEADER + "\n".join(lines) + "\npvs[1].setValue(x10)\n", ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings[0].endswith("(inlined expression exceeds 500 nodes)")


def test_formula_text_is_capped():
    reads = " + ".join(f"PVUtil.getDouble(pvs[{n}{'9' * 3000}])" for n in range(1, 5))
    text = HEADER + f"pvs[1].setValue({reads})\n"
    script = _script(text, ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings[0].endswith("(formula text exceeds 10000 characters)")


def test_if_else_form_nested_conditional():
    text = HEADER + (
        "v = PVUtil.getDouble(pvs[0])\n"
        "if v > 0:\n"
        "    pvs[1].write(0)\n"
        "elif v == 0:\n"
        "    pvs[1].write(2)\n"
        "else:\n"
        "    pvs[1].write(1)\n"
    )
    script = _script(text, ["CCD:Paddles:Status", "loc://led"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "0 if {0} > 0 else 2 if {0} == 0 else 1"
    assert cand.bindings == {"0": "CCD:Paddles:Status"}
    assert cand.target_key == "loc://led"


def test_if_else_two_branches_alias_target():
    text = HEADER + ("led = pvs[1]\nif PVUtil.getLong(pvs[0]) == 1:\n    led.write(1)\nelse:\n    led.write(0)\n")
    script = _script(text, ["S", "loc://led"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "1 if {0} == 1 else 0"


def test_all_local_bindings_accepted():
    text = HEADER + "pvs[2].setValue(PVUtil.getDouble(pvs[0]) + PVUtil.getDouble(pvs[1]))\n"
    script = _script(text, ["loc://a<VDouble>(1)", "loc://$(P):b", "loc://sum"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.bindings == {"0": "loc://a", "1": "loc://${P}:b"}


def test_close_display_request():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\nScriptUtil.closeDisplay(widget)\n"
    script = _script(text, ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression == "{0}"
    assert cand.actions == [{"type": "close_display"}]


def test_close_display_only():
    text = HEADER + "ScriptUtil.closeDisplay(widget)\n"
    script = _script(text, [])
    cand, warnings = _match(_widget("w", script), script)
    assert warnings == []
    assert cand.expression is None
    assert cand.target_key is None
    assert cand.actions == [{"type": "close_display"}]


# --- rejections -------------------------------------------------------------------

TIER2 = "script needs the script runtime (tier 2)"


def test_mixed_binding_rejected():
    text = HEADER + "pvs[2].setValue(PVUtil.getDouble(pvs[0]) + PVUtil.getDouble(pvs[1]))\n"
    script = _script(text, ["loc://a", "GW:PV", "loc://sum"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert len(warnings) == 1
    assert warnings[0].startswith("w: " + TIER2)
    assert "mixed" in warnings[0]


@pytest.mark.parametrize("pv", ["sim://sine", "calc://x"])
def test_sim_calc_binding_rejected(pv):
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\n"
    script = _script(text, [pv, "loc://out"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert len(warnings) == 1 and TIER2 in warnings[0]


def test_second_writer_script_rejected():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\n"
    mine = _script(text, ["A", "loc://N"], name="mine")
    theirs = _script(HEADER + "pvs[0].setValue(3)\n", ["loc://N<VDouble>(0)"], name="theirs")
    w1 = _widget("w1", mine)
    w2 = _widget("w2", theirs)
    cand, warnings = _match(w1, mine, [w2])
    assert cand is None
    assert len(warnings) == 1
    assert TIER2 in warnings[0]
    assert "loc://N" in warnings[0] and "theirs" in warnings[0] and "w2" in warnings[0]


def test_second_writer_write_pv_action_rejected():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\n"
    mine = _script(text, ["A", "loc://N"])
    button = BobWidget(
        type="action_button",
        name="Btn",
        actions=[BobAction(type="write_pv", fields={"pv_name": "loc://N<VLong>(1)", "value": "1"})],
    )
    w = _widget("w", mine)
    cand, warnings = _match(w, mine, [button])
    assert cand is None
    assert len(warnings) == 1 and "write_pv action on Btn" in warnings[0]


def test_nested_second_writer_found():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\n"
    mine = _script(text, ["A", "loc://N"])
    inner = BobWidget(
        type="action_button",
        name="Inner",
        actions=[BobAction(type="write_pv", fields={"pv_name": "loc://N", "value": "1"})],
    )
    group = BobWidget(type="group", name="G", children=[inner])
    cand, warnings = _match(_widget("w", mine), mine, [group])
    assert cand is None and "Inner" in warnings[0]


@pytest.mark.parametrize(
    "body, first_line",
    [
        ("pvs[1].setValue(PVUtil.getDouble(pvs[0])\n", "pvs[1].setValue(PVUtil.getDouble(pvs[0])"),  # SyntaxError
        ("for i in range(3):\n    pvs[1].setValue(i)\n", "for i in range(3):"),
        ("print('x')\n", "print('x')"),
        ("pvs[1].setValue(PVUtil.getString(pvs[0]))\n", "pvs[1].setValue(PVUtil.getString(pvs[0]))"),
        ("v = PVUtil.getDouble(pvs[0])\npvs[1].setValue(v)\npvs[1].setValue(v)\n", "v = PVUtil.getDouble(pvs[0])"),
    ],
)
def test_unsupported_scripts_warn_first_line(body, first_line):
    script = _script(HEADER + "\n# comment\n" + body, ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings == [f"w: {TIER2}: {first_line}"]


def test_write_to_gateway_pv_rejected():
    script = _script(HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]))\n", ["A", "REAL:PV"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None and len(warnings) == 1


def test_if_branches_different_targets_rejected():
    text = HEADER + ("if PVUtil.getLong(pvs[0]) == 1:\n    pvs[1].write(1)\nelse:\n    pvs[2].write(0)\n")
    script = _script(text, ["S", "loc://a", "loc://b"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None and len(warnings) == 1


def test_if_without_else_rejected():
    text = HEADER + "if PVUtil.getLong(pvs[0]) == 1:\n    pvs[1].write(1)\n"
    script = _script(text, ["S", "loc://a"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None and len(warnings) == 1


def test_if_branch_non_constant_rejected():
    text = HEADER + ("v = PVUtil.getLong(pvs[0])\nif v == 1:\n    pvs[1].write(v)\nelse:\n    pvs[1].write(0)\n")
    script = _script(text, ["S", "loc://a"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None and len(warnings) == 1


def test_missing_text_warns_with_path():
    script = BobScript(name="s", file="scripts/calc.py", text=None, pvs=[("A", True)])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings == [f"w: {TIER2}: scripts/calc.py"]


# --- writer census ----------------------------------------------------------------


def test_script_written_pvs_alias_and_direct():
    assert script_written_pvs(_script(HOST_MEM_LOAD, ["a", "b", "loc://c"])) == [2]
    assert script_written_pvs(_script("pvs[0].write(1)\npvs[3].setValue(2)\n", [])) == [0, 3]
    assert script_written_pvs(_script("pvs[0].write(\n", [])) == []
    assert script_written_pvs(_script(None, [])) == []


def test_census_keys_by_local_pv_key():
    script = _script(HOST_MEM_LOAD, ["$(P):MEM_MAX", "$(P):MEM_FREE", "loc://$(P):MEM_LOAD<VDouble>(0)"])
    button = BobWidget(
        type="action_button",
        name="Btn",
        actions=[
            BobAction(type="write_pv", fields={"pv_name": "loc://x<VLong>(1)", "value": "1"}),
            BobAction(type="write_pv", fields={"pv_name": "REAL:PV", "value": "1"}),
            BobAction(type="open_display", fields={"file": "a.bob"}),
        ],
    )
    census = build_writer_census([_widget("T", script), button])
    assert set(census) == {"loc://${P}:MEM_LOAD", "loc://x"}
    assert census["loc://${P}:MEM_LOAD"][0].source is script
    assert census["loc://x"][0].description == "write_pv action on Btn"


def test_written_string_holding_a_macro_stays_tier_2():
    text = HEADER + ("if PVUtil.getLong(pvs[0]) == 1:\n    pvs[1].write('${M}')\nelse:\n    pvs[1].write('off')\n")
    script = _script(text, ["S", "loc://a"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings[0].endswith("(writes a macro)")


def test_formula_outside_the_engine_subset_stays_tier_2():
    text = HEADER + "pvs[1].setValue(PVUtil.getDouble(pvs[0]) // 2)\n"
    script = _script(text, ["A", "loc://B"])
    cand, warnings = _match(_widget("w", script), script)
    assert cand is None
    assert warnings[0].endswith("(formula outside the Formula Engine subset)")
