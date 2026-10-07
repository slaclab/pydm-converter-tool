"""React/Canopy target entry point: dispatch ``.edl``/``.ui`` -> Screen IR JSON.

This is the ``--target react`` half of the converter. It picks the front-end adapter
by file suffix and writes ``*.screen.json``. The legacy ``--target pydm`` path
(``edm/converter.py``, which writes ``.ui``) is untouched.

TSX is intentionally not produced here — that is the Screen Builder's eject path
(``@canopy/emitters``); this side stops at the runtime-renderable IR JSON.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.edm.parser_helpers import SearchPaths
from pydmconverter.ir.emit import write_screen_json
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient
from pydmconverter.ui.ir_adapter import ui_file_to_ir

logger = logging.getLogger(__name__)

_ADAPTERS = {".edl": edm_file_to_ir, ".ui": ui_file_to_ir}
SUPPORTED_SUFFIXES = tuple(_ADAPTERS)


def convert_to_ir(
    input_path: str | Path,
    *,
    registry: RegistryClient | None = None,
    color_list_path: str | Path | None = None,
    calc_list_path: str | Path | None = None,
    site: str | None = None,
    search_paths: SearchPaths = None,
    confine_file_refs: bool = False,
) -> ScreenIR:
    """Parse an ``.edl`` or ``.ui`` file into a Screen IR, dispatching by suffix.

    ``color_list_path`` (``.edl`` inputs only) points at an EDM ``colors.list`` palette
    used to resolve "index N" color props; when omitted it is located via (in order)
    the ``EDMCOLORFILE`` env var, ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``.

    ``search_paths`` (``.edl`` inputs only) are extra directories (a single directory
    or a sequence) searched, like ``EDMDATAFILES``, for symbol files and ``calc.list``.
    ``confine_file_refs`` is for untrusted input: file names taken from it (``.edl``
    symbol files, a ``.ui`` PyDMTemplateRepeater's ``dataSource``/``templateFilename``)
    are read only from inside the file's own directory or, for ``.edl``,
    ``search_paths``, never ``EDMDATAFILES`` (see :func:`convert_bytes`,
    :func:`edm_file_to_ir` and :func:`ui_file_to_ir`).
    """
    suffix = Path(input_path).suffix.lower()
    adapter = _ADAPTERS.get(suffix)
    if adapter is None:
        raise ValueError(f"--target react supports {', '.join(SUPPORTED_SUFFIXES)} inputs, not {suffix!r}")
    if suffix == ".edl":
        return edm_file_to_ir(
            input_path,
            registry=registry,
            color_list_path=color_list_path,
            calc_list_path=calc_list_path,
            site=site,
            search_paths=search_paths,
            confine_file_refs=confine_file_refs,
        )
    return ui_file_to_ir(input_path, registry=registry, confine_file_refs=confine_file_refs)


def convert_bytes(
    data: bytes,
    *,
    kind: Literal["edl", "ui"],
    registry: RegistryClient | None = None,
    color_list_path: str | Path | None = None,
    calc_list_path: str | Path | None = None,
    site: str | None = None,
    filename: str | None = None,
    search_paths: SearchPaths = None,
    confine_file_refs: bool = False,
) -> ScreenIR:
    """Parse raw ``.edl``/``.ui`` bytes into a Screen IR, keyed on ``kind``.

    For HTTP callers (the Screen Builder uploads screens as bytes, a browser cannot
    hand the backend a server path), so callers need not spill uploads to disk. The
    EDM parser reads from a path, so the bytes are staged in a temp file scoped to
    this call rather than in every caller.

    ``filename`` is the upload's original file name. Its basename (directories are
    stripped; a missing ``.{kind}`` suffix is appended) names the staged file, so the
    screen id and EDM title come from it. Without it, or when the filesystem cannot
    hold that name, they are ``"screen"``.

    ``search_paths`` (``kind="edl"`` only) are extra directories (a single directory or
    a sequence) searched, like ``EDMDATAFILES``, for symbol files (activeSymbolClass)
    and ``calc.list``: the staged file's own directory is a private temp dir, so
    siblings of the original file are only found through here (e.g. the directory of
    an extracted archive).

    ``confine_file_refs`` should be set when ``data`` is untrusted, e.g. a user upload.
    File names inside the input come verbatim from the bytes, so by default an absolute
    name or ``..`` can read any file the process can reach and inline it into the
    returned IR. With the flag on:

    - ``kind="edl"``: an activeSymbolClass ``file`` is read only if it resolves inside
      the private staging dir or one of ``search_paths`` (any of them: a
      ``../sibling/x`` name between two search paths is fine). Absolute names, and
      anything resolving outside all of them (``..``, a symlink pointing elsewhere),
      are rejected before any existence check and never read. The symbol is left as
      an empty group, warned as "outside the search paths" when no directory could
      hold the name and as not found otherwise. ``EDMDATAFILES`` and its ``.`` (CWD)
      default are not searched, and empty ``search_paths`` entries are ignored: pass
      every allowed root explicitly.
    - ``kind="ui"``: a PyDMTemplateRepeater's ``dataSource`` and ``templateFilename``
      must resolve inside the staged file's directory, which holds only the upload,
      so in practice the repeater becomes a placeholder with a warning.

    ``color_list_path`` (``kind="edl"`` only) points at an EDM ``colors.list`` palette
    used to resolve "index N" color props; when omitted it falls back to the
    ``EDMCOLORFILE`` env var, then ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``.
    """
    if kind not in ("edl", "ui"):
        raise ValueError(f"convert_bytes kind must be 'edl' or 'ui', not {kind!r}")
    # A fixed basename in a private temp dir -> a deterministic screen id (not a
    # random temp stem), and conversion of identical bytes is byte-stable.
    tmp_dir = Path(tempfile.mkdtemp(prefix="pydmconv-"))
    try:
        staged = tmp_dir / _staged_name(filename, kind)
        try:
            staged.write_bytes(data)
        except OSError as exc:
            # The upload's name can be too long or hold characters this filesystem
            # reserves; fall back to the fixed name rather than failing the conversion.
            if staged.name == f"screen.{kind}":
                raise
            logger.warning("Cannot stage upload as %r (%s); using screen.%s", filename, exc, kind)
            staged = tmp_dir / f"screen.{kind}"
            staged.write_bytes(data)
        return convert_to_ir(
            staged,
            registry=registry,
            color_list_path=color_list_path,
            calc_list_path=calc_list_path,
            site=site,
            search_paths=search_paths,
            confine_file_refs=confine_file_refs,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _staged_name(filename: str | None, kind: str) -> str:
    """Basename for a staged upload: ``filename`` without its directories (it must
    not escape the temp dir), with the ``.{kind}`` suffix the dispatcher keys on;
    ``screen.{kind}`` when no usable name is given."""
    name = Path(filename.replace("\\", "/")).name if filename else ""
    if name in ("", ".", "..") or "\x00" in name:
        return f"screen.{kind}"
    if Path(name).suffix.lower() != f".{kind}":
        name = f"{name}.{kind}"
    return name


def _screen_json_path(input_path: Path, output_path: Path) -> Path:
    """Normalize the output to a ``*.screen.json`` path."""
    if output_path.suffix.lower() == ".json":
        return output_path
    return output_path.parent / f"{output_path.stem or input_path.stem}.screen.json"


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    override: bool = False,
    registry: RegistryClient | None = None,
    color_list_path: str | Path | None = None,
    calc_list_path: str | Path | None = None,
    site: str | None = None,
) -> Path:
    """Convert one ``.edl``/``.ui`` file to ``*.screen.json``; return the output path.

    ``color_list_path`` (``.edl`` inputs only) points at an EDM ``colors.list`` palette
    used to resolve "index N" color props; when omitted it falls back to the
    ``EDMCOLORFILE`` env var, then ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``.
    """
    inp = Path(input_path)
    out = _screen_json_path(inp, Path(output_path))
    if out.is_file() and not override:
        raise FileExistsError(f"Output file '{out}' already exists. Use --override or -o to overwrite it.")
    return write_screen_json(
        convert_to_ir(
            inp, registry=registry, color_list_path=color_list_path, calc_list_path=calc_list_path, site=site
        ),
        out,
    )


def convert_folder(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    override: bool = False,
    registry: RegistryClient | None = None,
    color_list_path: str | Path | None = None,
    calc_list_path: str | Path | None = None,
    site: str | None = None,
) -> tuple[int, list[str]]:
    """Recursively convert every ``.edl``/``.ui`` under ``input_dir``.

    Returns ``(files_found, files_failed)``.

    ``color_list_path`` (``.edl`` inputs only) points at an EDM ``colors.list`` palette
    used to resolve "index N" color props; when omitted it falls back to the
    ``EDMCOLORFILE`` env var, then ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list``.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    found = 0
    failed: list[str] = []
    for source in sorted(input_dir.rglob("*")):
        if not source.is_file() or source.suffix.lower() not in _ADAPTERS:
            continue
        found += 1
        relative = source.relative_to(input_dir)
        out = (output_dir / relative).parent / f"{source.stem}.screen.json"
        if out.is_file() and not override:
            failed.append(str(source))
            logger.warning("Skipped: %s already exists. Use --override or -o to overwrite it.", out)
            continue
        try:
            write_screen_json(
                convert_to_ir(
                    source,
                    registry=registry,
                    color_list_path=color_list_path,
                    calc_list_path=calc_list_path,
                    site=site,
                ),
                out,
            )
        except Exception as exc:  # noqa: BLE001 - report and continue the walk
            failed.append(str(source))
            logger.warning("Failed to convert %s: %s", source, exc)
    return found, failed
