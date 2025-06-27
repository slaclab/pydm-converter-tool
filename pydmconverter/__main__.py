#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pydmconverter.edm.converter import convert
from pathlib import Path


def run_gui() -> None:
    """
    launch the PyDMConverter gui
    """
    subprocess.run(["pydm", "--hide-nav-bar", "--hide-menu-bar", "view/main_window.py"])


def run_cli(args: argparse.Namespace) -> None:
    """
    run PyDMConverter through command line

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    print("Running CLI with arguments:", args)
    input_path: Path = Path(args.input_file)
    output_path: Path = Path(args.output_file)
    input_file_type: str = args.output_type

    if input_path.is_file():
        if output_path.suffix != ".ui":
            output_path = output_path.with_suffix(".ui")
        convert(str(input_path), str(output_path))
    else:
        if input_file_type[0] != ".":  # prepending . so it will not pick up other file types with same suffix
            input_file_type = "." + input_file_type
        output_path.mkdir(parents=True, exist_ok=True)
        convert_files_in_folder(input_path, output_path, input_file_type)


def convert_files_in_folder(input_path: Path, output_path: Path, input_file_type: str) -> int:
    """Recursively runs convert on files in directory and subdirectories

    Parameters
    ----------
    input_path : Path
        The parent directory of files to convert
    output_path: Path
        The directory where converted files will be stored
    input_file_type: str
        The type of file to convert (often will be .edl)

    Returns
    -------
    int
        Returns the amount of files found in this input directory
    """
    files_found = 0
    inputted_files = list(input_path.glob(f"*{input_file_type}"))
    for file in inputted_files:
        output_file_name = output_path / (file.stem + ".ui")
        convert(file, output_file_name)

    subdirectories = [item for item in input_path.iterdir() if item.is_dir()]
    for subdir in subdirectories:
        files_found += convert_files_in_folder(subdir, output_path, input_file_type)
    print(f"{files_found + len(inputted_files)} files found in {input_path}")
    return files_found + len(inputted_files)


def check_parser_errors(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Checks for invalid CLI calls

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments
    parser : argparse.ArgumentParser
        Parser object to allow for parser errors
    """
    if not args.input_file or not args.output_file:
        parser.error("Must input two files or two folders")
    if not Path(args.input_file).is_file() and not Path(args.input_file).is_dir():
        parser.error(f"Input path '{args.input_file}' is neither a file nor a directory.")


def create_new_directories(args: argparse.Namespace) -> None:
    """Creates an output directory if it does not already exist

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if input_path.is_file():
        file_dir = output_path.parent
        file_dir.mkdir(parents=True, exist_ok=True)
    elif input_path.is_dir() and not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Runs pydmconverter from the CLI or GUI"""
    print("Args:", sys.argv)
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("input_file", nargs="?", metavar="FILE")
    parser.add_argument("output_file", nargs="?", metavar="FILE")
    parser.add_argument("output_type", nargs="?", metavar="FILE TYPE")
    args: argparse.Namespace = parser.parse_args()

    if args.input_file:
        check_parser_errors(args, parser)
        create_new_directories(args)
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
