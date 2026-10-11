"""Point links at a menu mux display's menu screen.

A display with menu muxes converts to ``X.ui`` (its content) and ``X.py`` (the
MenuMuxScreen that shows the menus and passes their macros to ``X.ui``; see
:mod:`pydmconverter.edm.menumux`). A link to ``X.ui`` opens the content without
its menus, so the menu macros stay unset. :func:`link_menu_screens` points such a
link at ``X.py`` instead.
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from pydmconverter.edm.parser import _read_edm_text

logger = logging.getLogger(__name__)

_MENU_MUX_RE = re.compile(r"(?m)^object menuMuxClass\s*$")


def link_menu_screens(ui: ET.Element, search_dirs: Iterable[str], skip_widgets: set[str]) -> None:
    """Point related display and embedded display links at ``X.py`` where ``X.edl``
    has a menu mux.

    ``X.edl`` is looked up in ``search_dirs`` in order, as EDM looks up a display
    (the linking display's own directory, then its search paths and EDMDATAFILES). A
    name with a macro, or one that isn't found, keeps ``X.ui``. Nothing changes when
    the site drops menu muxes, since no ``X.py`` is written then.
    """
    if "menumuxclass" in skip_widgets:
        return
    dirs = list(search_dirs)
    has_menus: dict[str, bool] = {}
    for widget in ui.iter("widget"):
        cls = widget.get("class")
        if cls == "PyDMRelatedDisplayButton":
            strings = widget.findall("property[@name='filenames']/stringlist/string")
        elif cls == "PyDMEmbeddedDisplay":
            strings = widget.findall("property[@name='filename']/string")
        else:
            continue
        for string in strings:
            name = string.text or ""
            if not name.endswith(".ui") or "${" in name:
                continue
            stem = name[: -len(".ui")]
            if stem not in has_menus:
                has_menus[stem] = _has_menu_mux(stem + ".edl", dirs)
            if has_menus[stem]:
                string.text = stem + ".py"


def _has_menu_mux(edl_name: str, dirs: list[str]) -> bool:
    for directory in dirs:
        path = Path(directory) / edl_name
        if path.is_file():
            try:
                return bool(_MENU_MUX_RE.search(_read_edm_text(path)))
            except OSError:
                return False
    logger.debug(f"Link target {edl_name!r} not found; it keeps its .ui")
    return False
