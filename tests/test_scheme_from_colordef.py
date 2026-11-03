"""``canopy-scheme from-colordef``: regenerate a scheme's light values from a colour table."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydmconverter import scheme_cli
from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS
from pydmconverter.scheme import load_scheme

COLOR_DEF = """\
# synthetic
Background = 250, 250, 250
Semi = 10, 20, 30, 128
STOP = MAJOR
Halt = alias(MAJOR)
Copy = Semi
Broken = not a colour
Dangling = alias(NoSuchColour)
"""


def _run(capsys, *argv: str) -> tuple[int, str, str]:
    code = scheme_cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _write(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _colordef(tmp_path: Path) -> Path:
    path = tmp_path / "color.def"
    path.write_text(COLOR_DEF, encoding="utf-8")
    return path


def _gen(capsys, into: Path, *extra: str) -> tuple[int, str, str]:
    return _run(capsys, "from-colordef", "--extends", "canopy-default", "--into", str(into), *extra)


# --- parsing -----------------------------------------------------------------------------------------------------


def test_parse_color_def_keeps_aliases(tmp_path):
    warnings: list[str] = []
    table = scheme_cli.parse_color_table(_colordef(tmp_path), warnings)
    assert table == {
        "Background": "#fafafa",
        "Semi": "#0a141e80",
        "STOP": "@MAJOR",
        "Halt": "@MAJOR",
        "Copy": "@Semi",
    }
    assert any("Broken" in w for w in warnings)
    assert any("NoSuchColour" in w for w in warnings)


def test_builtin_table_is_hex():
    table = scheme_cli.parse_color_table(None, [])
    assert list(table) == list(BUILTIN_NAMED_COLORS)
    assert table["Transparent"] == "#ffffff00"
    assert table["Read_Background"] == "#f0f0f0"
    assert all(v.startswith("#") for v in table.values())


# --- create-if-missing -------------------------------------------------------------------------------------------


def test_missing_into_created_with_id(tmp_path, capsys):
    into = tmp_path / "facility-colors.json"
    code, out, _ = _gen(capsys, into, "--id", "facility-colors")
    assert code == 0
    doc = _read(into)
    assert doc["id"] == "facility-colors"
    assert doc["extends"] == "canopy-default"
    assert list(doc["roles"]) == list(BUILTIN_NAMED_COLORS)
    assert doc["roles"]["Text"] == {"light": "#000000"}
    assert "added: Text" in out.splitlines()
    assert not load_scheme(into).meta["errors"]


def test_missing_into_refused_without_id(tmp_path, capsys):
    into = tmp_path / "facility-colors.json"
    code, _, err = _gen(capsys, into)
    assert code != 0
    assert "--id" in err
    assert not into.exists()


def test_extends_must_be_canopy_default(tmp_path, capsys):
    with pytest.raises(SystemExit):
        scheme_cli.main(["from-colordef", "--extends", "other", "--into", str(tmp_path / "x.json"), "--id", "x"])


# --- per-mode conversion -----------------------------------------------------------------------------------------


def test_into_keeps_dark(tmp_path, capsys):
    into = _write(
        tmp_path / "s.json",
        {"id": "s", "extends": "canopy-default", "roles": {"Background": {"light": "#123456", "dark": "#0a0a0a"}}},
    )
    code, out, _ = _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert code == 0
    assert _read(into)["roles"]["Background"] == {"light": "#fafafa", "dark": "#0a0a0a"}
    assert "changed: Background" in out.splitlines()


def test_bare_hex_becomes_per_mode(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"Background": "#202020"}})
    _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert _read(into)["roles"]["Background"] == {"light": "#fafafa", "dark": "#202020"}


def test_bare_alias_becomes_per_mode(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"Background": "@Display_Background"}})
    _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert _read(into)["roles"]["Background"] == {"light": "#fafafa", "dark": "@Display_Background"}


def test_alias_preserved_as_light_alias(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"STOP": {"dark": "#ff0000"}}})
    code, out, _ = _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert code == 0
    roles = _read(into)["roles"]
    assert roles["STOP"] == {"light": "@MAJOR", "dark": "#ff0000"}
    assert roles["Halt"] == {"light": "@MAJOR"}
    assert roles["Copy"] == {"light": "@Semi"}
    assert "added: Halt" in out.splitlines()
    assert "changed: STOP" in out.splitlines()
    # The aliases resolve; the only errors are the new names' missing dark values, which are hand-written later.
    errors = load_scheme(into).meta["errors"]
    assert errors and all("no dark value" in e["message"] for e in errors)
    assert sorted(e["path"] for e in errors) == ["roles/Copy/dark", "roles/Halt/dark", "roles/Semi/dark"]


def test_unchanged_role_not_reported(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"Background": {"light": "#fafafa", "dark": "#000000"}}})
    _, out, _ = _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert "changed: Background" not in out.splitlines()
    assert "added: Background" not in out.splitlines()


# --- scope: only parsed names, import kept, removed reported -----------------------------------------------------


def test_removed_reported_not_deleted_and_import_kept(tmp_path, capsys):
    doc = {
        "id": "s",
        "extends": "canopy-default",
        "roles": {"Custom": {"light": "#111111", "dark": "#222222"}, "Grid": "#333333"},
        "import": {"phoebus": {"Custom": "Custom"}, "edm": {"x": None}},
    }
    into = _write(tmp_path / "s.json", doc)
    code, out, _ = _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert code == 0
    after = _read(into)
    assert after["roles"]["Custom"] == {"light": "#111111", "dark": "#222222"}
    # Grid is not in the parsed color.def, so it is untouched (still bare).
    assert after["roles"]["Grid"] == "#333333"
    assert after["import"] == doc["import"]
    assert after["id"] == "s"
    lines = out.splitlines()
    assert "removed: Custom" in lines
    assert "removed: Grid" in lines


def test_existing_order_kept_new_names_appended(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"Zed": "#010101", "Background": "#020202"}})
    _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert list(_read(into)["roles"]) == ["Zed", "Background", "Semi", "STOP", "Halt", "Copy"]


# --- --keep-light-aliases ----------------------------------------------------------------------------------------


def test_hand_written_light_alias_overwritten_by_default(tmp_path, capsys):
    into = _write(
        tmp_path / "s.json", {"id": "s", "roles": {"Background": {"light": "@Display_Background", "dark": "#000000"}}}
    )
    _gen(capsys, into, "--color-def", str(_colordef(tmp_path)))
    assert _read(into)["roles"]["Background"] == {"light": "#fafafa", "dark": "#000000"}


def test_keep_light_aliases(tmp_path, capsys):
    into = _write(
        tmp_path / "s.json",
        {
            "id": "s",
            "roles": {
                "Background": {"light": "@Display_Background", "dark": "#000000"},
                "Semi": "@Background",
                "STOP": {"light": "#00ff00"},
            },
        },
    )
    _, out, _ = _gen(capsys, into, "--color-def", str(_colordef(tmp_path)), "--keep-light-aliases")
    roles = _read(into)["roles"]
    assert roles["Background"] == {"light": "@Display_Background", "dark": "#000000"}
    assert roles["Semi"] == {"light": "@Background", "dark": "@Background"}
    # A hand-written hex light is not an alias, so it is still replaced.
    assert roles["STOP"] == {"light": "@MAJOR"}
    assert "changed: Background" not in out.splitlines()


def test_builtin_default_regenerates_existing(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {"Text": "#f4f4f4"}})
    _gen(capsys, into)
    assert _read(into)["roles"]["Text"] == {"light": "#000000", "dark": "#f4f4f4"}


def test_id_mismatch_on_existing_file_refused(tmp_path, capsys):
    into = _write(tmp_path / "s.json", {"id": "s", "roles": {}})
    code, _, err = _gen(capsys, into, "--id", "other")
    assert code != 0
    assert _read(into) == {"id": "s", "roles": {}}
