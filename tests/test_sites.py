import pytest
from pydmconverter.sites import get_skip_widgets


def test_get_skip_widgets_none():
    assert get_skip_widgets(None) == set()


def test_get_skip_widgets_slac():
    result = get_skip_widgets("slac")
    assert "activeexitbuttonclass" in result


def test_get_skip_widgets_unknown():
    with pytest.raises(ValueError, match="Unknown site"):
        get_skip_widgets("unknown")
