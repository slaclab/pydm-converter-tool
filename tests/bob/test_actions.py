"""Tests for Phoebus action lowering (``pydmconverter.bob.actions``)."""

from __future__ import annotations

import pytest

from pydmconverter.bob.actions import ActionContext, action_button_label, lower_actions
from pydmconverter.bob.parser import BobWidget, parse_bob


def _widget(actions_xml: str, *, extra: str = "", name: str = "Btn") -> BobWidget:
    xml = (
        '<display version="2.0.0"><name>D</name>'
        f'<widget type="action_button" version="3.0.0"><name>{name}</name>{extra}'
        f"<actions>{actions_xml}</actions></widget></display>"
    )
    return parse_bob(xml.encode()).widgets[0]


def _lower(actions_xml: str, **kw) -> tuple[list[dict], ActionContext]:
    ctx = ActionContext()
    return lower_actions(_widget(actions_xml, **kw), ctx), ctx


# --- open_display -----------------------------------------------------------------


@pytest.mark.parametrize(
    "target_xml, target",
    [
        ("", "replace"),
        ("<target>standalone</target>", "window"),
        ("<target>tab</target>", "tab"),
        ("<target>window</target>", "window"),
        ("<target>replace</target>", "replace"),
    ],
)
def test_open_display_target_forms(target_xml, target):
    out, ctx = _lower(f'<action type="open_display"><file>sub/panel.bob</file>{target_xml}</action>')
    assert out == [{"type": "open_display", "file": "sub/panel.screen.json", "target": target}]
    assert ctx.warnings == []


def test_open_display_unknown_target_warns_and_replaces():
    out, ctx = _lower('<action type="open_display"><file>a.bob</file><target>popup</target></action>')
    assert out[0]["target"] == "replace"
    assert ctx.warnings == ["Btn: open_display target popup unknown; using replace"]


def test_open_display_file_through_screen_ref_keeps_directory_and_macros():
    out, _ = _lower(
        '<action type="open_display"><file>../common/$(DEV)/KnobPanel.bob</file>'
        "<macros><DEV>$(P):X</DEV><N>1</N></macros></action>"
    )
    assert out == [
        {
            "type": "open_display",
            "file": "../common/${DEV}/KnobPanel.screen.json",
            "target": "replace",
            "macros": {"DEV": "${P}:X", "N": "1"},
        }
    ]


def test_open_display_opi_target_warns():
    out, ctx = _lower('<action type="open_display"><file>old/legacy.opi</file></action>')
    assert out[0]["file"] == "old/legacy.screen.json"
    assert ctx.warnings == ["Btn: open_display target old/legacy.opi is a legacy .opi that no converter produces"]


def test_open_display_empty_file_warns():
    out, ctx = _lower('<action type="open_display"><file/></action>')
    assert out == [{"type": "open_display", "file": "", "target": "replace"}]
    assert ctx.warnings == ["Btn: open_display with no file"]


# --- write_pv ---------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["write_pv", "WRITE_PV"])
def test_write_pv_both_spellings(kind):
    out, ctx = _lower(f'<action type="{kind}"><pv_name>$(P):SET</pv_name><value>1</value></action>')
    assert out == [{"type": "write_pv", "pvName": "${P}:SET", "value": "1"}]
    assert ctx.warnings == []


def test_write_pv_own_pv_name_local_carries_type_and_init():
    out, ctx = _lower(
        '<action type="write_pv"><pv_name>$(pv_name)</pv_name><value>0</value></action>',
        extra="<pv_name>loc://trig&lt;VLong&gt;(1)</pv_name>",
    )
    assert out == [{"type": "write_pv", "pvName": "loc://trig?type=int&init=1", "value": "0"}]
    assert ctx.warnings == []


# --- command / execute ------------------------------------------------------------


def test_command_becomes_execute_with_one_warning_per_widget():
    out, ctx = _lower(
        '<action type="command"><description>Start</description><command>run.sh $(P) a</command></action>'
        '<action type="command"><description>Stop</description><command>stop.sh</command></action>'
    )
    assert out == [
        {"type": "execute", "command": "run.sh ${P} a", "description": "Start"},
        {"type": "execute", "command": "stop.sh", "description": "Stop"},
    ]
    assert ctx.warnings == ["Btn: shell command carried as execute action; the web runtime does not run shell commands"]
    assert [a.type for a in ctx.carried] == ["command", "command"]


def test_jython_execute_is_tier2_carried_and_not_emitted():
    out, ctx = _lower(
        '<action type="execute"><description>Run</description>'
        '<script file="EmbeddedPy"><text>print(1)</text></script></action>'
        '<action type="write_pv"><pv_name>A</pv_name><value>2</value></action>'
    )
    assert out == [{"type": "write_pv", "pvName": "A", "value": "2"}]
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("Btn: ") and "tier 2" in ctx.warnings[0]
    assert [a.type for a in ctx.carried] == ["execute"]


