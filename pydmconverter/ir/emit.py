"""JSON emitter for the Screen IR.

Serializes a :class:`~pydmconverter.ir.model.ScreenIR` to a ``*.screen.json``
document: camelCase keys (via the model's alias generator), declaration key order
(stable, never alphabetized), and pruning of ``None`` values and empty lists so
the output stays clean and round-trip stable (D3). Empty dicts are kept — an
empty ``props`` is meaningful authored state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydmconverter.ir.model import ScreenIR


def _prune(value: Any) -> Any:
    """Recursively drop ``None`` values and empty lists; keep dicts (even empty)."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if item is None:
                continue
            if isinstance(item, list) and len(item) == 0:
                continue
            out[key] = _prune(item)
        return out
    if isinstance(value, list):
        return [_prune(item) for item in value]
    return value


def to_wire_dict(screen: ScreenIR) -> dict[str, Any]:
    """Return the camelCase wire dict for ``screen`` (pruned, deterministic)."""
    raw = screen.model_dump(by_alias=True, exclude_none=True)
    return _prune(raw)


def to_json(screen: ScreenIR, *, indent: int = 2) -> str:
    """Serialize ``screen`` to a JSON string with a trailing newline."""
    return json.dumps(to_wire_dict(screen), indent=indent, ensure_ascii=False) + "\n"


def write_screen_json(screen: ScreenIR, path: str | Path, *, indent: int = 2) -> Path:
    """Write ``screen`` to ``path`` as ``*.screen.json`` and return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(screen, indent=indent), encoding="utf-8")
    return out
