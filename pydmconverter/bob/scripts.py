"""Tier-0 matchers for Phoebus widget scripts in the ``.bob`` front-end.

Phoebus attaches Jython/JavaScript scripts to widgets (``<scripts><script>``); the
script receives the widget and its ``pvs`` list and runs on every trigger. Canopy has
no script runtime, so only scripts whose whole behaviour is expressible declaratively
are lowered; everything else becomes a tier-2 warning and its text is carried in
``meta.comment``.

Alarm-boilerplate matcher (:func:`match_alarm_boilerplate`): the EDM-to-Phoebus
converter stamps one fixed Jython script on every alarm-sensitive widget (read
``PVUtil.getSeverity(pvs[0])``, index the palette tuple, set a colour prop). The
matcher compares the script's normalised token stream against that form and lowers a
match to a severity rule on ``<pv>.SEVR``.

Loc-formula matcher (:func:`match_loc_formula`): a script that reads some PVs, does
arithmetic, and writes the result to one ``loc://`` PV is exactly a formula. The
matcher walks an ``ast.parse`` of the script through a fixed statement grammar
(aliases ``name = pvs[i]``, value bindings ``name = PVUtil.getDouble(...)`` and
arithmetic intermediates, then one ``setValue``/``write`` or an ``if/elif/else`` of
constant writes) and returns a :class:`FormulaCandidate`; interning the formula and
retargeting readers to ``formula://<id>`` is the adapter's job. A script is lowered only
when it is the sole writer of its local PV in the file, which the file-wide writer
census (:func:`build_writer_census`) decides.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass, field

from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS
from pydmconverter.bob.local_pv import is_gateway_channel, local_pv_key
from pydmconverter.bob.parser import BobScript, BobWidget, walk_widgets
from pydmconverter.bob.gates import expression_allowed, has_macro
from pydmconverter.bob.rules import RuleContext, resolve_target
from pydmconverter.colors import named_color
from pydmconverter.edm.ir_adapter import _severity_channel
from pydmconverter.ir.macros import normalize_macro_syntax
from pydmconverter.ir.source import RuleSpec

__all__ = [
    "ALARM_BOILERPLATE_SKIP_WARNING",
    "ALARM_BOILERPLATE_TARGET_WARNING",
    "TIER2_SCRIPT_WARNING",
    "FormulaCandidate",
    "LocalWriter",
    "ScriptFileContext",
    "build_writer_census",
    "first_code_line",
    "match_alarm_boilerplate",
    "match_loc_formula",
    "script_written_pvs",
]


# =====================================================================================
# Loc-formula matcher (b)
# =====================================================================================

TIER2_SCRIPT_WARNING = "script needs the script runtime (tier 2)"

_PVUTIL_GETTERS = frozenset({"getDouble", "getLong", "getInt"})
_WRITE_METHODS = frozenset({"setValue", "write"})
_ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_PLACEHOLDER_RE = re.compile(r"__pv(\d+)__")
# Inlining shares subtrees (``b = a + a`` reuses ``a``), so a few lines can expand to an
# exponentially large formula. Past this many nodes, or this much formula text, the
# script stays tier 2.
MAX_EXPRESSION_NODES = 500
MAX_EXPRESSION_CHARS = 10_000


@dataclass
class LocalWriter:
    """One writer of a ``loc://`` PV in the file."""

    description: str  # e.g. "script calc on Text Update_25", "write_pv action on Btn"
    source: object  # the BobScript or BobAction that writes


@dataclass
class ScriptFileContext:
    """File-wide state the matcher consults: the writer census and collected warnings."""

    writers: dict[str, list[LocalWriter]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FormulaCandidate:
    """A script lowered to a formula, not yet interned.

    ``expression`` uses positional ``{N}`` tokens and ``bindings`` maps ``"N"`` to the
    bound PV (``${VAR}`` macro syntax; local PVs by :func:`local_pv_key`). ``target_key``
    is the ``local_pv_key`` of the written PV: every reader with that key is retargeted
    to the interned formula. ``actions`` carries action requests such as
    ``{"type": "close_display"}``. A script that only closes the display has
    ``expression`` and ``target_key`` ``None``.
    """

    expression: str | None
    bindings: dict[str, str] = field(default_factory=dict)
    target_key: str | None = None
    target_pv: str | None = None
    actions: list[dict] = field(default_factory=list)


class _NoMatch(Exception):
    """The script falls outside the grammar; ``reason`` refines the warning when set."""

    def __init__(self, reason: str | None = None):
        super().__init__(reason)
        self.reason = reason


def first_code_line(script: BobScript) -> str:
    """First line that is not blank, a comment, or an import; the file path when no text."""
    if script.text is None:
        return script.file
    for raw in script.text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("import ", "from ")):
            continue
        return line
    return ""


