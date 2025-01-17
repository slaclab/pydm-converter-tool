"""
options_window.py

Attaches additional functionality to the options window view
"""

from qtpy.QtWidgets import QWidget
from model.options_model import OptionsModel
from qtpy.QtWidgets import QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QStackedWidget


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
        self.setFixedWidth(600)
        self.setFixedHeight(300)
        self.setWindowTitle("Options")

        self.options_group_list = QListWidget()
        self.options_group_list.setFixedWidth(200)
        self.options_group_list.addItem("General")
        self.options_group_list.addItem("EDM")

        general_group_view = QWidget()
        general_group_layout = QVBoxLayout()
        general_group_view.setLayout(general_group_layout)
        general_group_label = QLabel("General")
        general_group_layout.addWidget(general_group_label)
        general_group_layout.addStretch()

        edm_group_view = QWidget()
        edm_group_layout = QVBoxLayout()
        edm_group_view.setLayout(edm_group_layout)
        edm_group_label = QLabel("EDM")
        edm_group_layout.addWidget(edm_group_label)
        edm_group_layout.addStretch()

        self.options_group_view = QStackedWidget()
        self.options_group_view.addWidget(general_group_view)
        self.options_group_view.addWidget(edm_group_view)

        self.options_group_list.currentRowChanged.connect(self.options_group_view.setCurrentIndex)

        self.main_layout = QHBoxLayout()
        self.main_layout.addWidget(self.options_group_list)
        self.main_layout.addWidget(self.options_group_view)
        self.setLayout(self.main_layout)
