from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.registry import VendoredRegistry
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.ir.source import SourceNode


def _builder() -> IRBuilder:
    return IRBuilder(VendoredRegistry())


def _screen(top_level, **kw):
    kw.setdefault("screen_id", "s")
    kw.setdefault("title", "S")
    kw.setdefault("source_type", "edl-converter")
    kw.setdefault("size", (800, 600))
    return _builder().build_screen(top_level=top_level, **kw)


def test_root_canvas_and_metadata():
    screen = _screen([])
    assert screen.root.type == "absolute-canvas"
    assert screen.root.id == "w-001"
    assert screen.root.props == {"width": 800, "height": 600}
    assert screen.metadata.size.width == 800
    assert screen.metadata.source.type == "edl-converter"


def test_pv_label_prop_mapping_and_transform():
    """PyDMLabel -> pv-label; channel stripped to pv; format/precision mapped."""
    node = SourceNode(
        qt_class="PyDMLabel",
        qt_props={
            "channel": "ca://${PREFIX}:PRESSURE",
            "precision": 3,
            "showUnits": True,
            "alarmSensitiveContent": True,
            "displayFormat": "hex",
        },
        geometry=(10, 20, 200, 30),
    )
    label = _screen([node]).root.children[0]
    assert label.type == "pv-label"
    assert label.id == "w-002"
    assert label.props == {
        "pv": "${PREFIX}:PRESSURE",  # stripProtocol dropped ca://
        "precision": 3,
        "showUnits": True,
        "alarmSensitive": True,
        "format": "hex",
    }
    assert label.geometry.model_dump() == {"x": 10, "y": 20, "width": 200, "height": 30}


def test_pv_label_alignment_maps_to_align():
    """PyDMLabel alignment=Qt::AlignCenter -> pv-label align="center" (qtAlignment)."""
    node = SourceNode(
        qt_class="PyDMLabel",
        qt_props={"text": "Horizontal Motors", "alignment": "Qt::AlignCenter"},
    )
    label = _screen([node]).root.children[0]
    assert label.type == "pv-label"
    assert label.props == {"text": "Horizontal Motors", "align": "center"}


def test_bool_to_from_pv_true_and_false():
    true_node = SourceNode(qt_class="PyDMLabel", qt_props={"precisionFromPV": True})
    assert _screen([true_node]).root.children[0].props == {"precision": "fromPV"}
    # False defers to explicit precision -> the mapped prop is dropped
    false_node = SourceNode(qt_class="PyDMLabel", qt_props={"precisionFromPV": False})
    assert _screen([false_node]).root.children[0].props == {}


def test_slider_orientation_transform():
    node = SourceNode(qt_class="PyDMSlider", qt_props={"channel": "X:Y", "orientation": "Qt::Vertical"})
    slider = _screen([node]).root.children[0]
    assert slider.type == "pv-slider"
    assert slider.props == {"pv": "X:Y", "orientation": "vertical"}


def test_unmapped_props_are_dropped():
    """Only props in the widget's qtPropMap pass through."""
    node = SourceNode(qt_class="PyDMLabel", qt_props={"channel": "X", "notARealQtProp": 1})
    assert _screen([node]).root.children[0].props == {"pv": "X"}


def test_unknown_widget_node():
    node = SourceNode(
        qt_class="PyDMMysteryGauge",
        raw_class="activeMysteryClass",
        raw_props={"foo": 1, "bar": "baz"},
        geometry=(5, 6, 7, 8),
    )
    unknown = _screen([node]).root.children[0]
    assert unknown.type == "unknown-widget"
    assert unknown.props == {"originalClass": "activeMysteryClass", "originalProps": {"foo": 1, "bar": "baz"}}
    assert unknown.warnings == ["No registry entry for activeMysteryClass; rendering placeholder"]


def test_children_order_is_z_order_and_ids_deterministic():
    nodes = [
        SourceNode(qt_class="PyDMLabel", qt_props={"channel": "A"}),
        SourceNode(qt_class="PyDMPushButton", qt_props={"channel": "B"}),
        SourceNode(qt_class="PyDMLineEdit", qt_props={"channel": "C"}),
    ]
    children = _screen(nodes).root.children
    assert [c.type for c in children] == ["pv-label", "pv-button", "pv-text-input"]
    assert [c.id for c in children] == ["w-002", "w-003", "w-004"]


def test_nested_children():
    inner = SourceNode(qt_class="PyDMLabel", qt_props={"channel": "A"})
    # embedded-display supports children in the source tree; builder recurses
    outer = SourceNode(qt_class="PyDMEmbeddedDisplay", qt_props={"filename": "child.ui"}, children=[inner])
    node = _screen([outer]).root.children[0]
    assert node.type == "embedded-display"
    assert node.props == {"file": "child.screen.json"}
    assert node.children[0].type == "pv-label"


def test_macro_collection():
    nodes = [
        SourceNode(qt_class="PyDMLabel", qt_props={"channel": "${PREFIX}:P"}),
        SourceNode(qt_class="PyDMPushButton", qt_props={"channel": "${DEVICE}:GO", "text": "${DEVICE} go"}),
    ]
    screen = _screen(nodes)
    assert [(m.name, m.default) for m in screen.macros] == [("DEVICE", ""), ("PREFIX", "")]


def test_explicit_macros_override_collection():
    node = SourceNode(qt_class="PyDMLabel", qt_props={"channel": "${PREFIX}:P"})
    screen = _screen([node], macros=[])
    assert screen.macros == []


