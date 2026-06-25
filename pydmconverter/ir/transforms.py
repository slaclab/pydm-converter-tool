"""Prop-transform library.

Beaver widget definitions name a transform per mapped Qt prop
(``"transform": "stripProtocol"``); the function lives here. The set below is
exactly what the vendored registry references — keep it in lock-step with Beaver
(canopy issue #18). A name in a definition with no implementation here is a
silent prop drop, so :func:`apply_transform` raises on an unknown name and the
``test_transforms_cover_registry`` test asserts full coverage.

A transform may return :data:`DROP` to signal "omit this prop" (e.g.
``boolToFromPV(False)`` defers to the explicit ``precision`` prop). The IR builder
skips any mapped prop whose transformed value is ``DROP``.
"""

from __future__ import annotations

import re
from typing import Any, Callable


class _Drop:
    """Sentinel meaning 'omit this prop from the node'."""

    _instance: "_Drop | None" = None

    def __new__(cls) -> "_Drop":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "DROP"

    def __bool__(self) -> bool:
        return False


DROP = _Drop()

_PROTOCOLS = ("ca://", "pva://")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def _enum_tail(value: str) -> str:
    """The token after the last ``::`` (``Qt::AlignRight`` -> ``AlignRight``)."""
    return value.split("::")[-1].strip()


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()


def strip_protocol(value: Any) -> Any:
    """Drop a ``ca://`` / ``pva://`` scheme from a channel; leave ``${MACRO}``,
    ``loc://``, ``calc://``, ``fox://`` untouched."""
    if not isinstance(value, str):
        return value
    for prefix in _PROTOCOLS:
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def bool_to_from_pv(value: Any) -> Any:
    """``True`` -> ``"fromPV"``; ``False`` -> :data:`DROP` (use explicit precision)."""
    return "fromPV" if _as_bool(value) else DROP


def qt_orientation(value: Any) -> Any:
    """Qt orientation -> ``"horizontal"`` / ``"vertical"``."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {1: "horizontal", 2: "vertical"}.get(int(value), value)
    text = str(value).lower()
    if "horizontal" in text:
        return "horizontal"
    if "vertical" in text:
        return "vertical"
    return value


def qt_alignment(value: Any) -> Any:
    """Qt alignment flags -> horizontal component ``"left"`` / ``"center"`` / ``"right"``."""
    text = str(value).lower()
    if "right" in text:
        return "right"
    if "hcenter" in text:
        return "center"
    if "left" in text:
        return "left"
    if "center" in text and "vcenter" not in text:  # Qt::AlignCenter (H+V), not VCenter alone
        return "center"
    return "left"


def qt_frame_shape(value: Any) -> Any:
    """Qt frame shape enum -> kebab-case (``StyledPanel`` -> ``styled-panel``)."""
    return _camel_to_kebab(_enum_tail(str(value)))


def qt_frame_shadow(value: Any) -> Any:
    """Qt frame shadow enum -> ``"plain"`` / ``"raised"`` / ``"sunken"``."""
    return _enum_tail(str(value)).lower()


def qt_scroll_policy(value: Any) -> Any:
    """Qt scrollbar policy enum -> ``"auto"`` / ``"always-on"`` / ``"always-off"``."""
    text = str(value).lower()
    if "asneeded" in text:
        return "auto"
    if "alwaysoff" in text:
        return "always-off"
    if "alwayson" in text:
        return "always-on"
    return "auto"


def first_of(value: Any) -> Any:
    """First element of a list (``filenames`` -> ``file``); scalars pass through."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else DROP
    return value


TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "stripProtocol": strip_protocol,
    "boolToFromPV": bool_to_from_pv,
    "qtOrientation": qt_orientation,
    "qtAlignment": qt_alignment,
    "qtFrameShape": qt_frame_shape,
    "qtFrameShadow": qt_frame_shadow,
    "qtScrollPolicy": qt_scroll_policy,
    "firstOf": first_of,
}


def known_transforms() -> list[str]:
    """Sorted names of every implemented transform."""
    return sorted(TRANSFORMS)


def apply_transform(name: str, value: Any) -> Any:
    """Apply the named transform. Raises ``KeyError`` on an unknown name."""
    try:
        fn = TRANSFORMS[name]
    except KeyError:
        raise KeyError(
            f"unknown prop transform {name!r}; implement it here and keep in lock-step with Beaver (canopy #18)"
        ) from None
    return fn(value)
