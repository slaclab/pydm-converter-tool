"""Tests for the GUI options model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src"))

from model.options_model import OptionsModel  # noqa: E402


def test_override_existing_default():
    model = OptionsModel()
    assert model.override_existing is False


def test_override_existing_round_trip(tmp_path):
    options_file = str(tmp_path / "options.json")

    model = OptionsModel()
    model.output_folder = str(tmp_path)
    model.override_existing = True
    model.write_options_to_file(options_file)

    loaded = OptionsModel()
    loaded.get_options_from_file(options_file)
    assert loaded.override_existing is True


def test_override_existing_absent_from_file(tmp_path):
    options_file = str(tmp_path / "options.json")

    model = OptionsModel()
    model.output_folder = str(tmp_path)
    model.write_options_to_file(options_file)

    loaded = OptionsModel()
    loaded.get_options_from_file(options_file)
    assert loaded.override_existing is False
