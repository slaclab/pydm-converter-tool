import json
from pathlib import Path

import pytest

from pydmconverter import react

EDM_FIXTURE = Path(__file__).parent / "edm" / "fixtures" / "p0_min.edl"
UI_FIXTURE = Path(__file__).parent / "ui" / "fixtures" / "p0_min.ui"


def test_convert_to_ir_dispatches_by_suffix():
    assert react.convert_to_ir(EDM_FIXTURE).metadata.source.type == "edl-converter"
    assert react.convert_to_ir(UI_FIXTURE).metadata.source.type == "ui-converter"


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
