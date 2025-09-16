# Installation

## Prerequisites
- Python 3.12 or newer
- pip (Python package manager)
- (Optional) conda for environment management


## Clone the Repository

``` bash
git clone https://github.com/slaclab/pydm-converter-tool.git
```


## Create and Activate a Virtual Environment (Recommended)

Using `venv`:
``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Or using `conda`:
``` bash
conda env create -f environment.yml
conda activate pydm-converter-tool
```


## Install Dependencies

If using pip:
``` bash
pip install -r requirements.txt
```

Or with `conda` (if you created the environment above, dependencies are already installed):
``` bash
conda env update -f environment.yml
```


## Running PyDMConverter

The main startup file for PyDMConverter is located at `pydmconverter/__main__.py`.

With PyDMConverter, you can launch a GUI or run it with a CLI, where users can pass in additional [arguments].

  [arguments]: arguments.md

``` bash
PyDMConverter
```
