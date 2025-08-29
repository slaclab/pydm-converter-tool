"""
file_select_widget.py

Widget consisting of a line edit and a pushbutton that opens a file dialog.
Used to allow multimodal selection of a path (file or folder)
"""

from qtpy.QtWidgets import QHBoxLayout, QPushButton, QLineEdit, QWidget, QFileDialog


class FileSelectWidget(QWidget):
    def __init__(
        self,
        parent=None,
        path: str = None,
        filter_str: str = None,
        select_dir: bool = False,
        dialog_text: str = None,
    ) -> None:
        """Widget consisting of a line edit and a pushbutton that opens a file dialog.
        Used to allow multimodal selection of a path (file or folder)

        Args:
            parent (optional): Parent widget. Defaults to None.
            path (str, optional): Path string to prefill lineedit. Defaults to None.
            filter_str (str, optional): Filter string to use. Only matters when selecting files. Defaults to None.
            select_dir (bool, optional): Whether to select files or folders. Defaults to False.
            dialog_text (str, optional): Window text for file dialog. Defaults to None.
        """
        super().__init__(parent)
        self.path = path
        self.filter_str = filter_str
        self.select_dir = select_dir
        self.dialog_text = dialog_text
        self.setup_ui()

    def setup_ui(self) -> None:
        main_layout = QHBoxLayout()
        main_layout.setSpacing(0)
        self.path_lineedit = QLineEdit()
        if self.path is not None:
            self.path_lineedit.setText(self.path)
        self.file_dialog_button = QPushButton("...")
        self.file_dialog_button.clicked.connect(self.file_dialog_button_clicked)
        self.setFixedHeight(50)

        main_layout.addWidget(self.path_lineedit)
        main_layout.addWidget(self.file_dialog_button)
        self.setLayout(main_layout)

    def file_dialog_button_clicked(self) -> None:
        """Opens a file dialog with the desired configuration. If a file or folder is
        selected, set line edit text with result"""
        if self.select_dir:
            # Choose a directory
            dialog_text = self.dialog_text if self.dialog_text is not None else "Select Folder"
            folder_path = QFileDialog.getExistingDirectory(self, dialog_text)
            if folder_path:
                self.path_lineedit.setText(folder_path)
        else:
            # Choose a file, optionally applying a filter
            dialog = QFileDialog()
            dialog.setFileMode(QFileDialog.ExistingFile)
            if self.filter_str is not None:
                dialog.setNameFilter(self.filter_str)
            if dialog.exec_() == QFileDialog.Accepted:
                self.path_lineedit.setText(dialog.selectedFiles()[0])

    def get_path(self) -> None:
        """Returns selected path"""
        return self.path_lineedit.text()
