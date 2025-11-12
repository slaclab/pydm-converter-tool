#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pydmconverter.edm.converter import convert
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)


IMAGE_FILE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif"}


def run_gui() -> None:
    """
    launch the PyDMConverter gui
    """
    # Get the directory where this package is installed
    package_dir = Path(__file__).parent
    launch_script = package_dir / "launch_gui.sh"

    if not launch_script.exists():
        raise FileNotFoundError(
            f"launch_gui.sh not found at {launch_script}. Please ensure the package was installed correctly."
        )

    subprocess.run(["bash", str(launch_script)], check=True)


def run(input_file, output_file, input_file_type=".edl", override=False, scrollable=False):
    input_path: Path = Path(input_file)
    output_path: Path = Path(output_file)

    if input_path.is_file():
        if output_path.suffix != ".ui":
            output_path = output_path.with_suffix(".ui")
        if output_path.is_file() and not override:
            raise FileExistsError(f"Output file '{output_path}' already exists. Use --override or -o to overwrite it.")
        copy_img_files(input_path.parent, output_path.parent)
        convert(str(input_path), str(output_path), scrollable)
    else:
        if input_file_type[0] != ".":  # prepending . so it will not pick up other file types with same suffix
            input_file_type = "." + input_file_type
        output_path.mkdir(parents=True, exist_ok=True)
        files_found: int
        files_failed: list[str]
        files_found, files_failed = convert_files_in_folder(
            input_path, output_path, input_file_type, override, scrollable
        )

        if files_found == 0:
            print(f"No {input_file_type} files found in {input_path}")
        else:
            print(f"{files_found - len(files_failed)} {input_file_type} files converted from {input_path}")
        if files_failed:
            print(
                f"{len(files_failed)} files failed to convert to prevent overriding current files. Use --override or -o to overwrite these files."
            )
            print(f"Failed files: {', '.join(map(lambda path: str(path), files_failed))}")


def run_cli(args: argparse.Namespace) -> None:
    """
    run PyDMConverter through command line

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    logging.info(f"Running CLI with arguments: {args}")
    input_file: str = args.input_file
    output_file: str = args.output_file
    input_file_type: str = args.output_type
    override: bool = args.override
    scrollable: bool = args.scrollable
    run(input_file, output_file, input_file_type, override, scrollable)


"""
    if input_path.is_file():
        if output_path.suffix != ".ui":
            output_path = output_path.with_suffix(".ui")
        if output_path.is_file() and not override:
            raise FileExistsError(f"Output file '{output_path}' already exists. Use --override or -o to overwrite it.")
        convert(str(input_path), str(output_path), scrollable)
        copy_img_files(input_path.parent, output_path.parent)
    else:
        if not input_file_type:
            raise AttributeError(
                "No file type given. When converting directories, use this format: [Input_Dir] [Output_Dir] [File_Type]"
            )
        if input_file_type[0] != ".":  # prepending . so it will not pick up other file types with same suffix
            input_file_type = "." + input_file_type
        output_path.mkdir(parents=True, exist_ok=True)
        files_found: int
        files_failed: list[str]
        files_found, files_failed = convert_files_in_folder(
            input_path, output_path, input_file_type, override, scrollable
        )

        if files_found == 0:
            print(f"No {input_file_type} files found in {input_path}")
        else:
            print(f"{files_found - len(files_failed)} {input_file_type} files converted from {input_path}")
        if files_failed:
            print(
                f"{len(files_failed)} files failed to convert to prevent overriding current files. Use --override or -o to overwrite these files."
            )
            print(f"Failed files: {', '.join(map(lambda path: str(path), files_failed))}")
"""


def copy_img_files(input_path: Path, output_path: Path) -> None:
    for file in input_path.rglob("*"):
        if file.suffix.lower() in IMAGE_FILE_SUFFIXES:
            relative_path = file.relative_to(input_path)
            output_file_path = output_path / relative_path

            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file, "rb") as src, open(output_file_path, "wb") as dst:
                dst.write(src.read())


def convert_files_in_folder(
    input_path: Path, output_path: Path, input_file_type: str, override: bool, scrollable: bool
) -> tuple[int, list[str]]:
    """Recursively runs convert on files in directory and subdirectories

    Parameters
    ----------
    input_path : Path
        The parent directory of files to convert
    output_path: Path
        The directory where converted files will be stored
    input_file_type: str
        The type of file to convert (often will be .edl)
    override: bool
        Boolean if the override flag was included

    Returns
    -------
    tuple[int, list[str]]
        A tuple containing the amount of total files of valid type found in directory and a list of all files that failed due to override warnings
    """
    files_found: int = 0
    files_failed: list[str] = []

    inputted_files = list(input_path.glob(f"*{input_file_type}"))
    copy_img_files(input_path, output_path)
    for file in inputted_files:
        relative_path = file.relative_to(input_path)
        output_file_path = (output_path / relative_path).with_suffix(".ui")

        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        if output_file_path.is_file() and not override:
            files_failed.append(str(file))
            logging.warning(f"Skipped: {output_file_path} already exists. Use --override or -o to overwrite it.")
        else:
            try:
                convert(file, output_file_path, scrollable)
            except Exception as e:
                files_failed.append(str(file))
                logging.warning(f"Failed to convert {file}: {e}")
                breakpoint()
                continue

    subdirectories = [item for item in input_path.iterdir() if item.is_dir()]
    for subdir in subdirectories:
        sub_found, sub_failed = convert_files_in_folder(
            subdir, output_path / subdir.name, input_file_type, override, scrollable
        )
        files_found += sub_found
        files_failed += sub_failed

    return (files_found + len(inputted_files), files_failed)


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
        parser.error(f"Input path '{args.input_file}' is neither a valid file nor a valid directory.")


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
    logging.debug(f"Sys argv: {sys.argv}")
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("input_file", nargs="?", metavar="FILE")
    parser.add_argument("output_file", nargs="?", metavar="FILE")
    parser.add_argument("output_type", nargs="?", metavar="FILE TYPE")
    parser.add_argument("--override", "-o", action="store_true", help="Override the output file if it already exists")
    parser.add_argument(
        "--scrollable",
        "-s",
        action="store_true",
        help="create scrollable pydm windows that replicate edm windows (may cause spacing issues for embedded displays)",
    )
    args: argparse.Namespace = parser.parse_args()

    if args.input_file:
        check_parser_errors(args, parser)
        create_new_directories(args)
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
