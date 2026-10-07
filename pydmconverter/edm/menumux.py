import logging
import pprint
import re
import textwrap
from pathlib import Path
from pydmconverter.edm.parser import EDMObject

logger = logging.getLogger(__name__)


def generate_menumux_file(menumux_buttons: list[EDMObject], output_path: str | Path):
    output_path = Path(output_path)
    file_path = output_path.with_suffix(".py")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # The screen gets its menus as plain literals, so it runs with only qtpy and
    # pydm installed: position, item labels, (macro, value per item) pairs and
    # the EDM initialState.
    menus = []
    for obj in menumux_buttons:
        count = menu_item_count(obj)
        macros = menu_macros(obj, count)
        menus.append(
            {
                "x": obj.x,
                "y": obj.y,
                "width": obj.width,
                "height": obj.height,
                "items": menu_items(obj, count, macros),
                "macros": macros,
                "initialState": str(obj.properties.get("initialState", "0")),
            }
        )
    menus_literal = textwrap.indent(pprint.pformat(menus, width=100, sort_dicts=False), " " * 8).lstrip()

    # The .ui sits next to the generated .py, and PyDM resolves an embedded
    # display's relative filename against the .py's directory.
    code = f"""from qtpy.QtWidgets import (
    QVBoxLayout, QComboBox, QWidget, QStackedLayout
)
from qtpy.QtCore import QCoreApplication
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from pydm.widgets.rules import unregister_widget_rules
import json
import re

class MenuMuxScreen(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)

        self.muxes = []
        self.menus = {menus_literal}
        self.macro_mappings = []  # Each entry: [(macro_name, [value0, value1, ...]), ...]
        self.current_macros = dict()  # Dict of current macros to apply

        self.container = QWidget()
        self.stack_layout = QStackedLayout(self.container)

        self.embedded = PyDMEmbeddedDisplay()
        self.embedded.loadWhenShown = True
        self.embedded.filename = {output_path.name!r}
        self.stack_layout.addWidget(self.embedded)

        for i, menu in enumerate(self.menus):
            combo = QComboBox(self.container)
            combo.setFixedHeight(menu["height"])
            combo.setFixedWidth(menu["width"])
            combo.move(menu["x"], menu["y"])
            combo.raise_()

            combo.addItems(menu["items"])
            combo.setCurrentIndex(self.initial_index(menu["initialState"], combo.count()))
            combo.currentIndexChanged.connect(
                lambda selected_index, combo_index=i: self.update_display(combo_index, selected_index)
            )

            self.muxes.append(combo)
            self.macro_mappings.append(menu["macros"])

        layout = QVBoxLayout(self)
        layout.addWidget(self.container)

        # Start every menu at its initial item, then load once
        for j, combo in enumerate(self.muxes):
            self.set_menu_macros(j, combo.currentIndex())
        self.load()

    def initial_index(self, state, count):
        # EDM's initialState: the index of the first item shown. It may use
        # the screen's macros ("${{initDev}}") and is read like strtol, so
        # "3+1" is 3; anything unusable starts at 0.
        macros = self.macros()
        text = re.sub(
            "[$][{{(]([A-Za-z0-9_]+)[}})]",
            lambda m: str(macros.get(m.group(1), m.group(0))),
            state,
        )
        match = re.match("[ ]*(-?[0-9]+)", text)
        index = int(match.group(1)) if match else 0
        return index if 0 <= index < count else 0

    def set_menu_macros(self, combo_index, selected_index):
        for macro_name, value_list in self.macro_mappings[combo_index]:
            self.current_macros[macro_name] = value_list[selected_index]

    def update_display(self, combo_index, selected_index):
        self.set_menu_macros(combo_index, selected_index)
        self.load()

    def load(self):
        new_macros = json.dumps(self.current_macros)
        old = self.embedded.embedded_widget
        if old is not None and new_macros != self.embedded.macros:
            # PyDM keeps a loc:// variable, with its first init, while anything
            # listens to it, and connects the new display before releasing the
            # old one (slaclab/pydm#1354). Release the old display's channels
            # and rules first so variables initialised from these macros are
            # rebuilt with the new values.
            self.embedded.disconnect()
            unregister_widget_rules(old)
            QCoreApplication.sendPostedEvents()
        self.embedded.set_macros_and_filename(self.embedded.filename, new_macros)
"""

    with open(file_path, "w") as f:
        f.write(code)

    logger.info(f"Generated: {file_path}")


def menu_item_count(obj: EDMObject) -> int:
    """A menu mux's number of items: numItems, or failing that the length of
    symbolTag, or of its longest value array."""
    num_items = obj.properties.get("numItems")
    if isinstance(num_items, str) and num_items.strip().isdecimal():
        return int(num_items)
    tags = edm_array(obj.properties.get("symbolTag"))
    if tags:
        return len(tags)
    return max(
        (len(edm_array(value)) for key, value in obj.properties.items() if re.fullmatch("value[0-9]+", key)),
        default=0,
    )


def menu_macros(obj: EDMObject, count: int) -> list[tuple[str, list[str]]]:
    """A menu mux's (macro, value per item) pairs, one per symbol{i}. EDM
    leaves trailing empty strings out of value{i}, and leaves value{i} out
    altogether when all of its values are empty, so pad each to count."""
    if count == 0:
        # An empty menu has no item selected (index -1) to take values from.
        return []
    symbols = sorted(
        (key for key in obj.properties if re.fullmatch("symbol[0-9]+", key)),
        key=lambda key: int(key.removeprefix("symbol")),
    )
    macros = []
    for key in symbols:
        names = edm_array(obj.properties[key])
        if names and names[0]:
            values = edm_array(obj.properties.get("value" + key.removeprefix("symbol")))
            macros.append((names[0], padded(values, count)))
    return macros


def menu_items(obj: EDMObject, count: int, macros: list[tuple[str, list[str]]]) -> list[str]:
    """A menu mux's item labels. Without symbolTag EDM shows blank items, so
    label each item by its first macro's value instead."""
    tags = edm_array(obj.properties.get("symbolTag"))
    if tags:
        return padded(tags, count)
    return list(macros[0][1]) if macros else [""] * count


def edm_array(value) -> list[str]:
    """An EDM array property as a list: the parser gives a list for a
    { ... } block and a str for a single value."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else []


def padded(values: list[str], count: int) -> list[str]:
    """values cut to count entries, or padded to it with the trailing empty
    strings EDM leaves out."""
    return values[:count] + [""] * (count - len(values))
