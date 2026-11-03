"""Action lowering for the Phoebus ``.bob`` front-end.

A Phoebus widget's ``<actions>`` list (clicked through an ``action_button``, or the
context menu of any widget) becomes the Screen Builder's ``props.actions`` list, one
entry per action in document order, in the builder ``Action`` shape:

* ``open_display`` -> ``{"type": "open_display", "file", "target", "macros"?}``. The
  file goes through :func:`~pydmconverter.ir.transforms.screen_ref` (``.bob``/``.opi``
  -> ``.screen.json``, directory kept, macro refs untouched). Phoebus' ``<target>``
  absent means ``replace``; ``standalone`` is a new window; ``tab``/``window``/
  ``replace`` pass through; anything else warns and falls back to ``replace``.
* ``write_pv`` (BOY ``WRITE_PV``) -> ``{"type": "write_pv", "pvName", "value"}``. The
  target goes through :func:`~pydmconverter.bob.local_pv.rewrite_local_pv`, so a
  ``$(pv_name)`` substituted with a typed local PV keeps its ``?type=&init=`` form.
* ``command`` -> ``{"type": "execute", "command", "description"}`` with one warning per
  widget: the web runtime does not run shell commands.
* ``open_webpage`` -> ``{"type": "open_webpage", "url"}`` for an ``http``/``https`` or
  relative URL; any other scheme (``javascript:``, ``data:``, ``file:``, ...) or a macro
  that could supply one is dropped with a warning. ``open_file`` ->
  ``{"type": "open_file", "file"}`` for a file path (:func:`file_reference`, also
  applied to ``open_display`` files); ``close_display`` -> ``{"type": "close_display"}``,
  emitted unconditionally as the EDM adapter does.
* ``execute`` (a Jython/JavaScript script) has no web equivalent: a tier-2 warning and
  no entry.

``command`` and ``execute`` actions are also *carried*: handed to ``ctx`` so the source
carry-over (:func:`~pydmconverter.bob.meta.build_meta`) can show them verbatim.

:func:`action_button_label` derives an ``action_button`` caption: Phoebus' ``<text>``
defaults to ``$(actions)``, which shows the action descriptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydmconverter.bob.gates import FILE_REFERENCE_WARNING, WEB_URL_WARNING, file_reference, web_url
from pydmconverter.bob.local_pv import rewrite_local_pv
from pydmconverter.bob.parser import BobAction, BobWidget, prop_text
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.transforms import screen_ref

__all__ = [
    "COMMAND_TYPES",
    "EXECUTE_TYPES",
    "ActionContext",
    "action_button_label",
    "lower_actions",
]

# Phoebus <target> values -> builder targets (absent -> replace).
_TARGETS = {"replace": "replace", "tab": "tab", "window": "window", "standalone": "window"}

_OPEN_DISPLAY = frozenset({"open_display", "OPEN_DISPLAY"})
_WRITE_PV = frozenset({"write_pv", "WRITE_PV"})
COMMAND_TYPES = frozenset({"command", "EXECUTE_CMD"})
EXECUTE_TYPES = frozenset({"execute", "EXECUTE_PYTHONSCRIPT", "EXECUTE_JAVASCRIPT"})
_OPEN_WEBPAGE = frozenset({"open_webpage", "OPEN_WEBPAGE"})
_OPEN_FILE = frozenset({"open_file", "OPEN_FILE"})
_CLOSE_DISPLAY = frozenset({"close_display"})

_ACTIONS_MACRO = frozenset({"$(actions)", "${actions}"})

COMMAND_WARNING = "{widget}: shell command carried as execute action; the web runtime does not run shell commands"


@dataclass
class ActionContext:
    """Collects warnings and the actions carried over to ``meta.comment``."""

    warnings: list[str] = field(default_factory=list)
    carried: list[BobAction] = field(default_factory=list)

    def warn(self, message: str) -> None:
        """Record a conversion warning."""
        self.warnings.append(message)

    def carry(self, action: BobAction) -> None:
        """Keep ``action`` for the ``meta.comment`` carry-over."""
        self.carried.append(action)


def _warn(ctx: Any, message: str) -> None:
    warn = getattr(ctx, "warn", None)
    if callable(warn):
        warn(message)
    else:
        ctx.warnings.append(message)


def _carry(ctx: Any, action: BobAction) -> None:
    carry = getattr(ctx, "carry", None)
    if callable(carry):
        carry(action)
    elif isinstance(getattr(ctx, "carried", None), list):
        ctx.carried.append(action)


def _field(action: BobAction, *names: str) -> str:
    """First non-empty text among ``names`` (Phoebus spelling first, then BOY)."""
    for name in names:
        text = prop_text(action.fields.get(name)).strip()
        if text:
            return text
    return ""


def _open_display(action: BobAction, widget: str, ctx: Any) -> dict | None:
    raw = _field(action, "file", "path")
    if not raw:
        _warn(ctx, f"{widget}: open_display with no file")
        file = ""
    else:
        checked = file_reference(raw)
        if checked is None:
            _warn(ctx, FILE_REFERENCE_WARNING.format(widget=widget, what="open_display", reference=raw))
            return None
        if raw.lower().endswith(".opi"):
            _warn(ctx, f"{widget}: open_display target {raw} is a legacy .opi that no converter produces")
        file = screen_ref(checked)

    target_text = _field(action, "target")
    target = _TARGETS.get(target_text.lower(), None) if target_text else "replace"
    if target is None:
        _warn(ctx, f"{widget}: open_display target {target_text} unknown; using replace")
        target = "replace"

    entry: dict[str, Any] = {"type": "open_display", "file": file, "target": target}
    macros = action.fields.get("macros")
    if isinstance(macros, dict) and macros:
        entry["macros"] = {name: normalize_macro_syntax(value) for name, value in macros.items()}
    return entry


def _open_webpage(action: BobAction, widget: str, ctx: Any) -> dict | None:
    """The ``open_webpage`` entry, or ``None`` (with a warning) when :func:`web_url` refuses the URL."""
    raw = _field(action, "url", "hyperlink")
    url = web_url(raw)
    if url is None:
        _warn(ctx, WEB_URL_WARNING.format(widget=widget, reference=raw))
        return None
    return {"type": "open_webpage", "url": url}


def _open_file(action: BobAction, widget: str, ctx: Any) -> dict | None:
    """The ``open_file`` entry, or ``None`` (with a warning) for anything but a file path."""
    raw = _field(action, "file", "path")
    file = file_reference(raw)
    if file is None:
        _warn(ctx, FILE_REFERENCE_WARNING.format(widget=widget, what="open_file", reference=raw))
        return None
    return {"type": "open_file", "file": file}


def _write_pv(action: BobAction, widget: str, ctx: Any) -> dict:
    pv = _field(action, "pv_name")
    target = normalize_macro_syntax(rewrite_local_pv(pv, lambda m: _warn(ctx, m), widget=widget))
    value = normalize_macro_syntax(prop_text(action.fields.get("value")))
    return {"type": "write_pv", "pvName": target, "value": value}


def lower_actions(widget: BobWidget, ctx: Any) -> list[dict]:
    """Lower ``widget.actions`` into builder ``Action`` dicts, in document order.

    ``ctx`` receives warnings through ``ctx.warn(message)`` (or ``ctx.warnings``) and
    carried ``command``/``execute`` actions through ``ctx.carry(action)`` (or
    ``ctx.carried``); :class:`ActionContext` provides both. Never raises for
    unsupported input.
    """
    name = widget.name
    out: list[dict] = []
    command_warned = False
    for action in widget.actions:
        kind = action.type
        if kind in _OPEN_DISPLAY:
            entry = _open_display(action, name, ctx)
            if entry is not None:
                out.append(entry)
        elif kind in _WRITE_PV:
            out.append(_write_pv(action, name, ctx))
        elif kind in COMMAND_TYPES:
            out.append(
                {
                    "type": "execute",
                    "command": normalize_macro_syntax(_field(action, "command")),
                    "description": normalize_macro_syntax(action.description),
                }
            )
            _carry(ctx, action)
            if not command_warned:
                _warn(ctx, COMMAND_WARNING.format(widget=name))
                command_warned = True
        elif kind in EXECUTE_TYPES:
            _warn(ctx, f"{name}: execute action needs the script runtime (tier 2); carried, not emitted")
            _carry(ctx, action)
        elif kind in _OPEN_WEBPAGE:
            entry = _open_webpage(action, name, ctx)
            if entry is not None:
                out.append(entry)
        elif kind in _OPEN_FILE:
            entry = _open_file(action, name, ctx)
            if entry is not None:
                out.append(entry)
        elif kind in _CLOSE_DISPLAY:
            out.append({"type": "close_display"})
        else:
            _warn(ctx, f"{name}: action type {kind} not supported")
    return out


def _caption(action: BobAction) -> str:
    if action.description:
        return action.description
    return _field(action, "file", "path") or _field(action, "pv_name")


def action_button_label(widget: BobWidget) -> str:
    """The caption of an ``action_button``.

    ``<text>`` absent or ``$(actions)`` -> the action descriptions joined with
    ``' / '``, an empty description falling back to the action's file or PV (Phoebus
    shows "Choose 1 of N" for several actions; the joined list is a deliberate
    deviation). Otherwise the authored text. Macros are normalised to ``${VAR}``.
    """
    text = widget.props.get("text")
    if isinstance(text, str) and text.strip() not in _ACTIONS_MACRO:
        return normalize_macro_syntax(text)
    captions = [_caption(action) for action in widget.actions]
    return normalize_macro_syntax(" / ".join(c for c in captions if c))
