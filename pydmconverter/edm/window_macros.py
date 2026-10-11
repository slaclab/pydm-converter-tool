"""EDM's per-window ``$(!W)`` macro in converted PyDM screens.

EDM expands ``$(!W)`` to the address of the window showing the screen
(``activeWindowClass::genericCreate``), so local variables named
``LOC\\$(!W)name``, which are global to the EDM process, stay apart between
windows. An embedded window (activePipClass) is a window of its own: it gets
its parent's macros but a new ``$(!W)``. A menu mux change keeps the window,
and so its ``$(!W)``.

PyDM's loc:// variables are global to the process too, and PyDM has no
per-display macro. A converted screen therefore names ``$(!W)`` as the macro
``${EDM_W}``, which PyDM substitutes when the screen loads, so every widget of
one loaded copy names the same variable. Each embedded display passes its own
``EDM_W=${EDM_W_ROOT}<screen>_<n>``, unique to where it is embedded.
``EDM_W_ROOT`` names the top-level copy and only Python sets it (the generated
menu mux screen, or code loading a screen with macros), never a .ui: PyDM
repeats substitution until the text stops changing, so a value naming its own
macro (``EDM_W=${EDM_W}_1``) would grow for 100 rounds when loaded without it.

A screen opened without these macros keeps ``${EDM_W}`` literally, which PyDM
accepts in a loc:// name, so its top-level variables are shared with another
copy opened the same way in the same process. PyDM opens each new window in a
new process.

The Screen IR (``ir_adapter._name_windows``) names ``$(!W)`` and numbers its
embedded displays the same way. The Canopy runtime keeps one set of local
variables per page and substitutes macros in loc:// channels, so there too
each embedded copy names its own.

Unlike a .ui, the IR also passes each embedded display's id on as
``EDM_W_ROOT``: Canopy substitutes an embedded display's macros once, against
its parent's, so the windows an embedded copy embeds build their ids on that
copy's, and two copies of a screen give them different ones.
"""

import json
import xml.etree.ElementTree as ET
import zlib

from pydmconverter.widgets_helpers import Str

# EDMFileParser.modify_text replaces $(!W) with this marker.
WINDOW_MARKER = "__UNIQUE__"
WINDOW_MACRO = "EDM_W"
ROOT_MACRO = "EDM_W_ROOT"


def window_macro(text: str) -> str:
    """Name the parser's $(!W) marker as the PyDM macro ${EDM_W}."""
    return text.replace(WINDOW_MARKER, "${" + WINDOW_MACRO + "}")


def embedded_window_id(screen_name: str, index: int) -> str:
    """The EDM_W the index-th embedded display of screen_name passes:
    ``${EDM_W_ROOT}<crc32 of screen_name>_<index>``. The same on every
    conversion, and different for every embedding site, also between screens
    embedded in one another. The .ui and Screen IR targets both use it."""
    return "${" + ROOT_MACRO + "}" + f"{zlib.crc32(screen_name.encode()):08x}_{index}"


def resolve_window_macros(ui: ET.Element, screen_name: str) -> None:
    """Give each embedded display of a converted .ui its own EDM_W
    (:func:`embedded_window_id`, numbered in document order), and name every $(!W)
    marker (channels, rules, macros) as ${EDM_W}.
    """
    displays = [widget for widget in ui.iter("widget") if widget.get("class") == "PyDMEmbeddedDisplay"]
    for index, display in enumerate(displays):
        window_id = embedded_window_id(screen_name, index)
        string = display.find("property[@name='macros']/string")
        if string is None:
            display.append(Str("macros", json.dumps({WINDOW_MACRO: window_id})).to_xml())
            continue
        try:
            macros = json.loads(string.text or "{}")
        except ValueError:
            continue
        # Macros PyDM cannot read as a dict already fail to load; leave them be.
        if isinstance(macros, dict):
            macros[WINDOW_MACRO] = window_id
            string.text = json.dumps(macros)

    for element in ui.iter():
        if element.text and WINDOW_MARKER in element.text:
            element.text = window_macro(element.text)
