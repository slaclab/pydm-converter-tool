from pydmconverter.ir.registry import (
    BeaverGatewayRegistry,
    RegistryClient,
    VendoredRegistry,
    WidgetDefinition,
)

BASE_WIDGET_IDS = {
    "absolute-canvas",
    "embedded-display",
    "pv-label",
    "pv-text-input",
    "pv-button",
    "pv-led",
    "pv-slider",
    "pv-enum-combobox",
}


def test_vendored_registry_is_a_registry_client():
    assert isinstance(VendoredRegistry(), RegistryClient)


def test_base_widgets_present():
    """All 8 base widget ids resolve in the vendored snapshot."""
    reg = VendoredRegistry()
    assert BASE_WIDGET_IDS.issubset(set(reg.widget_ids))


def test_by_qt_class_resolves_pydm_classes():
    reg = VendoredRegistry()
    label = reg.by_qt_class("PyDMLabel")
    assert label is not None
    assert label.id == "pv-label"
    assert label.qt_class == "PyDMLabel"
    assert label.qt_prop_map["channel"] == {"to": "pv", "transform": "stripProtocol"}
    assert label.defaults == {"width": 100, "height": 24}
    assert label.supports_rules is True


def test_by_id_returns_full_definition():
    reg = VendoredRegistry()
    button = reg.by_id("pv-button")
    assert button is not None
    assert button.qt_class == "PyDMPushButton"
    assert isinstance(button.prop_schema, dict)


def test_registry_miss_returns_none():
    """A miss yields None so the IR builder can emit an unknown-widget node."""
    reg = VendoredRegistry()
    assert reg.by_qt_class("PyDMTotallyMadeUpGauge") is None
    assert reg.by_id("nonexistent-widget") is None


def test_sb_native_widgets_have_no_qt_class():
    """absolute-canvas / group have no qtMapping (06_beaver.md)."""
    reg = VendoredRegistry()
    assert reg.by_id("absolute-canvas").qt_class is None
    assert reg.by_id("group").qt_class is None


NEW_DRAWING_IDS = {"rectangle", "ellipse", "line", "arc", "group", "pv-meter"}


def test_new_widget_ids_resolve_by_id():
    """The six new EDM-coverage widgets resolve via by_id."""
    reg = VendoredRegistry()
    for widget_id in NEW_DRAWING_IDS:
        assert reg.by_id(widget_id) is not None, f"missing registry def for {widget_id!r}"


def test_new_widgets_resolve_by_qt_class():
    reg = VendoredRegistry()
    expected = {
        "PyDMDrawingRectangle": "rectangle",
        "PyDMDrawingEllipse": "ellipse",
        "PyDMDrawingPolyline": "line",
        "PyDMDrawingArc": "arc",
        "PyDMAnalogIndicator": "pv-meter",
        "PyDMEnumButton": "pv-radio-group",
    }
    for qt_class, widget_id in expected.items():
        definition = reg.by_qt_class(qt_class)
        assert definition is not None, f"no definition for qt_class {qt_class!r}"
        assert definition.id == widget_id


def test_group_has_no_qt_class_and_supports_children():
    """group is resolved by registry id from the EDM adapter; no Qt analog."""
    reg = VendoredRegistry()
    group = reg.by_id("group")
    assert group is not None
    assert group.qt_class is None
    assert reg.by_qt_class("group") is None
    assert group.supports_children is True


def test_widget_definition_ignores_unknown_fields():
    """The model tolerates extra Beaver fields (paletteIcon, inspectorSchema...)."""
    d = WidgetDefinition.model_validate(
        {"id": "x", "paletteIcon": "x.svg", "inspectorSchema": {"groups": []}, "supportsPv": True}
    )
    assert d.id == "x"
    assert d.supports_pv is True


def test_gateway_registry_is_a_registry_client_but_unimplemented():
    """The Canopy-port backend satisfies the protocol shape but is not wired here."""
    assert isinstance(BeaverGatewayRegistry(), RegistryClient)
