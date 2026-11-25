"""PyDM ``.ui`` precision: ``precisionFromPV`` defaults to true, so only an explicit false is written."""

from __future__ import annotations

import pytest

from pydmconverter.ui.ir_adapter import ui_file_to_ir


def _props(tmp_path, qt_class: str, extra: str) -> dict:
    (tmp_path / "d.ui").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<ui version="4.0"><class>d</class>'
        '<widget class="QWidget" name="d">'
        '<property name="geometry"><rect><x>0</x><y>0</y><width>200</width><height>100</height></rect></property>'
        f'<widget class="{qt_class}" name="t">'
        '<property name="geometry"><rect><x>0</x><y>0</y><width>100</width><height>20</height></rect></property>'
        '<property name="channel" stdset="0"><string>ca://SR:X</string></property>'
        f"{extra}</widget></widget></ui>",
        encoding="utf-8",
    )
    return ui_file_to_ir(tmp_path / "d.ui").root.children[0].props


PRECISION = '<property name="precision" stdset="0"><number>3</number></property>'


def _flag(value: str) -> str:
    return f'<property name="precisionFromPV" stdset="0"><bool>{value}</bool></property>'


@pytest.mark.parametrize("qt_class", ["PyDMLabel", "PyDMLineEdit"])
def test_explicit_false_is_written(tmp_path, qt_class):
    props = _props(tmp_path, qt_class, PRECISION + _flag("false"))
    assert (props["precision"], props["precisionFromPV"]) == (3, False)


@pytest.mark.parametrize("qt_class", ["PyDMLabel", "PyDMLineEdit"])
def test_precision_alone_adds_no_flag(tmp_path, qt_class):
    props = _props(tmp_path, qt_class, PRECISION)
    assert props["precision"] == 3 and "precisionFromPV" not in props


@pytest.mark.parametrize("qt_class", ["PyDMLabel", "PyDMLineEdit"])
def test_explicit_true_is_not_written(tmp_path, qt_class):
    props = _props(tmp_path, qt_class, PRECISION + _flag("true"))
    assert props["precision"] == 3 and "precisionFromPV" not in props
