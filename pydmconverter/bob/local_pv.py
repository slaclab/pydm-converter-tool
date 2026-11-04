"""Phoebus local-PV URL handling for the ``.bob`` front-end.

Phoebus declares a local PV inline in its URL: ``loc://name<VType>(initial)``.
Canopy's ``LocalPVService`` takes the same information as a query string,
``loc://name?type=<t>&init=<v>``. This module rewrites the former into the latter,
provides the one identity key every writer/reader comparison uses, and tells
gateway channels apart from the local/simulated/computed schemes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, Iterable, Iterator
from urllib.parse import quote

from pydmconverter.bob.bob_qt import qt_class_for
from pydmconverter.bob.parser import walk_widgets
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.source import SourceNode

if TYPE_CHECKING:
    from pydmconverter.bob.parser import BobWidget
    from pydmconverter.ir.registry import RegistryClient

__all__ = [
    "NON_GATEWAY_SCHEMES",
    "VTYPE_TO_LOCAL_TYPE",
    "is_gateway_channel",
    "local_pv_key",
    "plan_declarers",
    "rewrite_local_pv",
]

# Phoebus VType -> Canopy local-PV ``type`` query value.
VTYPE_TO_LOCAL_TYPE: dict[str, str] = {
    "VLong": "int",
    "VInt": "int",
    "VDouble": "float",
    "VString": "str",
}

# Schemes that never reach the gateway (evaluated or simulated client-side).
NON_GATEWAY_SCHEMES: tuple[str, ...] = ("loc", "sim", "calc", "formula")

# ``loc://name`` + optional ``<VType>`` + optional ``(initial)``; applied after macro
# normalisation, so the name holds no ``(``.
_LOC_RE = re.compile(r"^loc://(?P<name>[^<(?]*)(?:<(?P<vtype>[^>]*)>)?(?:\((?P<init>.*)\))?$", re.DOTALL)
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://")
_INT_RE = re.compile(r"^[+-]?\d+$")


def local_pv_key(url: str) -> str:
    """Identity of a local PV: macros normalised, then ``(...)``, ``<...>`` and ``?...`` stripped.

    ``loc://X<VDouble>(0)``, ``loc://X<VDouble>``, ``loc://X?type=float`` and
    ``loc://X`` all yield ``loc://X``.
    """
    key = normalize_macro_syntax(url).strip()
    if key.endswith(")") and "(" in key:  # from the first "(" to the final ")"
        key = key[: key.index("(")]
    return _strip_angle_spans(key).split("?", 1)[0]


def _strip_angle_spans(text: str) -> str:
    """Remove every ``<...>`` (no nesting) in one linear pass; an unclosed ``<`` stays."""
    out: list[str] = []
    i = 0
    while (j := text.find("<", i)) != -1 and (k := text.find(">", j + 1)) != -1:
        out.append(text[i:j])
        i = k + 1
    out.append(text[i:])
    return "".join(out)


def is_gateway_channel(url: str) -> bool:
    """True for a PV served by the gateway (plain names, ``ca://``, ``pva://``).

    False for ``loc``/``sim``/``calc``/``formula`` URLs, Phoebus ``=``
    formula PVs and empty strings.
    """
    if not isinstance(url, str):
        return False
    text = url.strip()
    if not text or text.startswith("="):
        return False
    match = _SCHEME_RE.match(text)
    return not (match and match.group(1).lower() in NON_GATEWAY_SCHEMES)


def _split_top_level_commas(literal: str) -> list[str]:
    """Split on commas outside single/double quotes."""
    parts: list[str] = []
    current: list[str] = []
    quote_char: str | None = None
    for ch in literal:
        if quote_char:
            if ch == quote_char:
                quote_char = None
        elif ch in "\"'":
            quote_char = ch
        elif ch == ",":
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def _unquote(literal: str) -> tuple[str, bool]:
    text = literal.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1], True
    return text, False


def _infer_type(value: str, quoted: bool) -> str:
    if quoted:
        return "str"
    if _INT_RE.match(value):
        return "int"
    try:
        float(value)
    except ValueError:
        return "str"
    return "float"


def rewrite_local_pv(url: str, warn: Callable[[str], None], *, widget: str | None = None) -> str:
    """Rewrite a Phoebus ``loc://name<VType>(v)`` URL into Canopy's query form.

    ``loc://name<VType>(v)`` -> ``loc://name?type=<t>&init=<v>``; ``loc://name<VType>``
    -> ``loc://name?type=<t>``; a typeless ``loc://name(v)`` infers the type from the
    literal. Quotes around the value are stripped and query-breaking characters in it
    percent-encoded (``${VAR}`` macros kept intact). Unmapped VTypes and array
    (comma-separated) initializers call ``warn`` and yield the bare ``loc://name``.
    ``sim://``, plain ``loc://`` and every other URL pass through unchanged. The
    output never contains ``<V``.

    ``warn`` receives the message; when ``widget`` is given it is prefixed as
    ``"<widget>: "``.
    """
    if not isinstance(url, str):
        return url
    match = _LOC_RE.match(normalize_macro_syntax(url).strip())
    if not match or (match.group("vtype") is None and match.group("init") is None):
        return url

    prefix = f"{widget}: " if widget else ""
    bare = f"loc://{match.group('name')}"
    vtype = match.group("vtype")
    init = match.group("init")

    local_type: str | None = None
    if vtype is not None:
        local_type = VTYPE_TO_LOCAL_TYPE.get(vtype.strip())
        if local_type is None:
            warn(f"{prefix}local PV type {vtype.strip()} not supported")
            return bare

    if init is None:
        return f"{bare}?type={local_type}"

    if len(_split_top_level_commas(init)) > 1:
        warn(f"{prefix}array local PV initializer not supported")
        return bare

    value, quoted = _unquote(init)
    if local_type is None:
        local_type = _infer_type(value, quoted)
    return f"{bare}?type={local_type}&init={quote(value, safe='${}')}"


def _is_initializer(url: object) -> bool:
    """True for a ``loc://`` URL carrying an ``(initial)`` value."""
    if not isinstance(url, str):
        return False
    match = _LOC_RE.match(normalize_macro_syntax(url).strip())
    return bool(match and match.group("init") is not None)


def _has_channel(widget: BobWidget, registry: RegistryClient) -> bool:
    mapped = qt_class_for(widget.type)
    if mapped is None:
        return False
    definition = registry.by_id(mapped[1])
    return definition is not None and "channel" in definition.qt_prop_map


def _references(widget: BobWidget) -> Iterator[object]:
    """Every PV a widget names, in document order: own, actions, rules, scripts."""
    yield widget.props.get("pv_name")
    for action in widget.actions:
        yield action.fields.get("pv_name")
    for rule in widget.rules:
        for pv, _trigger in rule.pvs:
            yield pv
    for script in widget.scripts:
        for pv, _trigger in script.pvs:
            yield pv


def plan_declarers(
    widgets: Iterable[BobWidget],
    registry: RegistryClient,
    *,
    warn: Callable[[str], None] | None = None,
) -> list[SourceNode]:
    """Hidden declarer nodes for local-PV initializers no channel carries.

    Canopy's ``LocalPVService`` initialises a local PV on the first *declaring
    subscribe* (a channel carrying ``?type=&init=``), never on a ``write_pv`` put.
    An initializer that is a widget's own ``pv_name`` on a type whose registry entry
    has a ``channel`` stays there (the adapter rewrites it in place). Any other
    initializer — the ``pv_name`` of an ``action_button``, or a ``loc://n<T>(v)``
    named in an action, rule or script — becomes a 0x0 ``pv-label`` declarer named
    ``<widget>.init`` with ``channel = loc://name?type=<t>&init=<v>``. There is no
    ``visible`` prop (hiding would unmount it) and no warning.

    ``widgets`` is walked recursively in document order (``$(pv_name)`` already
    substituted by the parser); one declarer per distinct :func:`local_pv_key`, the
    first initializer winning. The adapter inserts the result as the first root
    children. The parser output is not modified. An initializer
    :func:`rewrite_local_pv` cannot express (unsupported VType, array) yields no
    declarer; its warning goes to ``warn`` when given.
    """
    report = warn if warn is not None else (lambda _message: None)
    declared: set[str] = set()
    declarers: list[SourceNode] = []
    for widget in walk_widgets(widgets):
        own = widget.props.get("pv_name")
        keeps_own = _has_channel(widget, registry)
        for url in _references(widget):
            if not _is_initializer(url) or (keeps_own and url == own):
                continue
            key = local_pv_key(url)
            if key in declared:
                continue
            declared.add(key)
            rewritten = rewrite_local_pv(url, report, widget=widget.name)
            if "&init=" not in rewritten:
                continue
            name = f"{widget.name}.init"
            declarers.append(
                SourceNode(
                    qt_class="PyDMLabel",
                    qt_props={"channel": rewritten},
                    registry_id="pv-label",
                    geometry=(0, 0, 0, 0),
                    raw_class="PyDMLabel",
                    raw_props={"name": name},
                )
            )
    return declarers
