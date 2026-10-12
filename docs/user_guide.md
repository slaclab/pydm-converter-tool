#Installation

##Prerequisites

## Installation Methods

### Option 1: Install from PyPI (Recommended)
The easiest way to install the converter is directly from PyPI:
``` bash
pip install PyDMConverter
```

### Option 2: Install from Source
If you need the latest development version or want to contribute:

#### Clone the Repository
``` bash
git clone https://github.com/slaclab/pydm-converter-tool.git
cd pydm-converter-tool
```

#### Set up Environment
Using `conda`:
``` bash
conda env create -f environment.yml
conda activate pydm
```

Or using pip:
``` bash
pip install -e .
```

# How to Run the Converter

The converter can be run in two ways: via the command line interface (CLI) or through the graphical user interface (GUI).

## Launch the GUI

To launch the graphical interface:
``` bash
pydmconverter
```

This will open the PyDM Converter GUI where you can:
- Select files or folders to convert

## Command Line Interface

The CLI provides two main ways to run the converter: on individual files and entire folders. Users can include additional arguments described on the [Arguments] page.

  [Arguments]: arguments.md

## For individual files
When using the converter on a single file, the command line is:
``` bash
pydmconverter '/path/old_file.edl' 'new_file_name.ui' `
```
## For an entire folder
When converting an entire folder, the command line is:
``` bash
pydmconverter '/path_to_old_directory' '/new_file_location' 'old_file_type'
```

## Examples
To convert EDM file called "file.edl" to PYDM file called "file.ui" :
``` bash
pydmconverter /afs/slac/g/lcls/edm/file.edl file.ui`
```
To convert EDM files in a folder called "edm" to PYDM file in the current folder :
``` bash
pydmconverter /afs/slac/g/lcls/edm . .edl
```

To convert with SLAC-specific rules (e.g. skipping exit buttons):
``` bash
pydmconverter /afs/slac/g/lcls/edm/file.edl file.ui --site slac
```

# EDM Behaviours That Convert Differently

## Related display buttons

- **Close the parent window.** An EDM related display entry with *close action*
  set (`closeAction` or `closeDisplay`) opens its display in a new window, then
  closes the window it was opened from. When every entry of a button closes,
  the converted button has `openInNewWindow` set to false: in the PyDM app the
  new display replaces the current one in the same window, and the back button
  returns to it. Shift-click and the right-click *Open in New Window* still open
  a new window. A button where only some entries close opens all of them in a
  new window and leaves the parent open.
  EDM never closes the parent from a popup (*button3Popup*, or *useFocus* on a
  button with one display), so such a button keeps a new window.
- **Macro precedence.** PyDM passes the parent display's macros to the new
  display and lets the button's own macros override them. EDM, by default, puts
  the parent's macros first and drops a later duplicate, so where both define
  the same name the parent's value wins in EDM and the button's value wins in
  PyDM.
- **`propagateMacros` and `replaceSymbols`.** EDM can open a display with only
  the button's symbols (`replaceSymbols`), or with the `edm -m` macros and the
  button's symbols but not the parent's macros (`propagateMacros` off). PyDM
  always passes the parent's macros, so neither setting is converted.
