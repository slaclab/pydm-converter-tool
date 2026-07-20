"""Qt ``.ui`` front-end adapter: ``.ui`` XML -> SourceNode tree -> ScreenIR.

Qt/PyDM class and property names pass straight to the shared :class:`IRBuilder`
(the registry's ``qtPropMap`` does the translation); there is no per-attribute
mapping as on the EDM side. A widget's absolute ``geometry`` ``<rect>`` is
trusted; one without a rect (e.g. inside a Qt layout) warns and gets ``(0,0,0,0)``.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pydmconverter.ir.builder import IRBuilder
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient, VendoredRegistry
from pydmconverter.ir.source import RuleSpec, SourceNode

_SKIP = object()

# Rewrite synonym source classes to a canonical class the registry already
# knows, before lookup, so the builder resolves an existing IR type instead of
# emitting unknown-widget. Each target reuses an existing entry's qtPropMap
# verbatim. Classes needing their own prop translation get a dedicated registry
# entry instead (e.g. PyDMSpinbox -> pv-spinbox).
_QT_CLASS_ALIASES = {
    "PyDMEDMDisplayButton": "PyDMRelatedDisplayButton",
    "PyDMFrame": "QFrame",
    "Line": "PyDMDrawingPolyline",
    "PyDMDrawingLine": "PyDMDrawingPolyline",
    # No-PV text widgets degrade to a static text-label; authored text survives.
    "QTextEdit": "QLabel",
    "QTextBrowser": "QLabel",
    "QLineEdit": "QLabel",
    # Multi-page containers degrade to tabs; children and z-order survive.
    "QStackedWidget": "QTabWidget",
    "QToolBox": "QTabWidget",
    "PyDMTabWidget": "QTabWidget",
    "PyDMDrawingPie": "PyDMDrawingArc",  # renders as an outlined arc, not a filled wedge
    "PyDMDrawingTriangle": "PyDMDrawingIrregularPolygon",
    "PyDMDrawingCircle": "PyDMDrawingEllipse",
    "PyDMTimePlot": "PyDMWaveformPlot",  # time axis degrades to sample index
    "PyDMEventPlot": "PyDMWaveformPlot",
    "QComboBox": "PyDMEnumComboBox",
    "QSpinBox": "PyDMSpinbox",
}

# PyDM rule ``property`` -> IR target_property. Visibility is by far the common case.
_PYDM_RULE_PROPERTY_MAP = {
    "Visible": "visible",
    "Enable": "enabled",
    "Opacity": "opacity",
    "Text Color": "foregroundColor",
    "foregroundColor": "foregroundColor",
}

# Boolean targets whose ``initial_value`` string is coerced to a real bool.
_BOOLEAN_RULE_TARGETS = {"visible", "enabled"}

_CH_TOKEN = re.compile(r"ch\[\s*(\d+)\s*\]")
_CHANNEL_PREFIX = re.compile(r"^(?:ca|pva)://")


def _wire_expression(expression: str) -> str:
    """Translate a PyDM expression (``ch[0]``) to IR wire form (``{0}``)."""
    return _CH_TOKEN.sub(lambda m: "{" + m.group(1) + "}", expression or "")


def _coerce_default(initial_value: Any, target_property: str) -> Any:
    """Convert a PyDM rule ``initial_value`` to the right type for the target."""
    if target_property in _BOOLEAN_RULE_TARGETS:
        if isinstance(initial_value, bool):
            return initial_value
        if isinstance(initial_value, (int, float)):
            return bool(initial_value)
        if isinstance(initial_value, str):
            token = initial_value.strip().lower()
            if token in ("1", "true"):
                return True
            if token in ("0", "false"):
                return False
        return False
    return initial_value


def _parse_rules(rules_text: str | None, warnings: list[str]) -> list[RuleSpec]:
    """Parse a PyDM ``rules`` property JSON string into :class:`RuleSpec`s.

    Never raises: a missing/empty prop or malformed JSON yields ``[]`` (+ warning).
    """
    if not rules_text or not rules_text.strip():
        return []
    try:
        raw = json.loads(rules_text)
    except (ValueError, TypeError):
        warnings.append("could not parse PyDM 'rules' property (malformed JSON); dropped rules")
        return []
    if not isinstance(raw, list):
        warnings.append("PyDM 'rules' property is not a JSON array; dropped rules")
        return []

    specs: list[RuleSpec] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pydm_prop = entry.get("property", "Visible")
        target = _PYDM_RULE_PROPERTY_MAP.get(pydm_prop)
        if target is None:
            target = (pydm_prop[:1].lower() + pydm_prop[1:]) if pydm_prop else "visible"
            warnings.append(f"unknown PyDM rule property {pydm_prop!r}; mapped to {target!r} as best effort")

        pv_index: dict[str, int] = {}
        pvs: list[tuple[str, bool]] = []
        for chan in entry.get("channels", []) or []:
            if not isinstance(chan, dict):
                continue
            name = _CHANNEL_PREFIX.sub("", str(chan.get("channel", "")))
            if name not in pv_index:
                pv_index[name] = len(pvs)
                pvs.append((name, bool(chan.get("trigger", False))))

        wire = _wire_expression(entry.get("expression", ""))
        specs.append(
            RuleSpec(
                target_property=target,
                name=entry.get("name") or "Rule",
                pvs=pvs,
                conditions=[(wire, True)],
                default=_coerce_default(entry.get("initial_value"), target),
            )
        )
    return specs


def _parse_int(text: str) -> Any:
    """``<number>`` text -> int; tolerate a float-formatted value, ``_SKIP`` if unparseable."""
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return _SKIP


def _parse_float(text: str) -> Any:
    """``<double>`` text -> float, ``_SKIP`` if unparseable."""
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return _SKIP


def _scalar_property(prop: ET.Element) -> Any:
    """Extract a scalar value from a ``<property>``; ``_SKIP`` for complex kinds
    (font, sizepolicy, ...) that no supported prop consumes."""
    children = list(prop)
    if not children:
        return _SKIP
    el = children[0]
    text = (el.text or "").strip()
    tag = el.tag
    if tag == "string":
        return el.text or ""
    if tag == "bool":
        return text.lower() == "true"
    if tag == "number":
        return _parse_int(text)
    if tag == "double":
        return _parse_float(text)
    if tag in ("enum", "set"):
        return text
    if tag == "stringlist":
        return [c.text or "" for c in el]
    return _SKIP


def _font_pixels(prop: ET.Element) -> int | None:
    """Pixel font size from a Qt ``<font>``: ``<pixelsize>`` verbatim, else
    ``<pointsize>`` converted at 96 DPI (``pt * 96/72``). ``None`` if absent or
    unparseable — never raises."""
    font = prop.find("font")
    if font is None:
        return None
    pixel_el = font.find("pixelsize")
    if pixel_el is not None and pixel_el.text and pixel_el.text.strip():
        try:
            return int(pixel_el.text.strip())
        except ValueError:
            return None
    point_el = font.find("pointsize")
    if point_el is not None and point_el.text and point_el.text.strip():
        try:
            return round(int(point_el.text.strip()) * 96 / 72)
        except ValueError:
            return None
    return None


def _rect(prop: ET.Element) -> tuple[int, int, int, int] | None:
    rect = prop.find("rect")
    if rect is None:
        return None

    def part(tag: str) -> int:
        el = rect.find(tag)
        return int(el.text) if el is not None and el.text else 0

    return (part("x"), part("y"), part("width"), part("height"))


def _child_widgets(elem: ET.Element) -> list[ET.Element]:
    """Immediate child ``<widget>`` elements, reaching through ``<layout><item>``."""
    found: list[ET.Element] = []
    for child in elem:
        if child.tag == "widget":
            found.append(child)
        elif child.tag == "layout":
            found.extend(_layout_widgets(child))
    return found


def _layout_widgets(layout: ET.Element) -> list[ET.Element]:
    found: list[ET.Element] = []
    for item in layout.findall("item"):
        for sub in item:
            if sub.tag == "widget":
                found.append(sub)
            elif sub.tag == "layout":
                found.extend(_layout_widgets(sub))
    return found


def _template_root_size(path: Path) -> tuple[int, int] | None:
    """Width/height of a template ``.ui``'s root geometry rect — the per-instance
    footprint used to lay out repeater rows/columns. ``None`` if unreadable."""
    try:
        root_widget = ET.parse(path).getroot().find("widget")
    except (ET.ParseError, OSError):
        return None
    if root_widget is None:
        return None
    for prop in root_widget.findall("property"):
        if prop.get("name") == "geometry":
            rect = _rect(prop)
            if rect:
                return (rect[2], rect[3])
    return None


def _expand_template_repeater(
    props: dict[str, Any],
    geometry: tuple[int, int, int, int],
    source_dir: Path | None,
    warnings: list[str],
) -> list[SourceNode] | None:
    """Materialize a ``PyDMTemplateRepeater`` into one embedded-display per record.

    Each record in ``dataSource`` (a JSON list of macro dicts) becomes an
    embedded-display of the converted template, carrying the record as its
    ``macros`` and stepped along the repeater's rect by the template size +
    spacing. ``None`` (falls back to unknown-widget) if the dataSource is
    missing/unreadable/not-a-list.
    """
    template = props.get("templateFilename")
    data_source = props.get("dataSource")
    if not isinstance(template, str) or not template.strip():
        warnings.append("PyDMTemplateRepeater has no templateFilename; rendering placeholder")
        return None
    if not isinstance(data_source, str) or not data_source.strip():
        warnings.append("PyDMTemplateRepeater has no dataSource; rendering placeholder")
        return None
    if source_dir is None:
        warnings.append("PyDMTemplateRepeater: source directory unknown, cannot resolve dataSource; placeholder")
        return None

    def _resolve(ref: str) -> Path:
        """Resolve a repeater path against the source dir, falling back to the
        basename when a deploy-time env prefix (``$PYDM/mc/...``) won't resolve."""
        p = (source_dir / ref).resolve()
        if p.exists():
            return p
        base = ref.replace("\\", "/").rsplit("/", 1)[-1]
        alt = (source_dir / base).resolve()
        return alt if alt.exists() else p

    data_path = _resolve(data_source)
    try:
        records = json.loads(data_path.read_text())
    except (OSError, ValueError, TypeError):
        warnings.append(f"PyDMTemplateRepeater dataSource {data_source!r} missing/unreadable; rendering placeholder")
        return None
    if not isinstance(records, list):
        warnings.append(f"PyDMTemplateRepeater dataSource {data_source!r} is not a JSON list; rendering placeholder")
        return None

    # Fall back to the repeater rect if the template can't be sized.
    tmpl_path = _resolve(template)
    tmpl_size = _template_root_size(tmpl_path)
    if tmpl_size is None:
        warnings.append(f"PyDMTemplateRepeater template {template!r} unreadable; using repeater rect for instance size")
        tmpl_w, tmpl_h = geometry[2], geometry[3]
    else:
        tmpl_w, tmpl_h = tmpl_size

    layout = str(props.get("layoutType", "")).lower()
    horizontal = "horizontal" in layout  # absent -> Vertical (PyDM default)
    spacing = props.get("layoutSpacing", 0)
    if not isinstance(spacing, int):
        spacing = 0

    base_x, base_y = geometry[0], geometry[1]
    # Keep the relative path, not just the basename: subdirs share basenames
    # (Collimator/Widget vs Heater/Widget), so screenRef needs the dir to
    # resolve the right converted template.
    template_ref = template.strip().replace("\\", "/")
    # If the literal path didn't resolve but its basename did, emit the basename.
    if not (source_dir / template_ref).exists() and tmpl_path.name == template_ref.rsplit("/", 1)[-1]:
        if tmpl_path.exists():
            template_ref = tmpl_path.name

    nodes: list[SourceNode] = []
    for i, record in enumerate(records):
        macros = record if isinstance(record, dict) else {}
        if horizontal:
            x = base_x + i * (tmpl_w + spacing)
            y = base_y
        else:
            x = base_x
            y = base_y + i * (tmpl_h + spacing)
        nodes.append(
            SourceNode(
                qt_class="PyDMEmbeddedDisplay",
                qt_props={"filename": template_ref, "macros": macros},
                geometry=(x, y, tmpl_w, tmpl_h),
                raw_class="PyDMTemplateRepeater",
                raw_props={"filename": template_ref, "macros": macros},
                warnings=list(warnings) if i == 0 else [],
            )
        )
    return nodes


