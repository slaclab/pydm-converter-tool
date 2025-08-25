"""
main_window.py

Attaches additional functionality to the main window view
"""

import fnmatch
import os
from time import sleep
from typing import List
from pydm import Display
from qtpy.QtCore import Slot, QCoreApplication
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
import pydmconverter.__main__
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainWindow(Display):
    def __init__(self, parent=None, args=None, macros=None, ui_filename=None):
        super(MainWindow, self).__init__(parent, args, macros, "main_window.ui")
        self.app_model = AppModel()
        self.options_model = OptionsModel()
        self.options_model.get_options_from_file()
        sleep(1)  # Needed so the window resizes correctly

    @Slot()
    def on_add_file_button_clicked(self) -> None:
        """Button action to allow user to add a file to be added to the list"""
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

        # Create file dialog, filtering on valid file types
        dialog = QFileDialog()
        filter_string = f"Files ({' '.join(self.app_model.valid_file_types)})"
        dialog.setNameFilter(filter_string)
        dialog.setFileMode(QFileDialog.ExistingFile)
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
    def on_add_folder_button_clicked(self) -> None:
        """Button action to allow user to add a folder to be added to the list"""

        def get_files_recursively(folder: str, file_types: List[str]) -> List[str]:
            """Traverses through folder, returning files matching list of desired types"""
            matched_files = []
            for root, dirs, files in os.walk(folder):
                for file_type in file_types:
                    for file in fnmatch.filter(files, file_type):
                        matched_files.append(os.path.join(root, file))
            return matched_files

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

        # Create file dialog, filtering on folders
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        selected_folder = dialog.getExistingDirectory(None, "Select Folder")
        if not selected_folder:
            return

        files = get_files_recursively(selected_folder, self.app_model.valid_file_types)
        data = [
            [
                file,
                f"{self.options_model.output_folder}/{os.path.basename(os.path.normpath(selected_folder))}/{os.path.splitext(os.path.relpath(file, selected_folder))[0]}.ui",
                "Not converted",
            ]
            for file in files
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
        table_widget: QTableWidget = self.ui.table_widget
        output_folder = self.options_model.output_folder
        for row in range(table_widget.rowCount()):
            input_file = table_widget.item(row, 0).text()
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            new_output_path = os.path.join(output_folder, f"{base_name}.ui")
            table_widget.setItem(row, 1, QTableWidgetItem(new_output_path))

    @Slot()
    def on_options_button_clicked(self) -> None:
        """Opens options window to allow user to configure options"""
        self.options_window = OptionsWindow(self.options_model)
        self.options_window.show()

    @Slot()
    def on_remove_item_button_clicked(self) -> None:
        """Removes the currently selected row from table"""
        table_widget: QTableWidget = self.ui.table_widget
        table_widget.removeRow(table_widget.currentRow())

    @Slot()
    def on_clear_list_button_clicked(self) -> None:
        """Removes all rows from table"""
        table_widget: QTableWidget = self.ui.table_widget
        table_widget.setRowCount(0)

    @Slot()
    def on_clear_converted_button_clicked(self) -> None:
        """Removes all converted rows from table (and leaves unconverted or failed rows)"""
        table_widget: QTableWidget = self.ui.table_widget
        for i in range(
            table_widget.rowCount() - 1, -1, -1
        ):  # iterate backwards to make deletion indexing issues easier
            conversion_status = table_widget.item(i, 2).text()
            if conversion_status == "Converted":
                table_widget.removeRow(i)

    @Slot()
    def on_convert_button_clicked(self) -> None:
        table_widget: QTableWidget = self.ui.table_widget
        for row in range(table_widget.rowCount()):
            input_file = table_widget.item(row, 0).text()
            output_file = table_widget.item(row, 1).text()
            file_type = os.path.splitext(input_file)[1].lower()
            try:
                pydmconverter.__main__.run(input_file, output_file, file_type, override=True)
                logger.debug(f"converted {input_file} to {output_file}")
                table_widget.setItem(row, 2, QTableWidgetItem("Converted"))
            except Exception as msg:
                logger.debug(msg)
                table_widget.setItem(row, 2, QTableWidgetItem("Failed"))
            QCoreApplication.processEvents()

            """parser = self.app_model.parsers[file_type](input_file)
            if parser.ui:
                # TODO: instead of printing, pass the object to the xml writer
                # This would also be the place to report checks on converter success
                pprint(parser.ui, indent=2)
                table_widget.setItem(row, 2, QTableWidgetItem("Converted"))
            """
