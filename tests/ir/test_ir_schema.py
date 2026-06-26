from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import SCHEMA_PATH, load_schema, validate_screen_json


def test_vendored_schema_is_the_canonical_contract():
    """The schema we validate against is the *vendored* @canopy/screen-ir contract.

    @canopy/screen-ir owns the contract; this converter is a consumer. The vendored
    file is the editor's canonical schema (discriminated Rule union, open
    ScreenSource, sealed objects), NOT a schema this repo generates from its own
    models. These markers catch an accidental revert to a self-minted schema.
    """
    assert SCHEMA_PATH.is_file(), f"missing vendored schema at {SCHEMA_PATH}"
    schema = load_schema()
    # Owned-upstream provenance and structural markers unique to the canonical file.
    assert "Owned by @canopy/screen-ir" in schema["description"]
    rule = schema["$defs"]["Rule"]
    assert "oneOf" in rule, "vendored Rule must be the discriminated union (conditional | formula arm)"
    # The vendored schema seals top-level objects; the model-generated one does not.
    assert schema.get("additionalProperties") is False


def test_emitted_ir_validates_against_vendored_schema(sample_screen):
    """A representative emitted screen conforms to the vendored editor contract."""
    assert validate_screen_json(to_wire_dict(sample_screen)) == []


def test_converter_only_emits_the_conditional_rule_arm(sample_screen):
    """The converter emits the conditional arm (pvs + conditions), never the formula arm."""
    wire = to_wire_dict(sample_screen)

    def walk(node):
        for rule in node.get("rules", []):
            assert "conditions" in rule and "pvs" in rule
            assert "formula" not in rule, "converter must not emit the editor-authored formula arm"
        for child in node.get("children", []):
            walk(child)

    walk(wire["root"])


def test_invalid_ir_is_rejected():
    """Missing required fields surface as schema errors."""
    bad = {"schemaVersion": "1.0", "kind": "screen", "id": "s"}  # no metadata, no root
    errors = validate_screen_json(bad)
    assert errors, "expected schema validation errors for an incomplete screen"


def test_no_dangling_fox_references(sample_screen):
    """Every fox://X referenced in props resolves to a formulas[] entry named X.

    The editor's validate() rejects dangling refs; the converter never produces one
    (each fox:// is minted alongside its formula). This guards that invariant.
    """
    wire = to_wire_dict(sample_screen)
    declared = {f["name"] for f in wire.get("formulas", [])}

    def fox_name(value):
        """The name in a ``fox://<name>`` string, or None if it isn't one."""
        prefix = "fox://"
        if isinstance(value, str) and value.startswith(prefix):
            return value[len(prefix) :]
        return None

    def referenced(node):
        for value in node.get("props", {}).values():
            if (name := fox_name(value)) is not None:
                yield name
        for rule in node.get("rules", []):
            for pv in rule.get("pvs", []):
                if (name := fox_name(pv.get("name"))) is not None:
                    yield name
        for child in node.get("children", []):
            yield from referenced(child)

    dangling = [name for name in referenced(wire["root"]) if name not in declared]
    assert dangling == [], f"dangling fox:// references: {dangling}"


def test_vendored_schema_is_valid_json():
    """Sanity: the vendored file parses as JSON (a copy/paste corruption tripwire)."""
    load_schema()
