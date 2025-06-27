#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pydmconverter.edm.converter import convert
from pathlib import Path
import warnings


def run_gui() -> None:
    """
    launch the PyDMConverter gui
    """
    subprocess.run(["pydm", "--hide-nav-bar", "--hide-menu-bar", "view/main_window.py"])


def run_cli(args: argparse.Namespace) -> None:
    """
    run PyDMConverter through command line"
    """
    print("Running CLI with arguments:", args)
    input_path: Path = Path(args.input_file)
    output_path: Path = Path(args.output_file)
    input_file_type: str = args.output_type
    override: bool = args.override

    if input_path.is_file():
        if output_path.suffix != ".ui":
            output_path = output_path.with_suffix(".ui")
        if output_path.is_file() and not override:
            raise FileExistsError(f"Output file '{output_path}' already exists. Use --override or -o to overwrite it.")
        convert(str(input_path), str(output_path))
    else:
        if input_file_type[0] != ".":  # prepending . so it will not pick up other file types with same suffix
            input_file_type = "." + input_file_type
        output_path.mkdir(parents=True, exist_ok=True)
        files_found: int
        files_failed: list[str]
        files_found, files_failed = convert_files_in_folder(input_path, output_path, input_file_type, override)

        if files_found == 0:
            print(f"No {input_file_type} files found in {input_path}")
        else:
            print(f"{files_found - len(files_failed)} {input_file_type} files converted from {input_path}")
        if files_failed:
            print(f"{len(files_failed)} files failed to convert to prevent overriding current files")
            print(f"Failed files: {', '.join(map(lambda path: str(path), files_failed))}")


def convert_files_in_folder(
    input_path: Path, output_path: Path, input_file_type: str, override: bool
) -> tuple[int, list[str]]:
    files_found: int = 0
    files_failed: list[str] = []

    inputted_files = list(input_path.glob(f"*{input_file_type}"))
    for file in inputted_files:
        relative_path = file.relative_to(input_path)
        output_file_path = (output_path / relative_path).with_suffix(".ui")

        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        if output_file_path.is_file() and not override:
            files_failed.append(str(file))
            warnings.warn(
                f"Output file '{output_file_path}' already exists. Use --override or -o to overwrite it.",
                category=UserWarning,
            )
        else:
            convert(file, output_file_path)

    subdirectories = [item for item in input_path.iterdir() if item.is_dir()]
    for subdir in subdirectories:
        sub_found, sub_failed = convert_files_in_folder(subdir, output_path / subdir.name, input_file_type, override)
        files_found += sub_found
        files_failed += sub_failed

    return (files_found + len(inputted_files), files_failed)


def get_output_file_name(file: Path, output_path: Path) -> Path:
    return output_path / (file.stem + ".ui")


def check_parser_errors(args: object, parser: argparse.ArgumentParser) -> None:
    if not args.input_file or not args.output_file:
        parser.error("Must input two files or two folders")
    if not Path(args.input_file).is_file() and not Path(args.input_file).is_dir():
        parser.error(f"Input path '{args.input_file}' is neither a valid file nor a valid directory.")


def create_new_directories(args: argparse.Namespace) -> None:
    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if input_path.is_file():
        file_dir = output_path.parent
        file_dir.mkdir(parents=True, exist_ok=True)
    elif input_path.is_dir() and not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    print("Args:", sys.argv)
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("input_file", nargs="?", metavar="FILE")
    parser.add_argument("output_file", nargs="?", metavar="FILE")
    parser.add_argument("output_type", nargs="?", metavar="FILE TYPE")
    parser.add_argument("--override", "-o", action="store_true", help="Override the output file if it already exists")
    args: argparse.Namespace = parser.parse_args()

    if args.input_file:
        check_parser_errors(args, parser)
        create_new_directories(args)
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
