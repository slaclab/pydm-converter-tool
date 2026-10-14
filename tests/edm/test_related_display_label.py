"""A related display's label is its buttonLabel. Its value[] is the literal EDM
writes to pv[i] when it opens a display (related_display.cc), not a label; only
static text shows its value."""

import xml.etree.ElementTree as ET

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.ir_adapter import edm_file_to_ir

SCREEN = """4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 300
h 200
endScreenProperties
"""

RELATED_DISPLAY = """
object relatedDisplayClass
beginObjectProperties
major 4
minor 3
release 0
x 20
y 20
w 140
h 30
fgColor index 14
bgColor index 3
font "helvetica-medium-r-12.0"
{props}
numDsps 1
displayFileName {{
  0 "other.edl"
}}
endObjectProperties
"""

LABEL = 'buttonLabel "Open Mode B"'
PV_VALUE = """numPvs 4
pv {
  0 "DEMO:MODE"
}
value {
  0 "2"
}"""

TEXT = """
object activeXTextClass
beginObjectProperties
major 4
minor 1
release 1
x {x}
y 20
w 140
h 30
font "helvetica-medium-r-12.0"
fgColor index 14
bgColor index 3
useDisplayBg
value {{
  "{text}"
}}
endObjectProperties
"""

# value[] after buttonLabel used to replace the label; before it, it lost.
ORDERS = [
    pytest.param(f"{LABEL}\n{PV_VALUE}", id="value-after-label"),
    pytest.param(f"{PV_VALUE}\n{LABEL}", id="value-before-label"),
]


def _write(tmp_path, *objects):
    source = tmp_path / "reldsp.edl"
    source.write_text(SCREEN + "".join(objects), encoding="utf-8")
    return source


def _ui_widgets(tmp_path, source, widget_class):
    output = tmp_path / "reldsp.ui"
    convert(str(source), str(output))
    return [w for w in ET.parse(output).iter("widget") if w.get("class") == widget_class]


def _text(widget):
    prop = widget.find("property[@name='text']/string")
    return None if prop is None else prop.text


@pytest.mark.parametrize("props", ORDERS)
def test_ir_related_display_label_is_its_button_label(tmp_path, props):
    source = _write(tmp_path, RELATED_DISPLAY.format(props=props))
    [button] = edm_file_to_ir(source).root.children
    assert button.type == "related-display-button"
    assert button.props["label"] == "Open Mode B"


@pytest.mark.parametrize("props", ORDERS)
def test_ui_related_display_text_is_its_button_label(tmp_path, props):
    source = _write(tmp_path, RELATED_DISPLAY.format(props=props))
    [button] = _ui_widgets(tmp_path, source, "PyDMRelatedDisplayButton")
    assert _text(button) == "Open Mode B"


def test_ir_related_display_without_a_button_label_has_no_label(tmp_path):
    source = _write(tmp_path, RELATED_DISPLAY.format(props=PV_VALUE))
    [button] = edm_file_to_ir(source).root.children
    assert "label" not in button.props


def test_ui_related_display_without_a_button_label_has_no_text(tmp_path):
    source = _write(tmp_path, RELATED_DISPLAY.format(props=PV_VALUE))
    [button] = _ui_widgets(tmp_path, source, "PyDMRelatedDisplayButton")
    assert _text(button) is None


def test_static_text_value_is_its_text(tmp_path):
    source = _write(tmp_path, TEXT.format(x=20, text="Mode B"))
    [label] = edm_file_to_ir(source).root.children
    assert label.type == "text-label"
    assert label.props["text"] == "Mode B"
    [label] = _ui_widgets(tmp_path, source, "PyDMLabel")
    assert _text(label) == "Mode B"


def test_reg_text_value_is_its_text(tmp_path):
    source = _write(tmp_path, TEXT.format(x=20, text="Mode B").replace("activeXTextClass", "activeXRegTextClass"))
    [label] = edm_file_to_ir(source).root.children
    assert label.props["text"] == "Mode B"
    [label] = _ui_widgets(tmp_path, source, "PyDMLabel")
    assert _text(label) == "Mode B"


@pytest.mark.parametrize(
    "props",
    [
        pytest.param(LABEL, id="with-button-label"),
        pytest.param("", id="no-button-label"),
        # Its value {} used to keep the text off the button.
        pytest.param(f"{LABEL}\n{PV_VALUE}", id="with-value-block"),
    ],
)
def test_ui_text_covering_a_related_display_becomes_its_label(tmp_path, props):
    """The .ui merges a static text drawn over a related display into the button."""
    source = _write(tmp_path, RELATED_DISPLAY.format(props=props), TEXT.format(x=20, text="Mode B"))
    [button] = _ui_widgets(tmp_path, source, "PyDMRelatedDisplayButton")
    assert _text(button) == "Mode B"
    assert _ui_widgets(tmp_path, source, "PyDMLabel") == []


def test_ui_related_display_takes_one_covering_text(tmp_path):
    source = _write(
        tmp_path,
        RELATED_DISPLAY.format(props=LABEL),
        TEXT.format(x=20, text="Mode B"),
        TEXT.format(x=22, text="Second"),
    )
    [button] = _ui_widgets(tmp_path, source, "PyDMRelatedDisplayButton")
    assert _text(button) == "Mode B"
    assert [_text(label) for label in _ui_widgets(tmp_path, source, "PyDMLabel")] == ["Second"]
