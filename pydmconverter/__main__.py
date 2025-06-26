#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
#import edm.converter
from pydmconverter.edm.converter import convert
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
    input_file: str = args.input_file
    output_file: str = args.output_file #maybe confusing input and output file can also be directories
    input_file_type: str = args.output_type
    if os.path.isfile(args.input_file): 
        if len(output_file) < 3 or output_file[-3:] != '.ui':
            output_file += ".ui"
        convert(input_file, output_file)
    elif os.path.isdir(input_file):
        if not os.path.isdir(output_file):
            os.makedirs(output_file)
        if input_file_type[0] != '.': #prepending . #technically redundant
            input_file_type = '.' + input_file_type
        search_pattern = os.path.join(input_file, '*' + input_file_type)
        inputted_files = glob.glob(search_pattern)
        for file in inputted_files:
            output_file_name = get_output_file_name(file, output_file)
            convert(file, output_file_name)
    else:
        raise ValueError(f"Input path '{input_file}' is neither a file nor a directory.")

def get_output_file_name(file: str, output_file: str):
    input_file_name = file.split('/')[-1]
    #input_file_name = ".".join(input_file_name.split['.'][:-1]) #this works for all file types but may have issues if file does not end with a .type
    if len(input_file_name) >= 4 and input_file_name[-4:] == '.edl':
        input_file_name = input_file_name[:-4]
    input_file_name += '.ui'
    return output_file + '/' + input_file_name

def check_parser_errors(args: object, parser: argparse.ArgumentParser):
    if not args.input_file or not args.output_file: #techincally may be folders instead but this should still work for that
        parser.error("Must input two files")
    #if not os.path.isfile(args.input_file) or not os.path.isdir(args.input_file):
    #    parser.error("Invalid input file: Must input a valid file or directory")
    """if os.path.isfile(args.input_file):
        file_dir = "/".join(args.input_file.split('/')[:-1])
        if not os.path.isdir(file_dir):
            parser.error("Invalid output file directory")
    elif os.path.isdir(args.input_file) and not os.path.isdir(args.output_file): #this assumes that the user does not want to add the files to the root
        parser.error("Invalid output directory")
    else:
        parser.error("Invalid input file: Must input a valid file or directory")"""

def create_new_directories(args: object, parser: argparse.ArgumentParser):
    if os.path.isfile(args.input_file):
        file_dir = "/".join(args.output_file.split('/')[:-1])
        print(file_dir)
        if not os.path.isdir(file_dir) and file_dir:
            os.makedirs(file_dir)
        print('file_dir', file_dir)
    if os.path.isdir(args.input_file) and not os.path.isdir(args.output_file) and args.output_file: #maybe unnecesary
        os.makedirs(args.output_file)

def main():
    import sys
    print("Args:", sys.argv)
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
        check_parser_errors(args, parser)
        create_new_directories(args, parser)
        print
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
