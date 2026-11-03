"""Source carry-over for the Phoebus ``.bob`` front-end.

Whatever the adapter cannot lower -- a script that is not one of the two tier-0 idioms,
an ``execute`` (Jython/JavaScript) or ``command`` action, a formula PV the rewrite
declined -- is not dropped: it is carried verbatim on the node as ``meta.comment`` so the
original code is one click away in the builder.

:func:`build_meta` assembles that comment. Blocks follow the widget's document order,
scripts then actions, then any declined formula-PV text, separated by one blank line.
Each block is a one-line header followed by the full text::

    Phoebus script <name> [<file>] pvs=[<pv>, <pv>]
    <script text, or the file path alone when the file was not readable>

    Phoebus execute action: <file|inline>
    <script text, or the file path alone when the file was not readable>

    Phoebus command: <description>
    <command line>

    Phoebus formula PV: <text>

A widget with nothing to carry gets ``None``. The widget's ``type_id`` (a legacy BOY
``typeId`` widget) is never inspected, so legacy and Phoebus spellings carry identically.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from pathlib import Path

from pydmconverter.bob.actions import COMMAND_TYPES, EXECUTE_TYPES
from pydmconverter.bob.parser import (
    EMBEDDED_SCRIPT_FILES,
    BobAction,
    BobScript,
    BobWidget,
    prop_text,
    script_file_path,
)
from pydmconverter.ir.model import NodeMeta

__all__ = ["build_meta", "script_block", "action_block", "formula_pv_block"]

# Script ``file`` markers for inline scripts: none, or an embedded-script marker.
_INLINE_FILES = EMBEDDED_SCRIPT_FILES | {""}


REFUSED_FILE_WARNING = "{what} file {file!r} is outside the screen's directory; not read, carried as its path"


def _refused(file: str, base_dir: Path | None, confine: bool) -> bool:
    """True when ``confine`` kept a named (not inline) file from being read."""
    return (
        confine
        and base_dir is not None
        and file not in _INLINE_FILES
        and script_file_path(base_dir, file, confine=True) is None
    )


def _read_beside(file: str, base_dir: Path | None, confine: bool) -> str | None:
    candidate = script_file_path(base_dir, file, confine=confine)
    if candidate is None:
        return None
    try:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def script_block(script: BobScript) -> str:
    """One carried ``<script>``: header plus its text (or the file path alone)."""
    pvs = ", ".join(pv for pv, _trig in script.pvs)
    # Phoebus ``<script>`` elements are usually unnamed; no double space then.
    name = f"{script.name} " if script.name else ""
    header = f"Phoebus script {name}[{script.file}] pvs=[{pvs}]"
    body = script.text if script.text is not None else script.file
    return f"{header}\n{body}"


def _execute_parts(
    action: BobAction, base_dir: Path | None, confine: bool, warn: Callable[[str], None] | None
) -> tuple[str, str]:
    """(file, text) of an execute action; text is the file path when unreadable."""
    fields = action.fields
    script = fields.get("script")
    if isinstance(script, ET.Element):  # Phoebus: <script file="..."><text>...</text></script>
        file = script.get("file", "")
        text_el = script.find("text")
        text = text_el.text if text_el is not None else None
    else:  # BOY: <path>, <scriptText>, <embedded>; or a bare <file>
        file = prop_text(fields.get("path")) or prop_text(fields.get("file"))
        embedded = prop_text(fields.get("embedded")).strip().lower() == "true"
        text = prop_text(fields.get("scriptText")) if embedded or "scriptText" in fields else None
        if embedded:
            file = ""
    if text is None:
        text = _read_beside(file, base_dir, confine)
        if warn is not None and _refused(file, base_dir, confine):
            warn(REFUSED_FILE_WARNING.format(what="execute action", file=file))
    inline = file in _INLINE_FILES
    return ("inline" if inline else file), (text if text is not None else file)


def action_block(
    action: BobAction,
    base_dir: Path | None = None,
    *,
    confine_file_refs: bool = False,
    warn: Callable[[str], None] | None = None,
) -> str | None:
    """One carried ``execute``/``command`` action, or ``None`` for any other type."""
    if action.type in EXECUTE_TYPES:
        where, text = _execute_parts(action, base_dir, confine_file_refs, warn)
        return f"Phoebus execute action: {where}\n{text}"
    if action.type in COMMAND_TYPES:
        command = prop_text(action.fields.get("command"))
        return f"Phoebus command: {action.description}\n{command}"
    return None


def formula_pv_block(text: str) -> str:
    """One formula PV the rewrite declined, carried verbatim."""
    return f"Phoebus formula PV: {text}"


def _document_order(items: Sequence, order: Sequence) -> list:
    """Sort ``items`` by their position (identity) in ``order``; strangers keep theirs, last."""
    position = {id(item): i for i, item in enumerate(order)}
    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: position.get(id(pair[1]), len(order) + pair[0]))
    return [item for _i, item in indexed]


def build_meta(
    widget: BobWidget,
    unlowered_scripts: Sequence[BobScript],
    unlowered_actions: Sequence[BobAction],
    declined_formula_pvs: Sequence[str] = (),
    *,
    base_dir: Path | None = None,
    confine_file_refs: bool = False,
    warn: Callable[[str], None] | None = None,
) -> NodeMeta | None:
    """Build the carry-over ``NodeMeta`` for ``widget``, or ``None`` if nothing is carried.

    ``unlowered_scripts`` and ``unlowered_actions`` are the widget's scripts and actions
    the matchers/action lowering did not handle; they are emitted in the widget's document
    order, scripts first. ``declined_formula_pvs`` are formula-PV texts (``=...``) the
    rewrite declined. ``base_dir`` is the input file's directory, used to read an
    external execute-action script; scripts are already read by the parser.
    ``confine_file_refs`` (untrusted input) reads such a file only inside ``base_dir``;
    each one it refuses is reported through ``warn``.
    """
    scripts = _document_order(unlowered_scripts, widget.scripts)
    if warn is not None:
        for script in scripts:
            if script.text is None and _refused(script.file, base_dir, confine_file_refs):
                warn(REFUSED_FILE_WARNING.format(what="script", file=script.file))
    blocks: list[str] = [script_block(s) for s in scripts]
    for action in _document_order(unlowered_actions, widget.actions):
        block = action_block(action, base_dir, confine_file_refs=confine_file_refs, warn=warn)
        if block is not None:
            blocks.append(block)
    blocks.extend(formula_pv_block(text) for text in declined_formula_pvs)
    if not blocks:
        return None
    return NodeMeta(comment="\n\n".join(blocks))
