from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import SCHEMA_PATH, schema_json, validate_screen_json


def test_committed_schema_not_drifted():
    """The committed screen-ir.schema.json must match what the models generate.

    If this fails, regenerate it: `python -m pydmconverter.ir.schema` style call,
    or `from pydmconverter.ir.schema import write_schema; write_schema()`.
    """
    assert SCHEMA_PATH.is_file(), f"missing committed schema at {SCHEMA_PATH}"
    committed = SCHEMA_PATH.read_text(encoding="utf-8")
    assert committed == schema_json(), "committed IR schema is stale — regenerate with write_schema()"


def test_emitted_ir_validates(sample_screen):
    """A representative emitted screen validates against the IR schema."""
    assert validate_screen_json(to_wire_dict(sample_screen)) == []


def test_invalid_ir_is_rejected():
    """Missing required fields surface as schema errors."""
    bad = {"schemaVersion": "1.0", "kind": "screen", "id": "s"}  # no metadata, no root
    errors = validate_screen_json(bad)
    assert errors, "expected schema validation errors for an incomplete screen"
