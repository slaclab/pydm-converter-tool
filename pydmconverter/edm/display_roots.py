"""Map absolute EDM display names under a site's display root to root-relative names.

A SLAC display may name another display by its absolute path on the console
(``/usr/local/lcls/tools/edm/display/misc/steeringpanels/steer_li21_xcor.edl``).
PyDM joins each search directory with a file name, so an absolute name only
ever resolves to itself: the converted display opens nothing unless it was
converted in place on that console. With the site's display roots, such a name
becomes the path below the root (``misc/steeringpanels/steer_li21_xcor.edl``),
which PyDM finds when the converted root is the working directory or is listed
in ``PYDM_DISPLAYS_PATH``. That is already what the tree's cross-directory
names need (``facet/rf_all_main.edl`` opens ``llrf/rf_li10_ref_main.edl``),
since EDM finds them through ``EDMDATAFILES``.

Only the display names EDM opens are rewritten: a related display's
``displayFileName`` entries, and an embedded window's ``file`` and
``displayFileName`` entries. Other absolute names and relative names are left
as they are.
"""

import posixpath
import re
from typing import Iterable

from pydmconverter.edm.parser import EDMGroup, EDMObject

# EDM class (lowercase) -> the properties that name a display it opens
# (related_display.cc, pip.cc).
DISPLAY_NAME_PROPERTIES = {
    "relateddisplayclass": ("displayFileName",),
    "activepipclass": ("file", "displayFileName"),
}


def _root_pattern(root: str) -> re.Pattern:
    """A display root as a prefix pattern: any run of slashes may separate (and
    end) its segments, and at least one slash must follow it."""
    segments = [re.escape(segment) for segment in root.split("/") if segment]
    return re.compile("/+" + "/+".join(segments) + "/+")


def root_relative(name: str, roots: Iterable[str]) -> str:
    """``name`` below the first of ``roots`` it starts with, as a relative path;
    otherwise ``name`` unchanged.

    The rest of the name is kept as written (macros, a missing ``.edl``, a
    ``;`` macro suffix). A name that is the root itself, or that climbs out of
    it with ``..``, is left unchanged.
    """
    for root in roots:
        match = _root_pattern(root).match(name)
        if match is None:
            continue
        rest = name[match.end() :]
        if rest and posixpath.normpath(rest).split("/", 1)[0] != "..":
            return rest
    return name


def map_display_roots(group: EDMGroup, roots: Iterable[str]) -> None:
    """Rewrite, in place, the display names under ``roots`` of every related
    display and embedded window in ``group`` (nested groups included) to
    root-relative names. A block keeps its EDM array indices."""
    roots = tuple(roots)
    if not roots:
        return
    for obj in group.objects:
        if isinstance(obj, EDMGroup):
            map_display_roots(obj, roots)
            continue
        if not isinstance(obj, EDMObject):
            continue
        for key in DISPLAY_NAME_PROPERTIES.get(obj.name.lower(), ()):
            value = obj.properties.get(key)
            if isinstance(value, str):
                obj.properties[key] = root_relative(value, roots)
            elif isinstance(value, list):
                # In place, so an IndexedBlock keeps its indices.
                value[:] = [root_relative(item, roots) if isinstance(item, str) else item for item in value]
