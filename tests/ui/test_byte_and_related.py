from pathlib import Path

from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ui.ir_adapter import ui_file_to_ir

FIXTURE = Path(__file__).parent / "fixtures" / "byte_and_related.ui"


def _by_type():
    return {c.type: c for c in ui_file_to_ir(FIXTURE).root.children}


def test_all_widget_types_resolve():
    """byte/related-display/frame/progress-bar/group-box widgets resolve from .ui with no adapter changes (registry-driven)."""
    assert set(_by_type()) == {
        "pv-byte-led",
        "pv-checkbox",
        "related-display-button",
        "frame",
        "pv-progress-bar",
        "group-box",
    }


def test_byte_led_props():
    assert _by_type()["pv-byte-led"].props == {"pv": "${P}:BITS", "numBits": 8}


def test_related_display_firstof_and_label():
    """filenames stringlist -> file via firstOf; text -> label."""
    assert _by_type()["related-display-button"].props == {"file": "sub.screen.json", "label": "Open"}


def test_frame_enum_transforms():
    assert _by_type()["frame"].props == {"shape": "box", "shadow": "sunken"}


def test_progress_bar_limits():
    assert _by_type()["pv-progress-bar"].props == {"pv": "${P}:LVL", "min": 0.0, "max": 100.0}


def test_group_box_is_a_container():
    group = _by_type()["group-box"]
    assert group.props == {"title": "Group"}
    assert [child.type for child in group.children] == ["pv-label"]


def test_screen_validates():
    assert validate_screen_json(to_wire_dict(ui_file_to_ir(FIXTURE))) == []
