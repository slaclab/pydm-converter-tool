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

# EPICS CALC function names -> Fox namespace names (Canopy
# src/canopy/fox/language/namespace.py). EPICS SQR is square ROOT; LOG is
# log10 and LOGE/LN the natural log. Unknown names pass through and surface
# via Fox validation instead of being guessed at.
_CALC_TO_FOX_FUNCTIONS = {
    "MAX": "max",
    "MIN": "min",
    "ABS": "abs",
    "SQR": "sqrt",
    "SQRT": "sqrt",
    "EXP": "exp",
    "LOG": "log10",
    "LOGE": "log",
    "LN": "log",
    "CEIL": "ceil",
    "FLOOR": "floor",
    "SIN": "sin",
    "COS": "cos",
    "TAN": "tan",
    "ASIN": "asin",
    "ACOS": "acos",
    "ATAN": "atan",
    "ATAN2": "atan2",
}
_CALC_FUNCTION_RE = re.compile(r"\b(" + "|".join(_CALC_TO_FOX_FUNCTIONS) + r")\s*\(")


def to_fox_expression(expression: str) -> str:
    """Convert EPICS calc operators/functions to Fox/Python. Idempotent (the
    parser already applies the operator conversions; function names are only
    rewritten as call sites, so single-letter variables are never touched)."""
    expression = expression.replace("^", "**").replace("#", "!=")
    return _CALC_FUNCTION_RE.sub(lambda m: _CALC_TO_FOX_FUNCTIONS[m.group(1)] + "(", expression)


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
