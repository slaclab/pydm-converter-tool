#!/bin/bash

# Get the canonicalized absolute path of the script
script_dir="$(readlink -f "$(dirname "$0")")"
# echo "$script_dir"

# Get the canonicalized absolute path of the current working directory
current_dir="$(readlink -f "$PWD")"
# echo "$current_dir"

# Check if the current working directory is different from the script directory
if [ "$current_dir" != "$script_dir" ]; then
    # Change the current working directory to the script directory
    cd "$script_dir" || exit 1
    echo "Changed cwd to script directory: $script_dir"
else
    echo "Already in script directory: $script_dir"
fi

# Sets correct envs
source env.sh

# Launch GUI
pydm --hide-nav-bar --hide-menu-bar view/main_window.py

# Return to the original directory
cd "$current_dir" || exit 1
echo "Returned to original directory: $current_dir"
