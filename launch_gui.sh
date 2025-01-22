#!/bin/bash

# Get the canonicalized absolute path of the script
script_dir="$(readlink -f "$(dirname "$0")")"

# Get the canonicalized absolute path of the current working directory
current_dir="$(readlink -f "$PWD")"

# Check if the current working directory is different from the script directory
if [ "$current_dir" != "$script_dir" ]; then
    # Change the current working directory to the script directory
    cd "$script_dir" || exit 1
    echo "Changed cwd to script directory: $script_dir"
else
    echo "Already in script directory: $script_dir"
fi

# Sets correct envs
export PYTHONPATH="$script_dir:$script_dir/app/src:$script_dir/pydmconverter:$PYTHONPATH"

# Launch GUI
pydm --hide-nav-bar --hide-menu-bar app/src/view/main_window.py

# Return to the original directory
cd "$current_dir" || exit 1
echo "Returned to original directory: $current_dir"
