"""Parse Phoebus Display Builder ``.bob`` XML (legacy BOY ``.opi`` fields are tolerated).

The parser is deliberately thin: it turns the XML into a neutral tree of
``BobWidget`` / ``BobRule`` / ``BobScript`` / ``BobAction`` objects and leaves all
interpretation (class mapping, value coercion, rule lowering) to the lowering
modules. Leaf properties are kept as their text; structured properties (fonts,
colours, points, ...) are kept as the ``ET.Element`` so later stages can read
whatever sub-structure they need.

Two things happen here because every consumer needs them done first:

* Widget-scope macro: ``$(pv_name)`` / ``${pv_name}`` inside a widget's action
  ``pv_name``/``value`` fields and its rule/script PV lists refers to the
  widget's own ``pv_name`` property, so it is substituted in place.
* Script files named by ``<script file=...>`` are read from beside the input
  file when present; otherwise only the path is kept.

Uses stdlib ``xml.etree.ElementTree``; expat does not fetch external entities
and bounds entity expansion, which is sufficient for local display files.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pydmconverter.edm.parser_helpers import resolve_inside

__all__ = [
    "BobAction",
    "BobDisplay",
    "BobParseError",
    "BobRule",
    "BobScript",
    "BobWidget",
    "EMBEDDED_SCRIPT_FILES",
    "parse_bob",
    "prop_text",
    "walk_widgets",
]

# Child tags of <widget>/<display> that are structural, not plain props.
_STRUCTURAL_TAGS = frozenset({"widget", "name", "macros", "rules", "scripts", "actions"})

# Script ``file`` markers for inline scripts (Phoebus and BOY spellings).
EMBEDDED_SCRIPT_FILES = frozenset({"EmbeddedPy", "EmbeddedJs", "EmbeddedPython", "EmbeddedJavaScript"})


def script_file_path(base_dir: Path | None, file: str, *, confine: bool) -> Path | None:
    """Where a script or execute-action file named by a display may be read, or None.

    None for an inline marker or a display with no directory. With ``confine`` (untrusted
    input) also None for a name that resolves outside ``base_dir``: absolute, ``..`` or a
    symlink out, so an upload cannot make the converter read the server's files.
    """
    if base_dir is None or not file or file in EMBEDDED_SCRIPT_FILES:
        return None
    if confine:
        return resolve_inside(base_dir, file, [base_dir.resolve()])
    return base_dir / file


_PV_NAME_MACRO_RE = re.compile(r"\$\(pv_name\)|\$\{pv_name\}")


class BobParseError(ValueError):
    """The input is not well-formed XML or not a display file."""


@dataclass
class BobAction:
    """One ``<action>`` of a widget: its type, description and fields."""

    type: str
    description: str = ""
    # Leaf fields as text; a nested ``<macros>`` becomes ``dict[str, str]``.
    fields: dict = field(default_factory=dict)


@dataclass
class BobRule:
    """One ``<rule>``: target property, PVs and ``(condition, value)`` pairs."""

    name: str
    prop_id: str
    out_exp: bool
    pvs: list[tuple[str, bool]] = field(default_factory=list)
    # (bool_exp, value). Value is the text of ``<value>``/``<expression>``, or
    # the serialized ``<value>`` element when it carries structure (e.g. a colour).
    expressions: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class BobScript:
    """One ``<script>``: file or embedded text plus its PVs."""

    name: str
    file: str
    text: str | None
    pvs: list[tuple[str, bool]] = field(default_factory=list)


@dataclass
class BobWidget:
    """A parsed ``<widget>`` with its props, children, rules, scripts and actions."""

    type: str
    name: str
    props: dict[str, ET.Element | str] = field(default_factory=dict)
    children: list[BobWidget] = field(default_factory=list)
    rules: list[BobRule] = field(default_factory=list)
    scripts: list[BobScript] = field(default_factory=list)
    actions: list[BobAction] = field(default_factory=list)
    macros: dict[str, str] = field(default_factory=dict)
    type_id: str | None = None


@dataclass
class BobDisplay:
    """A parsed ``<display>``: top-level props, widgets and macros."""

    name: str
    props: dict[str, ET.Element | str] = field(default_factory=dict)
    widgets: list[BobWidget] = field(default_factory=list)
    macros: dict[str, str] = field(default_factory=dict)
    path: Path | None = None


def prop_text(value: object) -> str:
    """Text of a prop or action field: an element's text, a string as is, else ``""``."""
    if isinstance(value, ET.Element):
        return value.text or ""
    return value if isinstance(value, str) else ""


def walk_widgets(widgets: Iterable[BobWidget]) -> Iterator[BobWidget]:
    """Every widget of the tree, depth-first in document order."""
    for widget in widgets:
        yield widget
        yield from walk_widgets(widget.children)


