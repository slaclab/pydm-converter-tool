"""Phoebus ``precision`` on text widgets: -1 is the PV's precision, 0 and up is the widget's own.

An IR ``precision`` alone means the PV's precision wins, so an own precision is written
with ``precisionFromPV: false``. ``precisionFromPV: true`` is never written.
"""

from __future__ import annotations

import pytest

from pydmconverter.bob.ir_adapter import bob_file_to_ir


def _node(tmp_path, wtype: str, precision: str | None):
    line = f"<precision>{precision}</precision>" if precision is not None else ""
    (tmp_path / "d.bob").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<display version="2.0.0"><name>D</name>'
        f'<widget type="{wtype}" version="2.0.0"><name>t</name><pv_name>SR:X</pv_name>{line}</widget>'
        "</display>",
        encoding="utf-8",
    )
    return bob_file_to_ir(tmp_path / "d.bob").root.children[0]


def _props(tmp_path, wtype: str, precision: str | None) -> dict:
    return _node(tmp_path, wtype, precision).props


@pytest.mark.parametrize(("wtype", "registry_id"), [("textupdate", "pv-label"), ("textentry", "pv-text-input")])
def test_own_precision_is_binding(tmp_path, wtype, registry_id):
    node = _node(tmp_path, wtype, "2")
    assert node.type == registry_id
    props = node.props
    assert (props["precision"], props["precisionFromPV"]) == (2, False)


@pytest.mark.parametrize("wtype", ["textupdate", "textentry"])
def test_zero_precision_is_binding(tmp_path, wtype):
    props = _props(tmp_path, wtype, "0")
    assert (props["precision"], props["precisionFromPV"]) == (0, False)


@pytest.mark.parametrize("wtype", ["textupdate", "textentry"])
@pytest.mark.parametrize("precision", ["-1", None])
def test_pv_precision_writes_neither_key(tmp_path, wtype, precision):
    props = _props(tmp_path, wtype, precision)
    assert "precision" not in props and "precisionFromPV" not in props
