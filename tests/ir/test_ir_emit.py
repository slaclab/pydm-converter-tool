import json

from pydmconverter.ir import ScreenIR
from pydmconverter.ir.emit import to_json, to_wire_dict, write_screen_json


def test_prunes_empty_lists_and_none(sample_screen):
    """Empty collections and None values are dropped; populated ones remain."""
    text = to_json(sample_screen)
    assert '"rules": []' not in text
    assert '"children": []' not in text
    assert '"warnings": []' not in text
    assert '"savedAt"' not in text  # Source.saved_at is None
    # Real content survives.
    assert '"warnings"' in text  # the unknown-widget node has one
    assert '"borderColor"' in text


def test_keeps_empty_dict_props():
    """An empty props dict is meaningful authored state and is preserved."""
    minimal = {
        "id": "s",
        "metadata": {"title": "t", "source": {"type": "edl-converter"}, "size": {"width": 1, "height": 1}},
        "root": {
            "id": "w-001",
            "type": "absolute-canvas",
            "props": {},
            "geometry": {"x": 0, "y": 0, "width": 1, "height": 1},
        },
    }
    wire = to_wire_dict(ScreenIR.model_validate(minimal))
    assert wire["root"]["props"] == {}


def test_round_trip_byte_stable(sample_screen):
    """D3: emit -> reload -> re-emit is byte-identical."""
    first = to_json(sample_screen)
    reloaded = ScreenIR.model_validate(json.loads(first))
    second = to_json(reloaded)
    assert first == second


def test_trailing_newline(sample_screen):
    assert to_json(sample_screen).endswith("}\n")


def test_write_screen_json(tmp_path, sample_screen):
    out = write_screen_json(sample_screen, tmp_path / "nested" / "vac.screen.json")
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["id"] == "vacuum-system"
