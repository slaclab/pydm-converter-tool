#!/bin/bash

# Get the canonicalized absolute path of the script
script_dir="$(readlink -f "$(dirname "$0")")"

# Get the project root directory (parent of pydmconverter/)
project_root="$(dirname "$script_dir")"

# Get the canonicalized absolute path of the current working directory
current_dir="$(readlink -f "$PWD")"

# Check if the current working directory is different from the project root
if [ "$current_dir" != "$project_root" ]; then
    # Change the current working directory to the project root
    cd "$project_root" || exit 1
    echo "Changed cwd to project root: $project_root"
else
    echo "Already in project root: $project_root"
fi

# Sets correct envs
export PYTHONPATH="$project_root:$project_root/app/src:$project_root/pydmconverter:$PYTHONPATH"

# Launch GUI
pydm --hide-nav-bar --hide-menu-bar app/src/view/main_window.py

# Return to the original directory
cd "$current_dir" || exit 1
echo "Returned to original directory: $current_dir"

# Store the current shell's working directory for restoration
echo "Shell cwd was reset to $(pwd)"
