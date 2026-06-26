"""IR JSON Schema validation against the vendored ``@canopy/screen-ir`` contract.

Ownership note: ``@canopy/screen-ir`` owns the Canopy screen contract. This
converter is disposable migration scaffolding — a *consumer* that must produce
IR the editor accepts; it does not get to define the format. So the schema this
module validates against is **vendored** from ``@canopy/screen-ir`` (see
``data/VENDORED_SCHEMA.md`` for the pinned version/commit), not minted here.

The Pydantic models in :mod:`pydmconverter.ir.model` remain the way the converter
*builds* IR internally. ``validate_screen_json`` checks an emitted wire dict
against the vendored editor schema, so the converter can guarantee every
``*.screen.json`` it writes conforms to the real Canopy contract before it lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

DATA_DIR = Path(__file__).parent / "data"

#: The vendored ``@canopy/screen-ir`` schema. This is the contract the converter
#: validates against. Owned upstream; see ``data/VENDORED_SCHEMA.md`` for the pin.
SCHEMA_PATH = DATA_DIR / "screen-ir.schema.json"


def load_schema() -> dict[str, Any]:
    """Load the vendored ``@canopy/screen-ir`` schema (the validation contract)."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_screen_json(data: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    """Validate a wire dict against the vendored IR schema. Returns error messages."""
    validator = Draft202012Validator(schema or load_schema())
    return [f"{'/'.join(map(str, err.path))}: {err.message}" for err in validator.iter_errors(data)]
