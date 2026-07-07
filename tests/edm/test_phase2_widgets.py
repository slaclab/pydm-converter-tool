from pathlib import Path

from pydmconverter.edm.ir_adapter import edm_file_to_ir
from pydmconverter.ir.emit import to_wire_dict
from pydmconverter.ir.schema import validate_screen_json

FIXTURES = Path(__file__).parent / "fixtures"
COLORS = FIXTURES / "colors.list"


def _convert(name: str):
    return edm_file_to_ir(FIXTURES / name, color_list_path=COLORS)


# ---------------------------------------------------------------------------
# activeXTextDspClass:noedit / activeXTextDspClass (plain, regression)
# ---------------------------------------------------------------------------


def test_noedit_textdsp_exponential_format_and_display_bg_suppresses_background():
    label = _convert("phase2_textdsp.edl").root.children[0]
    assert label.type == "pv-label"
    assert label.props["pv"] == "${P}:VAL"
    assert label.props["format"] == "exponential"
    assert label.props["precision"] == 3
    assert label.props["showUnits"] is True
    assert label.props["foregroundColor"] == "#ffff00"
    assert "backgroundColor" not in label.props


def test_noedit_textdsp_decimal_format_normalizes_to_default():
    label = _convert("phase2_textdsp.edl").root.children[1]
    assert label.type == "pv-label"
    assert label.props["format"] == "default"


def test_plain_textdsp_class_regression_still_text_input():
    """A plain activeXTextDspClass (no :noedit) must keep mapping to pv-text-input."""
    text_input = _convert("phase2_textdsp.edl").root.children[2]
    assert text_input.type == "pv-text-input"
    assert text_input.props["pv"] == "${P}:SETPOINT"


# ---------------------------------------------------------------------------
# shellCmdClass
# ---------------------------------------------------------------------------


def test_shell_cmd_class_builds_actions_from_command_blocks():
    button = _convert("phase2_shell_cmd.edl").root.children[0]
    assert button.type == "regular-button"
    assert button.props["label"] == "Utilities"
    assert button.props["actions"] == [
        {"type": "shell_command", "command": "xterm -e top", "label": "Top"},
        {"type": "shell_command", "command": "alhDisable ${DEV}", "label": "Disable"},
    ]
    assert any("shell commands" in w for w in button.warnings)


# ---------------------------------------------------------------------------
# activeExitButtonClass
# ---------------------------------------------------------------------------


def test_exit_button_plain_closes_display_no_warnings():
    button = _convert("phase2_exit_button.edl").root.children[0]
    assert button.type == "regular-button"
    assert button.props["label"] == "EXIT"
    assert button.props["actions"] == [{"type": "close_display"}]
    assert button.warnings == []


def test_exit_button_exit_program_warns():
    button = _convert("phase2_exit_button.edl").root.children[1]
    assert button.props["actions"] == [{"type": "close_display"}]
    assert any("exitProgram" in w for w in button.warnings)


# ---------------------------------------------------------------------------
# activePngClass
# ---------------------------------------------------------------------------


def test_png_class_maps_to_image_view():
    image = _convert("phase2_png.edl").root.children[0]
    assert image.type == "image-view"
    assert image.props["src"] == "images/beamline"


# ---------------------------------------------------------------------------
# activeMeterClass
# ---------------------------------------------------------------------------


def test_meter_class_maps_to_pv_meter():
    meter = _convert("phase2_meter.edl").root.children[0]
    assert meter.type == "pv-meter"
    assert meter.props["pv"] == "${P}:CURRENT"
    assert meter.props["min"] == 0
    assert meter.props["max"] == 150
    assert meter.props["label"] == "Current"
    assert meter.warnings == []


# ---------------------------------------------------------------------------
# activeIndicatorClass
# ---------------------------------------------------------------------------


