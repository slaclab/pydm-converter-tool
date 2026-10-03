import json
from pathlib import Path

import pytest

from pydmconverter import react

EDM_FIXTURE = Path(__file__).parent / "edm" / "fixtures" / "basic_widgets.edl"
UI_FIXTURE = Path(__file__).parent / "ui" / "fixtures" / "basic_widgets.ui"


def test_convert_to_ir_dispatches_by_suffix():
    assert react.convert_to_ir(EDM_FIXTURE).metadata.source.type == "edl-converter"
    assert react.convert_to_ir(UI_FIXTURE).metadata.source.type == "ui-converter"


def test_convert_bytes_edl_and_ui():
    """convert_bytes runs the same pipeline as convert_to_ir but is keyed on kind (#146)."""
    edm = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl")
    ui = react.convert_bytes(UI_FIXTURE.read_bytes(), kind="ui")
    assert edm.metadata.source.type == "edl-converter"
    assert ui.metadata.source.type == "ui-converter"
    assert edm.root.children  # produced widgets through the shared builder


def test_convert_bytes_is_deterministic():
    data = EDM_FIXTURE.read_bytes()
    assert react.convert_bytes(data, kind="edl") == react.convert_bytes(data, kind="edl")


def test_convert_bytes_rejects_bad_kind():
    with pytest.raises(ValueError, match="kind"):
        react.convert_bytes(b"<x/>", kind="txt")


def test_convert_to_ir_rejects_unknown_suffix(tmp_path):
    bogus = tmp_path / "x.txt"
    bogus.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError, match="supports"):
        react.convert_to_ir(bogus)


def test_convert_file_writes_screen_json(tmp_path):
    out = react.convert_file(EDM_FIXTURE, tmp_path / "vac", override=True)
    assert out.name == "vac.screen.json"
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "screen"


def test_convert_file_honors_explicit_json_name(tmp_path):
    out = react.convert_file(UI_FIXTURE, tmp_path / "custom.json", override=True)
    assert out.name == "custom.json"


def test_convert_file_refuses_overwrite_without_override(tmp_path):
    target = tmp_path / "out.screen.json"
    react.convert_file(EDM_FIXTURE, target, override=True)
    with pytest.raises(FileExistsError):
        react.convert_file(EDM_FIXTURE, target, override=False)


def test_convert_folder(tmp_path):
    src = tmp_path / "in"
    (src / "nested").mkdir(parents=True)
    (src / "a.edl").write_text(EDM_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (src / "nested" / "b.ui").write_text(UI_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (src / "ignore.txt").write_text("x", encoding="utf-8")

    found, failed = react.convert_folder(src, tmp_path / "out", override=True)
    assert found == 2
    assert failed == []
    assert (tmp_path / "out" / "a.screen.json").is_file()
    assert (tmp_path / "out" / "nested" / "b.screen.json").is_file()


# --- convert_bytes keeps the upload's identity (filename / search_paths) -------

EDM_FIXTURES = Path(__file__).parent / "edm" / "fixtures"


def test_convert_bytes_without_filename_keeps_screen_id():
    """Backward compatible: no filename -> the fixed "screen" id/title."""
    ir = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl")
    assert (ir.id, ir.metadata.title) == ("screen", "screen")


def test_convert_bytes_filename_sets_id_and_title():
    edm = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl", filename="vac_gunb_main.edl")
    assert (edm.id, edm.metadata.title) == ("vac_gunb_main", "vac_gunb_main")
    ui = react.convert_bytes(UI_FIXTURE.read_bytes(), kind="ui", filename="mc_overview.ui")
    assert ui.id == "mc_overview"


def test_convert_bytes_filename_is_reduced_to_a_safe_basename():
    data = EDM_FIXTURE.read_bytes()
    assert react.convert_bytes(data, kind="edl", filename="../../etc/sub/vac.edl").id == "vac"
    assert react.convert_bytes(data, kind="edl", filename="C:\\screens\\vac.EDL").id == "vac"
    assert react.convert_bytes(data, kind="edl", filename="vac").id == "vac"  # suffix appended for dispatch
    assert react.convert_bytes(data, kind="edl", filename="..").id == "screen"


def test_convert_bytes_symbol_needs_search_paths():
    """The staged copy lives in a private temp dir, so the symbol file beside the
    original display is only found via search_paths; without it the symbol is an
    empty group whose warning names the missing file (it used to vanish)."""
    data = (EDM_FIXTURES / "symbol_two_state.edl").read_bytes()

    missing = react.convert_bytes(data, kind="edl", filename="symbol_two_state.edl").root.children[0]
    assert missing.type == "group"
    assert missing.children == []
    assert (missing.geometry.x, missing.geometry.y, missing.geometry.width, missing.geometry.height) == (50, 60, 24, 24)
    assert any("symbol file 'symbol_states.edl' not found" in w for w in missing.warnings)

    found = react.convert_bytes(
        data, kind="edl", filename="symbol_two_state.edl", search_paths=[str(EDM_FIXTURES)]
    ).root.children[0]
    assert len([child for child in found.children if child.type == "group"]) == 2
    assert not any("not found" in w for w in found.warnings)


def test_convert_bytes_calc_list_found_via_search_paths(monkeypatch):
    """A named CALC\\sum resolves from a calc.list in a search path directory."""
    monkeypatch.delenv("EDMFILES", raising=False)
    monkeypatch.delenv("EDMCOLORFILE", raising=False)
    data = (EDM_FIXTURES / "calc_rules.edl").read_bytes()

    def sum_formulas(ir):
        return [f for f in ir.formulas if f.expression in ("{A}+{B}", "A+B")]

    assert sum_formulas(react.convert_bytes(data, kind="edl", filename="calc_rules.edl")) == []
    ir = react.convert_bytes(data, kind="edl", filename="calc_rules.edl", search_paths=[EDM_FIXTURES])
    assert len(sum_formulas(ir)) == 1
