"""Macro helpers (Canopy macros design M1/M6).

Canopy uses ``${VAR}`` syntax; EDM and other sources use ``$(VAR)``. We normalize
on the way in and only ever store ``${VAR}`` in the IR. Macro names follow
``^[A-Z][A-Z0-9_]*$``.

Ports to ``@canopy/core`` macros (``findMacroReferences``/``resolveMacros``); kept
minimal here — the converter only needs reference-finding and syntax normalization.
"""

from __future__ import annotations

import re
from typing import Any

# Matches the broad ``\w+`` form the runtime resolver substitutes, so
# lowercase/mixed-case macros (${dev}, ${signal}) are found rather than dropped.
# The published @slaclab/canopy-screen-ir contract accepts this case too.
MACRO_REF_RE = re.compile(r"\$\{(\w+)\}")

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
