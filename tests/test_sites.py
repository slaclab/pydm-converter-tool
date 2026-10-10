import pytest
from pydmconverter.sites import get_display_roots, get_skip_widgets


def test_get_skip_widgets_none():
    assert get_skip_widgets(None) == set()


def test_get_skip_widgets_slac():
    result = get_skip_widgets("slac")
    assert "activeexitbuttonclass" in result


def test_get_skip_widgets_unknown():
    with pytest.raises(ValueError, match="Unknown site"):
        get_skip_widgets("unknown")


def test_get_display_roots_none():
    assert get_display_roots(None) == ()


def test_get_display_roots_slac():
    assert get_display_roots("slac") == ("/usr/local/lcls/tools/edm/display", "/usr/local/facet/tools/edm/display")


def test_get_display_roots_unknown():
    with pytest.raises(ValueError, match="Unknown site"):
        get_display_roots("unknown")
