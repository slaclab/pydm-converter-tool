"""Tests for PyDM ``.ui`` ``rules`` property -> IR RuleSpec parsing (Defect B)."""

from __future__ import annotations

import json

from pydmconverter.ui.ir_adapter import ui_file_to_ir


def _ui_with_rules(rules_text: str) -> str:
    """A minimal ``.ui`` document with one PyDMLabel carrying the given rules string."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <widget class="QWidget" name="Form">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>400</width><height>300</height></rect>
  </property>
  <widget class="PyDMLabel" name="label">
   <property name="geometry">
    <rect><x>10</x><y>20</y><width>100</width><height>30</height></rect>
   </property>
   <property name="rules">
    <string>{rules_text}</string>
   </property>
  </widget>
 </widget>
</ui>
"""


def _first_label(ir):
    """The PyDMLabel resolves to the registry's ``pv-label`` widget type."""

    def walk(node):
        if node.type == "pv-label":
            return node
        for child in node.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(ir.root)


def test_visibility_rule_parsed(tmp_path):
    rules = [
        {
            "name": "Visibility",
            "property": "Visible",
            "initial_value": "1",
            "expression": "ch[0] == 0",
            "channels": [{"channel": "ca://${DEV}:HomeStatus", "trigger": True, "use_enum": False}],
        }
    ]
    # XML-escape the JSON by using html entities for quotes; simplest is to embed raw
    # (the ElementTree parser handles double quotes inside element text fine).
    rules_text = json.dumps(rules).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ui_path = tmp_path / "vis.ui"
    ui_path.write_text(_ui_with_rules(rules_text))

    ir = ui_file_to_ir(ui_path)
    label = _first_label(ir)
    assert label is not None, "expected a PyDMLabel node in the IR"

    assert len(label.rules) == 1
    rule = label.rules[0]
    assert rule.target_property == "visible"
    assert len(rule.pvs) == 1
    assert rule.pvs[0].name == "${DEV}:HomeStatus"  # ca:// stripped, macro intact
    assert rule.pvs[0].trigger is True
    assert len(rule.conditions) == 1
    assert rule.conditions[0].expression == "{0} == 0"
    assert rule.conditions[0].value is True
    assert rule.default is True  # initial_value "1" -> True for a visible target

    # The raw rules JSON must NOT leak into props.
    assert "rules" not in label.props


def test_malformed_rules_do_not_crash(tmp_path):
    ui_path = tmp_path / "bad.ui"
    ui_path.write_text(_ui_with_rules("this is not valid json {["))

    ir = ui_file_to_ir(ui_path)
    label = _first_label(ir)
    assert label is not None
    assert len(label.rules) == 0
    assert any("rules" in w.lower() for w in label.warnings), "expected a warning about dropped rules"
