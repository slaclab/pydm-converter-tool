from typing import Optional, Set


def get_skip_widgets(site: Optional[str]) -> Set[str]:
    """Return set of lowercase EDM widget class names to skip for the given site."""
    if site is None:
        return set()
    if site == "slac":
        from pydmconverter.sites.slac import SKIP_WIDGETS

        return SKIP_WIDGETS
    raise ValueError(f"Unknown site: {site}")
