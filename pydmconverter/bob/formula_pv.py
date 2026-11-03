"""Formula-PV lowering for the Phoebus ``.bob`` front-end.

A Phoebus PV name starting with ``=`` is a *formula PV*: the rest of the text is an
expression over other PVs, evaluated client-side by Phoebus' ``FormulaPV``. PVs are
referenced as backticked names (```SR:PV```), single-quoted names (``'SR:PV'``) or
``pv("SR:PV")`` calls. The corpus forms are arithmetic, ``abs``, comparisons and the
JavaScript-style boolean operators, e.g. ``=(pv("X")*60)``, ``=abs(`A`-`B`) <= 0.25`` and
``=`A`&&`B```.

:func:`lower_formula_pv` rewrites such a text into a Formula Engine formula: every distinct PV name
(macro syntax normalised to ``${VAR}``) becomes a positional binding ``{0}``, ``{1}``, ...,
``&&``/``||``/``!`` become ``and``/``or``/``not``, and the result is interned in the
screen's formula pool, the caller retargeting the prop to ``formula://<name>``. Anything
the shared expression gate (:func:`~pydmconverter.bob.gates.expression_allowed`) refuses
(``concat``, ``elementAt``, other functions, bare names, a macro outside a PV name, a
rewrite that fails ``ast.parse``) is declined with a warning and ``None``; the caller
carries the text in ``meta.comment`` instead.
"""

from __future__ import annotations

import re
from typing import Any

from pydmconverter.bob.gates import expression_allowed
from pydmconverter.ir.macros import normalize_macro_syntax

__all__ = ["FORMULA_NOT_LOWERED_WARNING", "lower_formula_pv"]

FORMULA_NOT_LOWERED_WARNING = "{widget}: formula PV not lowered: {text}"

# PV references, in precedence order: pv("x") / pv('x') calls, `x`, 'x'.
_PV_REF_RE = re.compile(
    r"""pv\(\s*"(?P<dq>[^"]*)"\s*\)"""
    r"""|pv\(\s*'(?P<sq>[^']*)'\s*\)"""
    r"""|`(?P<bt>[^`]*)`"""
    r"""|'(?P<q>[^']*)'"""
)


def _tokenise(body: str) -> tuple[str, dict[str, str]]:
    """Replace PV references with ``{N}`` tokens; identical names share one index."""
    index_of: dict[str, int] = {}

    def token(m: re.Match) -> str:
        name = next(g for g in m.groups() if g is not None)
        name = normalize_macro_syntax(name.strip())
        n = index_of.setdefault(name, len(index_of))
        return f"{{{n}}}"

    text = _PV_REF_RE.sub(token, body)
    return text, {str(n): name for name, n in index_of.items()}


def _rewrite_operators(text: str) -> str:
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    return " ".join(text.split())


def _supported(expression: str, bindings: dict[str, str]) -> bool:
    """The shared expression gate, over exactly the tokenised PV bindings."""
    return expression_allowed(expression, len(bindings))


def _warn(ctx: Any, message: str) -> None:
    warn = getattr(ctx, "warn", None)
    if callable(warn):
        warn(message)
    else:
        ctx.warnings.append(message)


def lower_formula_pv(text: str, ctx: Any, *, widget: str | None = None) -> str | None:
    """Lower a Phoebus ``=`` formula PV to ``formula://<name>``, or return ``None``.

    ``ctx`` needs ``builder.formulas`` (a :class:`~pydmconverter.ir.ids.FormulaPool`,
    normally ``IRBuilder.formulas``) and either a ``warn(str)`` callable or a
    ``warnings`` list. ``widget`` prefixes the warning. On ``None`` exactly one
    warning, ``"<widget>: formula PV not lowered: <text>"``, has been recorded.
    """
    stripped = text.strip()
    if stripped.startswith("="):
        expression, bindings = _tokenise(stripped[1:])
        expression = _rewrite_operators(expression)
        if bindings and _supported(expression, bindings):
            return f"formula://{ctx.builder.formulas.intern(expression, bindings)}"
    message = f"formula PV not lowered: {text}"
    _warn(ctx, FORMULA_NOT_LOWERED_WARNING.format(widget=widget, text=text) if widget else message)
    return None