def parse_bob(path_or_bytes: str | Path | bytes, *, confine_file_refs: bool = False) -> BobDisplay:
    """Parse a ``.bob`` file path or raw XML bytes into a ``BobDisplay``.

    ``confine_file_refs`` is for untrusted input: a ``<script file=...>`` is read only
    when it resolves inside the display's directory (see :func:`script_file_path`).
    Raises ``BobParseError`` on malformed XML or a root that is not ``<display>``.
    """
    path: Path | None = None
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        path = Path(path_or_bytes)
        data = path.read_bytes()
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        where = f"{path}: " if path else ""
        raise BobParseError(f"{where}malformed display XML: {exc}") from exc
    if root.tag != "display":
        raise BobParseError(f"expected <display> root element, got <{root.tag}>")

    base_dir = path.parent if path is not None else None
    return BobDisplay(
        name=_child_text(root, "name"),
        props=_props(root),
        widgets=[_widget(w, base_dir, confine_file_refs) for w in root.findall("widget")],
        macros=_macros(root.find("macros")),
        path=path,
    )


def _text(el: ET.Element | None) -> str:
    return "" if el is None or el.text is None else el.text


def _child_text(el: ET.Element, tag: str) -> str:
    return _text(el.find(tag))


def _props(el: ET.Element) -> dict[str, ET.Element | str]:
    props: dict[str, ET.Element | str] = {}
    for child in el:
        if child.tag in _STRUCTURAL_TAGS:
            continue
        props[child.tag] = child if len(child) else _text(child)
    return props


def _macros(el: ET.Element | None) -> dict[str, str]:
    if el is None:
        return {}
    # BOY's <include_parent_macros> is a flag, not a macro.
    return {m.tag: _text(m) for m in el if m.tag != "include_parent_macros"}


def _pvs(el: ET.Element) -> list[tuple[str, bool]]:
    # Phoebus: <pv_name trig="true">; BOY: <pv trig="true">.
    return [(_text(p), p.get("trig", "true").strip().lower() != "false") for p in el if p.tag in ("pv_name", "pv")]


def _action(el: ET.Element) -> BobAction:
    fields: dict = {}
    description = ""
    for child in el:
        if child.tag == "description":
            description = _text(child)
        elif child.tag == "macros":
            fields["macros"] = _macros(child)
        else:
            fields[child.tag] = child if len(child) else _text(child)
    return BobAction(type=el.get("type", ""), description=description, fields=fields)


def _rule(el: ET.Element) -> BobRule:
    expressions: list[tuple[str, str]] = []
    for exp in el.findall("exp"):
        value_el = exp.find("value")
        if value_el is None:
            value_el = exp.find("expression")
        if value_el is None:
            value = ""
        elif len(value_el):
            value = ET.tostring(value_el, encoding="unicode").strip()
        else:
            value = _text(value_el)
        expressions.append((exp.get("bool_exp", ""), value))
    return BobRule(
        name=el.get("name", ""),
        prop_id=el.get("prop_id", ""),
        out_exp=el.get("out_exp", "false").strip().lower() == "true",
        pvs=_pvs(el),
        expressions=expressions,
    )


def _script(el: ET.Element, base_dir: Path | None, confine: bool) -> BobScript:
    file = el.get("file")
    if file is None:  # BOY: <path pathString="..."/>
        path_el = el.find("path")
        file = (path_el.get("pathString") if path_el is not None else None) or ""
    text_el = el.find("text")
    if text_el is None:
        text_el = el.find("scriptText")
    text: str | None = text_el.text if text_el is not None else None
    candidate = script_file_path(base_dir, file, confine=confine)
    if text is None and candidate is not None and candidate.is_file():
        text = candidate.read_text(encoding="utf-8", errors="replace")
    return BobScript(name=el.get("name", ""), file=file, text=text, pvs=_pvs(el))


def _widget(el: ET.Element, base_dir: Path | None, confine: bool) -> BobWidget:
    type_id = el.get("typeId")
    props = _props(el)
    props.setdefault("x", "0")
    props.setdefault("y", "0")

    actions_el = el.find("actions")
    rules_el = el.find("rules")
    scripts_el = el.find("scripts")
    widget = BobWidget(
        type=el.get("type") or type_id or "",
        name=_child_text(el, "name"),
        props=props,
        children=[_widget(c, base_dir, confine) for c in el.findall("widget")],
        rules=[_rule(r) for r in rules_el.findall("rule")] if rules_el is not None else [],
        scripts=[_script(s, base_dir, confine) for s in scripts_el.findall("script")] if scripts_el is not None else [],
        actions=[_action(a) for a in actions_el.findall("action")] if actions_el is not None else [],
        macros=_macros(el.find("macros")),
        type_id=type_id,
    )
    _substitute_pv_name(widget)
    return widget


def _substitute_pv_name(widget: BobWidget) -> None:
    """Replace the widget-scope ``$(pv_name)`` macro with the widget's own PV."""
    own = widget.props.get("pv_name")
    if not isinstance(own, str) or not own:
        return

    def sub(value: str) -> str:
        return _PV_NAME_MACRO_RE.sub(lambda _m: own, value)

    for action in widget.actions:
        for key in ("pv_name", "value"):
            if isinstance(action.fields.get(key), str):
                action.fields[key] = sub(action.fields[key])
    for rule in widget.rules:
        rule.pvs = [(sub(pv), trig) for pv, trig in rule.pvs]
    for script in widget.scripts:
        script.pvs = [(sub(pv), trig) for pv, trig in script.pvs]