def _widget_to_sources(widget: ET.Element, source_dir: Path | None) -> list[SourceNode]:
    """Normalize one ``<widget>`` into one *or more* SourceNodes.

    Almost every widget yields a single node; a ``PyDMTemplateRepeater`` fans out
    into one embedded-display per dataSource record (falling back to a single
    unknown-widget node if the dataSource can't be resolved).
    """
    raw_class = widget.get("class")
    qt_class = _QT_CLASS_ALIASES.get(raw_class, raw_class)  # raw_class kept for provenance
    props: dict[str, Any] = {}
    geometry: tuple[int, int, int, int] | None = None
    rules_text: str | None = None
    for prop in widget.findall("property"):
        name = prop.get("name")
        if name == "geometry":
            geometry = _rect(prop)
            continue
        if name == "rules":
            # A JSON string; parsed separately so it never leaks into qt_props.
            value = _scalar_property(prop)
            rules_text = value if isinstance(value, str) else None
            continue
        if name == "font":
            # Reduce the complex <font> to a synthetic fontSize prop; drop the rest.
            px = _font_pixels(prop)
            if px is not None:
                props["fontSize"] = px
            continue
        value = _scalar_property(prop)
        if value is not _SKIP and name:
            props[name] = value

    warnings: list[str] = []
    rules = _parse_rules(rules_text, warnings)
    if geometry is None:
        warnings.append(
            f"{widget.get('name') or raw_class} has no geometry rect (likely in a Qt layout); using (0,0,0,0)"
        )
        geometry = (0, 0, 0, 0)

    if raw_class == "PyDMTemplateRepeater":
        expanded = _expand_template_repeater(props, geometry, source_dir, warnings)
        if expanded is not None:
            return expanded
        # else fall through to the unknown-widget placeholder below

    children: list[SourceNode] = []
    for child in _child_widgets(widget):
        children.extend(_widget_to_sources(child, source_dir))

    return [
        SourceNode(
            qt_class=qt_class,
            qt_props=props,
            geometry=geometry,
            raw_class=raw_class,
            raw_props=dict(props),
            children=children,
            rules=rules,
            warnings=warnings,
        )
    ]


