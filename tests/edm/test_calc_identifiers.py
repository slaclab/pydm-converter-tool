"""Calc URL netlocs. PyDM keys calc connections by the netloc alone, for the
whole application (calc_plugin.py get_connection_id), so the netloc must tell
calcs with different inputs apart and be the same on every conversion."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pydmconverter.edm.converter import convert
from pydmconverter.edm.parser_helpers import translate_calc_pv_to_pydm

REPO = Path(__file__).resolve().parents[2]
CALC_DICT = {"twice": (None, "A*2")}


def netloc(url):
    return url.split("://", 1)[1].split("?", 1)[0]


def test_identifier_is_the_same_in_every_run():
    # translate in fresh interpreters with different string hash seeds
    code = (
        "import sys\n"
        "from pydmconverter.edm.parser_helpers import translate_calc_pv_to_pydm\n"
        "for pv in sys.argv[1:]:\n"
        "    print(translate_calc_pv_to_pydm(pv, {'twice': (None, 'A*2')}))\n"
    )
    pvs = [r"CALC\\\{A+B\}(X:1,${P}Y)", r"CALC\\twice(X:1)"]
    runs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(REPO))
        result = subprocess.run(
            [sys.executable, "-c", code, *pvs], env=env, cwd=REPO, capture_output=True, text=True, check=True
        )
        runs.append(result.stdout.split())
    assert runs[0] == runs[1]
    assert [netloc(url) for url in runs[0]] == [netloc(translate_calc_pv_to_pydm(pv, CALC_DICT)) for pv in pvs]


def test_same_name_with_different_inputs_gets_different_identifiers():
    first = translate_calc_pv_to_pydm(r"CALC\\twice(X:1)", CALC_DICT)
    assert re.fullmatch(r"twice_[0-9a-f]{12}", netloc(first))
    assert netloc(translate_calc_pv_to_pydm(r"CALC\\twice(X:2)", CALC_DICT)) != netloc(first)
    # The same query, written differently, shares the identifier.
    assert netloc(translate_calc_pv_to_pydm(r"CALC\\twice( X:1 )", CALC_DICT)) == netloc(first)

    inline = [translate_calc_pv_to_pydm(rf"CALC\\\{{A*2\}}({pv})") for pv in ("X:1", "X:2")]
    assert all(re.fullmatch(r"calc_[0-9a-f]{12}", netloc(url)) for url in inline)
    assert netloc(inline[0]) != netloc(inline[1])


def test_identifier_names_the_macros_the_query_uses():
    # Macros are substituted when PyDM loads the screen: two embedded copies with
    # different macros get different netlocs then.
    url = translate_calc_pv_to_pydm(r"CALC\\\{A+B+C\}(${P}:X,${R}:Y,${P}:Z)")
    assert re.fullmatch(r"calc_[0-9a-f]{12}_\$\{P\}_\$\{R\}", netloc(url))


def test_window_variable_makes_a_window_identifier(tmp_path, monkeypatch):
    url = translate_calc_pv_to_pydm(r"CALC\\\{A+1\}(LOC\\__UNIQUE__v)", default_prefix="")
    assert re.fullmatch(r"calc_[0-9a-f]{12}__UNIQUE__", netloc(url))

    # In a converted screen the marker names the window, like the variable itself.
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "screen.edl"
    source.write_text(
        "4 0 1\nbeginScreenProperties\nmajor 4\nminor 0\nrelease 1\nx 0\ny 0\nw 200\nh 100\n"
        "endScreenProperties\n"
        "object activeXTextDspClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        'x 10\ny 10\nw 100\nh 20\ncontrolPv "CALC\\\\\\{A+1\\}(LOC\\\\$(!W)v)"\nendObjectProperties\n'
    )
    convert(str(source), str(tmp_path / "screen.ui"))
    text = (tmp_path / "screen.ui").read_text()
    assert re.search(r"calc://calc_[0-9a-f]{12}\$\{EDM_W\}\?", text)
    assert "__UNIQUE__" not in text


def test_same_named_calc_on_different_inputs_shows_different_values(qtbot):
    pytest.importorskip("pydm")
    from pydm.widgets import PyDMLabel, PyDMLineEdit

    # The variables are defined (type and initial value) before the calcs connect to them.
    sources = [PyDMLineEdit(init_channel=f"loc://calcIdIn{i}?type=int&init={value}") for i, value in ((1, 1), (2, 5))]
    # An empty default prefix keeps the arguments loc:// channels (no Channel Access).
    labels = [
        PyDMLabel(
            init_channel=translate_calc_pv_to_pydm(rf"CALC\\twice(LOC\\calcIdIn{i})", CALC_DICT, default_prefix="")
        )
        for i in (1, 2)
    ]
    for widget in sources + labels:
        qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: [label.text() for label in labels] == ["2", "10"], timeout=3000)
