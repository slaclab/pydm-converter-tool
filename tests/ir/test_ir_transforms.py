import json

import pytest

from pydmconverter.ir.registry import WIDGET_REGISTRY_DIR
from pydmconverter.ir.transforms import DROP, apply_transform, known_transforms


def test_strip_protocol():
    assert apply_transform("stripProtocol", "ca://LI21:271:BACT") == "LI21:271:BACT"
    assert apply_transform("stripProtocol", "pva://X:Y") == "X:Y"
    assert apply_transform("stripProtocol", "${PREFIX}:PRESSURE") == "${PREFIX}:PRESSURE"
    # first-class schemes are preserved
    assert apply_transform("stripProtocol", "loc://sel?type=int") == "loc://sel?type=int"
    assert apply_transform("stripProtocol", "fox://f-001") == "fox://f-001"


def test_bool_to_from_pv():
    assert apply_transform("boolToFromPV", True) == "fromPV"
    assert apply_transform("boolToFromPV", "true") == "fromPV"
    assert apply_transform("boolToFromPV", 1) == "fromPV"
    # False defers to the explicit precision prop -> drop
    assert apply_transform("boolToFromPV", False) is DROP
    assert apply_transform("boolToFromPV", "false") is DROP


def test_qt_orientation():
    assert apply_transform("qtOrientation", "Qt::Horizontal") == "horizontal"
    assert apply_transform("qtOrientation", "Qt::Vertical") == "vertical"
    assert apply_transform("qtOrientation", 1) == "horizontal"
    assert apply_transform("qtOrientation", 2) == "vertical"


def test_qt_alignment():
    assert apply_transform("qtAlignment", "Qt::AlignLeft") == "left"
    assert apply_transform("qtAlignment", "Qt::AlignRight") == "right"
    assert apply_transform("qtAlignment", "Qt::AlignHCenter") == "center"
    assert apply_transform("qtAlignment", "Qt::AlignCenter") == "center"
    assert apply_transform("qtAlignment", "Qt::AlignRight|Qt::AlignVCenter") == "right"
    assert apply_transform("qtAlignment", "Qt::AlignVCenter") == "left"  # vertical only -> default


def test_qt_frame_shape():
    assert apply_transform("qtFrameShape", "QFrame::StyledPanel") == "styled-panel"
    assert apply_transform("qtFrameShape", "QFrame::HLine") == "h-line"
    assert apply_transform("qtFrameShape", "QFrame::NoFrame") == "no-frame"
    assert apply_transform("qtFrameShape", "QFrame::Box") == "box"


def test_qt_frame_shadow():
    assert apply_transform("qtFrameShadow", "QFrame::Sunken") == "sunken"
    assert apply_transform("qtFrameShadow", "QFrame::Raised") == "raised"
    assert apply_transform("qtFrameShadow", "QFrame::Plain") == "plain"


def test_qt_scroll_policy():
    assert apply_transform("qtScrollPolicy", "Qt::ScrollBarAsNeeded") == "auto"
    assert apply_transform("qtScrollPolicy", "Qt::ScrollBarAlwaysOff") == "always-off"
    assert apply_transform("qtScrollPolicy", "Qt::ScrollBarAlwaysOn") == "always-on"


def test_first_of():
    assert apply_transform("firstOf", ["a.ui", "b.ui"]) == "a.ui"
    assert apply_transform("firstOf", []) is DROP
    assert apply_transform("firstOf", "already-scalar") == "already-scalar"


def test_unknown_transform_raises():
    with pytest.raises(KeyError):
        apply_transform("notARealTransform", "x")


def test_transforms_cover_registry():
    """Every transform the vendored registry references must be implemented.

    Guards converter/Beaver lock-step: a referenced-but-missing transform would
    silently drop a prop in the IR builder.
    """
    referenced = set()
    for path in WIDGET_REGISTRY_DIR.glob("*.json"):
        definition = json.loads(path.read_text(encoding="utf-8"))
        for entry in definition.get("qtPropMap", {}).values():
            if isinstance(entry, dict) and "transform" in entry:
                referenced.add(entry["transform"])
    missing = referenced - set(known_transforms())
    assert not missing, f"registry references transforms with no implementation: {sorted(missing)}"
