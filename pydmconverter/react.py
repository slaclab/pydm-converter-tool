"""React/Canopy target entry point: dispatch ``.edl``/``.ui`` -> Screen IR JSON.

This is the ``--target react`` half of the converter. It picks the front-end adapter
by file suffix and writes ``*.screen.json``. The legacy ``--target pydm`` path
(``edm/converter.py``, which writes ``.ui``) is untouched.

TSX is intentionally not produced here — that is the Screen Builder's eject path
(``@canopy/emitters``); this side stops at the runtime-renderable IR JSON.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import write_screen_json
from pydmconverter.ir.model import ScreenIR
from pydmconverter.ir.registry import RegistryClient
from pydmconverter.ui.ir_adapter import ui_file_to_ir

logger = logging.getLogger(__name__)

_ADAPTERS = {".edl": edm_file_to_ir, ".ui": ui_file_to_ir}
SUPPORTED_SUFFIXES = tuple(_ADAPTERS)


def convert_to_ir(input_path: str | Path, *, registry: RegistryClient | None = None) -> ScreenIR:
    """Parse an ``.edl`` or ``.ui`` file into a Screen IR, dispatching by suffix."""
    suffix = Path(input_path).suffix.lower()
    adapter = _ADAPTERS.get(suffix)
    if adapter is None:
        raise ValueError(f"--target react supports {', '.join(SUPPORTED_SUFFIXES)} inputs, not {suffix!r}")
    return adapter(input_path, registry=registry)


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
) -> Path:
    """Convert one ``.edl``/``.ui`` file to ``*.screen.json``; return the output path."""
    inp = Path(input_path)
    out = _screen_json_path(inp, Path(output_path))
    if out.is_file() and not override:
        raise FileExistsError(f"Output file '{out}' already exists. Use --override or -o to overwrite it.")
    return write_screen_json(convert_to_ir(inp, registry=registry), out)


def convert_folder(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    override: bool = False,
    registry: RegistryClient | None = None,
) -> tuple[int, list[str]]:
    """Recursively convert every ``.edl``/``.ui`` under ``input_dir``.

    Returns ``(files_found, files_failed)``.
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
            write_screen_json(convert_to_ir(source, registry=registry), out)
        except Exception as exc:  # noqa: BLE001 - report and continue the walk
            failed.append(str(source))
            logger.warning("Failed to convert %s: %s", source, exc)
    return found, failed