def test_rules_get_ids_and_contribute_macros():
    """RuleSpecs become Rules with allocated r-NNN ids; rule PV macros are declared."""
    from pydmconverter.ir.source import RuleSpec

    node = SourceNode(
        qt_class="PyDMLabel",
        qt_props={"channel": "X"},
        rules=[
            RuleSpec(
                target_property="visible",
                name="V",
                pvs=[("${SECTOR}:OK", True)],
                conditions=[("{0} != 0", True)],
                default=False,
            )
        ],
    )
    screen = _screen([node])
    label = screen.root.children[0]
    assert label.rules[0].id == "r-001"
    assert label.rules[0].target_property == "visible"
    assert [m.name for m in screen.macros] == ["SECTOR"]


def test_calc_channel_hoisted_to_fox_formula():
    """A calc:// channel lowers to a screen-level formula + fox:// reference."""
    node = SourceNode(qt_class="PyDMLabel", qt_props={"channel": "calc://c?A=channel://${P}:V&B=ca://X&expr=A+B"})
    screen = _screen([node])
    assert screen.root.children[0].props["pv"] == "fox://f-001"
    assert len(screen.formulas) == 1
    formula = screen.formulas[0]
    assert formula.name == "f-001"
    assert formula.expression == "A+B"
    assert formula.bindings == {"A": "${P}:V", "B": "X"}
    assert [m.name for m in screen.macros] == ["P"]  # macro from the binding


def test_identical_calcs_share_one_formula():
    nodes = [
        SourceNode(qt_class="PyDMLabel", qt_props={"channel": "calc://a?A=channel://X&expr=A*2"}),
        SourceNode(qt_class="PyDMLabel", qt_props={"channel": "calc://b?A=channel://X&expr=A*2"}),
    ]
    screen = _screen(nodes)
    pvs = [c.props["pv"] for c in screen.root.children]
    assert pvs == ["fox://f-001", "fox://f-001"]  # deduped
    assert len(screen.formulas) == 1


def test_registry_id_builds_group_with_nested_child():
    """A SourceNode with registry_id="group" resolves by id and nests its children."""
    child = SourceNode(qt_class="PyDMLabel", qt_props={"channel": "X"})
    node = SourceNode(
        qt_class=None,
        registry_id="group",
        qt_props={"layoutMode": "absolute"},
        children=[child],
        geometry=(0, 0, 200, 150),
    )
    group = _screen([node]).root.children[0]
    assert group.type == "group"
    assert group.props == {"layoutMode": "absolute"}
    assert len(group.children) == 1
    assert group.children[0].type == "pv-label"


def test_registry_id_takes_precedence_over_qt_class():
    """When both are set, registry_id wins over qt_class."""
    node = SourceNode(qt_class="PyDMLabel", registry_id="group", qt_props={"layoutMode": "flex"})
    built = _screen([node]).root.children[0]
    assert built.type == "group"
    assert built.props == {"layoutMode": "flex"}


def test_unknown_registry_id_falls_back_to_unknown_widget():
    """An unresolvable registry_id (and no qt_class) falls back to unknown-widget."""
    node = SourceNode(
        qt_class=None,
        registry_id="not-a-real-registry-id",
        raw_class="edmMysteryGroup",
        raw_props={"foo": "bar"},
    )
    built = _screen([node]).root.children[0]
    assert built.type == "unknown-widget"
    assert built.props == {"originalClass": "edmMysteryGroup", "originalProps": {"foo": "bar"}}


def test_built_screen_validates_and_round_trips():
    nodes = [
        SourceNode(
            qt_class="PyDMLabel", qt_props={"channel": "ca://${PREFIX}:P", "precision": 2}, geometry=(1, 2, 3, 4)
        ),
        SourceNode(qt_class="ActiveMysteryClass", raw_class="activeMysteryClass", geometry=(0, 0, 1, 1)),
    ]
    screen = _screen(nodes)
    wire = to_wire_dict(screen)
    assert validate_screen_json(wire) == []
    # round-trip byte-stable
    from pydmconverter.ir.model import ScreenIR

    assert to_json(ScreenIR.model_validate(wire)) == to_json(screen)


def test_screen_size_expands_to_encompass_children():
    """metadata.size grows so children extending past the root rect aren't
    clipped (convert-fidelity defect O: PyDM windows auto-grow/scroll)."""
    from pydmconverter.ir.builder import IRBuilder
    from pydmconverter.ir.registry import VendoredRegistry
    from pydmconverter.ir.source import SourceNode

    b = IRBuilder(VendoredRegistry())
    # child reaches x+w=790, y+h=200; declared window is only 710x100
    child = SourceNode(qt_class="QLabel", qt_props={"text": "x"}, geometry=(10, 10, 780, 190))
    ir = b.build_screen(screen_id="t", title="t", source_type="ui-converter", size=(710, 100), top_level=[child])
    assert ir.metadata.size.width >= 790  # +margin
    assert ir.metadata.size.height >= 200
    # a screen whose children fit is left unchanged
    small = SourceNode(qt_class="QLabel", qt_props={"text": "x"}, geometry=(10, 10, 100, 20))
    ir2 = b.build_screen(screen_id="t2", title="t", source_type="ui-converter", size=(710, 500), top_level=[small])
    assert (ir2.metadata.size.width, ir2.metadata.size.height) == (710, 500)
