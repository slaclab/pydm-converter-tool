import os
import pytest
import tempfile
import textwrap

from src.edm.parser_helpers import (
    search_calc_list,
    parse_calc_list,
    parse_calc_pv,
    apply_rewrite_rule,
    translate_calc_pv_to_pydm,
    loc_conversion,
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
    assert "calc://inline_expr?" in pydm_inline
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

    edm_string_missing_equals = "LOC\\noEquals"
    with pytest.raises(ValueError):
        loc_conversion(edm_string_missing_equals)

    edm_string_missing_colon = "LOC\\noColon=i"
    with pytest.raises(ValueError):
        loc_conversion(edm_string_missing_colon)
