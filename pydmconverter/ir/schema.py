"""IR JSON Schema generation and validation.

The Pydantic models are the source of truth. ``build_schema()`` derives a JSON
Schema from them; that schema is committed at :data:`SCHEMA_PATH` as the contract
artifact for ``@canopy/screen-ir`` and the Screen Builder's ajv validator. A test
regenerates and compares so the committed file can never drift from the models.

``validate_screen_json`` validates a wire dict against the schema (belt-and-braces
on top of Pydantic's own validation), so the converter can guarantee every emitted
``*.screen.json`` conforms before it is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from pydmconverter.ir.model import ScreenIR

DATA_DIR = Path(__file__).parent / "data"
SCHEMA_PATH = DATA_DIR / "screen-ir.schema.json"

SCHEMA_ID = "https://canopy.slac.stanford.edu/schemas/screen-ir/1.0/schema.json"


def build_schema() -> dict[str, Any]:
    """Generate the IR JSON Schema from the Pydantic models (camelCase keys)."""
    schema = ScreenIR.model_json_schema(by_alias=True)
    # Stamp identity onto the generated schema. Pydantic emits a 2020-12 schema.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = SCHEMA_ID
    schema["title"] = "Canopy Screen IR"
    return schema


def schema_json(*, indent: int = 2) -> str:
    """The generated schema as a deterministic JSON string with trailing newline."""
    return json.dumps(build_schema(), indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


def write_schema(path: str | Path = SCHEMA_PATH) -> Path:
    """Write the generated schema to ``path`` (defaults to the committed location)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(schema_json(), encoding="utf-8")
    return out


def load_schema() -> dict[str, Any]:
    """Load the committed schema, falling back to a freshly generated one."""
    if SCHEMA_PATH.is_file():
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return build_schema()


def validate_screen_json(data: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    """Validate a wire dict against the IR schema. Returns a list of error messages."""
    validator = Draft202012Validator(schema or load_schema())
    return [f"{'/'.join(map(str, err.path))}: {err.message}" for err in validator.iter_errors(data)]
