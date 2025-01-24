"""
options_model.py

Contains the data model for the options of the GUI
"""

import json
import logging
import os


class OptionsModel:
    def __init__(self):
        self.output_folder = None

    def get_options_from_file(self, filepath: str = "./app/src/options.json") -> None:
        """Retrieves GUI options from file, if it exists. Otherwise creates options file.

        Args:
            filepath (str, optional): Path to file. Defaults to "./app/src/options.json".
        """
        # Make the file if it doesn't exist
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as json_file:
                json.dump({}, json_file)
            logging.info(f"Created a new options file at: {filepath}")

        # Read the file
        with open(filepath, "r") as json_file:
            try:
                data = json.load(json_file)
                output_folder = data.get("output_folder", None)
                if output_folder is not None and os.path.exists(output_folder):
                    self.output_folder = output_folder
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON in file: {filepath}.")

    def write_options_to_file(self, filepath: str = "./app/src/options.json") -> None:
        """Writes GUI options to file.

        Args:
            filepath (str, optional): Path to file. Defaults to "./app/src/options.json".
        """

        data = {}
        if self.output_folder is not None:
            data["output_folder"] = self.output_folder

        with open(filepath, "w") as json_file:
            json.dump(data, json_file, indent=4)
