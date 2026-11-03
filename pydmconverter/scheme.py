"""Color-scheme flattener: the single resolver for ``canopy-color-scheme/1`` files.

A facility scheme (for example ``facility-colors.json``) is layered on ``canopy-default``. :func:`load_scheme`
validates it against the vendored schema, merges it onto the base per role and per mode, resolves ``@alias``
references, canonicalises every hex the way the converter writes colors, and returns a :class:`SchemeResult`:

- ``flat``: ``{"roles": [name, ...], "light": [hex, ...], "dark": [hex, ...]}``, parallel lists;
- ``imports``: ``{"phoebus": {name: target}, "edm": {name: target}}``, the merged import maps, where a target is a
  role name or a slot object ``{"role": <default role>, <slot>: <role>, ...}`` choosing the role per source property;
- ``sources``: ``{role: hex}``, each role's declared ``phoebus`` source color (canonical hex), merged per role like a
  mode; roles without one are absent. Like ``imports`` it is a converter input, not a column of ``flat``, so it does
  not enter :meth:`SchemeResult.flat_json` or ``flatHash``;
- ``meta``: ``{"id", "sha256", "flatHash", "served", "errors": [{"path", "message"}]}``.

Bad input never raises. Every problem found is recorded in ``meta["errors"]``, and when there is any error the
result serves ``canopy-default`` (the base alone) instead of the facility scheme.

Role order is deterministic and independent of key order in the file: the base roles in base order, then any new
facility roles sorted by name. ``flatHash`` is a digest of the flat scheme actually served.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

DATA_DIR = Path(__file__).parent / "ir" / "data"

#: The vendored ``canopy-color-scheme/1`` JSON Schema.
SCHEMA_PATH = DATA_DIR / "canopy-color-scheme-1.schema.json"

#: The vendored ``canopy-default`` scheme, the default ``base_path``.
DEFAULT_SCHEME_PATH = DATA_DIR / "schemes" / "canopy-default.json"

DEFAULT_ID = "canopy-default"
MODES = ("light", "dark")
IMPORT_KINDS = ("phoebus", "edm")

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_ALIAS = re.compile(r"^@(.{1,64})$", re.DOTALL)

#: Marks a mode whose value was present but invalid. The validator already reported it, so it is neither a hole
#: nor something an alias can resolve to.
_INVALID = object()


@dataclass(frozen=True)
class SchemeResult:
    """A flattened scheme: the flat role table, the merged import maps and the meta block."""

    flat: dict[str, list[str]]
    imports: dict[str, dict[str, str | dict[str, str]]]
    meta: dict[str, Any]
    sources: dict[str, str] = field(default_factory=dict)

    def flat_json(self) -> dict[str, Any]:
        """The flat scheme plus ``meta``, as a fresh JSON-serialisable dict. ``imports`` and ``sources`` are not in it."""
        out: dict[str, Any] = copy.deepcopy(self.flat)
        out["meta"] = copy.deepcopy(self.meta)
        return out


def canonical_hex(value: str) -> str:
    """Canonicalise a hex color: expand ``#rgb``, lowercase, and drop an ``ff`` alpha."""
    digits = value[1:].lower()
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    if len(digits) == 8 and digits.endswith("ff"):
        digits = digits[:6]
    return "#" + digits


