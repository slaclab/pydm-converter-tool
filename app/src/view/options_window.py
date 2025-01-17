"""
options_window.py

Attaches additional functionality to the options window view
"""

from os import path
from qtpy.QtWidgets import QWidget
from model.options_model import OptionsModel


class OptionsWindow(QWidget):
    def __init__(
        self,
        options_model: OptionsModel,
        parent=None,
    ):
        super().__init__()
        self.options_model = options_model
        self.setup_ui()

    def setup_ui(self):
        # self.setFixedWidth(600)
        # self.setFixedHeight(300)
        pass
