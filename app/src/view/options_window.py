"""
options_window.py

Attaches additional functionality to the options window view
"""

from os import path
from pydm import Display
from model.options_model import OptionsModel


class OptionsWindow(Display):
    def __init__(
        self,
        options_model: OptionsModel,
        parent=None,
        args=None,
        macros=None,
        ui_filename=None,
    ):
        super(OptionsWindow, self).__init__(parent, args, macros, ui_filename)
        self.options_model = options_model
        self.setup_ui()

    def ui_filename(self):
        return "options_window.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())

    def setup_ui(self):
        self.setFixedWidth(600)
        self.setFixedHeight(300)
