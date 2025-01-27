"""
options_window.py

The options window view
"""

import os
from qtpy.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QStackedWidget,
    QCheckBox,
    QGroupBox,
    QMessageBox,
    QDialogButtonBox,
)
from view.file_select_widget import FileSelectWidget
from model.options_model import OptionsModel


class OptionsWindow(QWidget):
    def __init__(
        self,
        options_model: OptionsModel,
        parent=None,
    ):
        super().__init__(parent)
        self.options_model = options_model
        self.setup_ui()

    def setup_ui(self):
        self.setFixedWidth(600)
        self.setFixedHeight(300)
        self.setWindowTitle("Options")

        self.options_group_list = QListWidget()
        self.options_group_list.setFixedWidth(200)
        self.options_group_list.addItem("General")
        self.options_group_list.addItem("EDM")

        output_folder_group = QGroupBox("Output Folder")
        output_folder_group_layout = QVBoxLayout()
        output_folder_group.setLayout(output_folder_group_layout)
        self.output_folder_select = FileSelectWidget(path=self.options_model.output_folder, select_dir=False)
        output_folder_group_layout.addWidget(self.output_folder_select)

        self.general_group_view = QWidget()
        general_group_layout = QVBoxLayout()
        self.general_group_view.setLayout(general_group_layout)
        general_group_label = QLabel("General")
        general_group_layout.addWidget(general_group_label)
        general_group_layout.addWidget(output_folder_group)
        general_group_layout.addStretch()

        edm_colors_group = QGroupBox("colors.list")
        edm_colors_group_layout = QVBoxLayout()
        edm_colors_group.setLayout(edm_colors_group_layout)
        self.edm_override_colors_checkbox = QCheckBox("Override default colors.list")
        if self.options_model.edm_override_def_colors:
            self.edm_override_colors_checkbox.setChecked()
        edm_custom_colors_view = QWidget()
        edm_custom_colors_layout = QHBoxLayout()
        edm_custom_colors_view.setLayout(edm_custom_colors_layout)
        self.edm_override_file_select = FileSelectWidget(
            path=self.options_model.edm_custom_colors_path,
            filter_str="Colors File (*.list)",
            dialog_text="Select Colors File",
        )
        edm_custom_colors_layout.addWidget(self.edm_override_file_select)
        edm_colors_group_layout.addWidget(self.edm_override_colors_checkbox)
        edm_colors_group_layout.addWidget(edm_custom_colors_view)

        self.edm_group_view = QWidget()
        edm_group_layout = QVBoxLayout()
        self.edm_group_view.setLayout(edm_group_layout)
        edm_group_label = QLabel("EDM")
        edm_group_layout.addWidget(edm_group_label)
        edm_group_layout.addWidget(edm_colors_group)
        edm_group_layout.addStretch()

        self.options_group_view = QStackedWidget()
        self.options_group_view.addWidget(self.general_group_view)
        self.options_group_view.addWidget(self.edm_group_view)

        self.options_group_list.currentRowChanged.connect(self.options_group_view.setCurrentIndex)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.on_ok_clicked)
        self.button_box.rejected.connect(self.close)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_clicked)

        self.main_layout = QVBoxLayout()

        self.content = QWidget()
        self.content_layout = QHBoxLayout()
        self.content_layout.addWidget(self.options_group_list)
        self.content_layout.addWidget(self.options_group_view)
        self.content.setLayout(self.content_layout)

        self.main_layout.addWidget(self.content)
        self.main_layout.addWidget(self.button_box)
        self.setLayout(self.main_layout)

    def on_ok_clicked(self):
        """Apply changes and close"""
        if self.on_apply_clicked():
            self.close()

    def on_apply_clicked(self) -> bool:
        """Validate options configuration and write to model

        Returns:
            bool : whether or not the configuration is valid (and has been applied)
        """
        # General options
        output_folder_path = self.output_folder_select.get_path()
        if os.path.exists(output_folder_path):
            self.options_model.output_folder = output_folder_path
        else:
            QMessageBox.critical(self, "Invalid Path", "The entered output folder path is not valid.")
            return False

        # EDM options
        colors_path = self.edm_override_file_select.get_path()
        if self.edm_override_colors_checkbox.isChecked():
            if os.path.exists(colors_path):
                self.options_model.edm_override_def_colors = True
                self.options_model.edm_custom_colors_path = colors_path
            else:
                QMessageBox.critical(
                    self,
                    "Invalid Path",
                    "The entered colors file path is not valid.\n"
                    + "Uncheck 'Override default colors.list' to use the default colors.list",
                )
                return False
        else:
            self.options_model.edm_override_def_colors = False
            self.options_model.edm_custom_colors_path = colors_path

        self.options_model.write_options_to_file()

        return True
