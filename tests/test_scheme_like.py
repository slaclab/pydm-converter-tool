"""The ``scheme=`` parameter is a duck type (``pydmconverter.colors.SchemeLike``).

Canopy will own the scheme flattener and pass its own result to ``convert_bytes(scheme=...)``,
so the converter must accept any object exposing ``.flat``, ``.imports``, ``.sources`` and
``.meta`` with the documented shapes, not only its own ``SchemeResult``.
"""

from __future__ import annotations

from types import SimpleNamespace

from pydmconverter.colors import ColorContext, SchemeLike, named_color
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.react import convert_bytes
from pydmconverter.scheme import SchemeResult

_FLAT = {"roles": ["Text", "Grid"], "light": ["#000000", "#c6c6c6"], "dark": ["#f4f4f4", "#393939"]}
_IMPORTS = {"phoebus": {"Text": "Text", "Grid": "Grid"}, "edm": {}}
_SOURCES = {"Grid": "#808080"}
_META = {"id": "x", "sha256": "", "flatHash": "", "served": "x", "errors": []}

_BOB = b"""<?xml version="1.0" encoding="UTF-8"?>
<display version="2.0.0"><name>D</name>
<widget type="label" version="2.0.0"><name>L</name><x>0</x><y>0</y><text>t</text>
<foreground_color><color name="Text" red="0" green="0" blue="0"/></foreground_color>
<background_color><color name="Grid" red="128" green="128" blue="128"/></background_color>
<transparent>false</transparent>
</widget>
</display>"""


def _plain_scheme() -> SimpleNamespace:
    """Not a SchemeResult: a bare object with the four attributes."""
    return SimpleNamespace(flat=dict(_FLAT), imports=dict(_IMPORTS), sources=dict(_SOURCES), meta=dict(_META))


def test_plain_object_converts_named_colors_to_roles():
    wire = to_wire_dict(convert_bytes(_BOB, kind="bob", scheme=_plain_scheme()))
    (label,) = wire["root"]["children"]
    assert label["props"]["foregroundColor"] == {"$role": "Text", "fallback": "#000000"}
    # Grid declares a phoebus source: the saved grey matches it, so the restyled role applies.
    assert label["props"]["backgroundColor"] == {"$role": "Grid", "fallback": "#808080"}
    assert wire["schemaVersion"] == "1.1"


def test_plain_object_and_scheme_result_convert_identically():
    result = SchemeResult(flat=_FLAT, imports=_IMPORTS, sources=_SOURCES, meta=_META)
    assert to_wire_dict(convert_bytes(_BOB, kind="bob", scheme=result)) == to_wire_dict(
        convert_bytes(_BOB, kind="bob", scheme=_plain_scheme())
    )


def test_color_context_reads_only_the_four_attributes():
    ctx = ColorContext.from_scheme(_plain_scheme())
    assert named_color("Text", (0, 0, 0, 255), "foreground_color", ctx) == {"$role": "Text", "fallback": "#000000"}
    assert ctx.compared_value("Grid") == ("phoebus", "#808080")


def test_scheme_result_is_a_scheme_like():
    """A static-typing contract, checked structurally here: every protocol member exists."""
    result = SchemeResult(flat=_FLAT, imports=_IMPORTS, sources=_SOURCES, meta=_META)
    for member in ("flat", "imports", "sources", "meta"):
        assert hasattr(SchemeLike, member) and hasattr(result, member), member
