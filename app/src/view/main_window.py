"""
main_window.py

Attaches additional functionality to the main window view
"""

from os import path
from pydm import Display
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QFileDialog, QTableWidget, QTableWidgetItem

from model.app_model import AppModel
from model.options_model import OptionsModel
from view.options_window import OptionsWindow


class MainWindow(Display):
    def __init__(self, parent=None, args=None, macros=None, ui_filename=None):
        super(MainWindow, self).__init__(parent, args, macros, ui_filename)
        self.app_model = AppModel()
        self.options_model = OptionsModel()
        self.setup_ui()

    def ui_filename(self):
        return "main_window.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def setup_ui(self):
        # Set Window Size
        self.setFixedWidth(750)
        self.setFixedHeight(600)

    @Slot()
    def on_add_item_button_clicked(self):
        if self.options_model.output_folder is None:
            print("no output folder set")

        table_widget: QTableWidget = self.ui.table_widget
        table_widget.insertRow(table_widget.rowCount())
        data = ["A", "B", "C"]
        for col, item in enumerate(data):
            table_widget.setItem(
                table_widget.rowCount() - 1,
                col,
                QTableWidgetItem(f"{item}{table_widget.rowCount()}"),
            )

    @Slot()
    def on_output_folder_button_clicked(self) -> None:
        """Opens file dialog to allow user to select output folder."""
        dir_dialog = QFileDialog(self)
        dir_dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dir_dialog.setFileMode(QFileDialog.Directory)
        if self.options_model.output_folder is not None:
            dir_dialog.setDirectory(self.options_model.output_folder)
        selected_dir = dir_dialog.getExistingDirectory(self, "Select Output Folder")
        if selected_dir:
            self.options_model.output_folder = selected_dir

    @Slot()
    def on_options_button_clicked(self):
        """Opens options window to allow user to configure options"""
        options_window = OptionsWindow(self.options_model)
        options_window.show()

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
