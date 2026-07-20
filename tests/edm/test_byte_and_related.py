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
