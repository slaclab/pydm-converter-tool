#Installation

##Prerequisites


## Clone the Repository
``` bash
git clone https://github.com/slaclab/pydm-converter-tool.git
```

## Set up Environment
Using `conda`:
``` bash
conda env create -f environment.yml
conda activate pydm
```

# How to Run the Converter

This outlines the two main ways to run the converter: on individual files and entire folders. Users can include additional arguments described on the [Arguments] page.

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
pydmconverter /afs/slac/g/lcls/edm . .edl`
```
