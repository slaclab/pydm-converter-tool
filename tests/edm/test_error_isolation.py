"""One EDM object (or IR node) that fails to convert must not abort the screen."""

from pydmconverter.edm import ir_adapter
from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.registry import VendoredRegistry
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ir.source import SourceNode

_EDL = """4 0 0
beginScreenProperties
major 4
minor 0
release 0
x 0
y 0
w 200
h 100
endScreenProperties

object activeRectangleClass
beginObjectProperties
major 4
minor 0
release 0
x 10
y 10
w 20
h 20
lineColor index 14
visPv "$(P):VIS"
endObjectProperties

object activeXTextClass
beginObjectProperties
major 4
minor 1
release 1
x 40
y 10
w 60
h 20
value {
  "ok"
}
endObjectProperties
"""


def test_failing_edm_object_becomes_placeholder(tmp_path, monkeypatch):
    def boom(obj, qt_props, warnings):
        raise RuntimeError("fixup exploded")

    monkeypatch.setitem(ir_adapter._CLASS_FIXUPS, "activerectangleclass", boom)
    edl = tmp_path / "iso.edl"
    edl.write_text(_EDL, encoding="utf-8")
    screen = edm_file_to_ir(edl)
    failed, label = screen.root.children
    assert failed.type == "unknown-widget"
    assert failed.props["originalClass"] == "activeRectangleClass"
    assert (failed.geometry.x, failed.geometry.y, failed.geometry.width, failed.geometry.height) == (10, 10, 20, 20)
    assert failed.warnings == [
        "Conversion of activeRectangleClass failed (RuntimeError: fixup exploded); rendering placeholder"
    ]
    assert label.type == "text-label"
    assert validate_screen_json(to_wire_dict(screen)) == []


def test_failing_group_visibility_keeps_group(tmp_path, monkeypatch):
    def boom(group):
        raise ValueError("bad symbol range")

    monkeypatch.setattr(ir_adapter, "_symbol_state_vis", boom)
    edl = tmp_path / "grp.edl"
    edl.write_text(
        _EDL.split("object activeRectangleClass")[0]
        + """object activeGroupClass
beginObjectProperties
major 4
minor 0
release 0
x 0
y 0
w 100
h 50
beginGroup

object activeXTextClass
beginObjectProperties
major 4
minor 1
release 1
x 5
y 5
w 60
h 20
value {
  "in group"
}
endObjectProperties

endGroup

endObjectProperties
""",
        encoding="utf-8",
    )
    group = edm_file_to_ir(edl).root.children[0]
    assert group.type == "group"
    assert group.rules == []
    assert group.warnings == ["EDM group visibility not converted (ValueError: bad symbol range)"]
    assert [child.type for child in group.children] == ["text-label"]


def test_builder_node_failure_becomes_placeholder(monkeypatch):
    """A node the builder cannot build (e.g. a transform raising) is isolated too."""
    builder = IRBuilder(VendoredRegistry())
    original = builder._map_props

    def flaky(qt_props, definition):
        if qt_props.get("text") == "bad":
            raise TypeError("unexpected value")
        return original(qt_props, definition)

    monkeypatch.setattr(builder, "_map_props", flaky)
    nodes = [
        SourceNode(qt_class="QLabel", qt_props={"text": "bad"}, geometry=(0, 0, 10, 10), raw_class="QLabel"),
        SourceNode(qt_class="QLabel", qt_props={"text": "good"}, geometry=(0, 20, 10, 10)),
    ]
    screen = builder.build_screen(
        screen_id="s", title="s", source_type="ui-converter", size=(100, 100), top_level=nodes
    )
    bad, good = screen.root.children
    assert bad.type == "unknown-widget"
    assert bad.warnings == ["Conversion of QLabel failed (TypeError: unexpected value); rendering placeholder"]
    assert good.type == "text-label"
    assert validate_screen_json(to_wire_dict(screen)) == []
