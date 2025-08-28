from pathlib import Path
from pydmconverter.edm.parser import EDMObject


def generate_menumux_file(menumux_buttons: list[EDMObject], output_path: str | Path):
    output_path = Path(output_path)
    file_path = output_path.with_suffix(".py")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    add_menumux_indices(menumux_buttons)

    code = f"""from qtpy.QtWidgets import (
    QVBoxLayout, QComboBox, QWidget, QStackedLayout
)
from qtpy import QtCore
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
from pydmconverter.edm.parser import EDMObject
import json

class MenuMuxScreen(Display):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.muxes = []
        self.menumux_buttons = {menumux_buttons}
        self.macro_mappings = []  # Each entry: (macro_name, [value0, value1, ...])
        self.current_macros = dict()  # Dict of current macros to apply

        #self.labels = labels
        #self.loca_values = self.labels.copy()

        self.container = QWidget()
        self.stack_layout = QStackedLayout(self.container)

        self.embedded = PyDMEmbeddedDisplay()
        self.embedded.loadWhenShown = True
        self.embedded.filename = "{str(output_path)}"
        self.stack_layout.addWidget(self.embedded)

        for i, obj in enumerate(self.menumux_buttons):
            combo = QComboBox(self.container)
            combo.setFixedHeight(obj.height)
            combo.setFixedWidth(obj.width)
            combo.move(obj.x, obj.y)
            combo.raise_()

            # Get symbol and values for first index
            macro_names_list = obj.properties["symbolIndices"]
            values_list = obj.properties["valueIndices"]
            symbols = obj.properties["symbolTag"]

            combo.addItems(symbols)
            combo.currentIndexChanged.connect(
                lambda selected_index, combo_index=i: self.update_display(combo_index, selected_index)
            )

            self.muxes.append(combo)
            #self.macro_mappings.append((macro_name, values))
            inner_mapping = []
            for i in range(len(macro_names_list)):
                inner_mapping.append((macro_names_list[i][0], values_list[i]))
            self.macro_mappings.append(inner_mapping)

        layout = QVBoxLayout(self)
        layout.addWidget(self.container)

        # Initialize all macros
        for j in range(len(self.muxes)):
            self.update_display(j, 0)

    def update_display(self, combo_index, selected_index):
        for i in range(len(self.macro_mappings[combo_index])):
            macro_name, value_list = self.macro_mappings[combo_index][i]
            macro_value = value_list[selected_index]
            self.current_macros[macro_name] = macro_value

        added_macros = json.dumps(self.current_macros)
        self.embedded.set_macros_and_filename(self.embedded.filename, added_macros)
        self.embedded.open_file()
"""

    with open(file_path, "w") as f:
        f.write(code)

    print(f"Generated: {file_path}")


def add_menumux_indices(menumux_buttons):
    for obj in menumux_buttons:
        index = 0
        symbol_indices = []
        value_indices = []
        while f"symbol{index}" in obj.properties and f"value{index}" in obj.properties:
            symbol_indices.append(obj.properties[f"symbol{index}"])
            value_indices.append(obj.properties[f"value{index}"])
            index += 1
        obj.properties["symbolIndices"] = symbol_indices
        obj.properties["valueIndices"] = value_indices
