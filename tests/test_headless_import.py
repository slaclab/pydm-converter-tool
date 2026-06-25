"""The IR / react.py path must import with zero Qt/PyDM/EPICS (issue #145).

The Canopy backend imports `pydmconverter.react` in a headless, slim container with
no PyQt5/pydm/pyepics installed. This guards against a regression that re-introduces
a module-scope Qt/EPICS import on the conversion path. It runs in a subprocess so the
check holds even though this dev env *does* have Qt installed: the point is that the
react path must never *touch* those modules.
"""

import subprocess
import sys
import textwrap


def test_react_path_imports_without_qt_pydm_or_epics():
    code = textwrap.dedent(
        """
        import sys
        import pydmconverter.react
        from pydmconverter.react import convert_to_ir, convert_bytes, convert_file, convert_folder

        forbidden = [
            "qtpy",
            "pydm",
            "epics",
            "pydmconverter.edm.converter_helpers",
            "pydmconverter.edm.menumux",
            "pydmconverter.widgets",
        ]
        loaded = [name for name in forbidden if name in sys.modules]
        assert not loaded, f"react path pulled in heavy modules: {loaded}"
        """
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
