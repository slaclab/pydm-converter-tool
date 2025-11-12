import os
import pytest
import tempfile
import textwrap
from unittest.mock import patch

from pydmconverter.edm.parser_helpers import (
    search_calc_list,
    parse_calc_list,
    parse_calc_pv,
    apply_rewrite_rule,
    translate_calc_pv_to_pydm,
    loc_conversion,
    replace_calc_and_loc_in_edm_content,
    parse_colors_list,
    search_color_list,
)


def test_search_calc_list(tmp_path, monkeypatch):
    """
    Test that search_calc_list returns the local directory if calc.list
    exists there, otherwise checks EDMFILES.
    """
    fake_file = tmp_path / "fake.edl"
    fake_file.touch()

    local_calc_list = tmp_path / "calc.list"
    local_calc_list.touch()

    result = search_calc_list(str(fake_file))
    assert result == str(tmp_path), "Expected to find local calc.list in the directory."

    local_calc_list.unlink()
    global_calc_dir = tempfile.mkdtemp()
    global_calc_list = os.path.join(global_calc_dir, "calc.list")
    with open(global_calc_list, "w") as f:
        f.write("# Global calc.list")

    monkeypatch.setenv("EDMFILES", global_calc_dir)
    result = search_calc_list(str(fake_file))
    assert result == global_calc_list, "Expected to find calc.list in EDMFILES path."

    monkeypatch.delenv("EDMFILES", raising=False)
    result = search_calc_list(str(fake_file))
    assert result is None, "Expected None if no calc.list is found."


def test_parse_calc_list(tmp_path):
    """
    Test that parse_calc_list correctly parses a calc.list file, ignoring comments
    and empty lines, and properly retrieves the calc_name, rewrite_rule, and expression.
    """
    content = textwrap.dedent("""
        # This is a comment
        sum
        @$(A),$(A).SEVR
        A+B

        difference
        # Just a comment in between
        A-B
    """).strip()

    calc_list_file = tmp_path / "calc.list"
    with open(calc_list_file, "w") as f:
        f.write(content)

    calc_dict = parse_calc_list(str(calc_list_file))

    assert len(calc_dict) == 2, "Expected two calculations parsed."

    sum_rewrite, sum_expr = calc_dict["sum"]
    assert sum_rewrite == "$(A),$(A).SEVR"
    assert sum_expr == "A+B"

    diff_rewrite, diff_expr = calc_dict["difference"]
    assert diff_rewrite is None, "Expected None rewrite rule for 'difference'."
    assert diff_expr == "A-B"


def test_parse_calc_pv():
    """
    Test parse_calc_pv with both a named calc and an inline expression.
    """
    edm_pv_named = "CALC\\sum(pv1, pv2)"
    name_or_expr, arg_list, is_inline = parse_calc_pv(edm_pv_named)
    assert name_or_expr == "sum", "Should parse the calc name as 'sum'."
    assert arg_list == ["pv1", "pv2"], "Should parse arguments correctly."
    assert is_inline is False, "Should be recognized as a named calc, not inline."

    edm_pv_inline = "CALC\\{A+B}(pvX, pvY)"
    name_or_expr, arg_list, is_inline = parse_calc_pv(edm_pv_inline)
    assert name_or_expr == "A+B", "Should parse the inline expression."
    assert arg_list == ["pvX", "pvY"], "Should parse arguments correctly."
    assert is_inline is True, "Should recognize the inline curly brace syntax."


def test_apply_rewrite_rule():
    """
    Test apply_rewrite_rule expands placeholders correctly.
    """
    rewrite = "$(A),$(A).SEVR"
    args = ["myPV"]
    result = apply_rewrite_rule(rewrite, args)
    assert result == ["myPV", "myPV.SEVR"], "Rewrite rule did not expand placeholders as expected."

    rewrite2 = "$(A),$(B),$(A).SEVR"
    args2 = ["firstPV", "secondPV"]
    result2 = apply_rewrite_rule(rewrite2, args2)
    assert result2 == ["firstPV", "secondPV", "firstPV.SEVR"]


