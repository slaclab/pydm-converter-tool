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


def test_parse_points():
    # "x, y" stringlist -> structured {x, y} floats
    assert apply_transform("parsePoints", ["0.0, 0.0", "7.0, 5.0", "14.0, 0.0"]) == [
        {"x": 0.0, "y": 0.0},
        {"x": 7.0, "y": 5.0},
        {"x": 14.0, "y": 0.0},
    ]
    # tolerant of spacing variants and negatives
    assert apply_transform("parsePoints", ["1,2", " -3 , 4 "]) == [
        {"x": 1.0, "y": 2.0},
        {"x": -3.0, "y": 4.0},
    ]
    # a lone string is wrapped
    assert apply_transform("parsePoints", "5, 6") == [{"x": 5.0, "y": 6.0}]
    # unparseable entries are skipped, not fatal
    assert apply_transform("parsePoints", ["1, 2", "junk", "3, 4"]) == [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0, "y": 4.0},
    ]
    # idempotent: already-structured points pass through
    already = [{"x": 1.0, "y": 2.0}]
    assert apply_transform("parsePoints", already) == already


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


def test_edm_line_style():
    assert apply_transform("edmLineStyle", "solid") == "solid"
    assert apply_transform("edmLineStyle", "dash") == "dashed"
    assert apply_transform("edmLineStyle", "Qt::DashLine") == "dashed"
    assert apply_transform("edmLineStyle", "DotLine") == "dotted"
    assert apply_transform("edmLineStyle", "anything") == "solid"


def test_parse_json_strings():
    # a stringlist of JSON blobs -> list of parsed objects
    assert apply_transform("parseJsonStrings", ['{"a": 1}', '{"b": 2}']) == [{"a": 1}, {"b": 2}]
    # a malformed entry is skipped, not fatal
    assert apply_transform("parseJsonStrings", ['{"a": 1}', "not json"]) == [{"a": 1}]
    # a lone JSON string is wrapped into a one-element list
    assert apply_transform("parseJsonStrings", '{"a": 1}') == [{"a": 1}]
    # empty list stays empty; non-list passes through
    assert apply_transform("parseJsonStrings", []) == []
    assert apply_transform("parseJsonStrings", 5) == 5


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


def test_screen_ref_rewrites_to_screen_json():
    from pydmconverter.ir.transforms import screen_ref, DROP

    # .ui / .edl -> .screen.json, RELATIVE DIR PRESERVED (subdir templates share
    # basenames — Collimator/Widget vs Heater/Widget — so the dir must survive).
    assert screen_ref("motor-simple.ui") == "motor-simple.screen.json"
    assert screen_ref("sub/dir/foo.edl") == "sub/dir/foo.screen.json"
    assert screen_ref("Collimator/Widget.ui") == "Collimator/Widget.screen.json"
    # filenames stringlist -> first, rewritten
    assert screen_ref(["a.ui", "b.ui"]) == "a.screen.json"
    # extensionless PyDM related-display target -> append
    assert screen_ref("mc_li21_coll") == "mc_li21_coll.screen.json"
    # already-converted / macro refs left sensible
    assert screen_ref("x.screen.json") == "x.screen.json"
    assert screen_ref("${SCREEN}") == "${SCREEN}"
    # empty list drops
    assert screen_ref([]) is DROP
