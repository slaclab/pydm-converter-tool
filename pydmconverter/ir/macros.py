"""Macro helpers (Canopy macros design M1/M6).

Canopy uses ``${VAR}`` syntax; EDM and other sources use ``$(VAR)``. We normalize
on the way in and only ever store ``${VAR}`` in the IR. Macro names follow
``MACRO_NAME_PATTERN`` (``^[A-Za-z][A-Za-z0-9_]*$``); :func:`valid_macro_name`
renames source names outside it (``6X6FBCKPV`` -> ``M_6X6FBCKPV``).

Ports to ``@canopy/core`` macros (``findMacroReferences``/``resolveMacros``); kept
minimal here — the converter only needs reference-finding and syntax normalization.
"""

from __future__ import annotations

import re
from typing import Any

from pydmconverter.ir.model import MACRO_NAME_PATTERN

# Matches the broad ``\w+`` form the runtime resolver substitutes, so
# lowercase/mixed-case macros (${dev}, ${signal}) are found rather than dropped.
# The published @slaclab/canopy-screen-ir contract accepts this case too.
MACRO_REF_RE = re.compile(r"\$\{(\w+)\}")

_VALID_NAME_RE = re.compile(MACRO_NAME_PATTERN)

# EDM-style ``$(VAR)`` to tolerate on input; normalized to ``${VAR}`` (M1).
_EDM_MACRO_RE = re.compile(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)")


def normalize_macro_syntax(value: Any) -> Any:
    """Rewrite ``$(VAR)`` -> ``${VAR}``. Non-strings pass through unchanged."""
    if not isinstance(value, str):
        return value
    return _EDM_MACRO_RE.sub(r"${\1}", value)


def find_macro_references(template: Any) -> list[str]:
    """Return the distinct ``${VAR}`` macro names referenced in ``template`` (in order)."""
    if not isinstance(template, str):
        return []
    return list(dict.fromkeys(MACRO_REF_RE.findall(template)))


def valid_macro_name(name: str) -> str:
    """``name`` when the IR accepts it (``MACRO_NAME_PATTERN``), else a deterministic rename.

    Sources accept names the IR rejects (EDM passes ``6X6FBCKPV=...``). Characters
    outside ``[A-Za-z0-9_]`` become ``_`` and a name not starting with a letter gets
    an ``M_`` prefix (``6X6FBCKPV`` -> ``M_6X6FBCKPV``). Because the mapping is
    deterministic, a converted target screen and every converted caller that passes
    the macro agree on the new name. Empty names are returned unchanged.
    """
    if not name or _VALID_NAME_RE.match(name):
        return name
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    return cleaned if _VALID_NAME_RE.match(cleaned) else f"M_{cleaned}"
