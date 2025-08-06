from pathlib import Path


def generate_menumux_file(labels: list[str], output_path: str | Path):
    file_path = Path(output_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    code = f"""from qtpy.QtWidgets import (
    QVBoxLayout, QComboBox, QWidget, QStackedLayout
)
from qtpy import QtCore
from pydm import Display
from pydm.widgets import PyDMEmbeddedDisplay
import json

class MenuMuxLOCA(Display):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.labels = {labels!r}
        self.loca_values = self.labels.copy()

        self.container = QWidget()
        self.stack_layout = QStackedLayout(self.container)

        self.embedded = PyDMEmbeddedDisplay()
        self.embedded.loadWhenShown = True
        self.embedded.filename = "menumux_loca.ui"
        self.stack_layout.addWidget(self.embedded)

        self.combo = QComboBox(self.container)
        self.combo.addItems(self.labels)
        self.combo.currentIndexChanged.connect(self.update_display)
        self.combo.setFixedWidth(100)
        self.combo.move(20, 100)
        self.combo.raise_()

        layout = QVBoxLayout(self)
        layout.addWidget(self.container)

        self.update_display(0)

    def update_display(self, index):
        macro_dict = {{"LOCA": self.loca_values[index]}}
        self.embedded.macros = json.dumps(macro_dict)
        self.embedded.filename = self.embedded.filename
"""

    with open(file_path, "w") as f:
        f.write(code)

    print(f"Generated: {file_path}")
