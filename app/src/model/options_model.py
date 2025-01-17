"""
options_model.py

Contains the data model for the options of the GUI
"""

import json
import os


class OptionsModel:
    def __init__(self):
        self.output_folder = None

    def get_options_from_file(self, filepath="./options.json"):
        # Make the file if it doesn't exist
        if not os.path.exists(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as json_file:
                json.dump({}, json_file)
            print(f"Created a new options file at: {filepath}")

        # Read the file
        with open(filepath, "r") as json_file:
            try:
                data = json.load(json_file)
                output_folder = data.get("output_folder", None)
                if output_folder is not None and os.path.exists(output_folder):
                    self.output_folder = output_folder
            except json.JSONDecodeError:
                print(f"Invalid JSON in file: {filepath}.")

    def write_options_to_file(self, filepath="./options.json"):
        data = {}
        if self.output_folder is not None:
            data["output_folder"] = self.output_folder

        with open(filepath, "w") as json_file:
            json.dump(data, json_file, indent=4)
