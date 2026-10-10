from typing import Optional, Set, Tuple


def get_skip_widgets(site: Optional[str]) -> Set[str]:
    """Return set of lowercase EDM widget class names to skip for the given site."""
    if site is None:
        return set()
    if site == "slac":
        from pydmconverter.sites.slac import SKIP_WIDGETS

        return SKIP_WIDGETS
    raise ValueError(f"Unknown site: {site}")


def get_display_roots(site: Optional[str]) -> Tuple[str, ...]:
    """Return the absolute display directories whose display names the given
    site maps to root-relative names (see pydmconverter.edm.display_roots)."""
    if site is None:
        return ()
    if site == "slac":
        from pydmconverter.sites.slac import DISPLAY_ROOTS

        return DISPLAY_ROOTS
    raise ValueError(f"Unknown site: {site}")
