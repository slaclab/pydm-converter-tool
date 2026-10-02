import json

from pydmconverter.ir.registry import (
    WIDGET_REGISTRY_DIR,
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


def test_by_id_returns_full_definition():
    reg = VendoredRegistry()
    button = reg.by_id("pv-button")
    assert button is not None
    assert button.qt_class == "PyDMPushButton"
    assert button.qt_prop_map["channel"]["to"] == "pv"


def test_registry_miss_returns_none():
    """A miss yields None so the IR builder can emit an unknown-widget node."""
    reg = VendoredRegistry()
    assert reg.by_qt_class("PyDMTotallyMadeUpGauge") is None
    assert reg.by_id("nonexistent-widget") is None


def test_sb_native_widgets_have_no_qt_class():
    """absolute-canvas / group have no qtMapping: they have no Qt analog."""
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


def test_group_has_no_qt_class():
    """group is resolved by registry id from the EDM adapter; no Qt analog."""
    reg = VendoredRegistry()
    group = reg.by_id("group")
    assert group is not None
    assert group.qt_class is None
    assert reg.by_qt_class("group") is None


def test_widget_definition_ignores_unknown_fields():
    """The model tolerates fields the converter does not read (propSchema, paletteIcon, ...)."""
    d = WidgetDefinition.model_validate(
        {"id": "x", "paletteIcon": "x.svg", "propSchema": {"type": "object"}, "supportsPv": True}
    )
    assert d.id == "x"
    assert d.qt_class is None


def test_registry_files_carry_only_converter_fields():
    """Each definition holds its id and Qt mappings and nothing else.

    The IR contract (props, ``supports*``) is canopy-spec's and editor metadata
    belongs to the widget set, so neither is copied here to drift.
    """
    paths = sorted(WIDGET_REGISTRY_DIR.glob("*.json"))
    assert paths
    for path in paths:
        definition = json.loads(path.read_text(encoding="utf-8"))
        assert definition["id"] == path.stem
        assert set(definition) <= {"id", "qtMapping", "qtPropMap"}, path.name


def test_newly_supported_ui_classes_resolve_by_qt_class():
    """QWidget / PyDMShellCommand / PyDMWaveformPlot resolve instead of unknown-widget."""
    reg = VendoredRegistry()
    expected = {
        "QWidget": "qwidget-container",
        "PyDMShellCommand": "shell-command-button",
        "PyDMWaveformPlot": "waveform-plot",
    }
    for qt_class, widget_id in expected.items():
        definition = reg.by_qt_class(qt_class)
        assert definition is not None, f"no definition for qt_class {qt_class!r}"
        assert definition.id == widget_id


def test_group_stays_sb_native():
    """group must remain SB-native (no Qt class) — QWidget uses qwidget-container instead."""
    reg = VendoredRegistry()
    assert reg.by_id("group").qt_class is None
    assert reg.by_qt_class("QWidget").id != "group"
