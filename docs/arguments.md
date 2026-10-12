Pydmconverter supports a few optional startup arguments that allow users to execute specific actions when running the converter.

Below, you'll find a detailed overview of each available argument to help you use the converter as you need to.

## Override

`-o` or `--override`

This argument allows users to override the output file if it already exists. Most often this will be used with the scroll bar argument if it appears a screen exceeds the screen. This will replace the file with a new converted file.


## Scroll Bars

`-s` or `--scrollable`

This argument adds scroll bars to converted screens. It will ad a horizontal and vertical scroll bar. If this argument is not included, the screen will not contain a scroll bar.

## Site

`--site <name>`

This argument applies site-specific conversion rules during the conversion process. Some facilities have EDM widgets or patterns that have no equivalent in PyDM and should be skipped or handled differently. The `--site` flag lets you opt into these rules without affecting the default conversion behavior.

**Available sites:**

| Site   | Rules Applied |
|--------|---------------|
| `slac` | Skips `activeExitButtonClass` (exit buttons present on every SLAC EDM screen that have no PyDM equivalent) |

**Usage:**
``` bash
pydmconverter /path/to/file.edl output.ui --site slac
```

**Adding a new site:**
To add conversion rules for a new site, create a new module in `pydmconverter/sites/` (e.g. `mysite.py`) that defines a `SKIP_WIDGETS` set, then register it in `pydmconverter/sites/__init__.py`.

## Display roots

`--display-root <dir>` or the `PYDMCONVERTER_DISPLAY_ROOTS` environment variable

An EDM display can open another display by its absolute path on the EDM console, for example `/opt/edm/display/misc/panel.edl`. PyDM joins each directory it searches with the display name, so an absolute name only finds a file at that exact path. Give the console's display directory as a display root, and related display and embedded display names below it are written relative to it: `/opt/edm/display/misc/panel.edl` becomes `misc/panel.ui` (`misc/panel.screen.json` with `--target react`). PyDM finds the converted display when the converted display tree is the working directory or is listed in `PYDM_DISPLAYS_PATH`.

- Repeat `--display-root` for more than one directory. In the environment variable, separate them with `:`, as in `EDMDATAFILES`.
- `--display-root` overrides the environment variable. With neither, display names are left as they are.
- A display root must be an absolute directory other than `/`.
- Other names are unchanged: relative names, other absolute paths, a name that climbs out of the root with `..`, and image and shell command files.
- The roots are the EDM console's directories, not those of the machine running the converter, so they are not taken from `EDMDATAFILES`.

**Usage:**
``` bash
pydmconverter /path/to/file.edl output.ui --display-root /opt/edm/display
```
``` bash
export PYDMCONVERTER_DISPLAY_ROOTS=/opt/edm/display:/opt/other/edm/display
pydmconverter /path/to/file.edl output.ui
```

## Help

`-h` or `--help`

This argument shows the converter's help message, which outlines the available arguments for users.
