"""The Screen IR ``schemaVersion`` stamp: ``"1.1"`` iff the screen carries a well-formed colour role.

:func:`pydmconverter.scheme.stamp_schema_version` decides on the wire doc (the SDK's
``stampSchemaVersion``); :func:`pydmconverter.react.convert_to_ir` reads the same answer off
the model with :func:`pydmconverter.react._has_color_role`, so the two must agree everywhere a
role can sit: a prop at any depth, a rule condition value, a rule default, in any descendant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pydmconverter import react
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.model import ScreenIR
from pydmconverter.react import _has_color_role
from pydmconverter.scheme import load_scheme, stamp_schema_version

EDM_FIXTURES = Path(__file__).parent / "edm" / "fixtures"
UI_FIXTURES = Path(__file__).parent / "ui" / "fixtures"

ROLE = {"$role": "Text", "fallback": "#161616"}
ROLE_DARK = {"$role": "Text", "fallback": "#161616", "fallbackDark": "#f4f4f4ff"}
# Not roles: a short hex, an extra key, an empty and a 65-character name.
BAD_ROLES = [
    {"$role": "Text", "fallback": "#fff"},
    {"$role": "Text", "fallback": "#161616", "extra": 1},
    {"$role": "", "fallback": "#161616"},
    {"$role": "x" * 65, "fallback": "#161616"},
]


def _widget(wid: str, props: dict | None = None, rules: list | None = None, children: list | None = None) -> dict:
    return {
        "id": wid,
        "type": "text-label",
        "props": props or {},
        "geometry": {"x": 0, "y": 0, "width": 10, "height": 10},
        "rules": rules or [],
        "children": children or [],
    }


def _rule(value, default) -> dict:
    return {
        "id": "r-001",
        "name": "colour",
        "targetProperty": "foregroundColor",
        "pvs": [{"name": "X:SEV", "trigger": True}],
        "conditions": [{"expression": "{0} == 1", "value": value}],
        "default": default,
    }


def _screen(root: dict) -> ScreenIR:
    return ScreenIR.model_validate(
        {
            "schemaVersion": "1.0",
            "kind": "screen",
            "id": "s",
            "metadata": {"title": "s", "source": {"type": "test"}, "size": {"width": 10, "height": 10}},
            "macros": [],
            "root": root,
        }
    )


CASES = {
    "no role": (_widget("root", {"backgroundColor": "#ffffff"}), False),
    "role in a root prop": (_widget("root", {"backgroundColor": ROLE}), True),
    "role with fallbackDark": (_widget("root", {"backgroundColor": ROLE_DARK}), True),
    "role deep in a list prop": (_widget("root", {"curves": [{"name": "a", "color": ROLE}]}), True),
    "role in a grandchild": (
        _widget("root", children=[_widget("g", children=[_widget("gg", {"foregroundColor": ROLE})])]),
        True,
    ),
    "role as a rule condition value": (_widget("root", rules=[_rule(ROLE, "#000000")]), True),
    "role as a rule default": (_widget("root", rules=[_rule("#ff0000", ROLE)]), True),
    "literal rule only": (_widget("root", rules=[_rule("#ff0000", "#000000")]), False),
    **{f"malformed role {i}": (_widget("root", {"backgroundColor": bad}), False) for i, bad in enumerate(BAD_ROLES)},
}


@pytest.mark.parametrize("root,expected", CASES.values(), ids=CASES.keys())
def test_model_walk_and_wire_stamp_agree(root, expected):
    ir = _screen(root)
    assert _has_color_role(ir) is expected
    assert stamp_schema_version(to_wire_dict(ir)) == ("1.1" if expected else "1.0")


def test_stamp_never_counts_the_version_string_itself():
    doc = to_wire_dict(_screen(_widget("root")))
    doc["schemaVersion"] = "1.1"
    assert stamp_schema_version(doc) == "1.0"


@pytest.fixture
def white_palette(tmp_path: Path) -> Path:
    path = tmp_path / "white.list"
    path.write_text(
        '4 0 0\n\nblinkms=500\ncolumns=5\nmax=0x10000\n\nstatic 0 "Black" { 0 0 0 }\n'
        'static 4 "GLOBAL canvas" { 0xffff 0xffff 0xffff }\nstatic 15 "Monitor: NORMAL" { 0x2424 0xa1a1 0x4848 }\n'
        'static 20 "Monitor: MAJOR" { 0xdada 0x1e1e 0x2828 }\n',
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_converted_screens_are_stamped_as_the_wire_doc_says(white_palette):
    """Every entry point stamps what the wire-doc rule would: 1.1 with roles, 1.0 without."""
    themed = react.convert_to_ir(EDM_FIXTURES / "theming.edl", color_list_path=white_palette, scheme=load_scheme(None))
    plain = react.convert_to_ir(EDM_FIXTURES / "theming.edl", color_list_path=white_palette)
    ui = react.convert_to_ir(UI_FIXTURES / "byte_and_related.ui")
    for ir, expected in ((themed, "1.1"), (plain, "1.0"), (ui, "1.0")):
        assert ir.schema_version == expected
        assert stamp_schema_version(to_wire_dict(ir)) == expected