def test_translate_calc_pv_to_pydm():
    """
    Test translate_calc_pv_to_pydm handles both inline and named calc, with or
    without rewrite rules.
    """
    calc_dict = {
        "sum": ("$(A),$(A).SEVR", "A+B"),
        "sub": (None, "A-B"),
    }

    edm_pv_named = "CALC\\sum(pv1)"
    pydm_pv = translate_calc_pv_to_pydm(edm_pv_named, calc_dict, default_prefix="pva://")
    assert "calc://sum?" in pydm_pv
    assert "A=pva://pv1" in pydm_pv
    assert "B=pva://pv1.SEVR" in pydm_pv
    assert "expr=A+B" in pydm_pv

    edm_pv_named_no_rewrite = "CALC\\sub(myPV1, myPV2)"
    pydm_pv_no_rewrite = translate_calc_pv_to_pydm(edm_pv_named_no_rewrite, calc_dict, default_prefix="pva://")
    assert "calc://sub?" in pydm_pv_no_rewrite
    assert "A=pva://myPV1" in pydm_pv_no_rewrite
    assert "B=pva://myPV2" in pydm_pv_no_rewrite
    assert "expr=A-B" in pydm_pv_no_rewrite

    edm_pv_inline = "CALC\\{A*B}(x, y)"
    pydm_inline = translate_calc_pv_to_pydm(edm_pv_inline, default_prefix="pva://")
    # Inline expressions now use hash-based identifiers for uniqueness
    assert "calc://calc_" in pydm_inline
    assert "A=pva://x" in pydm_inline
    assert "B=pva://y" in pydm_inline
    assert "expr=A*B" in pydm_inline


def test_loc_conversion():
    """
    Test loc_conversion from LOC to loc:// syntax with type mapping and init values.
    """
    edm_string = "LOC\\myLocal=i:123"
    result = loc_conversion(edm_string)
    assert result.startswith("loc://myLocal?type=int&init=123"), f"Unexpected loc_conversion result: {result}"

    edm_string_float = "LOC\\myFloat=d:3.14"
    result_float = loc_conversion(edm_string_float)
    assert "loc://myFloat?type=float&init=3.14" in result_float

    edm_string_enum = "LOC\\myEnum=e:2"
    result_enum = loc_conversion(edm_string_enum)
    assert "loc://myEnum?type=int&init=2" in result_enum

    edm_string_invalid = "LOC\\myBadType=x:0"
    with pytest.raises(ValueError):
        loc_conversion(edm_string_invalid)

    # When equals sign is missing, the function returns a simple loc:// reference
    edm_string_missing_equals = "LOC\\noEquals"
    result_no_equals = loc_conversion(edm_string_missing_equals)
    assert result_no_equals == "loc://noEquals", f"Expected 'loc://noEquals', got '{result_no_equals}'"

    # When colon is missing but value is 'i', it should be treated as a type char without value
    edm_string_missing_colon = "LOC\\noColon=i"
    result_no_colon = loc_conversion(edm_string_missing_colon)
    assert "loc://noColon" in result_no_colon, f"Expected loc://noColon in result, got '{result_no_colon}'"


