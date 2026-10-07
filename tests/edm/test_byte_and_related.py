from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURE = Path(__file__).parent / "fixtures" / "byte_and_related.edl"


def _by_type():
    return {c.type: c for c in edm_file_to_ir(FIXTURE).root.children}


def test_byte_class_to_pv_byte_led():
    byte = _by_type()["pv-byte-led"]
    assert byte.props == {"pv": "${P}:BITS", "numBits": 8}  # numBits coerced to int


def test_related_display_class():
    """displayFileName list -> file (firstOf); buttonLabel -> label; symbols -> macros."""
    rel = _by_type()["related-display-button"]
    assert rel.props == {"file": "subscreen.screen.json", "label": "Open", "macros": {"DEV": "${P}"}}


def test_screen_validates():
    assert validate_screen_json(to_wire_dict(edm_file_to_ir(FIXTURE))) == []


def test_related_display_opens_first_listed_display(tmp_path):
    """dc282Brd.edl: entry 0 is unused, so displayFileName and symbols start at index 1."""
    text = FIXTURE.read_text().replace('  0 "subscreen"', '  1 "subscreen"').replace('  0 "DEV=$(P)"', '  1 "DEV=$(P)"')
    edl = tmp_path / "related.edl"
    edl.write_text(text)
    rel = {c.type: c for c in edm_file_to_ir(edl).root.children}["related-display-button"]
    assert rel.props == {"file": "subscreen.screen.json", "label": "Open", "macros": {"DEV": "${P}"}}
