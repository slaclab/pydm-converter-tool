#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pydmconverter.edm.converter import convert
from pydmconverter.scheme import load_scheme
from pydmconverter.edm.display_roots import DISPLAY_ROOTS_ENV, resolve_display_roots
from pathlib import Path
import logging

logging.basicConfig(level=logging.WARNING)


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


def run(
    input_file,
    output_file,
    input_file_type=".edl",
    override=False,
    scrollable=False,
    site=None,
    calc_list=None,
    color_list=None,
    target="pydm",
    out_format="json",
    color_def=None,
    scheme=None,
    display_roots=None,
):
    if target == "react":
        run_react(
            input_file,
            output_file,
            override,
            site=site,
            calc_list=calc_list,
            color_list=color_list,
            color_def=color_def,
            scheme=scheme,
            display_roots=display_roots,
        )
        return

    input_path: Path = Path(input_file)
    output_path: Path = Path(output_file)

    if input_path.is_file():
        if output_path.suffix != ".ui":
            output_path = output_path.with_suffix(".ui")
        if output_path.is_file() and not override:
            raise FileExistsError(f"Output file '{output_path}' already exists. Use --override or -o to overwrite it.")
        copy_img_files(input_path.parent, output_path.parent)
        convert(
            str(input_path),
            str(output_path),
            scrollable,
            site=site,
            calc_list_file=calc_list,
            color_list_file=color_list,
            display_roots=display_roots,
        )
    else:
        if input_file_type[0] != ".":  # prepending . so it will not pick up other file types with same suffix
            input_file_type = "." + input_file_type
        output_path.mkdir(parents=True, exist_ok=True)
        files_found: int
        files_failed: list[str]
        files_found, files_failed = convert_files_in_folder(
            input_path,
            output_path,
            input_file_type,
            override,
            scrollable,
            site=site,
            calc_list=calc_list,
            color_list=color_list,
            display_roots=display_roots,
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


def run_react(
    input_file,
    output_file,
    override,
    site=None,
    calc_list=None,
    color_list=None,
    color_def=None,
    scheme=None,
    display_roots=None,
) -> None:
    """Convert .edl/.ui/.bob to Canopy Screen IR JSON (the --target react path).

    ``color_list`` is an EDM ``colors.list`` palette applied to ``.edl`` inputs only. ``color_def`` is a
    Phoebus ``color.def`` applied to ``.bob`` inputs only. ``scheme`` is a loaded
    :class:`pydmconverter.scheme.SchemeResult` (or ``None``) passed through to the converter.
    ``display_roots`` (``.edl`` inputs only) are absolute display directories
    (see :mod:`pydmconverter.edm.display_roots`).
    """
    from pydmconverter import react

    input_path = Path(input_file)
    output_path = Path(output_file)
    if input_path.is_file():
        out = react.convert_file(
            input_path,
            output_path,
            override=override,
            calc_list_path=calc_list,
            color_list_path=color_list,
            site=site,
            color_def_path=color_def,
            scheme=scheme,
            display_roots=display_roots,
        )
        print(f"Converted {input_path} -> {out}")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
        found, failed = react.convert_folder(
            input_path,
            output_path,
            override=override,
            calc_list_path=calc_list,
            color_list_path=color_list,
            site=site,
            color_def_path=color_def,
            scheme=scheme,
            display_roots=display_roots,
        )
        if found == 0:
            print(f"No {' or '.join(react.SUPPORTED_SUFFIXES)} files found in {input_path}")
        else:
            print(f"{found - len(failed)} files converted from {input_path}")
        if failed:
            print(f"{len(failed)} files failed to convert. Use --override or -o to overwrite existing files.")


def load_cli_scheme(path):
    """Load ``--scheme <file>``; return ``(scheme, failed)``.

    With no path, returns ``(None, False)`` and nothing is loaded, so output is unchanged. Otherwise every
    ``meta["errors"]`` entry is printed to stderr, and ``failed`` is true when there are errors or the scheme
    served is not the file's own (``served != id``). A failed scheme still converts with the scheme
    ``load_scheme`` served (``canopy-default``); the caller turns ``failed`` into a non-zero exit.
    """
    if path is None:
        return None, False
    scheme = load_scheme(Path(path))
    meta = scheme.meta
    for error in meta["errors"]:
        print(f"scheme {path}: {error['path'] or '<root>'}: {error['message']}", file=sys.stderr)
    failed = bool(meta["errors"]) or meta["served"] != meta["id"]
    if failed and not meta["errors"]:
        print(f"scheme {path}: served {meta['served']!r}, not the file's id {meta['id']!r}", file=sys.stderr)
    return scheme, failed


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
    site: str = args.site
    calc_list: str = args.calc_list
    color_list: str = args.color_list
    scheme, scheme_failed = load_cli_scheme(args.scheme)
    run(
        input_file,
        output_file,
        input_file_type,
        override,
        scrollable,
        site=site,
        calc_list=calc_list,
        color_list=color_list,
        target=args.target,
        out_format=args.format,
        color_def=args.color_def,
        scheme=scheme,
        display_roots=args.display_roots,
    )
    if scheme_failed:
        sys.exit(1)


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
            input_path, output_path, input_file_type, override, scrollable, site=site
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
    input_path: Path,
    output_path: Path,
    input_file_type: str,
    override: bool,
    scrollable: bool,
    site=None,
    calc_list=None,
    color_list=None,
    display_roots=None,
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
                convert(
                    file,
                    output_file_path,
                    scrollable,
                    site=site,
                    calc_list_file=calc_list,
                    color_list_file=color_list,
                    display_roots=display_roots,
                )
            except Exception as e:
                files_failed.append(str(file))
                logging.warning(f"Failed to convert {file}: {e}")
                continue

    subdirectories = [item for item in input_path.iterdir() if item.is_dir()]
    for subdir in subdirectories:
        sub_found, sub_failed = convert_files_in_folder(
            subdir,
            output_path / subdir.name,
            input_file_type,
            override,
            scrollable,
            site=site,
            calc_list=calc_list,
            color_list=color_list,
            display_roots=display_roots,
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
    # Here, not once per converted file.
    try:
        resolve_display_roots(args.display_roots)
    except ValueError as e:
        parser.error(str(e))


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
    parser.add_argument(
        "--site",
        type=str,
        default=None,
        help="Apply site-specific conversion rules (e.g., slac)",
    )
    parser.add_argument(
        "--calc-list",
        type=str,
        default=None,
        help="Path to an EDM calc.list file used to resolve named CALC PVs",
    )
    parser.add_argument(
        "--color-list",
        type=str,
        default=None,
        help="Path to an EDM colors.list palette used to resolve 'index N' colors (overrides EDMCOLORFILE)",
    )
    parser.add_argument(
        "--color-def",
        type=str,
        default=None,
        help="Path to a Phoebus color.def used to resolve named colors in .bob inputs (--target react only)",
    )
    parser.add_argument(
        "--scheme",
        type=str,
        default=None,
        help="Path to a canopy-color-scheme/1 facility scheme; named colors it imports become color roles "
        "(--target react, .bob inputs). Scheme errors are printed and the exit status is non-zero",
    )
    parser.add_argument(
        "--display-root",
        dest="display_roots",
        action="append",
        default=None,
        metavar="DIR",
        help=(
            "Absolute EDM display directory: a related or embedded display named below it gets the name relative "
            f"to it, for PYDM_DISPLAYS_PATH. Repeat for more than one (overrides {DISPLAY_ROOTS_ENV})"
        ),
    )
    parser.add_argument(
        "--target",
        choices=["pydm", "react"],
        default="pydm",
        help="Output target: 'pydm' writes .ui (default), 'react' writes Canopy Screen IR .screen.json",
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format for --target react (json; TSX is generated by the Screen Builder)",
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
