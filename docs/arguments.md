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

## Help

`-h` or `--help`

This argument shows the converter's help message, which outlines the available arguments for users.
