"""
app_model.py

Contains the data model for the GUI
"""

from pydmconverter.edm.parser import EDMFileParser


class AppModel:
    def __init__(self):
        # Filetypes that can be converted
        self.valid_file_types = ["*.edl"]

        # Filetype to parser mapping
        self.parsers = {
            ".edl": EDMFileParser,
        }
