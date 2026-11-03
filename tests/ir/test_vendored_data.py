"""Pins the vendored Canopy contracts and checks they ship as package data.

The widget registry is not vendored: since #166 its ``{id, qtMapping, qtPropMap}``
files are this package's own Qt mappings (see ``tests/ir/test_ir_registry.py``).

The values here must match the table in ``pydmconverter/ir/data/VENDORED_SCHEMA.md``.
Everything is read through ``importlib.resources`` on the installed package, so a
missing ``package-data`` glob fails here rather than at a user's import.
"""

import hashlib
import json
import re
from importlib.resources import files
from typing import get_args

import jsonschema
import pytest

from pydmconverter.ir.model import SchemaVersion, ScreenIR

PINNED = {
    "screen-ir.schema.json": "c8e4c82a3d77ce4db29309daaf9869d7888a9ed59609de6c359cb5a0ac4e5474",
    "canopy-color-scheme-1.schema.json": "180c9b21c4d42e3d315b58a23a95e107b9fb8f8871066e726c522c23708c74fa",
    "schemes/canopy-default.json": "0a8f403e70f0b9a5dc2eb9679da24f72f54209e19a8a9043d3de636e49ce810d",
}


def data_dir():
    return files("pydmconverter") / "ir" / "data"


def resource(rel):
    node = data_dir()
    for part in rel.split("/"):
        node = node / part
    return node


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("rel", sorted(PINNED))
def test_vendored_file_matches_pinned_sha256(rel):
    """Each vendored file is the exact byte copy recorded in VENDORED_SCHEMA.md."""
    node = resource(rel)
    assert node.is_file(), f"{rel} is not shipped as package data"
    assert sha256(node.read_bytes()) == PINNED[rel]


def test_registry_files_end_in_one_newline():
    """Registry files keep one normalisation: exactly one final newline per file."""
    for entry in (data_dir() / "widget-registry").iterdir():
        if entry.name.endswith(".json"):
            data = entry.read_bytes()
            assert data.endswith(b"}\n") and not data.endswith(b"\n\n"), entry.name


def test_vendored_schema_md_records_the_pinned_values():
    """VENDORED_SCHEMA.md and this test pin the same sha256 values."""
    text = (data_dir() / "VENDORED_SCHEMA.md").read_text(encoding="utf-8")
    for rel, digest in PINNED.items():
        assert re.search(rf"`{re.escape(rel)}` \| `[^`]+` \| `{digest}`", text), rel


def test_vendored_schema_md_sources_are_repo_relative():
    """Sources are recorded as ``<repo>: <path>``, never an absolute or tool-local path."""
    text = (data_dir() / "VENDORED_SCHEMA.md").read_text(encoding="utf-8")
    sources = re.findall(r"\| `[^`]+` \| `([^`]+)` \| `[0-9a-f]{64}` \|", text)
    assert len(sources) == len(PINNED)
    for source in sources:
        repo, _, path = source.partition(": ")
        assert repo in {"canopy", "canopy-spec"}, source
        assert path and not path.startswith(("/", "~")) and ".claude" not in path, source


def test_schema_and_model_accept_1_0_and_1_1():
    """The vendored 1.1 schema and the model both accept 1.0 and 1.1 documents."""
    schema = json.loads(resource("screen-ir.schema.json").read_text(encoding="utf-8"))
    assert sorted(schema["properties"]["schemaVersion"]["enum"]) == ["1.0", "1.1"]
    assert get_args(SchemaVersion) == ("1.0", "1.1")
    assert ScreenIR.model_fields["schema_version"].default == "1.0"


def test_color_scheme_schema_validates_the_default_scheme():
    """The vendored default scheme conforms to the vendored colour-scheme schema."""
    schema = json.loads(resource("canopy-color-scheme-1.schema.json").read_text(encoding="utf-8"))
    scheme = json.loads(resource("schemes/canopy-default.json").read_text(encoding="utf-8"))
    jsonschema.validate(scheme, schema)
    assert scheme["id"] == "canopy-default"
