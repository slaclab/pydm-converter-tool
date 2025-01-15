"""
main_window.py

Attaches additional functionality to the main window view
"""

from os import path
from pydm import Display
from qtpy.QtCore import Slot

from model.app_model import AppModel
from model.options_model import OptionsModel


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
        # self.ui.add_item_button.clicked.connect(self.on_add_item_button_clicked)

    @Slot()
    def on_add_item_button_clicked(self):
        print("Add")

    @Slot()
    def on_output_folder_button_clicked(self):
        print("output")

    @Slot()
    def on_options_button_clicked(self):
        print("options")

    @Slot()
    def on_remove_item_button_clicked(self):
        print("remove")

    @Slot()
    def on_clear_list_button_clicked(self):
        print("clear")

    @Slot()
    def on_convert_button_clicked(self):
        print("convert")
