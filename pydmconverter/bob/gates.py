"""The gates every ``.bob`` value passes before it reaches the emitted screen.

A display file is untrusted input, and some of what it names is later evaluated or
followed: expressions go to the Formula Engine, URLs and files to the browser and the
runtime. Each kind has one gate here, and every sink calls it:

* :func:`expression_allowed` -- rule conditions, formula PVs and lowered formula
  scripts: the Formula Engine's expression subset over ``{N}`` bindings, no macros.
* :func:`web_url` -- ``open_webpage``: ``http``, ``https`` or relative, never
  protocol-relative (``//host/...``).
* :func:`file_reference` -- every file a display names (``open_file``,
  ``open_display``, navigation tabs, embedded and picture files, button images,
  ``file`` rule values): a relative or absolute path, nothing else.

All scans are linear in the input, no expression over :data:`MAX_EXPRESSION_CHARS` or
script over :data:`MAX_SCRIPT_CHARS` is parsed, and every parse goes through
:func:`parse_python`, which gives the parser a stack it cannot overflow.
"""

from __future__ import annotations

import ast
import re
import threading

from pydmconverter.ir.macros import normalize_macro_syntax

__all__ = [
    "FILE_REFERENCE_WARNING",
    "MAX_EXPRESSION_CHARS",
    "MAX_SCRIPT_CHARS",
    "PARSE_ERRORS",
    "WEB_URL_WARNING",
    "expression_allowed",
    "file_reference",
    "has_macro",
    "parse_python",
    "web_url",
]

FILE_REFERENCE_WARNING = "{widget}: {what} {reference!r} is not a file path; dropped"
WEB_URL_WARNING = "{widget}: open_webpage URL {reference!r} is not http, https or relative; dropped"

# --- expressions -----------------------------------------------------------------------

_BINDING_RE = re.compile(r"\{(\d+)\}")
_MACRO_CLOSERS = {"{": "}", "(": ")"}
#: The longest expression the gate passes: the Formula Engine's default maximum
#: expression length (``max_expression_len``, configurable there, 2048 by default).
#: An expression over it would be interned and then refused at evaluation time. For
#: a rule the engine compiles every condition into one ladder, so a per-condition
#: cap is an approximation of that limit, not the limit itself.
MAX_EXPRESSION_CHARS = 2048
#: The longest script text :func:`parse_python` parses. Longer text is unparseable
#: (``ValueError``), so the script stays tier 2 and the writer census finds nothing in
#: it. Together with :data:`PARSE_STACK_BYTES` this bounds the parser's stack use.
MAX_SCRIPT_CHARS = 256 * 1024
#: The C stack :func:`parse_python` gives the parser. Python 3.10's parser has no depth
#: guard: a chain of a few thousand terms overflows a 1 MB main-thread stack (Windows)
#: and kills the process instead of raising. 256 MB is address space, not memory; it
#: parses a 130k-term chain (twice what :data:`MAX_SCRIPT_CHARS` allows) with room to spare.
PARSE_STACK_BYTES = 256 * 1024 * 1024
#: What ``ast.parse`` raises on text it cannot turn into a tree: a syntax error, a null
#: byte or over-long text (``ValueError``), or an expression nested past the interpreter's
#: recursion limit (``RecursionError``, historically ``MemoryError``). Every parse of
#: display text catches these.
PARSE_ERRORS: tuple[type[BaseException], ...] = (SyntaxError, ValueError, RecursionError, MemoryError)

_PARSE_STACK_LOCK = threading.Lock()


def parse_python(text: str, *, mode: str = "exec") -> ast.AST:
    """``ast.parse(text, mode=mode)`` on a thread whose stack is :data:`PARSE_STACK_BYTES`.

    Raises what ``ast.parse`` raises (see :data:`PARSE_ERRORS`), plus ``ValueError`` for
    text over :data:`MAX_SCRIPT_CHARS`, before any parse. The thread stack size is
    process-wide state, so it is set and restored under a lock around the thread's start.
    """
    if len(text) > MAX_SCRIPT_CHARS:
        raise ValueError(f"text is {len(text)} characters, over the {MAX_SCRIPT_CHARS} the parser accepts")
    outcome: list[object] = []

    def run() -> None:
        try:
            outcome.append(ast.parse(text, mode=mode))
        except BaseException as exc:  # re-raised on the caller's thread below
            outcome.append(exc)

    with _PARSE_STACK_LOCK:
        previous = threading.stack_size(PARSE_STACK_BYTES)
        try:
            worker = threading.Thread(target=run, name="bob-parse", daemon=True)
            worker.start()
        finally:
            threading.stack_size(previous)
    worker.join()
    if not outcome:
        raise RecursionError("the parser thread ended without a result")
    if isinstance(outcome[0], BaseException):
        raise outcome[0]
    return outcome[0]  # type: ignore[return-value]


_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)
_ALLOWED_FUNCTIONS = frozenset({"abs", "floor"})
_ALLOWED_CONSTANTS = (bool, int, float, str)


