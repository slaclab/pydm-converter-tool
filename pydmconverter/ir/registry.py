"""Widget registry access.

The converter resolves a source widget (EDM class -> Qt class, or a Qt class
straight from a ``.ui``) to a Canopy widget definition: its registry id (the IR
``type``), ``qtPropMap`` (drives prop translation), ``propSchema`` (the bindable
surface for rules), and ``defaults``.

In the Canopy backend this is an in-process call to ``canopy.beaver.gateway``.
Here, with Beaver not yet merged and no canopy dependency, we read a vendored
snapshot of the Beaver ``widget-registry-data/widgets/*.json`` files (provenance
in ``data/widget-registry/.beaver-snapshot-sha``). Both satisfy
:class:`RegistryClient`; the converter only depends on the protocol, so the port
is a one-class swap (:class:`BeaverGatewayRegistry`).

A registry miss returns ``None`` so the IR builder can emit a D11
``unknown-widget`` node — the converter never crashes on an unknown class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

WIDGET_REGISTRY_DIR = Path(__file__).parent / "data" / "widget-registry"


class WidgetDefinition(BaseModel):
    """A Canopy widget definition (subset of the Beaver meta-schema we consume).

    Unknown fields (``paletteIcon``, ``inspectorSchema``, ``description``, ...) are
    ignored so the snapshot can carry more than the converter reads.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    id: str
    version: str | None = None
    display_name: str | None = None
    category: str | None = None
    react_component: dict[str, Any] = {}
    qt_mapping: dict[str, Any] | None = None
    prop_schema: dict[str, Any] = {}
    qt_prop_map: dict[str, Any] = {}
    defaults: dict[str, Any] = {}
    supports_pv: bool = False
    supports_rules: bool = False
    supports_children: bool = False

    @property
    def qt_class(self) -> str | None:
        """The Qt class this widget maps from, if any (``None`` for SB-native ids)."""
        return (self.qt_mapping or {}).get("class")


@runtime_checkable
class RegistryClient(Protocol):
    """The seam. Both the vendored snapshot and the Canopy gateway implement it."""

    def by_id(self, widget_id: str) -> WidgetDefinition | None: ...

    def by_qt_class(self, qt_class: str) -> WidgetDefinition | None: ...


class VendoredRegistry:
    """:class:`RegistryClient` backed by the vendored Beaver snapshot on disk.

    Lazily loads and indexes the JSON definitions on first lookup, then caches.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._dir = data_dir or WIDGET_REGISTRY_DIR
        self._by_id: dict[str, WidgetDefinition] = {}
        self._by_qt_class: dict[str, WidgetDefinition] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        for path in sorted(self._dir.glob("*.json")):
            definition = WidgetDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            self._by_id[definition.id] = definition
            if definition.qt_class:
                self._by_qt_class[definition.qt_class] = definition
        self._loaded = True

    def by_id(self, widget_id: str) -> WidgetDefinition | None:
        self._ensure_loaded()
        return self._by_id.get(widget_id)

    def by_qt_class(self, qt_class: str) -> WidgetDefinition | None:
        self._ensure_loaded()
        return self._by_qt_class.get(qt_class)

    @property
    def widget_ids(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._by_id)


class BeaverGatewayRegistry:
    """Canopy-port target: :class:`RegistryClient` over ``canopy.beaver.gateway``.

    Intentionally not implemented in pydm-converter-tool (no canopy dependency).
    When this package becomes ``src/canopy/converter/``, implement these two
    methods as thin in-process calls into the Beaver gateway. Kept here so the
    swap point is explicit.
    """

    def by_id(self, widget_id: str) -> WidgetDefinition | None:
        raise NotImplementedError("BeaverGatewayRegistry lands in the Canopy port (canopy.beaver.gateway)")

    def by_qt_class(self, qt_class: str) -> WidgetDefinition | None:
        raise NotImplementedError("BeaverGatewayRegistry lands in the Canopy port (canopy.beaver.gateway)")
