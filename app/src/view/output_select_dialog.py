"""
output_select_dialog.py

Modal prompting user to select output folder.
"""

import os
import sys
from model.options_model import OptionsModel
from qtpy.QtWidgets import (
    QDialogButtonBox,
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QWidget,
    QFileDialog,
    QMessageBox,
)
from qtpy.QtCore import Qt


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

        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setSpacing(0)
        self.path_lineedit = QLineEdit(self)
        if self.options_model.output_folder is not None:
            self.path_lineedit.setText(self.options_model.output_folder)
        row_layout.addWidget(self.path_lineedit)
        self.file_dialog_button = QPushButton("...", self)
        self.file_dialog_button.clicked.connect(self.file_dialog_button_clicked)
        row_layout.addWidget(self.file_dialog_button)
        row_widget.setLayout(row_layout)
        self.main_layout.addWidget(row_widget)

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

    def file_dialog_button_clicked(self):
        """Opens file dialog for path selection, sets lineedit to selected path"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.path_lineedit.setText(folder_path)

    def validate_and_accept(self):
        """Checks if the supplied path is valid, accepting if it is"""
        path = self.path_lineedit.text()
        if os.path.exists(path):
            self.options_model.output_folder = path
            if self.save_checkbox.isChecked():
                self.options_model.write_options_to_file()
            self.accept()
        else:
            QMessageBox.critical(self, "Invalid Path", "The entered path is not valid.")

    def quit(self):
        sys.exit()
