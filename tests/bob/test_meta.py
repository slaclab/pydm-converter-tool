"""Tests for ``pydmconverter.bob.meta``: the verbatim ``meta.comment`` carry-over."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydmconverter.bob.meta import build_meta
from pydmconverter.bob.parser import BobAction, BobScript, BobWidget, parse_bob

SCRIPT_A = "# first\nfrom org.csstudio.display.builder.runtime.script import PVUtil\nx = 1\n"
EXEC_TEXT = "# Embedded python script\nimport time\nPVUtil.writePV('SR:DN:Power', 2, 1000)"

WIDGET_BODY = (
    "<name>Btn</name>"
    "<pv_name>SR:A</pv_name>"
    "<scripts>"
    '<script file="EmbeddedPy"><text><![CDATA[' + SCRIPT_A + "]]></text>"
    '<pv_name trig="true">$(pv_name)</pv_name><pv_name trig="false">loc://x</pv_name></script>'
    '<script file="missing/helper.py"><pv_name>$(P):B</pv_name></script>'
    "</scripts>"
    "<actions>"
    '<action type="write_pv"><pv_name>SR:A</pv_name><value>1</value></action>'
    '<action type="execute"><script file="EmbeddedPy"><text><![CDATA[' + EXEC_TEXT + "]]></text></script>"
    "<description>Reboot</description></action>"
    "</actions>"
)

EXPECTED = (
    "Phoebus script [EmbeddedPy] pvs=[SR:A, loc://x]\n" + SCRIPT_A + "\n\n"
    "Phoebus script [missing/helper.py] pvs=[$(P):B]\nmissing/helper.py\n\n"
    "Phoebus execute action: inline\n" + EXEC_TEXT
)


def _doc(widget_open: str) -> bytes:
    return f"<display><name>D</name>{widget_open}{WIDGET_BODY}</widget></display>".encode()


def _carry(widget: BobWidget) -> str | None:
    # The two scripts are unlowered; of the actions only execute is (write_pv lowered).
    meta = build_meta(widget, widget.scripts, [a for a in widget.actions if a.type == "execute"])
    return None if meta is None else meta.comment


# --- exact join ---


def test_two_scripts_and_execute_action_exact_join():
    widget = parse_bob(_doc('<widget type="action_button">')).widgets[0]
    assert _carry(widget) == EXPECTED


def test_typeid_legacy_widget_keeps_meta():
    widget = parse_bob(_doc('<widget typeId="org.csstudio.opibuilder.widgets.ActionButton" version="1.0.0">')).widgets[
        0
    ]
    assert widget.type_id is not None
    assert _carry(widget) == EXPECTED


def test_document_order_regardless_of_argument_order():
    widget = parse_bob(_doc('<widget type="action_button">')).widgets[0]
    meta = build_meta(widget, list(reversed(widget.scripts)), [widget.actions[1]])
    assert meta is not None and meta.comment == EXPECTED


# --- nothing to carry ---


def test_nothing_to_carry_is_none():
    widget = parse_bob(_doc('<widget type="action_button">')).widgets[0]
    assert build_meta(widget, [], []) is None
    # a non-carried action type contributes nothing
    assert build_meta(widget, [], [widget.actions[0]]) is None


# --- file scripts ---


def test_script_file_read_beside_input(tmp_path: Path):
    (tmp_path / "helper.py").write_text("print('hi')\n", encoding="utf-8")
    bob = tmp_path / "panel.bob"
    bob.write_text(
        '<display><widget type="label"><name>L</name><scripts>'
        '<script file="helper.py"><pv_name>A</pv_name></script>'
        "</scripts></widget></display>",
        encoding="utf-8",
    )
    widget = parse_bob(bob).widgets[0]
    meta = build_meta(widget, widget.scripts, [])
    assert meta is not None
    assert meta.comment == "Phoebus script [helper.py] pvs=[A]\nprint('hi')\n"


def test_named_script_header():
    script = BobScript(name="Calc", file="calc.py", text="a = 1", pvs=[("X", True), ("Y", False)])
    widget = BobWidget(type="label", name="L", scripts=[script])
    meta = build_meta(widget, [script], [])
    assert meta is not None and meta.comment == "Phoebus script Calc [calc.py] pvs=[X, Y]\na = 1"


# --- actions ---


def test_command_action():
    action = BobAction(type="command", description="TWE", fields={"command": '/bin/run.sh "TWE"'})
    widget = BobWidget(type="action_button", name="B", actions=[action])
    meta = build_meta(widget, [], [action])
    assert meta is not None and meta.comment == 'Phoebus command: TWE\n/bin/run.sh "TWE"'


def test_execute_external_file_read_with_base_dir(tmp_path: Path):
    (tmp_path / "go.py").write_text("go()", encoding="utf-8")
    display = parse_bob(
        b'<display><widget type="action_button"><name>B</name><actions>'
        b'<action type="execute"><script file="go.py"><text/></script></action>'
        b"</actions></widget></display>"
    )
    widget = display.widgets[0]
    action = widget.actions[0]
    # an empty <text/> carries no inline code, so the file is the source
    assert build_meta(widget, [], [action]).comment == "Phoebus execute action: go.py\ngo.py"
    assert build_meta(widget, [], [action], base_dir=tmp_path).comment == "Phoebus execute action: go.py\ngo()"


@pytest.mark.parametrize(
    "fields, expected",
    [
        ({"path": "", "scriptText": "print(1)", "embedded": "true"}, "Phoebus execute action: inline\nprint(1)"),
        ({"path": "x.py", "embedded": "false"}, "Phoebus execute action: x.py\nx.py"),
    ],
)
def test_boy_execute_action(fields, expected):
    action = BobAction(type="EXECUTE_PYTHONSCRIPT", fields=fields)
    widget = BobWidget(type="ActionButton", name="B", actions=[action], type_id="ActionButton")
    assert build_meta(widget, [], [action]).comment == expected


# --- formula PVs ---


def test_declined_formula_pv_appended_last():
    script = BobScript(name="S", file="EmbeddedPy", text="pass", pvs=[])
    widget = BobWidget(type="textupdate", name="T", scripts=[script])
    meta = build_meta(widget, [script], [], ["=concat(`A`, `B`)"])
    assert meta is not None
    assert meta.comment == "Phoebus script S [EmbeddedPy] pvs=[]\npass\n\nPhoebus formula PV: =concat(`A`, `B`)"


def test_formula_pv_only():
    widget = BobWidget(type="textupdate", name="T")
    meta = build_meta(widget, [], [], ["=elementAt(`A`, 1)"])
    assert meta is not None and meta.comment == "Phoebus formula PV: =elementAt(`A`, 1)"
