from pydmconverter.ir.registry import (
    BeaverGatewayRegistry,
    RegistryClient,
    VendoredRegistry,
    WidgetDefinition,
)

P0_IDS = {
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


def test_p0_widgets_present():
    """All 8 P0 widget ids resolve in the vendored snapshot."""
    reg = VendoredRegistry()
    assert P0_IDS.issubset(set(reg.widget_ids))


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
    """absolute-canvas / pv-radio-group have no qtMapping (06_beaver.md)."""
    reg = VendoredRegistry()
    assert reg.by_id("absolute-canvas").qt_class is None
    assert reg.by_id("pv-radio-group").qt_class is None


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