def replace_macros(text: str, replacement: str) -> str:
    """Replace every ``${...}``/``$(...)`` (no nesting, leftmost first) in one linear pass.

    An opener with no closer after it can never close later, so its kind is not searched again.
    """
    out: list[str] = []
    unclosed: set[str] = set()
    i = 0
    while (j := text.find("$", i)) != -1 and j + 1 < len(text):
        closer = _MACRO_CLOSERS.get(text[j + 1])
        k = -1 if closer is None or closer in unclosed else text.find(closer, j + 2)
        if k == -1:
            if closer is not None:
                unclosed.add(closer)
            out.append(text[i : j + 1])
            i = j + 1
            continue
        out.append(text[i:j])
        out.append(replacement)
        i = k + 1
    out.append(text[i:])
    return "".join(out)


def has_macro(text: str) -> bool:
    """Whether ``text`` holds a ``${...}`` or ``$(...)`` macro reference."""
    return replace_macros(text, "") != text


def _allowed_tree(tree: ast.AST, names: set[str]) -> bool:
    callees: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return False
        if isinstance(node, ast.Constant) and type(node.value) not in _ALLOWED_CONSTANTS:
            return False
        if isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCTIONS) or node.keywords:
                return False
            callees.add(id(node.func))
    # Function names may only appear as the callee; other names must be bindings.
    return all(
        node.id in names or (node.id in _ALLOWED_FUNCTIONS and id(node) in callees)
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    )


def expression_allowed(expression: str, binding_count: int | None = None) -> bool:
    """Whether ``expression`` stays inside the subset the Formula Engine evaluates.

    Arithmetic, comparisons, ``and``/``or``/``not``, conditional expressions, number,
    string and bool constants, ``abs``/``floor`` calls (positional arguments) and
    ``{N}`` bindings; no attributes, subscripts, other names or calls. A macro anywhere
    fails: the check would see its name, while a consumer that substitutes it could
    run its value as code (in code position, or after closing a string literal).
    ``binding_count`` limits the bindings to ``{0}``..``{binding_count - 1}``; ``None``
    accepts any index. Text over :data:`MAX_EXPRESSION_CHARS` fails before any parse.
    """
    if len(expression) > MAX_EXPRESSION_CHARS or has_macro(expression):
        return False
    indices = [int(m.group(1)) for m in _BINDING_RE.finditer(expression)]
    if binding_count is not None and any(n >= binding_count for n in indices):
        return False
    text = _BINDING_RE.sub(lambda m: f"_pv{m.group(1)}", expression)
    try:
        tree = parse_python(text.strip(), mode="eval")
    except PARSE_ERRORS:
        return False
    return _allowed_tree(tree, {f"_pv{n}" for n in indices})


# --- references --------------------------------------------------------------------------

# What a browser ignores in a URL: leading/trailing C0 controls and spaces, and tab/LF/CR anywhere.
_EDGE = "".join(chr(c) for c in range(0x21))
_NEWLINE_TAB_RE = re.compile(r"[\t\n\r]")
_WEB_SCHEMES = frozenset({"http", "https"})


def _clean(text: str) -> str:
    """``text`` with macros normalised, as a browser reads it."""
    return _NEWLINE_TAB_RE.sub("", normalize_macro_syntax(text).strip(_EDGE))


def _relative_or_scheme(reference: str, schemes: frozenset[str]) -> bool:
    """Whether ``reference`` is relative (or absolute-path) or uses one of ``schemes``.

    The scheme is read from the part before the first ``/``, ``?`` or ``#``: a colon
    there must follow an allowed scheme. A macro there with no colon could expand to
    a scheme, so it is refused too. That head is empty for a protocol-relative
    reference, so :func:`_names_host` is checked first by every caller.
    """
    head = re.split(r"[/?#]", reference, maxsplit=1)[0]
    if ":" in head:
        return head.split(":", 1)[0].lower() in schemes
    return "${" not in head


def _names_host(reference: str) -> bool:
    """Whether ``reference`` opens with two slash-like characters (``//``, ``/\\``, ``\\\\``, ``\\/``).

    A browser reads each of those as an authority, so ``//evil.example/x`` is a
    different host under the page's scheme, not a relative URL.
    """
    return len(reference) >= 2 and reference[0] in "/\\" and reference[1] in "/\\"


def web_url(text: str) -> str | None:
    """``text`` cleaned when it is an ``http``/``https`` or relative URL, else ``None``.

    ``https://${HOST}/x``, ``docs/${X}.html`` and ``/abs/path.html`` pass;
    ``javascript:``, ``data:``, ``file:``, ``${BASE}/x`` and a protocol-relative
    ``//host/x`` (in any mix of ``/`` and ``\\``, after the browser's cleaning) do not.
    """
    url = _clean(text)
    if _names_host(url) or not _relative_or_scheme(url, _WEB_SCHEMES):
        return None
    return url


def file_reference(text: str) -> str | None:
    """``text`` cleaned when it is a relative or absolute file path, else ``None``.

    Backslashes read as ``/``. No scheme, no host (``//host/...``, ``\\\\host\\...``)
    and no macro before the first ``/`` that could expand to either: ``a.png``,
    ``../x/${DEV}.bob`` and ``/opt/ops/${IOC}`` pass; ``${F}``, ``C:/x`` and
    ``https://...`` do not.
    """
    reference = _clean(text).replace("\\", "/")
    if _names_host(reference) or not _relative_or_scheme(reference, frozenset()):
        return None
    return reference