def flat_hash(flat: dict[str, list[str]]) -> str:
    """A stable digest of a flat scheme."""
    blob = json.dumps(flat, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_scheme(path: Path | None, *, base_path: Path | None = None) -> SchemeResult:
    """Flatten the facility scheme at ``path`` onto ``base_path`` (default: the vendored canopy-default).

    With ``path`` ``None`` the base alone is served, with ``id`` and ``served`` ``canopy-default``, the base file's
    sha256 and no errors. Never raises on a bad facility file.
    """
    base_path = Path(base_path) if base_path is not None else DEFAULT_SCHEME_PATH
    base_bytes = base_path.read_bytes()
    base_doc = json.loads(base_bytes.decode("utf-8"))
    base_roles, base_imports, base_sources, base_errors = _flatten({}, {}, {}, base_doc, prefix="base:", sort_new=False)
    base_flat = _to_flat(base_roles)
    base = (base_flat, base_imports, base_sources)

    if path is None:
        return _result(*base, DEFAULT_ID, hashlib.sha256(base_bytes).hexdigest(), DEFAULT_ID, base_errors)

    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _fallback(base, None, None, [_err("", f"cannot read {path}: {exc.strerror or exc}")])
    digest = hashlib.sha256(raw).hexdigest()

    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return _fallback(base, None, digest, [_err("", f"not valid JSON: {exc}")])

    errors = _schema_errors(doc)
    scheme_id = doc.get("id") if isinstance(doc, dict) and isinstance(doc.get("id"), str) and doc["id"] else None
    if not isinstance(doc, dict):
        return _fallback(base, scheme_id, digest, errors)

    base_values = {
        name: {mode: (value, f"base:roles/{name}/{mode}") for mode, value in modes.items()}
        for name, modes in base_roles.items()
    }
    roles, imports, sources, flatten_errors = _flatten(
        base_values, base_imports, base_sources, doc, prefix="", sort_new=True
    )
    errors.extend(flatten_errors)
    if errors:
        return _fallback(base, scheme_id, digest, errors)
    return _result(_to_flat(roles), imports, sources, scheme_id, digest, scheme_id or DEFAULT_ID, [])


#: The SDK's ``ColorRole`` shape (``colorRole.ts``): only these keys, ``$role`` 1-64 UTF-16 units, hex fallbacks.
_ROLE_KEYS = frozenset({"$role", "fallback", "fallbackDark"})
_ROLE_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_ROLE_MAX_LENGTH = 64


def _is_color_role(node: Any) -> bool:
    """Mirror of the SDK's ``isColorRole``: a well-formed ``{"$role", "fallback", "fallbackDark"?}`` dict."""
    if not isinstance(node, dict) or not set(node) <= _ROLE_KEYS:
        return False
    role = node.get("$role")
    if not isinstance(role, str) or not 1 <= len(role.encode("utf-16-le")) // 2 <= _ROLE_MAX_LENGTH:
        return False

    def is_hex(value: Any) -> bool:
        return isinstance(value, str) and _ROLE_HEX.fullmatch(value) is not None

    return is_hex(node.get("fallback")) and ("fallbackDark" not in node or is_hex(node["fallbackDark"]))


def _contains_color_role(node: Any) -> bool:
    if _is_color_role(node):
        return True
    if isinstance(node, dict):
        return any(_contains_color_role(value) for value in node.values())
    if isinstance(node, (list, tuple)):
        return any(_contains_color_role(value) for value in node)
    return False


def stamp_schema_version(doc: Any) -> str:
    """The Screen IR ``schemaVersion`` a wire doc must carry: ``"1.1"`` iff it contains a colour role, else ``"1.0"``.

    Mirrors the SDK's ``stampSchemaVersion``: a deep walk over dict values and list items for a well-formed
    ``ColorRole``. The doc's own ``schemaVersion`` is a string, so it never counts. Never raises.
    """
    return "1.1" if _contains_color_role(doc) else "1.0"


# -- internals -----------------------------------------------------------------------------------------------------


def _err(path: str, message: str) -> dict[str, str]:
    return {"path": path, "message": message}


def _result(flat, imports, sources, scheme_id, digest, served, errors) -> SchemeResult:
    meta = {"id": scheme_id, "sha256": digest, "flatHash": flat_hash(flat), "served": served, "errors": errors}
    return SchemeResult(flat=copy.deepcopy(flat), imports=copy.deepcopy(imports), meta=meta, sources=dict(sources))


def _fallback(base, scheme_id, digest, errors) -> SchemeResult:
    """Serve the base: ``base`` is its ``(flat, imports, sources)``."""
    return _result(*base, scheme_id, digest, DEFAULT_ID, errors)


def _to_flat(roles: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    names = list(roles)
    return {"roles": names, "light": [roles[n]["light"] for n in names], "dark": [roles[n]["dark"] for n in names]}


_validator: Draft202012Validator | None = None


def _schema_errors(doc: Any) -> list[dict[str, str]]:
    global _validator
    if _validator is None:
        _validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for err in sorted(_validator.iter_errors(doc), key=lambda e: [str(p) for p in e.absolute_path]):
        for entry in _leaf_errors(err):
            key = (entry["path"], entry["message"])
            if key not in seen:
                seen.add(key)
                out.append(entry)
    return out


def _leaf_errors(err) -> list[dict[str, str]]:
    """Descend ``anyOf`` failures to the deepest branch, so a bad hex is reported at its own path."""
    depth = len(err.absolute_path)
    if err.validator == "anyOf" and err.context:
        deepest = max(len(e.absolute_path) for e in err.context)
        if deepest > depth:
            leaves: list[dict[str, str]] = []
            done: set[str] = set()
            for sub in err.context:
                if len(sub.absolute_path) == deepest:
                    for leaf in _leaf_errors(sub):
                        if leaf["path"] not in done:
                            done.add(leaf["path"])
                            leaves.append(leaf)
            return leaves
    path = "/".join(str(p) for p in err.absolute_path)
    message = err.message
    if err.validator == "anyOf" and isinstance(err.instance, str) and path.startswith("roles/"):
        message = f"{err.instance!r} is not a hex color (#rgb, #rrggbb, #rrggbbaa) or an @alias"
    return [_err(path, message)]


def _parse_color(value: Any) -> Any:
    """A canonical hex, ``("alias", name)``, or ``_INVALID``."""
    if isinstance(value, str):
        if _HEX.match(value):
            return canonical_hex(value)
        m = _ALIAS.match(value)
        if m:
            return ("alias", m.group(1))
    return _INVALID


def _flatten(base_values, base_imports, base_sources, doc, *, prefix: str, sort_new: bool):
    """Merge ``doc`` onto the base, resolve aliases and check imports.

    ``base_values`` maps role -> mode -> (value, origin path); ``base_sources`` maps role -> phoebus hex. Returns
    (roles, imports, sources, errors) where roles maps each fully resolved role to ``{"light": hex, "dark": hex}``;
    roles that failed to resolve are left out, and so are their sources. New roles keep file order for the base
    itself and are sorted by name for a facility file (so key order cannot matter).
    """
    errors: list[dict[str, str]] = []
    merged: dict[str, dict[str, tuple[Any, str]]] = {name: dict(modes) for name, modes in base_values.items()}
    merged_sources: dict[str, str] = dict(base_sources)

    doc_roles = doc.get("roles") if isinstance(doc, dict) else None
    if not isinstance(doc_roles, dict):
        doc_roles = {}
    new_names = [n for n in doc_roles if n not in merged]
    if sort_new:
        new_names.sort()
    for name in new_names:
        merged[name] = {}
    for name, value in doc_roles.items():
        if isinstance(value, dict):
            for mode in MODES:
                if mode in value:
                    merged[name][mode] = (_parse_color(value[mode]), f"{prefix}roles/{name}/{mode}")
            if "phoebus" in value:
                source = value["phoebus"]
                if isinstance(source, str) and _HEX.match(source):
                    merged_sources[name] = canonical_hex(source)
                else:
                    # The schema reports a facility file's bad source; the base file is not schema-checked.
                    if prefix:
                        errors.append(_err(f"{prefix}roles/{name}/phoebus", f"{source!r} is not a hex color"))
                    merged_sources.pop(name, None)
        else:
            parsed = _parse_color(value)
            for mode in MODES:
                merged[name][mode] = (parsed, f"{prefix}roles/{name}")

    for name, modes in merged.items():
        for mode in MODES:
            if mode not in modes:
                errors.append(
                    _err(f"{prefix}roles/{name}/{mode}", f"role {name!r} has no {mode} value after inheritance")
                )

    resolved: dict[str, dict[str, str]] = {name: {} for name in merged}
    reported_cycles: set[tuple[str, frozenset[str]]] = set()
    for mode in MODES:
        for name in merged:
            value = _resolve(name, mode, merged, errors, reported_cycles)
            if value is not None:
                resolved[name][mode] = value
    roles = {name: modes for name, modes in resolved.items() if len(modes) == len(MODES)}
    sources = {name: merged_sources[name] for name in roles if name in merged_sources}

    imports: dict[str, dict[str, Any]] = {kind: dict(base_imports.get(kind, {})) for kind in IMPORT_KINDS}
    doc_imports = doc.get("import") if isinstance(doc, dict) else None
    if isinstance(doc_imports, dict):
        for kind in IMPORT_KINDS:
            mapping = doc_imports.get(kind)
            if not isinstance(mapping, dict):
                continue
            for key, target in mapping.items():
                if target is None:
                    imports[kind].pop(key, None)
                elif isinstance(target, (str, dict)):
                    imports[kind][key] = copy.deepcopy(target)  # replaces the inherited entry whole
    for kind in IMPORT_KINDS:
        for key, target in imports[kind].items():
            if isinstance(target, dict):
                if "role" not in target:
                    errors.append(_err(f"{prefix}import/{kind}/{key}/role", "slot import has no default 'role'"))
                for slot, slot_role in target.items():
                    if not isinstance(slot_role, str) or slot_role not in merged:
                        errors.append(
                            _err(f"{prefix}import/{kind}/{key}/{slot}", f"import target {slot_role!r} is not a role")
                        )
            elif target not in merged:
                errors.append(_err(f"{prefix}import/{kind}/{key}", f"import target {target!r} is not a role"))
    return roles, imports, sources, errors


def _resolve(name, mode, merged, errors, reported_cycles) -> str | None:
    """Follow the alias chain from ``name`` in ``mode`` with a visited-set guard; report dangling aliases and cycles."""
    chain: list[str] = []
    visited: set[str] = set()
    current = name
    while True:
        entry = merged.get(current, {}).get(mode)
        if entry is None or entry[0] is _INVALID:
            return None  # a hole or a bad value, reported on its own
        value, origin = entry
        if isinstance(value, str):
            return value
        chain.append(current)
        visited.add(current)
        target = value[1]
        if target in visited:
            cycle = chain[chain.index(target) :] + [target]
            key = (mode, frozenset(cycle))
            if key not in reported_cycles:
                reported_cycles.add(key)
                head = merged[cycle[0]][mode][1]
                errors.append(_err(head, f"alias cycle in {mode}: {' -> '.join(cycle)}"))
            return None
        if target not in merged:
            if current == name:
                errors.append(_err(origin, f"alias @{target} ({mode}) does not name a role"))
            return None
        current = target
