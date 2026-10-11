import json
import re
from pathlib import Path

import pytest

from pydmconverter import react

EDM_FIXTURE = Path(__file__).parent / "edm" / "fixtures" / "basic_widgets.edl"
UI_FIXTURE = Path(__file__).parent / "ui" / "fixtures" / "basic_widgets.ui"


def test_convert_to_ir_dispatches_by_suffix():
    assert react.convert_to_ir(EDM_FIXTURE).metadata.source.type == "edl-converter"
    assert react.convert_to_ir(UI_FIXTURE).metadata.source.type == "ui-converter"


def test_convert_bytes_edl_and_ui():
    """convert_bytes runs the same pipeline as convert_to_ir but is keyed on kind (#146)."""
    edm = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl")
    ui = react.convert_bytes(UI_FIXTURE.read_bytes(), kind="ui")
    assert edm.metadata.source.type == "edl-converter"
    assert ui.metadata.source.type == "ui-converter"
    assert edm.root.children  # produced widgets through the shared builder


def test_convert_bytes_is_deterministic():
    data = EDM_FIXTURE.read_bytes()
    assert react.convert_bytes(data, kind="edl") == react.convert_bytes(data, kind="edl")


def test_convert_bytes_rejects_bad_kind():
    with pytest.raises(ValueError, match="kind"):
        react.convert_bytes(b"<x/>", kind="txt")


def test_convert_to_ir_rejects_unknown_suffix(tmp_path):
    bogus = tmp_path / "x.txt"
    bogus.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError, match="supports"):
        react.convert_to_ir(bogus)


def test_convert_file_writes_screen_json(tmp_path):
    out = react.convert_file(EDM_FIXTURE, tmp_path / "vac", override=True)
    assert out.name == "vac.screen.json"
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "screen"


def test_convert_file_honors_explicit_json_name(tmp_path):
    out = react.convert_file(UI_FIXTURE, tmp_path / "custom.json", override=True)
    assert out.name == "custom.json"


def test_convert_file_refuses_overwrite_without_override(tmp_path):
    target = tmp_path / "out.screen.json"
    react.convert_file(EDM_FIXTURE, target, override=True)
    with pytest.raises(FileExistsError):
        react.convert_file(EDM_FIXTURE, target, override=False)


