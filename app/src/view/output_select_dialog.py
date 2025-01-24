"""
output_select_dialog.py

Modal prompting user to select output folder.
"""

import os
import sys
from qtpy.QtWidgets import (
    QDialogButtonBox,
    QDialog,
    QVBoxLayout,
    QLabel,
    QCheckBox,
    QMessageBox,
)
from qtpy.QtCore import Qt
from model.options_model import OptionsModel
from view.file_select_widget import FileSelectWidget


class OutputSelectDialog(QDialog):
    def __init__(
        self,
        options_model: OptionsModel,
        parent=None,
        close_app_on_cancel=False,
    ):
        super().__init__(parent)
        self.options_model = options_model
        self.close_app_on_cancel = close_app_on_cancel
        self.setup_ui()

    def setup_ui(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(400)
        self.setFixedHeight(150)
        self.setWindowTitle("Select Output Folder")

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(-1, -1, -1, 5)
        self.main_layout.setSpacing(5)

        self.main_layout.addWidget(QLabel("Select Output Folder"))

        self.folder_select = FileSelectWidget(path=self.options_model.output_folder, select_dir=True)
        self.main_layout.addWidget(self.folder_select)

        self.save_checkbox = QCheckBox("Remember my preference", self)
        self.main_layout.addWidget(self.save_checkbox)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.setLayoutDirection(Qt.LeftToRight)
        self.button_box.accepted.connect(self.validate_and_accept)
        if self.close_app_on_cancel:
            self.button_box.rejected.connect(self.quit)
        else:
            self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        self.setLayout(self.main_layout)

    def validate_and_accept(self):
        """Checks if the supplied path is valid, accepting if it is"""
        path = self.folder_select.get_path()
        if os.path.exists(path):
            self.options_model.output_folder = path
            if self.save_checkbox.isChecked():
                self.options_model.write_options_to_file()
            self.accept()
        else:
            QMessageBox.critical(self, "Invalid Path", "The entered path is not valid.")

    def quit(self):
        sys.exit()