def _pv_index(node: ast.AST) -> int | None:
    """``pvs[i]`` with a literal non-negative int -> ``i``."""
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "pvs"
        and isinstance(node.slice, ast.Constant)
        and type(node.slice.value) is int
        and node.slice.value >= 0
    ):
        return node.slice.value
    return None


def _pv_ref(node: ast.AST, aliases: dict[str, int]) -> int | None:
    """``pvs[i]`` or an alias of it -> ``i``."""
    index = _pv_index(node)
    if index is not None:
        return index
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    return None


def _is_close_display(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr == "closeDisplay"
        and isinstance(stmt.value.func.value, ast.Name)
        and stmt.value.func.value.id == "ScriptUtil"
    )


def _write_call(stmt: ast.stmt, aliases: dict[str, int]) -> tuple[int, ast.expr] | None:
    """``(pvs[k] | alias).setValue|write(<arg>)`` -> ``(k, arg)``."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return None
    call = stmt.value
    if not (isinstance(call.func, ast.Attribute) and call.func.attr in _WRITE_METHODS):
        return None
    if len(call.args) != 1 or call.keywords:
        return None
    index = _pv_ref(call.func.value, aliases)
    return None if index is None else (index, call.args[0])


def _placeholder(index: int) -> ast.Name:
    return ast.Name(id=f"__pv{index}__", ctx=ast.Load())


def _getter_index(node: ast.AST, aliases: dict[str, int]) -> int | None:
    """``PVUtil.get{Double,Long,Int}(pvs[i] | alias)`` -> ``i``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _PVUTIL_GETTERS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "PVUtil"
        and len(node.args) == 1
        and not node.keywords
    ):
        return _pv_ref(node.args[0], aliases)
    return None


