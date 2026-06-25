"""Lower PyDM ``calc://`` channels to Canopy Fox formulas.

The EDM parser rewrites EDM ``CALC\\`` PVs into PyDM ``calc://`` URLs of the form
``calc://<id>?A=channel://pv1&B=ca://pv2&expr=A+B`` (the EPICS operators ``^``/``#``
are already converted to ``**``/``!=``). This module parses that URL back into a Fox
``(expression, bindings)`` pair: the expression in Fox grammar (asteval/numexpr) and
``bindings`` mapping each variable to its PV name. Numeric-literal args are inlined
into the expression rather than bound (Fox binds variables to PVs, not constants).

The builder hoists each distinct calc into the screen-level ``formulas[]`` (deduped)
and references it from the channel prop as ``fox://<name>`` — the same value-sourcing
seam Fox uses, reused from the converter side.
"""

from __future__ import annotations

import re

from pydmconverter.ir.macros import normalize_macro_syntax

_CHANNEL_PREFIXES = ("channel://", "ca://", "pva://")
_NUMERIC = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")


def to_fox_expression(expression: str) -> str:
    """Convert EPICS calc operators to Fox/Python. Idempotent (already applied at parse)."""
    return expression.replace("^", "**").replace("#", "!=")


def _strip_channel(value: str) -> str:
    for prefix in _CHANNEL_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def parse_calc_url(url: str) -> tuple[str, dict[str, str]] | None:
    """Parse a ``calc://`` URL into ``(fox_expression, bindings)``, or None.

    The query is split manually (not via ``parse_qs``) so a ``+`` in ``expr`` stays an
    operator rather than decoding to a space.
    """
    if not isinstance(url, str) or not url.startswith("calc://") or "?" not in url:
        return None
    query = url.split("?", 1)[1]
    expression = ""
    raw_args: dict[str, str] = {}
    for pair in query.split("&"):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        if key == "expr":
            expression = value
        else:
            raw_args[key] = value

    expression = to_fox_expression(expression)
    bindings: dict[str, str] = {}
    for var, value in raw_args.items():
        if _NUMERIC.match(value):
            # Inline a constant arg as a whole-word token (vars are single letters A-L).
            expression = re.sub(rf"\b{re.escape(var)}\b", value, expression)
        else:
            bindings[var] = normalize_macro_syntax(_strip_channel(value))
    return expression, bindings
