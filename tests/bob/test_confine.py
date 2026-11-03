"""A ``.bob`` names script files by path; an untrusted one must not read the server's files.

``convert_bytes`` confines file references by default (it serves uploads); ``convert_to_ir``
and the CLI read trusted input and stay unconfined.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydmconverter import react
from pydmconverter.ir.emit import to_wire_dict

MARKER = "SECRET-OUTSIDE-THE-UPLOAD"


def _bob(script_file: str, *, execute: bool = False) -> bytes:
    if execute:
        body = (
            '<actions><action type="execute"><script file="' + script_file + '"><text/></script>'
            "<description>Go</description></action></actions>"
        )
    else:
        body = '<scripts><script file="' + script_file + '"><pv_name>SR:A</pv_name></script></scripts>'
    return (
        '<display><name>D</name><widget type="action_button" version="3.0.0">'
        f"<name>Btn</name><pv_name>SR:A</pv_name>{body}</widget></display>"
    ).encode()


def _wire(ir) -> str:
    return json.dumps(to_wire_dict(ir))


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    path = tmp_path / "outside" / "secret.py"
    path.parent.mkdir()
    path.write_text(f"print('{MARKER}')\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("execute", [False, True], ids=["script", "execute-action"])
def test_upload_does_not_read_an_absolute_script_file(secret: Path, execute: bool):
    wire = _wire(react.convert_bytes(_bob(str(secret), execute=execute), kind="bob", filename="panel.bob"))
    assert MARKER not in wire
    assert str(secret) in wire  # carried as its path
    assert "outside the screen's directory" in wire


@pytest.mark.parametrize("execute", [False, True], ids=["script", "execute-action"])
def test_upload_does_not_read_a_dotdot_script_file(secret: Path, execute: bool):
    escape = "../" * 40 + str(secret).lstrip("/")
    wire = _wire(react.convert_bytes(_bob(escape, execute=execute), kind="bob", filename="panel.bob"))
    assert MARKER not in wire


@pytest.mark.parametrize("execute", [False, True], ids=["script", "execute-action"])
def test_confined_conversion_still_reads_a_script_beside_the_screen(tmp_path: Path, execute: bool):
    (tmp_path / "helper.py").write_text(f"print('{MARKER}')\n", encoding="utf-8")
    screen = tmp_path / "panel.bob"
    screen.write_bytes(_bob("helper.py", execute=execute))
    assert MARKER in _wire(react.convert_to_ir(screen, confine_file_refs=True))


def test_trusted_conversion_stays_unconfined(tmp_path: Path, secret: Path):
    screen = tmp_path / "panel.bob"
    screen.write_bytes(_bob(str(secret)))
    assert MARKER in _wire(react.convert_to_ir(screen))
