"""
main_window.py

Attaches additional functionality to the main window view
"""

import os
from time import sleep
from pydm import Display
from qtpy.QtCore import Slot
from qtpy.QtWidgets import (
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QMessageBox,
)

from model.app_model import AppModel
from model.options_model import OptionsModel
from view.options_window import OptionsWindow
from view.output_select_dialog import OutputSelectDialog


class MainWindow(Display):
    def __init__(self, parent=None, args=None, macros=None, ui_filename=None):
        super(MainWindow, self).__init__(parent, args, macros, "main_window.ui")
        self.app_model = AppModel()
        self.options_model = OptionsModel()
        self.options_model.get_options_from_file()
        sleep(1)  # Needed so the window resizes correctly

    @Slot()
    def on_add_item_button_clicked(self):
        # Require user to set output folder before adding items
        if self.options_model.output_folder is None:
            self.on_output_folder_button_clicked()
            if self.options_model.output_folder is None:
                QMessageBox.critical(
                    self,
                    "Set Output Folder First",
                    "Select an output folder before adding items.",
                )
                return

        dialog = QFileDialog()
        if dialog.exec_() == QDialog.Accepted:
            selected_path = dialog.selectedFiles()[0]
        else:
            return

        # Eventually will support adding folders; data processing is already set up to
        # add multiple rows at a time.
        data = [
            [
                selected_path,
                f"{self.options_model.output_folder}/{os.path.splitext(os.path.basename(selected_path))[0]}.ui",
                "Not converted",
            ]
        ]

        table_widget: QTableWidget = self.ui.table_widget
        for row, row_data in enumerate(data):
            table_widget.insertRow(table_widget.rowCount())
            for col, item in enumerate(row_data):
                table_widget.setItem(
                    table_widget.rowCount() - 1,
                    col,
                    QTableWidgetItem(item),
                )

    @Slot()
    def on_output_folder_button_clicked(self) -> None:
        """Opens file dialog to allow user to select output folder."""
        dialog = OutputSelectDialog(self.options_model, self)
        dialog.exec_()

    @Slot()
    def on_options_button_clicked(self):
        """Opens options window to allow user to configure options"""
        self.options_window = OptionsWindow(self.options_model, self)
        self.options_window.show()

    @Slot()
    def on_remove_item_button_clicked(self):
        """Removes the currently selected row from table"""
        table_widget: QTableWidget = self.ui.table_widget
        table_widget.removeRow(table_widget.currentRow())

    @Slot()
    def on_clear_list_button_clicked(self):
        """Removes all rows from table"""
        table_widget: QTableWidget = self.ui.table_widget
        table_widget.setRowCount(0)

    @Slot()
    def on_convert_button_clicked(self):
        print("convert")
        table_widget: QTableWidget = self.ui.table_widget
        for row in range(table_widget.rowCount()):
            print(row)
            # Converter goes here
