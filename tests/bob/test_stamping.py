"""Tests for ``schema_version`` stamping (``pydmconverter.scheme.stamp_schema_version``).

A converted screen is stamped ``1.1`` iff a well-formed colour role appears anywhere in its
wire form, mirroring the SDK's ``stampSchemaVersion``; otherwise it stays ``1.0`` and the
output is byte-identical to a conversion without a scheme. All panels are synthetic.
"""

from __future__ import annotations

import pytest

from pydmconverter import react
from pydmconverter.ir.emit import to_json, to_wire_dict
from pydmconverter.ir.schema import validate_screen_json
from pydmconverter.scheme import SchemeResult, load_scheme, stamp_schema_version


def _panel(body: str, background: str = "") -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0"><name>t</name>{background}{body}</display>'
    ).encode()


def _textupdate(name: str, color_xml: str) -> str:
    return (
        f'<widget type="textupdate" version="2.0.0"><name>{name}</name><pv_name>sim://x</pv_name>'
        f"<foreground_color>{color_xml}</foreground_color></widget>"
    )


# Literal RGB only: no named colour, so no scheme can turn anything into a role.
_ROLE_FREE = _panel(_textupdate("T1", '<color red="12" green="34" blue="56"/>'))

# A named display background: the default scheme imports it as the Display_Background role.
_NAMED = _panel(
    _textupdate("T1", '<color red="12" green="34" blue="56"/>'),
    '<background_color><color name="Display_Background" red="255" green="255" blue="255"/></background_color>',
)


# -- stamp_schema_version on plain dicts ---------------------------------------------------------------------------


def test_empty_and_scalar_docs_are_1_0():
    assert stamp_schema_version({}) == "1.0"
    assert stamp_schema_version([]) == "1.0"
    assert stamp_schema_version("#ffffff") == "1.0"
    assert stamp_schema_version(None) == "1.0"


def test_nested_role_is_1_1():
    doc = {"root": {"children": [{"props": {"color": {"$role": "Text", "fallback": "#000000"}}}]}}
    assert stamp_schema_version(doc) == "1.1"


def test_role_in_list_and_with_fallback_dark_is_1_1():
    role = {"$role": "OK", "fallback": "#00ff00", "fallbackDark": "#00aa00cc"}
    assert stamp_schema_version({"curves": [{"color": "#123456"}, {"color": role}]}) == "1.1"


def test_doc_own_schema_version_is_ignored():
    assert stamp_schema_version({"schemaVersion": "1.1", "root": {}}) == "1.0"


@pytest.mark.parametrize(
    "candidate",
    [
        {"$role": "Text"},  # no fallback
        {"fallback": "#000000"},  # no $role
        {"$role": "", "fallback": "#000000"},  # empty role
        {"$role": "x" * 65, "fallback": "#000000"},  # role too long
        {"$role": 3, "fallback": "#000000"},  # role not a string
        {"$role": "Text", "fallback": "#000"},  # short hex is not a role fallback
        {"$role": "Text", "fallback": "black"},
        {"$role": "Text", "fallback": "#000000\n"},  # trailing newline must not match
        {"$role": "Text", "fallback": "#000000", "fallbackDark": "#12"},
        {"$role": "Text", "fallback": "#000000", "extra": 1},  # unknown key
    ],
)
def test_malformed_roles_are_not_roles(candidate):
    assert stamp_schema_version({"props": {"color": candidate}}) == "1.0"


def test_role_at_max_length_is_1_1():
    assert stamp_schema_version({"c": {"$role": "x" * 64, "fallback": "#ABCDEF"}}) == "1.1"


def test_role_length_counts_utf16_units_like_the_sdk():
    # 32 astral characters are 64 UTF-16 units (allowed); 33 are 66 (rejected), as in JS.
    assert stamp_schema_version({"c": {"$role": "\U0001f600" * 32, "fallback": "#000000"}}) == "1.1"
    assert stamp_schema_version({"c": {"$role": "\U0001f600" * 33, "fallback": "#000000"}}) == "1.0"


# -- the convert path ------------------------------------------------------------------------------------------------


def test_no_scheme_role_free_bob_is_byte_identical_and_1_0():
    ir = react.convert_bytes(_ROLE_FREE, kind="bob")
    assert ir.schema_version == "1.0"
    assert to_json(ir) == to_json(react.convert_bytes(_ROLE_FREE, kind="bob", scheme=None))
    assert validate_screen_json(to_wire_dict(ir)) == []


def test_scheme_with_role_free_bob_is_byte_identical_and_1_0():
    # A scheme that imports no names: nothing can become a role. (The default scheme would map even an
    # undeclared display background to Display_Background, so it is not role-free.)
    base = load_scheme(None)
    no_imports = SchemeResult(flat=base.flat, imports={"phoebus": {}, "edm": {}}, meta={})
    plain = react.convert_bytes(_ROLE_FREE, kind="bob")
    schemed = react.convert_bytes(_ROLE_FREE, kind="bob", scheme=no_imports)
    assert schemed.schema_version == "1.0"
    assert to_json(schemed) == to_json(plain)


def test_no_scheme_named_bob_stays_1_0():
    ir = react.convert_bytes(_NAMED, kind="bob")
    assert ir.schema_version == "1.0"
    assert stamp_schema_version(to_wire_dict(ir)) == "1.0"


def test_scheme_with_role_stamps_1_1_and_validates():
    ir = react.convert_bytes(_NAMED, kind="bob", scheme=load_scheme(None))
    wire = to_wire_dict(ir)
    assert wire["root"]["props"]["backgroundColor"]["$role"] == "Display_Background"
    assert ir.schema_version == "1.1"
    assert wire["schemaVersion"] == "1.1"
    assert validate_screen_json(wire) == []


def test_convert_file_writes_stamped_json(tmp_path):
    src = tmp_path / "p.bob"
    src.write_bytes(_NAMED)
    out = react.convert_file(src, tmp_path / "p", scheme=load_scheme(None))
    assert '"schemaVersion": "1.1"' in out.read_text(encoding="utf-8")
