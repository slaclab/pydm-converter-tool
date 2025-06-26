import argparse
import subprocess
import sys
import os
#import edm.converter
from edm.converter import convert
import glob

def run_gui():
    """
    launch the PyDMConverter gui
    """
    subprocess.run(["pydm", "--hide-nav-bar", "--hide-menu-bar", "view/main_window.py"])


def run_cli(args):
    """
    run PyDMConverter through command line"
    """
    print("Running CLI with arguments:", args)
    input_file = args.input_file
    output_file = args.output_file
    output_file_type = args.output_type
    if os.path.isfile(input_file) and os.path.isfile(input_file):
        convert(input_file, output_file)
    elif os.path.isdir(input_file) and os.path.isdir(output_file):
        search_pattern = os.path.join(input_file, '*' + output_file_type)
        inputted_files = glob.glob(search_pattern)
    else:
        raise TypeError("Arguments must either be both files or both folders")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cli", action="store_true", help="If provided, run in command-line (CLI) mode instead of GUI."
    )
    parser.add_argument(
        "input_file", nargs='?', metavar="FILE"
    )
    parser.add_argument(
        "output_file", nargs='?', metavar="FILE"
    )
    parser.add_argument(
        "output_type", nargs='?', metavar="FILE TYPE"
    )
    args = parser.parse_args()
    

    if args.cli:
        if not args.input_file or not args.output_file: #techincally may be folders instead but this should still work for that
            parser.error("Must input two files")
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
