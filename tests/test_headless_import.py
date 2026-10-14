"""The IR / react.py path must import with zero Qt/PyDM/EPICS (issue #145), and
the .ui path must convert without EPICS.

The Canopy backend imports `pydmconverter.react` in a headless, slim container with
no PyQt5/pydm/pyepics installed. This guards against a regression that re-introduces
a module-scope Qt/EPICS import on the conversion path. It runs in a subprocess so the
check holds even though this dev env *does* have Qt installed: the point is that the
react path must never *touch* those modules.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_ui_target_converts_without_epics(tmp_path):
    """Converting to .ui never connects to a PV, so it works with pyepics missing."""
    source = tmp_path / "button.edl"
    source.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 200\nh 100\nendScreenProperties\n\n"
        "object activeButtonClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\nx 10\ny 10\nw 80\nh 20\n"
        'onColor index 15\noffColor index 20\ncontrolPv "X:VALVE"\nendObjectProperties\n'
    )
    code = textwrap.dedent(
        """
        import sys
        sys.modules["epics"] = None  # any `import epics` now raises ImportError
        from pydmconverter.edm.converter import convert
        convert(sys.argv[1], sys.argv[2])
        """
    )
    # Running in tmp_path takes the checkout off sys.path, so put it back: the test
    # must import the tree under test, not whatever pydmconverter is installed.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")]))}
    result = subprocess.run(
        [sys.executable, "-c", code, str(source), str(tmp_path / "button.ui")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    assert (tmp_path / "button.ui").exists()