def _string_property(widget: ET.Element, name: str) -> str | None:
    for prop in widget.findall("property"):
        if prop.get("name") == name:
            el = prop.find("string")
            if el is not None:
                return el.text or ""
    return None


def parse_ui(path: str | Path) -> tuple[ET.Element, str, tuple[int, int]]:
    """Return the root ``<widget>`` element, its window title, and screen size."""
    root_widget = ET.parse(path).getroot().find("widget")
    if root_widget is None:
        raise ValueError(f"{path}: no root <widget> element in .ui file")
    title = _string_property(root_widget, "windowTitle") or root_widget.get("name") or "screen"
    size: tuple[int, int] = (0, 0)
    for prop in root_widget.findall("property"):
        if prop.get("name") == "geometry":
            rect = _rect(prop)
            if rect:
                size = (rect[2], rect[3])
            break
    return root_widget, title, size


def ui_file_to_ir(input_path: str | Path, *, registry: RegistryClient | None = None) -> ScreenIR:
    """Parse a ``.ui`` file and build its Screen IR."""
    path = Path(input_path)
    root_widget, title, size = parse_ui(path)
    source_dir = path.parent
    top_level: list[SourceNode] = []
    for child in _child_widgets(root_widget):
        top_level.extend(_widget_to_sources(child, source_dir))
    builder = IRBuilder(registry or VendoredRegistry())
    return builder.build_screen(
        screen_id=path.stem,
        title=title,
        source_type="ui-converter",
        size=size,
        top_level=top_level,
    )
