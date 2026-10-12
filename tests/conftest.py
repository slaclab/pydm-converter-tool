import pytest

from pydmconverter.edm.display_roots import DISPLAY_ROOTS_ENV


@pytest.fixture(autouse=True)
def no_display_roots_from_the_shell(monkeypatch):
    """Display roots set in the shell running the tests would rewrite absolute
    display names in every conversion."""
    monkeypatch.delenv(DISPLAY_ROOTS_ENV, raising=False)