@pytest.mark.parametrize(
    "edm_content",
    [
        """
    object activeXTextClass {
      controlPv "CALC\\\\sum(pv1, pv2)"
    }
    object activeXTextClass {
      controlPv "CALC\\\\sum(pv1, pv2)"
    }
    object activeXTextClass {
      controlPv "CALC\\\\{A-B}(anotherPv, 10.5)"
    }
    object activeXTextClass {
      controlPv "LOC\\myLocal=d:3.14"
    }
    object activeXTextClass {
      controlPv "LOC\\myLocal=d:3.14"
    }
    object activeXTextClass {
      controlPv "LOC\\myLocalInt=i:42"
    }
    """
    ],
)
@patch("pydmconverter.edm.parser_helpers.loc_conversion")
@patch("pydmconverter.edm.parser_helpers.translate_calc_pv_to_pydm")
@patch("pydmconverter.edm.parser_helpers.parse_calc_list")
@patch("pydmconverter.edm.parser_helpers.search_calc_list")
def test_replace_calc_and_loc_in_edm_content(
    mock_search_calc_list, mock_parse_calc_list, mock_translate_calc_pv_to_pydm, mock_loc_conversion, edm_content
):
    r"""
    Tests that replace_calc_and_loc_in_edm_content correctly:
      - Finds and replaces CALC\ and LOC\ references.
      - Uses full PyDM strings on first occurrence, short references subsequently.
      - Returns dictionaries for encountered references.
    """
    mock_search_calc_list.return_value = "/fake/path/calc.list"
    mock_parse_calc_list.return_value = {
        "sum": (None, "A+B"),
        "avg": (None, "(A+B)/2"),
    }

    def mock_calc_translate(edm_pv, calc_dict=None):
        if "sum" in edm_pv:
            return "calc://sum?A=channel://pv1&B=channel://pv2&expr=A+B"
        elif "{A-B}" in edm_pv:
            return "calc://inline_expr?A=channel://anotherPv&B=channel://10.5&expr=A-B"
        return "calc://unknown_calc"

    mock_translate_calc_pv_to_pydm.side_effect = mock_calc_translate

    def mock_loc_conv(edm_pv):
        if "LOC\\myLocal=d:3.14" in edm_pv:
            return "loc://myLocal?type=float&init=3.14"
        elif "LOC\\myLocalInt=i:42" in edm_pv:
            return "loc://myLocalInt?type=int&init=42"
        return "loc://unknown_local"

    mock_loc_conversion.side_effect = mock_loc_conv

    new_content, encountered_calcs, encountered_locs = replace_calc_and_loc_in_edm_content(
        edm_content, filepath="/some/fake/edm_file.edl"
    )

    mock_search_calc_list.assert_called_once_with("/some/fake/edm_file.edl")
    mock_parse_calc_list.assert_called_once_with("/fake/path/calc.list")

    assert "calc://sum?A=channel://pv1&B=channel://pv2&expr=A+B" in new_content
    assert "calc://sum" in new_content
    assert "calc://inline_expr?A=channel://anotherPv&B=channel://10.5&expr=A-B" in new_content

    assert "loc://myLocal?type=float&init=3.14" in new_content
    assert "loc://myLocal" in new_content
    assert "loc://myLocalInt?type=int&init=42" in new_content

    assert "CALC\\\\sum(pv1, pv2)" in encountered_calcs
    sum_entry = encountered_calcs["CALC\\\\sum(pv1, pv2)"]
    assert sum_entry["full"] == "calc://sum?A=channel://pv1&B=channel://pv2&expr=A+B"
    assert sum_entry["short"] == "calc://sum"

    assert "CALC\\\\{A-B}(anotherPv, 10.5)" in encountered_calcs
    inline_entry = encountered_calcs["CALC\\\\{A-B}(anotherPv, 10.5)"]
    assert inline_entry["full"] == "calc://inline_expr?A=channel://anotherPv&B=channel://10.5&expr=A-B"
    assert inline_entry["short"] == "calc://inline_expr"

    assert "LOC\\myLocal=d:3.14" in encountered_locs
    myLocal_entry = encountered_locs["LOC\\myLocal=d:3.14"]
    assert myLocal_entry["full"] == "loc://myLocal?type=float&init=3.14"
    assert myLocal_entry["short"] == "loc://myLocal"

    assert "LOC\\myLocalInt=i:42" in encountered_locs
    myLocalInt_entry = encountered_locs["LOC\\myLocalInt=i:42"]
    assert myLocalInt_entry["full"] == "loc://myLocalInt?type=int&init=42"
    assert myLocalInt_entry["short"] == "loc://myLocalInt"