def test_convert_folder(tmp_path):
    src = tmp_path / "in"
    (src / "nested").mkdir(parents=True)
    (src / "a.edl").write_text(EDM_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (src / "nested" / "b.ui").write_text(UI_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (src / "ignore.txt").write_text("x", encoding="utf-8")

    found, failed = react.convert_folder(src, tmp_path / "out", override=True)
    assert found == 2
    assert failed == []
    assert (tmp_path / "out" / "a.screen.json").is_file()
    assert (tmp_path / "out" / "nested" / "b.screen.json").is_file()


# --- convert_bytes keeps the upload's identity (filename / search_paths) -------

EDM_FIXTURES = Path(__file__).parent / "edm" / "fixtures"


def test_convert_bytes_without_filename_keeps_screen_id():
    """Backward compatible: no filename -> the fixed "screen" id/title."""
    ir = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl")
    assert (ir.id, ir.metadata.title) == ("screen", "screen")


def test_convert_bytes_filename_sets_id_and_title():
    edm = react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl", filename="vac_gunb_main.edl")
    assert (edm.id, edm.metadata.title) == ("vac_gunb_main", "vac_gunb_main")
    ui = react.convert_bytes(UI_FIXTURE.read_bytes(), kind="ui", filename="mc_overview.ui")
    assert ui.id == "mc_overview"


def test_convert_bytes_filename_is_reduced_to_a_safe_basename():
    data = EDM_FIXTURE.read_bytes()
    assert react.convert_bytes(data, kind="edl", filename="../../etc/sub/vac.edl").id == "vac"
    assert react.convert_bytes(data, kind="edl", filename="C:\\screens\\vac.EDL").id == "vac"
    assert react.convert_bytes(data, kind="edl", filename="vac").id == "vac"  # suffix appended for dispatch
    assert react.convert_bytes(data, kind="edl", filename="..").id == "screen"


def test_convert_bytes_unwritable_filename_falls_back_to_screen():
    """A name the filesystem cannot hold (here: too long) stages as "screen" instead of failing."""
    assert react.convert_bytes(EDM_FIXTURE.read_bytes(), kind="edl", filename="x" * 300 + ".edl").id == "screen"


SYMBOL_DISPLAY = EDM_FIXTURES / "symbol_two_state.edl"
SYMBOL_FILE = EDM_FIXTURES / "symbol_states.edl"


def _isolate_symbol_lookup(monkeypatch, tmp_path):
    """Keep symbol lookup off the host's EDMDATAFILES and its "." default (the CWD)."""
    monkeypatch.delenv("EDMDATAFILES", raising=False)
    monkeypatch.chdir(tmp_path)


def _convert_symbol_display(data=None, **kwargs):
    """Convert symbol_two_state.edl (or ``data`` in its place) and return its symbol node."""
    data = SYMBOL_DISPLAY.read_bytes() if data is None else data
    return react.convert_bytes(data, kind="edl", filename="symbol_two_state.edl", **kwargs).root.children[0]


def _write_symbol_file(tmp_path, data):
    """Write ``data`` as symbol_states.edl in its own dir (not the CWD) and return that dir."""
    symbols = tmp_path / "symbols"
    symbols.mkdir()
    (symbols / "symbol_states.edl").write_bytes(data)
    return symbols


def test_convert_bytes_symbol_needs_search_paths(monkeypatch, tmp_path):
    """The staged copy lives in a private temp dir, so the symbol file beside the
    original display is only found via search_paths; without it the symbol is an
    empty group whose warning names the missing file (it used to vanish)."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    data = (EDM_FIXTURES / "symbol_two_state.edl").read_bytes()

    missing = react.convert_bytes(data, kind="edl", filename="symbol_two_state.edl").root.children[0]
    assert missing.type == "group"
    assert missing.children == []
    assert (missing.geometry.x, missing.geometry.y, missing.geometry.width, missing.geometry.height) == (50, 60, 24, 24)
    assert any("symbol file 'symbol_states.edl' not found" in w for w in missing.warnings)

    found = react.convert_bytes(
        data, kind="edl", filename="symbol_two_state.edl", search_paths=[str(EDM_FIXTURES)]
    ).root.children[0]
    assert len([child for child in found.children if child.type == "group"]) == 2
    assert not any("not found" in w for w in found.warnings)


def test_convert_bytes_accepts_a_single_search_path(monkeypatch, tmp_path):
    """search_paths may be one directory (str or Path), not only a sequence of them."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    for search_paths in (str(EDM_FIXTURES), EDM_FIXTURES):
        found = _convert_symbol_display(search_paths=search_paths)
        assert len([child for child in found.children if child.type == "group"]) == 2
        assert not any("not found" in w for w in found.warnings)


def test_convert_bytes_latin1_symbol_file(monkeypatch, tmp_path):
    """A symbol file that is not valid UTF-8 (a Latin-1 degree sign) is still parsed."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    text = SYMBOL_FILE.read_text(encoding="utf-8")
    assert "endScreenProperties\n" in text
    text = text.replace("endScreenProperties\n", "endScreenProperties\n# 20 \xb0C\n", 1)
    symbols = _write_symbol_file(tmp_path, text.encode("latin-1"))

    found = _convert_symbol_display(search_paths=[symbols])
    assert len([child for child in found.children if child.type == "group"]) == 2


def test_convert_bytes_symbol_file_without_screen_header(monkeypatch, tmp_path):
    """A symbol file lacking the beginScreenProperties block is loaded rather than raising."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    text = SYMBOL_FILE.read_text(encoding="utf-8")
    headerless = re.sub(r"beginScreenProperties.*?endScreenProperties\n", "", text, flags=re.S)
    assert headerless != text
    symbols = _write_symbol_file(tmp_path, headerless.encode("utf-8"))

    found = _convert_symbol_display(search_paths=[symbols])
    assert found.type == "group"
    assert not any("not found" in w for w in found.warnings)


def test_convert_bytes_symbol_without_file_property_warns(monkeypatch, tmp_path):
    """An activeSymbolClass with no file is an empty group at its rect that says why."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    text = SYMBOL_DISPLAY.read_text(encoding="utf-8")
    assert 'file "symbol_states"\n' in text
    data = text.replace('file "symbol_states"\n', "", 1).encode("utf-8")

    symbol = _convert_symbol_display(data)
    assert symbol.type == "group"
    assert symbol.children == []
    assert (symbol.geometry.x, symbol.geometry.y, symbol.geometry.width, symbol.geometry.height) == (50, 60, 24, 24)
    assert "EDM symbol has no file property; symbol not rendered" in symbol.warnings


def test_convert_bytes_symbol_without_pvs_or_ranges_shows_state_one(monkeypatch, tmp_path):
    """numPvs 0 with no minValues/maxValues shows state 1 (symbol.cc: no control
    PV -> index = 1), not state 0 and not nothing."""
    _isolate_symbol_lookup(monkeypatch, tmp_path)
    text = SYMBOL_DISPLAY.read_text(encoding="utf-8")
    stripped = re.sub(
        r"minValues \{.*?\}\nmaxValues \{.*?\}\ncontrolPvs \{.*?\}\nnumPvs 1\n", "numPvs 0\n", text, flags=re.S
    )
    assert stripped != text

    found = _convert_symbol_display(stripped.encode("utf-8"), search_paths=[EDM_FIXTURES])
    (state,) = [child for child in found.children if child.type == "group"]
    # symbol_states.edl: state 0 is a rectangle, state 1 a circle.
    assert [child.type for child in state.children] == ["ellipse"]


def test_convert_bytes_calc_list_found_via_search_paths(monkeypatch):
    """A named CALC\\sum resolves from a calc.list in a search path directory."""
    monkeypatch.delenv("EDMFILES", raising=False)
    monkeypatch.delenv("EDMCOLORFILE", raising=False)
    data = (EDM_FIXTURES / "calc_rules.edl").read_bytes()

    def sum_formulas(ir):
        return [f for f in ir.formulas if f.expression in ("{A}+{B}", "A+B")]

    assert sum_formulas(react.convert_bytes(data, kind="edl", filename="calc_rules.edl")) == []
    ir = react.convert_bytes(data, kind="edl", filename="calc_rules.edl", search_paths=[EDM_FIXTURES])
    assert len(sum_formulas(ir)) == 1


# --- confine_file_refs: an upload's symbol paths stay inside the search paths ---


@pytest.fixture
def symbol_tree(tmp_path):
    """A search root holding ``sub/symbol_states.edl`` and, outside it, ``outside/secret.edl``
    (both copies of the two-state symbol fixture, so "read" means two state groups)."""
    symbol = (EDM_FIXTURES / "symbol_states.edl").read_bytes()
    (tmp_path / "root" / "sub").mkdir(parents=True)
    (tmp_path / "root" / "sub" / "symbol_states.edl").write_bytes(symbol)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.edl").write_bytes(symbol)
    return tmp_path


def _symbol_node(symbol_file, **kwargs):
    """Convert symbol_two_state.edl with its symbol ``file`` replaced; return the symbol's group."""
    data = (EDM_FIXTURES / "symbol_two_state.edl").read_bytes()
    assert b'file "symbol_states"' in data
    data = data.replace(b'file "symbol_states"', f'file "{symbol_file}"'.encode())
    return react.convert_bytes(data, kind="edl", filename="upload.edl", **kwargs).root.children[0]


def _state_groups(node):
    return [child for child in node.children if child.type == "group"]


def _rejected(node):
    return node.children == [] and any("outside the search paths" in w for w in node.warnings)


def test_confine_file_refs_rejects_absolute_paths(symbol_tree):
    """An absolute symbol path is never read when confined, even one inside a search path."""
    root = symbol_tree / "root"
    for target in (symbol_tree / "outside" / "secret", root / "sub" / "symbol_states"):
        node = _symbol_node(target.as_posix(), search_paths=[root], confine_file_refs=True)
        assert _rejected(node), node.warnings


def test_confine_file_refs_rejects_parent_escape(symbol_tree):
    """``..`` that leaves the search path is rejected before any existence check, so a
    missing target gets the same warning (no probing for files outside the roots)."""
    root = symbol_tree / "root"
    for name in ("../outside/secret", "sub/../../outside/secret", "../outside/no_such_file"):
        assert _rejected(_symbol_node(name, search_paths=[root], confine_file_refs=True)), name


def test_confine_file_refs_rejects_symlink_out_of_search_path(symbol_tree):
    """A symlink under a search path that points outside every root is not followed.
    The display's own dir gives ``link/secret`` an in-bounds candidate that does not
    exist, so the warning is the plain "not found" one."""
    root = symbol_tree / "root"
    try:
        (root / "link").symlink_to(symbol_tree / "outside", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not available")
    assert len(_state_groups(_symbol_node("link/secret", search_paths=[root]))) == 2
    confined = _symbol_node("link/secret", search_paths=[root], confine_file_refs=True)
    assert confined.children == []
    assert any("symbol file 'link/secret.edl' not found" in w for w in confined.warnings)


def test_confine_file_refs_resolves_subdir_symbol(symbol_tree):
    """Relative paths that stay inside a search path (EDM's usual subdir form) still resolve."""
    root = symbol_tree / "root"
    for name in ("sub/symbol_states", "sub/../sub/symbol_states"):
        node = _symbol_node(name, search_paths=[symbol_tree / "outside", root], confine_file_refs=True)
        assert len(_state_groups(node)) == 2, name
        assert not any("symbol file" in w for w in node.warnings)


def test_confine_file_refs_reads_parent_reference_between_search_paths(symbol_tree):
    """``..`` may leave the search path it was joined to when it lands inside another
    one (SLAC displays use ``../pps/...``): with [root/lcls, root], ``../pps/sym``
    joined to root/lcls is root/pps/sym.edl."""
    root = symbol_tree / "root"
    (root / "lcls").mkdir()
    (root / "pps").mkdir()
    (root / "pps" / "sym.edl").write_bytes(SYMBOL_FILE.read_bytes())

    node = _symbol_node("../pps/sym", search_paths=[root / "lcls", root], confine_file_refs=True)
    assert len(_state_groups(node)) == 2
    assert not any("symbol file" in w for w in node.warnings)
    # Without root among the search paths the same name lands outside every root.
    assert _rejected(_symbol_node("../pps/sym", search_paths=[root / "lcls"], confine_file_refs=True))


def test_confine_file_refs_missing_in_bounds_symbol_is_not_found(symbol_tree):
    """A name that resolves inside some root but is not there is "not found", even when
    it leaves the other roots; "outside" is only for names no root can hold."""
    root = symbol_tree / "root"
    (root / "lcls").mkdir()
    for name in ("../sub/no_such_file", "no_such_file"):
        node = _symbol_node(name, search_paths=[root / "lcls", root], confine_file_refs=True)
        assert node.children == []
        assert any(f"symbol file '{name}.edl' not found" in w for w in node.warnings), name
        assert not any("outside the search paths" in w for w in node.warnings), name


def test_confine_file_refs_empty_search_path_is_not_the_cwd(symbol_tree, monkeypatch):
    """An empty search_paths entry is dropped, not read as "." (the CWD)."""
    monkeypatch.chdir(symbol_tree / "outside")
    node = _symbol_node("secret", search_paths=[""], confine_file_refs=True)
    assert node.children == []
    assert any("symbol file 'secret.edl' not found" in w for w in node.warnings)
    # A caller who means the CWD passes ".".
    assert len(_state_groups(_symbol_node("secret", search_paths=["."], confine_file_refs=True))) == 2


def test_confine_file_refs_skips_edmdatafiles(symbol_tree, monkeypatch):
    """Confined lookups search only the display's dir and search_paths: not $EDMDATAFILES,
    and not its "." (CWD) default."""
    monkeypatch.setenv("EDMDATAFILES", str(symbol_tree / "outside"))
    assert len(_state_groups(_symbol_node("secret"))) == 2
    confined = _symbol_node("secret", confine_file_refs=True)
    assert confined.children == []
    assert any("symbol file 'secret.edl' not found" in w for w in confined.warnings)

    monkeypatch.delenv("EDMDATAFILES")
    monkeypatch.chdir(symbol_tree / "outside")
    assert len(_state_groups(_symbol_node("secret"))) == 2
    assert _symbol_node("secret", confine_file_refs=True).children == []


def test_symbol_files_unconfined_by_default(symbol_tree):
    """Without the flag (CLI and PyDM target) absolute and ``..`` symbol paths resolve as in EDM."""
    root = symbol_tree / "root"
    for name in ((symbol_tree / "outside" / "secret").as_posix(), "../outside/secret"):
        node = _symbol_node(name, search_paths=[root])
        assert len(_state_groups(node)) == 2, name
        assert not any("symbol file" in w for w in node.warnings)


# --- symbol files that include themselves are not expanded again ----------------

INCLUDES_ITSELF = "includes itself (directly or through another symbol); symbol not rendered"


def _symbol_object(symbol_file):
    """symbol_two_state.edl's activeSymbolClass object with its ``file`` set to ``symbol_file``."""
    text = SYMBOL_DISPLAY.read_text(encoding="utf-8")
    return text[text.index("# (Symbol)\n") :].replace('file "symbol_states"', f'file "{symbol_file}"')


def _display_of(*symbol_files):
    """symbol_two_state.edl with one symbol object per name in ``symbol_files``."""
    text = SYMBOL_DISPLAY.read_text(encoding="utf-8")
    header = text[: text.index("# (Symbol)\n")]
    return (header + "\n".join(_symbol_object(name) for name in symbol_files)).encode()


def _symbol_including(symbol_file):
    """The two-state symbol file with a symbol of ``symbol_file`` added to its first state group."""
    text = SYMBOL_FILE.read_text(encoding="utf-8")
    assert text.count("# (Rectangle)\n") == 1
    return text.replace("# (Rectangle)\n", _symbol_object(symbol_file) + "\n# (Rectangle)\n").encode()


def _all_warnings(node):
    return [*node.warnings, *(w for child in node.children for w in _all_warnings(child))]


@pytest.mark.parametrize("confine", [False, True])
def test_symbol_file_including_itself_is_not_expanded(confine):
    """An upload staged as upload.edl whose symbol is ``file "upload"`` names itself (the
    staging dir is the display's dir): a placeholder, not a RecursionError."""
    node = _symbol_node("upload", confine_file_refs=confine)
    assert node.children == []
    assert f"EDM symbol file 'upload.edl' {INCLUDES_ITSELF}" in node.warnings


@pytest.mark.parametrize("confine", [False, True])
def test_symbol_cycle_through_another_symbol_is_not_expanded(tmp_path, confine):
    """a.edl shows b.edl, which shows a.edl again: that inner a.edl is a placeholder."""
    (tmp_path / "a.edl").write_bytes(_symbol_including("b"))
    (tmp_path / "b.edl").write_bytes(_symbol_including("a"))
    node = _symbol_node("a", search_paths=[tmp_path], confine_file_refs=confine)
    assert len(_state_groups(node)) == 2
    assert f"EDM symbol file 'a.edl' {INCLUDES_ITSELF}" in _all_warnings(node)


@pytest.mark.parametrize("confine", [False, True])
def test_symbol_cut_short_as_recursive_still_renders_at_top_level(tmp_path, confine):
    """The cycle check runs per use against the symbols being expanded, and its outcome
    is not cached: a symbol used twice that includes itself renders both times."""
    (tmp_path / "loop.edl").write_bytes(_symbol_including("loop"))
    ir = react.convert_bytes(
        _display_of("loop", "loop"),
        kind="edl",
        filename="upload.edl",
        search_paths=[tmp_path],
        confine_file_refs=confine,
    )
    assert len(ir.root.children) == 2
    for node in ir.root.children:
        assert len(_state_groups(node)) == 2
        assert not any("includes itself" in w for w in node.warnings)
        assert f"EDM symbol file 'loop.edl' {INCLUDES_ITSELF}" in _all_warnings(node)


def test_symbol_found_on_an_absolute_edmdatafiles_list(symbol_tree, monkeypatch):
    """EDMDATAFILES lists absolute directories joined with ":"; a symbol in the second one is found."""
    (symbol_tree / "empty").mkdir()
    monkeypatch.setenv("EDMDATAFILES", f"{symbol_tree / 'empty'}:{symbol_tree / 'outside'}")
    node = _symbol_node("secret", confine_file_refs=False)
    assert len(_state_groups(node)) == 2
    assert not any("symbol file" in w for w in node.warnings)


def test_symbol_found_on_an_edmdatafiles_default_entry(symbol_tree, monkeypatch):
    """A leading "=" marks EDM's default directory; the directory after it is searched."""
    monkeypatch.setenv("EDMDATAFILES", f"={symbol_tree / 'outside'}")
    node = _symbol_node("secret", confine_file_refs=False)
    assert len(_state_groups(node)) == 2
    assert not any("symbol file" in w for w in node.warnings)


def test_edmdatafiles_url_entry_is_not_split_into_local_directories(symbol_tree, monkeypatch):
    """An http:// entry is not split on its "://", so "http" (here a dir in the CWD) is
    not searched."""
    (symbol_tree / "http").mkdir()
    (symbol_tree / "http" / "secret.edl").write_bytes((symbol_tree / "outside" / "secret.edl").read_bytes())
    monkeypatch.chdir(symbol_tree)
    monkeypatch.setenv("EDMDATAFILES", "http://example.invalid/displays")
    node = _symbol_node("secret", confine_file_refs=False)
    assert _state_groups(node) == []
    assert any("'secret.edl' not found" in w for w in node.warnings), node.warnings