def _resolve(node: ast.AST, aliases: dict[str, int], values: dict[str, ast.expr], *, logic: bool) -> ast.expr:
    """Rebuild ``node`` over PV placeholders, inlining value bindings and intermediates.

    Arithmetic only; with ``logic`` also comparisons, ``and``/``or``/``not``.
    """
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return ast.Constant(value=node.value)
    if isinstance(node, ast.Name):
        if node.id in values:
            return values[node.id]
        raise _NoMatch()
    index = _getter_index(node, aliases)
    if index is not None:
        return _placeholder(index)
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
        return ast.BinOp(
            left=_resolve(node.left, aliases, values, logic=logic),
            op=node.op,
            right=_resolve(node.right, aliases, values, logic=logic),
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return ast.UnaryOp(op=node.op, operand=_resolve(node.operand, aliases, values, logic=logic))
    if logic:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return ast.UnaryOp(op=node.op, operand=_resolve(node.operand, aliases, values, logic=True))
        if isinstance(node, ast.BoolOp):
            return ast.BoolOp(op=node.op, values=[_resolve(v, aliases, values, logic=True) for v in node.values])
        if isinstance(node, ast.Compare) and not any(
            isinstance(o, (ast.Is, ast.IsNot, ast.In, ast.NotIn)) for o in node.ops
        ):
            return ast.Compare(
                left=_resolve(node.left, aliases, values, logic=True),
                ops=node.ops,
                comparators=[_resolve(c, aliases, values, logic=True) for c in node.comparators],
            )
    raise _NoMatch()


def _expanded_size(node: ast.AST, memo: dict[int, int]) -> int:
    """Node count of ``node`` once every shared subtree is written out (linear in the DAG)."""
    key = id(node)
    if key not in memo:
        memo[key] = 1 + sum(_expanded_size(child, memo) for child in ast.iter_child_nodes(node))
    return memo[key]


def _bounded(node: ast.expr) -> ast.expr:
    """``node``, or :class:`_NoMatch` when it would expand past ``MAX_EXPRESSION_NODES``.

    The memo is per call: it is keyed by ``id()``, which a freed node can hand on.
    """
    if _expanded_size(node, {}) > MAX_EXPRESSION_NODES:
        raise _NoMatch(f"inlined expression exceeds {MAX_EXPRESSION_NODES} nodes")
    return node


def _write_constant(node: ast.expr) -> ast.expr:
    """A literal number (optionally signed) or string written by an if/elif/else branch."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float, str):
        if isinstance(node.value, str) and has_macro(node.value):
            raise _NoMatch("writes a macro")  # a substituted value could close the string literal
        return ast.Constant(value=node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in (int, float)
    ):
        return ast.UnaryOp(op=node.op, operand=ast.Constant(value=node.operand.value))
    raise _NoMatch()


def _lower_if(stmt: ast.If, aliases: dict[str, int], values: dict[str, ast.expr]) -> tuple[int, ast.expr]:
    """``if/elif/else`` with exactly one constant write per branch -> ``(k, IfExp)``."""
    target: int | None = None

    def branch_value(body: list[ast.stmt]) -> ast.expr:
        nonlocal target
        if len(body) != 1:
            raise _NoMatch()
        write = _write_call(body[0], aliases)
        if write is None:
            raise _NoMatch()
        index, arg = write
        if target is None:
            target = index
        elif index != target:
            raise _NoMatch()
        return _write_constant(arg)

    arms: list[tuple[ast.expr, ast.expr]] = []
    current: ast.If = stmt
    while True:
        arms.append((_resolve(current.test, aliases, values, logic=True), branch_value(current.body)))
        if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
            continue
        if not current.orelse:
            raise _NoMatch()  # no else: the PV would keep a stale value
        result = branch_value(current.orelse)
        break
    for test, value in reversed(arms):
        result = ast.IfExp(test=test, body=value, orelse=result)
    assert target is not None
    return target, result


def _match_grammar(body: list[ast.stmt]) -> tuple[int, ast.expr]:
    """Walk the statement grammar; return the written index and the resolved expression."""
    if not body:
        raise _NoMatch()
    *prefix, final = body
    aliases: dict[str, int] = {}
    values: dict[str, ast.expr] = {}
    for stmt in prefix:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            raise _NoMatch()
        name = stmt.targets[0].id
        if name in ("pvs", "widget", "PVUtil", "ScriptUtil"):
            raise _NoMatch()
        index = _pv_index(stmt.value)
        aliases.pop(name, None)
        values.pop(name, None)
        if index is not None:
            aliases[name] = index
        else:
            values[name] = _bounded(_resolve(stmt.value, aliases, values, logic=False))
    if isinstance(final, ast.If):
        index, expr = _lower_if(final, aliases, values)
        return index, _bounded(expr)
    write = _write_call(final, aliases)
    if write is None:
        raise _NoMatch()
    index, arg = write
    return index, _bounded(_resolve(arg, aliases, values, logic=False))


def _binding_value(pv: str) -> str:
    text = pv.strip()
    if text.startswith("loc://"):
        return local_pv_key(text)
    return normalize_macro_syntax(text)


def _script_pvs(script: BobScript) -> list[str]:
    return [pv for pv, _trig in script.pvs]


def match_loc_formula(script: BobScript, widget: BobWidget, file_ctx: ScriptFileContext) -> FormulaCandidate | None:
    """Lower ``script`` to a formula candidate, or warn (tier 2) and return ``None``.

    Warnings go to ``file_ctx.warnings`` prefixed ``"<widget name>: "``.
    """
    first_line = first_code_line(script)

    def reject(reason: str | None = None) -> None:
        suffix = f" ({reason})" if reason else ""
        file_ctx.warnings.append(f"{widget.name}: {TIER2_SCRIPT_WARNING}: {first_line}{suffix}")

    if script.text is None:
        reject()
        return None
    try:
        module = ast.parse(script.text)
    except SyntaxError:
        reject()
        return None

    body = [s for s in module.body if not isinstance(s, (ast.Import, ast.ImportFrom))]
    close = [s for s in body if _is_close_display(s)]
    body = [s for s in body if not _is_close_display(s)]
    actions: list[dict] = [{"type": "close_display"}] if close else []
    if not body and actions:
        return FormulaCandidate(expression=None, actions=actions)

    pvs = _script_pvs(script)
    try:
        target_index, expr = _match_grammar(body)
    except _NoMatch as exc:
        reject(exc.reason)
        return None
    if target_index >= len(pvs):
        reject(f"pvs[{target_index}] is not declared")
        return None
    target_pv = pvs[target_index].strip()
    if not target_pv.startswith("loc://"):
        reject()
        return None
    target_key = local_pv_key(target_pv)

    # Number the bound PVs by first appearance in the rendered expression.
    rendered = ast.unparse(ast.fix_missing_locations(expr))
    if len(rendered) > MAX_EXPRESSION_CHARS:
        reject(f"formula text exceeds {MAX_EXPRESSION_CHARS} characters")
        return None
    order: list[int] = []
    for match in _PLACEHOLDER_RE.finditer(rendered):
        index = int(match.group(1))
        if index not in order:
            order.append(index)
    if not order:
        reject("no PV is read")
        return None
    if any(index >= len(pvs) for index in order):
        reject("reads an undeclared pvs[] entry")
        return None
    bound = [pvs[index].strip() for index in order]
    if any(not pv.startswith("loc://") and not is_gateway_channel(pv) for pv in bound):
        reject("binding without an evaluation venue (sim://, calc:// or formula)")
        return None
    local = [pv.startswith("loc://") for pv in bound]
    if any(local) and not all(local):
        reject("mixed loc:// and gateway bindings")
        return None
    if target_key in {local_pv_key(pv) for pv in bound if pv.startswith("loc://")}:
        reject(f"{target_key} reads itself")
        return None

    others = [w for w in file_ctx.writers.get(target_key, []) if w.source is not script]
    if others:
        reject(f"{target_key} has another writer: {others[0].description}")
        return None

    token_of = {index: str(n) for n, index in enumerate(order)}
    expression = _PLACEHOLDER_RE.sub(lambda m: "{" + token_of[int(m.group(1))] + "}", rendered)
    if not expression_allowed(expression, len(order)):  # the gate rule conditions pass too
        reject("formula outside the Formula Engine subset")
        return None
    bindings = {token_of[index]: _binding_value(pvs[index]) for index in order}
    return FormulaCandidate(
        expression=expression,
        bindings=bindings,
        target_key=target_key,
        target_pv=normalize_macro_syntax(target_pv),
        actions=actions,
    )


# --- writer census -------------------------------------------------------------------


def script_written_pvs(script: BobScript) -> list[int]:
    """Indices ``k`` of every ``(pvs[k] | alias).setValue|write(...)`` in the script.

    Aliases are ``name = pvs[k]`` assignments anywhere in the script. Unparseable or
    missing text yields ``[]``.
    """
    if script.text is None:
        return []
    try:
        module = ast.parse(script.text)
    except SyntaxError:
        return []
    aliases: dict[str, int] = {}
    for node in ast.walk(module):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            index = _pv_index(node.value)
            if index is not None:
                aliases[node.targets[0].id] = index
    written: set[int] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _WRITE_METHODS:
            index = _pv_ref(node.func.value, aliases)
            if index is not None:
                written.add(index)
    return sorted(written)


def build_writer_census(widgets: Iterable[BobWidget]) -> dict[str, list[LocalWriter]]:
    """Every writer of every ``loc://`` PV in the widget tree, keyed by ``local_pv_key``.

    Writers are scripts (``setValue``/``write`` on ``pvs[k]``) and ``write_pv`` actions;
    order is document order.
    """
    census: dict[str, list[LocalWriter]] = {}

    def add(pv: object, writer: LocalWriter) -> None:
        if isinstance(pv, str) and pv.strip().startswith("loc://"):
            census.setdefault(local_pv_key(pv), []).append(writer)

    for widget in walk_widgets(widgets):
        for script in widget.scripts:
            pvs = _script_pvs(script)
            for index in script_written_pvs(script):
                if index < len(pvs):
                    add(pvs[index], LocalWriter(f"script {script.name or script.file} on {widget.name}", script))
        for action in widget.actions:
            if action.type == "write_pv":
                add(action.fields.get("pv_name"), LocalWriter(f"write_pv action on {widget.name}", action))
    return census


# =====================================================================================
# Alarm-boilerplate matcher (a)
# =====================================================================================

ALARM_BOILERPLATE_SKIP_WARNING = "{widget}: alarm-colour script not lowered: {pv} has no alarm severity channel"
ALARM_BOILERPLATE_TARGET_WARNING = "{widget}: alarm-colour script not lowered: target {target} is not supported"

# Statements after normalisation (tokens joined without whitespace, string literals
# re-quoted with single quotes). The two imports may come in either order.
_ALARM_IMPORTS = frozenset(
    {
        "fromorg.csstudio.display.builder.runtime.scriptimportPVUtil",
        "fromorg.csstudio.display.builder.model.persistimportWidgetColorService",
    }
)
_ALARM_SEVERITY_RE = re.compile(r"(?P<sevr>[A-Za-z_]\w*)=PVUtil\.getSeverity\(pvs\[0\]\)")
_ALARM_PALETTE_RE = re.compile(
    r"(?P<cn>[A-Za-z_]\w*)=\('OK','MINOR','MAJOR','INVALID','DISCONNECTED'\)\[(?P<index>[A-Za-z_]\w*)\]"
)
_ALARM_SET_RE = re.compile(
    r"widget\.setPropertyValue\('(?P<prop>[A-Za-z_]\w*)',WidgetColorService\.getColor\((?P<cn>[A-Za-z_]\w*)\)\)"
)
# Phoebus alarm palette: severity code -> named colour; OK is the default.
_ALARM_PALETTE = (("{0}==1", "MINOR"), ("{0}==2", "MAJOR"), ("{0}>=3", "INVALID"))


def _normalised_statements(text: str) -> list[str] | None:
    """Logical lines of ``text`` without comments or whitespace; ``None`` if untokenisable.

    String literals are re-rendered with single quotes so quoting style does not matter.
    """
    statements: list[str] = []
    current: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text.replace("\r\n", "\n")).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.NEWLINE:
                if current:
                    statements.append("".join(current))
                current = []
                continue
            if tok.type == tokenize.STRING:
                value = ast.literal_eval(tok.string)
                if not isinstance(value, str) or "'" in value or "\\" in value:
                    return None
                current.append(f"'{value}'")
                continue
            current.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return None
    if current:
        statements.append("".join(current))
    return statements


def _boilerplate_target(text: str) -> str | None:
    """The Phoebus prop the boilerplate colours, or ``None`` when ``text`` is not it."""
    statements = _normalised_statements(text)
    if statements is None or len(statements) != 5:
        return None
    if frozenset(statements[:2]) != _ALARM_IMPORTS:
        return None
    severity = _ALARM_SEVERITY_RE.fullmatch(statements[2])
    palette = _ALARM_PALETTE_RE.fullmatch(statements[3])
    setter = _ALARM_SET_RE.fullmatch(statements[4])
    if severity is None or palette is None or setter is None:
        return None
    if palette.group("index") != severity.group("sevr") or setter.group("cn") != palette.group("cn"):
        return None
    return setter.group("prop")


def _alarm_colour(ctx: RuleContext, name: str, slot: str) -> str | dict:
    """The alarm colour ``name`` (a Phoebus named colour); a scheme role under the parity rule."""
    table = ctx.named_colors or {}
    return named_color(name, table.get(name, BUILTIN_NAMED_COLORS[name]), slot, ctx.color)


def match_alarm_boilerplate(
    script: BobScript,
    widget: BobWidget,
    ctx: RuleContext,
    *,
    registry_id: str | None = None,
) -> RuleSpec | None:
    """Lower the EDM alarm-colour boilerplate script to a severity rule, else ``None``.

    A non-matching script returns ``None`` silently. A matching script whose PV is not
    a gateway channel (``loc://``, ``sim://``, ``calc://``, formulas) or whose target
    prop does not map warns on ``ctx`` and returns ``None``. ``registry_id`` overrides
    the class-table id, as in :func:`~pydmconverter.bob.rules.lower_rule`.
    """
    if script.text is None or not script.pvs:
        return None
    prop = _boilerplate_target(script.text)
    if prop is None:
        return None
    raw_pv = script.pvs[0][0].strip()
    if not is_gateway_channel(raw_pv):
        ctx.warn(ALARM_BOILERPLATE_SKIP_WARNING.format(widget=widget.name, pv=raw_pv))
        return None
    target = resolve_target(prop, widget, ctx, registry_id)
    if target is None:
        ctx.warn(ALARM_BOILERPLATE_TARGET_WARNING.format(widget=widget.name, target=prop))
        return None
    pv = _severity_channel(normalize_macro_syntax(raw_pv))
    return RuleSpec(
        target_property=target,
        name=script.name or "alarm color",
        pvs=[(pv, True)],
        conditions=[(condition, _alarm_colour(ctx, colour, prop)) for condition, colour in _ALARM_PALETTE],
        default=_alarm_colour(ctx, "OK", prop),
    )