def test_indicator_class_maps_to_pv_progress_bar():
    indicator = _convert("phase2_indicator.edl").root.children[0]
    assert indicator.type == "pv-progress-bar"
    assert indicator.props["pv"] == "${P}:LVL"
    assert indicator.props["min"] == 0
    assert indicator.props["max"] == 10


# ---------------------------------------------------------------------------
# activeRadioButtonClass
# ---------------------------------------------------------------------------


def test_radio_button_class_maps_to_pv_radio_group():
    radio = _convert("phase2_radio.edl").root.children[0]
    assert radio.type == "pv-radio-group"
    assert radio.props["pv"] == "${P}:MODE"


# ---------------------------------------------------------------------------
# activeFreezeButtonClass / activeRampButtonClass / activeUpdownButtonClass
# ---------------------------------------------------------------------------


def test_freeze_button_has_no_pv_and_warns():
    """Corpus finding: 0/102 sampled freeze buttons carry a controlPv, so it maps
    to a plain regular-button rather than a PyDM PV widget."""
    freeze = _convert("phase2_misc_buttons.edl").root.children[0]
    assert freeze.type == "regular-button"
    assert freeze.props["label"] == "Freeze"
    assert "pv" not in freeze.props
    assert any("freeze-button" in w for w in freeze.warnings)


def test_ramp_button_maps_to_pv_button_and_warns():
    ramp = _convert("phase2_misc_buttons.edl").root.children[1]
    assert ramp.type == "pv-button"
    assert ramp.props["pv"] == "${P}:SP"
    assert ramp.props["label"] == "Ramp"
    assert any("ramp-button" in w for w in ramp.warnings)


def test_updown_button_maps_to_pv_button_and_warns():
    updown = _convert("phase2_misc_buttons.edl").root.children[2]
    assert updown.type == "pv-button"
    assert updown.props["pv"] == "${P}:SP"
    assert updown.props["label"] == "- | +"
    assert any("up/down increment" in w for w in updown.warnings)


# ---------------------------------------------------------------------------
# mmvClass / multiLineTextEntryClass
# ---------------------------------------------------------------------------


def test_mmv_class_maps_to_pv_slider_horizontal_and_drops_ctrl2():
    mmv = _convert("phase2_mmv_multiline.edl").root.children[0]
    assert mmv.type == "pv-slider"
    assert mmv.props["pv"] == "${P}:M1"
    assert mmv.props["orientation"] == "horizontal"
    assert any("ctrl2Pv" in w for w in mmv.warnings)


def test_multiline_text_entry_maps_to_pv_text_input_and_warns():
    multiline = _convert("phase2_mmv_multiline.edl").root.children[1]
    assert multiline.type == "pv-text-input"
    assert multiline.props["pv"] == "${P}:NOTES"
    assert any("multi-line text entry" in w for w in multiline.warnings)


# ---------------------------------------------------------------------------
# menuMuxClass (unmapped -> unknown-widget)
# ---------------------------------------------------------------------------


def test_menu_mux_class_stays_unknown_widget():
    unknown = _convert("phase2_unknown.edl").root.children[0]
    assert unknown.type == "unknown-widget"
    assert unknown.props["originalClass"] == "menuMuxClass"
    assert any("placeholder" in w for w in unknown.warnings)


# ---------------------------------------------------------------------------
# Schema validation across every fixture in this module
# ---------------------------------------------------------------------------

PHASE2_FIXTURES = [
    "phase2_textdsp.edl",
    "phase2_shell_cmd.edl",
    "phase2_exit_button.edl",
    "phase2_png.edl",
    "phase2_meter.edl",
    "phase2_indicator.edl",
    "phase2_radio.edl",
    "phase2_misc_buttons.edl",
    "phase2_mmv_multiline.edl",
    "phase2_unknown.edl",
]


def test_every_fixture_validates_against_schema():
    for name in PHASE2_FIXTURES:
        screen = _convert(name)
        assert validate_screen_json(to_wire_dict(screen)) == [], f"{name} failed schema validation"
