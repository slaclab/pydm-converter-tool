"""Map absolute EDM display names under a display root to root-relative names.

A display may name another display by its absolute path on the EDM console
(``/opt/site/edm/display/misc/panel.edl``). PyDM joins each search directory with
a file name, so an absolute name only ever resolves to itself: the converted
display opens nothing unless it was converted in place on that console. Under a
display root, such a name becomes the path below the root (``misc/panel.edl``),
which PyDM finds when the converted root is the working directory or is listed
in ``PYDM_DISPLAYS_PATH``. That is already what a display tree's cross-directory
names need, since EDM finds them through ``EDMDATAFILES``.

The roots come from the caller (``display_roots``, the ``--display-root`` option)
or else from the ``PYDMCONVERTER_DISPLAY_ROOTS`` environment variable; with
neither, no name is mapped. They are the console's directories, not the
converting machine's, so they cannot be taken from its ``EDMDATAFILES``.

Only the display names EDM opens are rewritten: a related display's
``displayFileName`` entries, and an embedded window's ``file`` and
``displayFileName`` entries. Other absolute names and relative names are left
as they are.
"""

import os
import posixpath
import re
from typing import Iterable

from pydmconverter.edm.parser import EDMGroup, EDMObject
from pydmconverter.edm.parser_helpers import SearchPaths, normalize_search_paths, split_edm_path_list

# Directories separated as in EDMDATAFILES (/opt/a/display:/opt/b/display).
DISPLAY_ROOTS_ENV = "PYDMCONVERTER_DISPLAY_ROOTS"

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


def resolve_display_roots(display_roots: SearchPaths = None) -> tuple[str, ...]:
    """The display roots to map: ``display_roots`` when given (a single directory
    or a sequence; an empty sequence maps nothing), otherwise the
    ``PYDMCONVERTER_DISPLAY_ROOTS`` environment variable. Empty entries are
    dropped. A root that is not an absolute directory below ``/`` raises
    ValueError: it could never match a name, so it is a mistake."""
    if display_roots is None:
        source = DISPLAY_ROOTS_ENV
        roots = split_edm_path_list(os.environ.get(DISPLAY_ROOTS_ENV, ""))
    else:
        source = "display_roots (--display-root)"
        roots = normalize_search_paths(display_roots)
    for root in roots:
        if not root.startswith("/") or not root.strip("/"):
            raise ValueError(f"{source}: a display root must be an absolute directory other than /, not {root!r}")
    return tuple(roots)


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
