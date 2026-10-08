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


def resolve_window_macros(ui: ET.Element, screen_name: str) -> None:
    """Give each embedded display of a converted .ui its own EDM_W, and name
    every $(!W) marker (channels, rules, macros) as ${EDM_W}.

    The n-th embedded display in document order gets
    ``${EDM_W_ROOT}<crc32 of screen_name>_<n>``: the same on every conversion,
    and different for every embedding site, also between screens embedded in
    one another.
    """
    site = format(zlib.crc32(screen_name.encode()), "08x")
    displays = [widget for widget in ui.iter("widget") if widget.get("class") == "PyDMEmbeddedDisplay"]
    for index, display in enumerate(displays):
        window_id = "${" + ROOT_MACRO + "}" + f"{site}_{index}"
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
