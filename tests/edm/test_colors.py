from pathlib import Path

import pytest

from pydmconverter.edm import ir_adapter
from pydmconverter.edm.ir_adapter import edm_color_to_hex
from pydmconverter.edm.parser_helpers import parse_colors_list
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.react import convert_to_ir

FIXTURES = Path(__file__).parent / "fixtures"
COLORS_FIXTURE = FIXTURES / "colors.list"
COLORS_FILE = FIXTURES / "p0_colors.edl"


@pytest.fixture
def colors():
    return parse_colors_list(str(COLORS_FIXTURE))


# --- edm_color_to_hex unit tests -------------------------------------------------


def test_index_resolves_to_hex(colors):
    assert edm_color_to_hex("index 25", colors) == "#0000ff"
    assert edm_color_to_hex("index 14", colors) == "#ffff00"


def test_blinking_index_uses_first_state(colors):
    """A blinking static colour carries six components (two RGB states); only the first is used."""
    assert edm_color_to_hex("index 33", colors) == "#ff0000"


def test_unknown_index_is_none(colors):
    assert edm_color_to_hex("index 9999", colors) is None


def test_rgb_16bit_is_scaled(colors):
    assert edm_color_to_hex("rgb 65535 0 0", colors) == "#ff0000"


def test_rgb_8bit_is_unscaled(colors):
    assert edm_color_to_hex("rgb 0 0 0", colors) == "#000000"
    assert edm_color_to_hex("rgb 128 128 128", colors) == "#808080"


@pytest.mark.parametrize("value", ["banana", "", None])
def test_garbage_values_are_none(colors, value):
    assert edm_color_to_hex(value, colors) is None


# --- end-to-end conversion via convert_to_ir -------------------------------------


def _by_type_list(color_list_path=COLORS_FIXTURE):
    ir = convert_to_ir(COLORS_FILE, color_list_path=str(color_list_path))
    return ir.root.children


def test_resolved_static_colours():
    widget = _by_type_list()[0]
    assert widget.type == "text-label"
    assert widget.props["foregroundColor"] == "#0000ff"
    assert widget.props["backgroundColor"] == "#000000"


def test_use_display_bg_skips_background():
    widget = _by_type_list()[1]
    assert widget.props["foregroundColor"] == "#ffff00"
    assert "backgroundColor" not in widget.props


def test_unresolvable_colour_drops_prop_with_warning():
    widget = _by_type_list()[2]
    assert "foregroundColor" not in widget.props
    assert any("index 9999" in warning for warning in widget.warnings)


def test_dynamic_colour_flag_warns_and_prop_map_drops_colour():
    """pv-text-input's qtPropMap has no foregroundColor entry, so the resolved
    rgb colour is silently dropped by the allowlist; the colorPv flag still warns."""
    widget = _by_type_list()[3]
    assert widget.type == "pv-text-input"
    assert "foregroundColor" not in widget.props
    assert any("dynamic colour" in warning for warning in widget.warnings)


def test_p0_colors_screen_validates():
    ir = convert_to_ir(COLORS_FILE, color_list_path=str(COLORS_FIXTURE))
    assert validate_screen_json(to_wire_dict(ir)) == []


# --- injection mechanism ----------------------------------------------------------


def test_no_param_no_env_no_default_drops_index_colour(monkeypatch):
    """With no palette resolvable at all, an "index N" colour cannot be resolved."""
    monkeypatch.setattr(ir_adapter, "search_color_list", lambda cli_color_file=None: None)
    ir = convert_to_ir(COLORS_FILE)
    widget = ir.root.children[0]
    assert "foregroundColor" not in widget.props
    assert any("index 25" in warning for warning in widget.warnings)


def test_edmcolorfile_env_is_used_when_no_param(monkeypatch):
    monkeypatch.setenv("EDMCOLORFILE", str(COLORS_FIXTURE))
    monkeypatch.delenv("EDMFILES", raising=False)
    ir = convert_to_ir(COLORS_FILE)
    widget = ir.root.children[0]
    assert widget.props["foregroundColor"] == "#0000ff"


def test_explicit_param_beats_env(monkeypatch, tmp_path):
    monkeypatch.setenv("EDMCOLORFILE", str(COLORS_FIXTURE))
    alt_colors = tmp_path / "colors.list"
    alt_colors.write_text(
        "4 0 0\n\nmax=0x10000\n\nstatic 25 \"Controller\" { 0xffff 0 0 }\n",
        encoding="utf-8",
        newline="\n",
    )
    ir = convert_to_ir(COLORS_FILE, color_list_path=str(alt_colors))
    widget = ir.root.children[0]
    assert widget.props["foregroundColor"] == "#ff0000"
