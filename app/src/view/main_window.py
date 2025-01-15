"""
main_window.py

Attaches additional functionality to the main window view
"""

from os import path
from pydm import Display


class MainWindow(Display):
    def __init__(self, parent=None, args=None, macros=None, ui_filename=None):
        super(MainWindow, self).__init__(parent, args, macros, ui_filename)
        self.setFixedWidth(750)
        self.setFixedHeight(600)

    def ui_filename(self):
        return "main_window.ui"

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)), self.ui_filename())