@pytest.fixture
def colors_list_file():
    """
    Pytest fixture that creates a temporary file with mock EDM color file content,
    then yields the file path, and finally cleans up the file.
    """
    mock_content = """\
4 0 0

# Global settings
blinkms=750
max=0x10000
columns=5

# Aliases
alias trace0 red
alias trace1 green

# Static colors
static 25 Controller { 0 0 65535 }
static 26 "blinking red" { 65535 0 0 41120 0 0 }

# Another static color with hex values
static 27 "dark green" { 0xafff 0xafff 0 }

# Rule definition
rule 100 exampleRule {
 =100 || =200 : strange
 >=20         : invisible
 >0 && <10    : red
 >=10 && <20  : "blinking red"
 default      : green
}

# Menumap
menumap {
  "blinking red"
  Controller
  "dark green"
}

# Alarm
alarm {
  disconnected : "dark green"
  invalid      : "blinking red"
  minor        : Controller
  major        : red
  noalarm      : *
}
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
        filepath = tmp_file.name
        tmp_file.write(mock_content)
        tmp_file.flush()

    yield filepath

    os.remove(filepath)


def test_parse_colors_list_complex(colors_list_file):
    """
    Test that parse_colors_list correctly parses a complex EDM colors.list file.
    """
    parsed = parse_colors_list(colors_list_file)

    print(parsed)
    assert parsed["version"]["major"] == 4
    assert parsed["version"]["minor"] == 0
    assert parsed["version"]["release"] == 0

    assert parsed["blinkms"] == 750
    assert parsed["columns"] == 5
    assert parsed["max"] == 0x10000

    assert "trace0" in parsed["alias"]
    assert parsed["alias"]["trace0"] == "red"
    assert "trace1" in parsed["alias"]
    assert parsed["alias"]["trace1"] == "green"

    assert 25 in parsed["static"]
    assert parsed["static"][25]["name"] == "Controller"
    assert parsed["static"][25]["rgb"] == [0, 0, 65535]

    assert 26 in parsed["static"]
    assert parsed["static"][26]["name"] == "blinking red"
    assert parsed["static"][26]["rgb"] == [65535, 0, 0, 41120, 0, 0]

    assert 27 in parsed["static"]
    assert parsed["static"][27]["name"] == "dark green"
    assert parsed["static"][27]["rgb"] == [45055, 45055, 0]

    assert 100 in parsed["rules"]
    rule_data = parsed["rules"][100]
    assert rule_data["name"] == "exampleRule"
    conditions = rule_data["conditions"]

    assert len(conditions) == 5
    assert conditions[0]["condition"] == "=100 || =200"
    assert conditions[0]["color"] == "strange"
    assert conditions[-1]["condition"] == "default"
    assert conditions[-1]["color"] == "green"

    assert parsed["menumap"] == ["blinking red", "Controller", "dark green"]

    assert parsed["alarm"]["disconnected"] == "dark green"
    assert parsed["alarm"]["invalid"] == "blinking red"
    assert parsed["alarm"]["minor"] == "Controller"
    assert parsed["alarm"]["major"] == "red"
    assert parsed["alarm"]["noalarm"] == "*"


@pytest.fixture
def clear_env(monkeypatch):
    """
    Fixture to clear relevant environment variables before each test
    so they don't interfere with each other.
    """
    monkeypatch.delenv("EDMCOLORFILE", raising=False)
    monkeypatch.delenv("EDMFILES", raising=False)


def test_cli_argument_valid(monkeypatch, clear_env):
    """
    If cli_color_file is provided and the file exists, it should return immediately.
    """
    test_path = "/some/cli/path/colors.list"
    monkeypatch.setattr(os.path, "isfile", lambda path: path == test_path)

    result = search_color_list(cli_color_file=test_path)
    assert result == test_path, "Should return the CLI path if it exists"


def test_cli_argument_invalid(monkeypatch, clear_env):
    """
    If cli_color_file is provided but the file doesn't exist,
    it should ignore and proceed to check environment variables or defaults.
    """
    test_path = "/some/cli/path/does_not_exist.list"
    monkeypatch.setattr(os.path, "isfile", lambda path: False)

    result = search_color_list(cli_color_file=test_path)
    assert result is None, "Should return None if CLI file is invalid and no other fallback exists"


def test_env_edmcolorfile_valid(monkeypatch, clear_env):
    """
    If EDMCOLORFILE is set and points to an existing file, it should be used.
    """
    env_path = "/env/path/edm_color_file.list"

    monkeypatch.setenv("EDMCOLORFILE", env_path)
    monkeypatch.setattr(os.path, "isfile", lambda path: path == env_path)

    result = search_color_list()
    assert result == env_path, "Should return the EDMCOLORFILE path if it exists"


def test_env_edmcolorfile_invalid(monkeypatch, clear_env):
    """
    If EDMCOLORFILE is set but the file doesn't exist,
    it should ignore it and check EDMFILES or default next.
    """
    env_path = "/env/path/does_not_exist.list"
    monkeypatch.setenv("EDMCOLORFILE", env_path)
    monkeypatch.setattr(os.path, "isfile", lambda path: False)

    result = search_color_list()
    assert result is None, "Should return None if EDMCOLORFILE is invalid and no fallback exists"


def test_env_edmfiles_valid(monkeypatch, clear_env):
    """
    If EDMFILES is set, we look for `colors.list` in that directory.
    """
    env_dir = "/some/env/directory"
    candidate_path = os.path.join(env_dir, "colors.list")

    monkeypatch.setenv("EDMFILES", env_dir)
    monkeypatch.setattr(os.path, "isfile", lambda path: path == candidate_path)

    result = search_color_list()
    assert result == candidate_path, "Should return /some/env/directory/colors.list if it exists"


def test_env_edmfiles_invalid(monkeypatch, clear_env):
    """
    If EDMFILES is set but `colors.list` doesn't exist in that directory,
    it should ignore it and check the default path.
    """
    env_dir = "/some/env/directory"

    monkeypatch.setenv("EDMFILES", env_dir)
    monkeypatch.setattr(os.path, "isfile", lambda path: False)

    result = search_color_list()
    assert result is None, "Should return None if EDMFILES and EDMCOLORFILE are invalid and no default exists"


def test_default_valid(monkeypatch, clear_env):
    """
    If no CLI argument and no valid environment variables exist,
    the function checks /etc/edm/colors.list by default.
    """
    default_path = "/etc/edm/colors.list"
    monkeypatch.setattr(os.path, "isfile", lambda path: path == default_path)

    result = search_color_list()
    assert result == default_path, "Should return the default path if it exists"


def test_default_invalid(monkeypatch, clear_env):
    """
    If there's no CLI argument, no valid environment variables, and the default doesn't exist,
    the function should return None.
    """
    monkeypatch.setattr(os.path, "isfile", lambda path: False)

    result = search_color_list()
    assert result is None, "Should return None if nothing else is found"