# --- open_webpage / open_file / close_display --------------------------------------


def test_open_webpage():
    out, _ = _lower('<action type="open_webpage"><url>https://example.com/$(X)</url></action>')
    assert out == [{"type": "open_webpage", "url": "https://example.com/${X}"}]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a",
        "HTTPS://example.com/a?b=c#d",
        "https://${HOST}/x",
        "//example.com/a",
        "/docs/manual.html",
        "docs/${X}.html",
        "manual.html#part:2",
        "?q=a:b",
    ],
)
def test_open_webpage_keeps_web_and_relative_urls(url):
    out, ctx = _lower(f'<action type="open_webpage"><url>{url}</url></action>')
    assert out == [{"type": "open_webpage", "url": url}]
    assert ctx.warnings == []


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "  javascript:alert(1)",
        "java&#9;script:alert(1)",
        "java&#10;script:alert(1)",
        "data:text/html,&lt;script&gt;alert(1)&lt;/script&gt;",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://example.com/a",
        "$(URL)",
        "${BASE}/page.html",
        "java$(X)script:alert(1)",
    ],
)
def test_open_webpage_drops_other_schemes_with_a_warning(url):
    out, ctx = _lower(f'<action type="open_webpage"><url>{url}</url></action><action type="close_display"/>')
    assert out == [{"type": "close_display"}]
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0].startswith("Btn: open_webpage URL ") and ctx.warnings[0].endswith(
        "is not http, https or relative; dropped"
    )


@pytest.mark.parametrize(
    "path, file",
    [
        ("docs/manual.pdf", "docs/manual.pdf"),
        ("GammaAreaDetectors.plt", "GammaAreaDetectors.plt"),
        ("/vxboot/PVnames/$(IOC)", "/vxboot/PVnames/${IOC}"),
        ("../$(DIR)/notes.txt", "../${DIR}/notes.txt"),
    ],
)
def test_open_file(path, file):
    out, ctx = _lower(f'<action type="open_file"><file>{path}</file></action>')
    assert out == [{"type": "open_file", "file": file}]
    assert ctx.warnings == []


@pytest.mark.parametrize(
    "path",
    ["file:///etc/passwd", "javascript:alert(1)", "https://example.com/a.pdf", "C:/data/x.txt", "$(F)", "${DIR}/x"],
)
def test_open_file_drops_anything_but_a_path_with_a_warning(path):
    out, ctx = _lower(f'<action type="open_file"><file>{path}</file></action>')
    assert out == []
    assert len(ctx.warnings) == 1 and ctx.warnings[0].endswith("is not a file path; dropped")


def test_close_display_unconditional():
    out, ctx = _lower('<action type="close_display"><description>Close</description></action>')
    assert out == [{"type": "close_display"}]
    assert ctx.warnings == []


def test_unknown_action_type_warns_and_is_skipped():
    out, ctx = _lower('<action type="teleport"/>')
    assert out == []
    assert ctx.warnings == ["Btn: action type teleport not supported"]


def test_order_preserved_and_no_actions():
    out, _ = _lower(
        '<action type="write_pv"><pv_name>A</pv_name><value>1</value></action>'
        '<action type="write_pv"><pv_name>B</pv_name><value>2</value></action>'
    )
    assert [a["pvName"] for a in out] == ["A", "B"]
    assert lower_actions(_widget(""), ActionContext()) == []


def test_ctx_with_only_warnings_list():
    class Bare:
        def __init__(self):
            self.warnings: list[str] = []

    ctx = Bare()
    out = lower_actions(_widget('<action type="execute"><script file="x.py"/></action>'), ctx)
    assert out == [] and len(ctx.warnings) == 1


# --- action_button caption ---------------------------------------------------------


_TWO = (
    '<action type="open_display"><description>Details</description><file>d.bob</file></action>'
    '<action type="write_pv"><description></description><pv_name>$(P):GO</pv_name><value>1</value></action>'
)


@pytest.mark.parametrize(
    "actions_xml, text_xml, label",
    [
        ("", "", ""),
        ('<action type="open_display"><description>Open</description><file>a.bob</file></action>', "", "Open"),
        ('<action type="open_display"><file>sub/a.bob</file></action>', "", "sub/a.bob"),
        (_TWO, "", "Details / ${P}:GO"),
        (_TWO, "<text>$(actions)</text>", "Details / ${P}:GO"),
        (_TWO, "<text>Go now</text>", "Go now"),
        (_TWO, "<text></text>", ""),
    ],
)
def test_action_button_label(actions_xml, text_xml, label):
    assert action_button_label(_widget(actions_xml, extra=text_xml)) == label
