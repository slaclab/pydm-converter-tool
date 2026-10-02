"""Widget registry access.

The converter resolves a source widget (EDM class -> Qt class, or a Qt class
straight from a ``.ui``) to a registry definition: its id (the IR ``type``), its
``qtMapping`` and its ``qtPropMap`` (drives prop translation).

The definitions live in ``data/widget-registry/*.json`` and are the source of
truth for the Qt mappings; edit them here. They carry only what the converter
reads. The IR contract for each type (its props and ``supports*`` flags) is
published by slaclab/canopy-spec, and editor metadata lives with the screen
widget set.

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
    """A registry definition: an IR widget type and how Qt widgets map onto it.

    Unknown fields are ignored, so a definition carrying more than the converter
    reads still loads.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    id: str
    qt_mapping: dict[str, Any] | None = None
    qt_prop_map: dict[str, Any] = {}

    @property
    def qt_class(self) -> str | None:
        """The Qt class this widget maps from, if any (``None`` for ids with no Qt analog)."""
        return (self.qt_mapping or {}).get("class")


@runtime_checkable
class RegistryClient(Protocol):
    """The seam the IR builder resolves widgets through."""

    def by_id(self, widget_id: str) -> WidgetDefinition | None: ...

    def by_qt_class(self, qt_class: str) -> WidgetDefinition | None: ...


class VendoredRegistry:
    """:class:`RegistryClient` backed by the bundled definitions on disk.

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
