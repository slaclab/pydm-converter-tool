import argparse
import subprocess

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cli",
        action="store_true",
        help="If provided, run in command-line (CLI) mode instead of GUI."
    ) 
    args = parser.parse_args()

    if args.cli:
        run_cli(args)
    else:
        run_gui()

if __name__ == "__main__":
    main()