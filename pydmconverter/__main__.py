import argparse
import subprocess
import sys
import os
#import edm.converter
from edm.converter import convert

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

    convert(input_file, output_file)


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
