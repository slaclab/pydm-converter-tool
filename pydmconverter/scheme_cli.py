"""``canopy-scheme``: check a color scheme file, and survey the named colors a panel corpus uses.

``check <file>`` flattens the scheme the way the converter does and prints every validation error and every role
that has no dark value; it exits 1 when there is any.

``survey <dir>... [--scheme <file>] [--corpus-root <dir>] [--exclude <glob>]... [--deployed-prefix <path>]`` counts
the ``<color>`` elements of the ``.bob`` files under the directories, per ``(name, slot, saved RGB)``, and says what
each would become under the scheme. ``--exclude`` skips files whose corpus-relative path matches the glob.
``--deployed-prefix`` names the absolute directory a checked-out corpus is deployed at: a dangling symlink into it is
read from ``--corpus-root`` instead (without it, dangling symlinks are skipped).

``from-colordef [--color-def <file>] --extends canopy-default --into <file> [--id <id>] [--keep-light-aliases]``
writes the light value of every name in a colour table (the built-in Phoebus table, or a ``color.def``) into a
scheme file, keeping each role's dark value. ``Name = Other`` and ``alias(Other)`` become the light alias
``"@Other"``. Names in the file but not in the table are reported as removed and left in place.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from pydmconverter.bob.coercion import BUILTIN_NAMED_COLORS, parse_rgba_list
from pydmconverter.colors import ColorContext, rgba_to_hex
from pydmconverter.scheme import SchemeResult, canonical_hex, load_scheme

GLOB = "**/*.bob"

NO_SCHEME_FATE = "n/a (no scheme)"
UNNAMED = "(unnamed)"

RGBA = tuple[int, int, int, int]
Key = tuple[str, str, RGBA]


@dataclass(frozen=True)
class CorpusFile:
    """One file to survey: ``rel`` is the re-rooted corpus-relative path, ``source`` the file read."""

    rel: PurePosixPath
    source: Path


def is_excluded(rel: PurePosixPath, exclude: tuple[str, ...]) -> bool:
    text = rel.as_posix()
    return any(fnmatch(text, pattern) for pattern in exclude)


def _rerooted(root: Path, link: Path, deployed_prefix: str | None) -> tuple[PurePosixPath, Path] | None:
    if not deployed_prefix:
        return None
    prefix = deployed_prefix.rstrip("/") + "/"
    target = os.readlink(link)
    if not target.startswith(prefix):
        return None
    suffix = target[len(prefix) :]
    candidate = root / suffix
    return (PurePosixPath(suffix), candidate) if candidate.is_file() else None


def scan_dir(
    directory: Path, root: Path, *, exclude: tuple[str, ...] = (), deployed_prefix: str | None = None
) -> list[CorpusFile]:
    """The corpus files under ``directory``, with paths relative to ``root``, in sorted path order.

    ``exclude`` globs match the path relative to ``root``. A dangling symlink is skipped unless it points under
    ``deployed_prefix``, in which case it is read from ``root`` and keeps the re-rooted path.
    """
    out: list[CorpusFile] = []
    for path in sorted(directory.glob(GLOB)):
        try:
            rel = PurePosixPath(path.relative_to(root).as_posix())
        except ValueError:
            rel = PurePosixPath(path.relative_to(directory).as_posix())
        if is_excluded(rel, exclude):
            continue
        if path.is_symlink():
            if path.exists():
                resolved = path.resolve()
                if resolved.is_relative_to(root.resolve()):
                    rel = PurePosixPath(resolved.relative_to(root.resolve()).as_posix())
                out.append(CorpusFile(rel, path))
                continue
            rerooted = _rerooted(root, path, deployed_prefix)
            if rerooted is not None:
                out.append(CorpusFile(rerooted[0], rerooted[1]))
            continue
        if path.is_file():
            out.append(CorpusFile(rel, path))
    return out


def _default_root(dirs: list[Path]) -> Path:
    if len(dirs) == 1:
        return dirs[0]
    return Path(os.path.commonpath([str(d.resolve()) for d in dirs]))


def _file_colors(source: Path) -> dict[Key, int]:
    """Counts of ``<color>`` elements in one ``.bob`` file, keyed ``(name, slot, saved RGBA)``."""
    counts: dict[Key, int] = {}
    try:
        tree = ET.parse(source)
    except (ET.ParseError, OSError):
        return counts
    for parent in tree.iter():
        for child in parent:
            if child.tag != "color":
                continue
            try:
                rgb = tuple(int(float(child.get(c, "0"))) for c in ("red", "green", "blue"))
                alpha = int(float(child.get("alpha", "255")))
            except ValueError:
                continue
            key = (child.get("name") or UNNAMED, parent.tag, (*rgb, alpha))
            counts[key] = counts.get(key, 0) + 1
    return counts


def fate(name: str, rgba: RGBA, ctx: ColorContext | None) -> str:
    """What a color becomes under the scheme: ``role <name>`` or ``literal`` (with the reason).

    The survey reports the import's default role (no slot); the match is the converter's:
    the role's ``phoebus`` source when it declares one, else its light value.
    """
    if ctx is None:
        return NO_SCHEME_FATE
    role = None if name == UNNAMED else ctx.role_for(name)
    if role is None:
        return "literal (not imported)"
    basis, value = ctx.compared_value(role)
    if value == canonical_hex(rgba_to_hex(rgba)):
        return f"role {role}"
    return f"literal (role {role} {basis} {value} differs)"


def _row(key: Key, count: int, ctx: ColorContext | None) -> str:
    name, slot, rgba = key
    return f"{name}\t{slot}\t{rgba_to_hex(rgba)}\t{count}\t{fate(name, rgba, ctx)}"


def survey(
    dirs: list[Path],
    scheme: SchemeResult | None,
    root: Path | None,
    out,
    *,
    exclude: tuple[str, ...] = (),
    deployed_prefix: str | None = None,
) -> None:
    root = root if root is not None else _default_root(dirs)
    ctx = ColorContext.from_scheme(scheme) if scheme is not None else None
    seen: set[PurePosixPath] = set()
    total: dict[Key, int] = {}
    print("# name\tslot\tsaved RGB\tcount\tfate", file=out)
    for directory in dirs:
        for item in scan_dir(directory, root, exclude=exclude, deployed_prefix=deployed_prefix):
            if item.rel in seen:
                continue
            seen.add(item.rel)
            counts = _file_colors(item.source)
            print(f"# file: {item.rel.as_posix()}", file=out)
            for key in sorted(counts):
                print(_row(key, counts[key], ctx), file=out)
                total[key] = total.get(key, 0) + counts[key]
    print(f"# total: {len(seen)} file(s)", file=out)
    for key in sorted(total):
        print(_row(key, total[key], ctx), file=out)


def check(path: Path, out) -> int:
    result = load_scheme(path)
    errors = result.meta["errors"]
    no_dark = sorted(
        {e["path"].split("/")[-2] for e in errors if e["path"].endswith("/dark") and "no dark value" in e["message"]}
    )
    for err in errors:
        print(f"error: {err['path'] or '<file>'}: {err['message']}", file=out)
    for name in no_dark:
        print(f"no dark value: {name}", file=out)
    if errors:
        print(f"{path}: {len(errors)} error(s)", file=out)
        return 1
    print(f"{path}: ok ({len(result.flat['roles'])} roles)", file=out)
    return 0


def parse_color_table(path: Path | None, warnings: list[str]) -> dict[str, str]:
    """A colour table as ``{name: "#hex" | "@Other"}`` in table order: the built-ins, or the entries of ``path``.

    ``color.def`` grammar: ``Name = r, g, b [, a]`` | ``Name = Other`` | ``Name = alias(Other)``, ``#`` comments.
    Both reference forms keep the reference as a light alias. ``Other`` must be a built-in or defined earlier in the
    file. Lines that do not parse, or reference an undefined name, are skipped with a warning.
    """
    if path is None:
        return {name: canonical_hex(rgba_to_hex(rgba)) for name, rgba in BUILTIN_NAMED_COLORS.items()}
    known = set(BUILTIN_NAMED_COLORS)
    table: dict[str, str] = {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = (s.strip() for s in line.partition("="))
        if not sep or not name:
            warnings.append(f"{path}:{lineno}: cannot parse '{line}'")
            continue
        ref = None
        if value.startswith("alias"):
            rest = value[5:].strip()
            if not (rest.startswith("(") and rest.endswith(")")):
                warnings.append(f"{path}:{lineno}: cannot parse color '{name}' from '{value}'")
                continue
            ref = rest[1:-1].strip()
        elif value in known:
            ref = value
        if ref is not None:
            if ref not in known:
                warnings.append(f"{path}:{lineno}: color '{name}' references undefined '{ref}'")
                continue
            table[name] = f"@{ref}"
        else:
            rgba = parse_rgba_list(value)
            if rgba is None:
                warnings.append(f"{path}:{lineno}: cannot parse color '{name}' from '{value}'")
                continue
            table[name] = canonical_hex(rgba_to_hex(rgba))
        known.add(name)
    return table


def _is_alias(value: object) -> bool:
    return isinstance(value, str) and value.startswith("@")


def merge_light(roles: dict, table: dict[str, str], keep_light_aliases: bool) -> tuple[list[str], list[str]]:
    """Write ``table`` as light values into ``roles`` in place; returns ``(added, changed)`` names.

    Every touched role ends in the per-mode form: a bare value becomes the dark value, an object keeps its dark.
    With ``keep_light_aliases`` an existing light alias is kept instead of replaced.
    """
    added: list[str] = []
    changed: list[str] = []
    for name, new in table.items():
        if name not in roles:
            roles[name] = {"light": new}
            added.append(name)
            continue
        old = roles[name]
        if isinstance(old, dict):
            value = dict(old)
            old_light = old.get("light")
        else:
            value = {"light": old, "dark": old}
            old_light = old
        if not (keep_light_aliases and _is_alias(old_light)):
            value["light"] = new
        value = {mode: value[mode] for mode in ("light", "dark") if mode in value} | value
        if value != old:
            roles[name] = value
            if value.get("light") != old_light:
                changed.append(name)
    return added, changed


def from_colordef(
    color_def: Path | None, extends: str, into: Path, scheme_id: str | None, keep_light_aliases: bool, out, err
) -> int:
    if into.exists():
        try:
            doc = json.loads(into.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"{into}: cannot read scheme: {exc}", file=err)
            return 1
        if not isinstance(doc, dict) or not isinstance(doc.get("roles", {}), dict):
            print(f"{into}: not a scheme object with a 'roles' object", file=err)
            return 1
        if scheme_id is not None and doc.get("id") != scheme_id:
            print(f"{into}: --id {scheme_id!r} does not match the file's id {doc.get('id')!r}", file=err)
            return 1
    else:
        if not scheme_id:
            print(f"{into}: file does not exist; pass --id to create it", file=err)
            return 1
        doc = {"id": scheme_id, "extends": extends, "roles": {}}

    warnings: list[str] = []
    try:
        table = parse_color_table(color_def, warnings)
    except OSError as exc:
        print(f"{color_def}: cannot read: {exc.strerror or exc}", file=err)
        return 1
    for warning in warnings:
        print(f"warning: {warning}", file=err)

    roles = doc.setdefault("roles", {})
    removed = [name for name in roles if name not in table]
    added, changed = merge_light(roles, table, keep_light_aliases)

    tmp = into.with_name(into.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, into)

    for label, names in (("added", added), ("changed", changed), ("removed", removed)):
        for name in names:
            print(f"{label}: {name}", file=out)
    print(f"{into}: {len(added)} added, {len(changed)} changed, {len(removed)} removed (kept, not deleted)", file=out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="canopy-scheme", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="validate a scheme file")
    p_check.add_argument("file", type=Path)
    p_survey = sub.add_parser("survey", help="count the named colors a corpus uses")
    p_survey.add_argument("dirs", nargs="+", type=Path)
    p_survey.add_argument("--scheme", type=Path, default=None)
    p_survey.add_argument("--corpus-root", type=Path, default=None)
    p_survey.add_argument(
        "--exclude", action="append", default=[], help="skip files whose corpus-relative path matches (repeatable)"
    )
    p_survey.add_argument(
        "--deployed-prefix", default=None, help="read dangling symlinks into this deployed path from --corpus-root"
    )
    p_gen = sub.add_parser("from-colordef", help="write a colour table's light values into a scheme file")
    p_gen.add_argument("--color-def", type=Path, default=None, help="a Phoebus color.def (default: built-in table)")
    p_gen.add_argument("--extends", required=True, choices=["canopy-default"])
    p_gen.add_argument("--into", type=Path, required=True, help="the scheme file to update or create")
    p_gen.add_argument("--id", default=None, help="scheme id; required when --into does not exist")
    p_gen.add_argument("--keep-light-aliases", action="store_true", help="keep hand-written light aliases")
    args = parser.parse_args(argv)

    if args.command == "check":
        return check(args.file, sys.stdout)
    if args.command == "from-colordef":
        return from_colordef(
            args.color_def, args.extends, args.into, args.id, args.keep_light_aliases, sys.stdout, sys.stderr
        )
    scheme = load_scheme(args.scheme) if args.scheme is not None else None
    if scheme is not None and scheme.meta["errors"]:
        print(f"{args.scheme}: scheme has errors; run 'canopy-scheme check'", file=sys.stderr)
        return 1
    survey(
        args.dirs,
        scheme,
        args.corpus_root,
        sys.stdout,
        exclude=tuple(args.exclude),
        deployed_prefix=args.deployed_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
