"""Tests for the D1 color-scheme flattener, :func:`pydmconverter.scheme.load_scheme`."""

import hashlib
import json
from pathlib import Path

import pytest

from pydmconverter.scheme import DEFAULT_SCHEME_PATH, SchemeResult, load_scheme

PACKAGED_SHA256 = "0a8f403e70f0b9a5dc2eb9679da24f72f54209e19a8a9043d3de636e49ce810d"
DEFAULT = json.loads(DEFAULT_SCHEME_PATH.read_text(encoding="utf-8"))
DEFAULT_ROLES = list(DEFAULT["roles"])


def write(tmp_path: Path, doc, name: str = "facility.json") -> Path:
    path = tmp_path / name
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return path


def role(result: SchemeResult, name: str) -> tuple[str, str]:
    i = result.flat["roles"].index(name)
    return result.flat["light"][i], result.flat["dark"][i]


def error_paths(result: SchemeResult) -> list[str]:
    return [e["path"] for e in result.meta["errors"]]


def assert_serves_default(result: SchemeResult) -> None:
    default = load_scheme(None)
    assert result.meta["served"] == "canopy-default"
    assert result.flat == default.flat
    assert result.imports == default.imports
    assert result.meta["flatHash"] == default.meta["flatHash"]


# -- no facility file ----------------------------------------------------------------------------------------------


def test_no_file_meta_is_pinned_default():
    result = load_scheme(None)
    assert result.meta["id"] == "canopy-default"
    assert result.meta["served"] == "canopy-default"
    assert result.meta["sha256"] == PACKAGED_SHA256
    assert result.meta["errors"] == []
    assert isinstance(result.meta["flatHash"], str) and result.meta["flatHash"]


def test_no_file_flat_matches_packaged_default():
    result = load_scheme(None)
    assert result.flat["roles"] == DEFAULT_ROLES
    for name, value in DEFAULT["roles"].items():
        assert role(result, name) == (value["light"], value["dark"])
    assert result.imports == DEFAULT["import"]


def test_no_file_with_custom_base_path_hashes_that_base(tmp_path):
    base = write(tmp_path, {"id": "canopy-default", "roles": {"A": "#ABC"}, "import": {"edm": {"x": "A"}}}, "base.json")
    result = load_scheme(None, base_path=base)
    assert result.meta["sha256"] == hashlib.sha256(base.read_bytes()).hexdigest()
    assert result.meta["errors"] == []
    assert result.flat == {"roles": ["A"], "light": ["#aabbcc"], "dark": ["#aabbcc"]}
    assert result.imports == {"phoebus": {}, "edm": {"x": "A"}}


def test_flat_json_is_flat_plus_meta_and_serialisable():
    result = load_scheme(None)
    out = result.flat_json()
    assert set(out) == {"roles", "light", "dark", "meta"}
    assert out["meta"] == result.meta
    json.dumps(out)
    out["roles"].append("mutated")
    assert "mutated" not in result.flat["roles"]


def test_flat_lists_are_parallel_and_canonical():
    flat = load_scheme(None).flat
    assert len(flat["roles"]) == len(flat["light"]) == len(flat["dark"]) == len(set(flat["roles"]))


# -- extends and merging --------------------------------------------------------------------------------------------


def test_missing_extends_flattens_like_explicit_extends(tmp_path):
    doc = {"id": "fac", "roles": {"OK": "#00ff00", "Extra": {"light": "#111", "dark": "#222"}}}
    implicit = load_scheme(write(tmp_path, doc, "a.json"))
    explicit = load_scheme(write(tmp_path, {**doc, "extends": "canopy-default"}, "b.json"))
    assert implicit.meta["errors"] == [] and explicit.meta["errors"] == []
    assert implicit.flat == explicit.flat
    assert implicit.imports == explicit.imports
    assert implicit.meta["flatHash"] == explicit.meta["flatHash"]


def test_extends_other_than_canopy_default_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "extends": "other", "roles": {"OK": "#000"}}))
    assert "extends" in error_paths(result)
    assert result.meta["id"] == "fac"
    assert_serves_default(result)


def test_valid_facility_is_served_and_inherits_base(tmp_path):
    path = write(tmp_path, {"id": "facility", "extends": "canopy-default", "roles": {"OK": "#00FF00"}})
    result = load_scheme(path)
    assert result.meta["errors"] == []
    assert result.meta["id"] == "facility"
    assert result.meta["served"] == "facility"
    assert result.meta["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert role(result, "OK") == ("#00ff00", "#00ff00")
    assert role(result, "MAJOR") == (DEFAULT["roles"]["MAJOR"]["light"], DEFAULT["roles"]["MAJOR"]["dark"])
    assert result.flat["roles"] == DEFAULT_ROLES


def test_per_mode_merge_keeps_inherited_mode(tmp_path):
    result = load_scheme(
        write(tmp_path, {"id": "fac", "roles": {"OK": {"dark": "#123456"}, "MAJOR": {"light": "#abc"}}})
    )
    assert result.meta["errors"] == []
    assert role(result, "OK") == (DEFAULT["roles"]["OK"]["light"], "#123456")
    assert role(result, "MAJOR") == ("#aabbcc", DEFAULT["roles"]["MAJOR"]["dark"])


def test_new_roles_append_after_base_in_name_order(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"Zed": "#000", "Alpha": "#fff"}}))
    assert result.flat["roles"] == DEFAULT_ROLES + ["Alpha", "Zed"]


def test_null_import_deletes_inherited_mapping_and_others_merge(tmp_path):
    doc = {
        "id": "fac",
        "import": {"edm": {"invisible": None, "my red": "MAJOR"}, "phoebus": {"OK": "MINOR"}},
    }
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    assert "invisible" not in result.imports["edm"]
    assert result.imports["edm"]["my red"] == "MAJOR"
    assert result.imports["edm"]["GLOBAL canvas"] == "Display_Background"
    assert result.imports["phoebus"]["OK"] == "MINOR"
    assert result.imports["phoebus"]["STOP"] == "STOP"


def test_null_import_of_unknown_key_is_harmless(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "import": {"edm": {"never-there": None}}}))
    assert result.meta["errors"] == []
    assert result.imports == DEFAULT["import"]


def test_import_target_not_a_role_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "import": {"phoebus": {"Foo": "NoSuchRole"}}}))
    assert "import/phoebus/Foo" in error_paths(result)
    assert_serves_default(result)


def test_import_target_may_be_a_new_facility_role(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"Mine": "#010203"}, "import": {"edm": {"m": "Mine"}}}))
    assert result.meta["errors"] == []
    assert result.imports["edm"]["m"] == "Mine"


# -- aliases ---------------------------------------------------------------------------------------------------------


def test_alias_chain_resolves_per_mode(tmp_path):
    doc = {"id": "fac", "roles": {"A": "@B", "B": {"light": "@OK", "dark": "#000000"}, "Text": {"dark": "@A"}}}
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    ok_light = DEFAULT["roles"]["OK"]["light"]
    assert role(result, "A") == (ok_light, "#000000")
    assert role(result, "B") == (ok_light, "#000000")
    assert role(result, "Text") == (DEFAULT["roles"]["Text"]["light"], "#000000")


def test_alias_uses_merged_target_value(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"STOP": "@OK", "OK": "#ABCDEF"}}))
    assert role(result, "STOP") == ("#abcdef", "#abcdef")


def test_alias_cycle_reported_with_path(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"A": {"light": "@B", "dark": "#000"}, "B": "@A"}}))
    errors = result.meta["errors"]
    cycles = [e for e in errors if "cycle" in e["message"]]
    assert len(cycles) == 1
    assert cycles[0]["path"] == "roles/A/light"
    assert "A -> B -> A" in cycles[0]["message"]
    assert_serves_default(result)


def test_self_alias_is_a_cycle(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": "@OK"}}))
    messages = [e["message"] for e in result.meta["errors"]]
    assert any("OK -> OK" in m for m in messages)
    assert {"roles/OK"} == set(error_paths(result))
    assert_serves_default(result)


def test_dangling_alias_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"A": {"light": "#000", "dark": "@Nope"}}}))
    assert error_paths(result) == ["roles/A/dark"]
    assert "Nope" in result.meta["errors"][0]["message"]
    assert_serves_default(result)


# -- hex canonicalisation ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "canonical"),
    [
        ("#ABC", "#aabbcc"),
        ("#a1B2c3", "#a1b2c3"),
        ("#AABBCCFF", "#aabbcc"),
        ("#aabbccff", "#aabbcc"),
        ("#AABBCC80", "#aabbcc80"),
        ("#ffffff00", "#ffffff00"),
    ],
)
def test_hex_is_canonicalised(tmp_path, given, canonical):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"X": given}}))
    assert result.meta["errors"] == []
    assert role(result, "X") == (canonical, canonical)


@pytest.mark.parametrize("bad", ["#ab", "#abcd", "red", "#gggggg", "abcdef"])
def test_bad_hex_is_an_error_with_its_path(tmp_path, bad):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"X": {"light": bad, "dark": "#000"}}}))
    assert error_paths(result) == ["roles/X/light"]
    assert_serves_default(result)


# -- holes and collecting every error -----------------------------------------------------------------------------------


def test_new_role_missing_a_mode_is_a_hole(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"Half": {"light": "#fff"}}}))
    assert error_paths(result) == ["roles/Half/dark"]
    assert "dark" in result.meta["errors"][0]["message"]
    assert_serves_default(result)


def test_empty_role_object_is_a_hole_in_both_modes(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"Empty": {}}}))
    assert sorted(error_paths(result)) == ["roles/Empty/dark", "roles/Empty/light"]


def test_all_errors_are_collected(tmp_path):
    doc = {
        "id": "fac",
        "roles": {
            "Bad": {"light": "#xyz", "dark": "#000"},
            "Dangle": "@Missing",
            "Half": {"dark": "#000"},
            "C1": "@C2",
            "C2": "@C1",
        },
        "import": {"edm": {"e": "Ghost"}},
    }
    result = load_scheme(write(tmp_path, doc))
    paths = set(error_paths(result))
    assert {"roles/Bad/light", "roles/Dangle", "roles/Half/light", "roles/C1", "import/edm/e"} <= paths
    assert result.meta["id"] == "fac"
    assert_serves_default(result)


def test_schema_violations_are_reported(tmp_path):
    result = load_scheme(write(tmp_path, {"roles": {"X": {"light": "#000", "dark": "#000", "dim": "#000"}}, "x": 1}))
    assert result.meta["id"] is None
    messages = " ".join(e["message"] for e in result.meta["errors"])
    assert "id" in messages
    assert len(result.meta["errors"]) >= 3
    assert_serves_default(result)


def test_non_object_document_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, "[1, 2]"))
    assert result.meta["id"] is None
    assert result.meta["errors"]
    assert_serves_default(result)


# -- unreadable and unparseable files ----------------------------------------------------------------------------------


def test_unparseable_file_gives_null_id_and_default(tmp_path):
    path = write(tmp_path, "{ not json")
    result = load_scheme(path)
    assert result.meta["id"] is None
    assert result.meta["served"] == "canopy-default"
    assert result.meta["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(result.meta["errors"]) == 1
    assert_serves_default(result)


def test_missing_file_gives_null_sha256(tmp_path):
    result = load_scheme(tmp_path / "absent.json")
    assert result.meta["sha256"] is None
    assert result.meta["id"] is None
    assert result.meta["served"] == "canopy-default"
    assert len(result.meta["errors"]) == 1
    assert_serves_default(result)


def test_directory_path_is_unreadable(tmp_path):
    result = load_scheme(tmp_path)
    assert result.meta["sha256"] is None
    assert result.meta["errors"]
    assert_serves_default(result)


def test_unreadable_file_gives_null_sha256(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "fac"})
    real = Path.read_bytes

    def deny(self):
        if self == path:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", deny)
    result = load_scheme(path)
    assert result.meta["sha256"] is None
    assert result.meta["id"] is None
    assert result.meta["errors"]
    monkeypatch.undo()
    assert_serves_default(result)


def test_non_utf8_file_is_unparseable(tmp_path):
    path = tmp_path / "latin.json"
    path.write_bytes(b'{"id": "caf\xe9"}')
    result = load_scheme(path)
    assert result.meta["id"] is None
    assert result.meta["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert_serves_default(result)


# -- flatHash ------------------------------------------------------------------------------------------------------------


def test_flat_hash_is_stable_across_key_order(tmp_path):
    roles = {"Zed": "#000", "OK": {"dark": "#111", "light": "#222"}, "Alpha": "@Zed", "Mid": "#abc"}
    reordered = {k: roles[k] for k in reversed(list(roles))}
    reordered["OK"] = {"light": "#222", "dark": "#111"}
    a = load_scheme(write(tmp_path, {"id": "fac", "roles": roles}, "a.json"))
    b = load_scheme(write(tmp_path, {"roles": reordered, "id": "fac"}, "b.json"))
    assert a.meta["errors"] == [] and b.meta["errors"] == []
    assert a.flat == b.flat
    assert a.meta["flatHash"] == b.meta["flatHash"]


def test_flat_hash_changes_with_content(tmp_path):
    a = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": "#000"}}, "a.json"))
    b = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": "#001"}}, "b.json"))
    assert a.meta["flatHash"] != b.meta["flatHash"]
    assert a.meta["flatHash"] != load_scheme(None).meta["flatHash"]


def test_flat_hash_is_deterministic_across_calls():
    assert load_scheme(None).meta["flatHash"] == load_scheme(None).meta["flatHash"]


# -- role sources (phoebus) ------------------------------------------------------------------------------------------

#: flatHash of the vendored canopy-default; sources are not a flat column, so they must never move it.
DEFAULT_FLAT_HASH = "570b18da90319ef309645f8450a4a5a420c39fdc98046bdd2f142d1c74072b93"


def test_default_has_no_sources_and_flat_is_unchanged_by_sources():
    result = load_scheme(None)
    assert result.sources == {}
    assert result.meta["flatHash"] == DEFAULT_FLAT_HASH
    out = result.flat_json()
    assert set(out) == {"roles", "light", "dark", "meta"}
    assert "phoebus" not in out and "sources" not in out


def test_source_is_collected_and_canonicalised(tmp_path):
    doc = {
        "id": "fac",
        "roles": {"OK": {"phoebus": "#ABC"}, "Mine": {"light": "#010203", "dark": "#040506", "phoebus": "#0A0B0CFF"}},
    }
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    assert result.sources == {"OK": "#aabbcc", "Mine": "#0a0b0c"}
    # A role carrying only a phoebus value keeps its inherited colours.
    assert role(result, "OK") == (DEFAULT["roles"]["OK"]["light"], DEFAULT["roles"]["OK"]["dark"])


def test_sources_do_not_change_flat_or_flat_hash(tmp_path):
    plain = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": "#123456"}}, "a.json"))
    sourced = load_scheme(
        write(
            tmp_path,
            {"id": "fac", "roles": {"OK": {"light": "#123456", "dark": "#123456", "phoebus": "#00ff00"}}},
            "b.json",
        )
    )
    assert sourced.sources == {"OK": "#00ff00"}
    assert plain.flat == sourced.flat
    assert plain.meta["flatHash"] == sourced.meta["flatHash"]
    assert {k: v for k, v in plain.flat_json().items() if k != "meta"} == {
        k: v for k, v in sourced.flat_json().items() if k != "meta"
    }


def test_facility_source_overrides_base_source(tmp_path):
    base = write(
        tmp_path,
        {
            "id": "canopy-default",
            "roles": {"A": {"light": "#111111", "dark": "#222222", "phoebus": "#333333"}, "B": "#444444"},
        },
        "base.json",
    )
    assert load_scheme(None, base_path=base).sources == {"A": "#333333"}
    fac = write(tmp_path, {"id": "fac", "roles": {"A": {"phoebus": "#FFF"}}})
    result = load_scheme(fac, base_path=base)
    assert result.meta["errors"] == []
    assert result.sources == {"A": "#ffffff"}
    # A facility value that omits phoebus inherits the base source, like an omitted mode.
    kept = load_scheme(
        write(tmp_path, {"id": "fac", "roles": {"A": {"light": "#000000"}}}, "kept.json"), base_path=base
    )
    assert kept.sources == {"A": "#333333"}
    # A string value sets both modes but carries no source, so it inherits too.
    stringy = load_scheme(write(tmp_path, {"id": "fac", "roles": {"A": "#000000"}}, "s.json"), base_path=base)
    assert stringy.sources == {"A": "#333333"}


def test_source_on_unknown_role_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"Ghost": {"phoebus": "#123456"}}}))
    paths = error_paths(result)
    assert "roles/Ghost/light" in paths and "roles/Ghost/dark" in paths
    assert_serves_default(result)
    assert result.sources == {}


def test_bad_source_hex_is_an_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": {"phoebus": "@MAJOR"}}}))
    assert "roles/OK/phoebus" in error_paths(result)
    assert_serves_default(result)
    assert result.sources == {}


def test_fallback_serves_base_sources(tmp_path):
    base = write(
        tmp_path,
        {"id": "canopy-default", "roles": {"A": {"light": "#111111", "dark": "#222222", "phoebus": "#333333"}}},
        "base.json",
    )
    result = load_scheme(write(tmp_path, "{not json"), base_path=base)
    assert result.meta["served"] == "canopy-default"
    assert result.sources == {"A": "#333333"}


def test_sources_are_a_copy(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": {"phoebus": "#123456"}}}))
    result.sources["OK"] = "#000000"
    again = load_scheme(write(tmp_path, {"id": "fac", "roles": {"OK": {"phoebus": "#123456"}}}, "b.json"))
    assert again.sources == {"OK": "#123456"}


# -- slot imports ----------------------------------------------------------------------------------------------------


def test_default_keeps_the_grid_slot_import():
    result = load_scheme(None)
    assert result.meta["errors"] == []
    assert result.imports["phoebus"]["Grid"] == {"role": "Grid", "background_color": "Grid_Fill"}
    assert result.imports == DEFAULT["import"]


def test_slot_object_is_merged_and_validated(tmp_path):
    doc = {
        "id": "fac",
        "import": {"phoebus": {"OK": {"role": "OK", "line_color": "MAJOR", "background_color": "MINOR"}}},
    }
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    assert result.imports["phoebus"]["OK"] == {"role": "OK", "line_color": "MAJOR", "background_color": "MINOR"}
    assert result.imports["phoebus"]["STOP"] == "STOP"


def test_bad_slot_target_reports_its_path(tmp_path):
    doc = {"id": "fac", "import": {"phoebus": {"OK": {"role": "OK", "background_color": "NoSuchRole"}}}}
    result = load_scheme(write(tmp_path, doc))
    assert "import/phoebus/OK/background_color" in error_paths(result)
    assert_serves_default(result)


def test_bad_default_slot_role_reports_role_path(tmp_path):
    doc = {"id": "fac", "import": {"edm": {"x": {"role": "Nope", "line_color": "OK"}}}}
    result = load_scheme(write(tmp_path, doc))
    assert error_paths(result) == ["import/edm/x/role"]
    assert_serves_default(result)


def test_slot_object_without_role_is_a_schema_error(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "import": {"phoebus": {"OK": {"line_color": "OK"}}}}))
    assert result.meta["errors"]
    assert_serves_default(result)


def test_string_replaces_inherited_slot_object(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "import": {"phoebus": {"Grid": "Grid_Fill"}}}))
    assert result.meta["errors"] == []
    assert result.imports["phoebus"]["Grid"] == "Grid_Fill"


def test_slot_object_replaces_inherited_string_and_object_whole(tmp_path):
    doc = {"id": "fac", "import": {"phoebus": {"OK": {"role": "MINOR"}, "Grid": {"role": "Grid", "line_color": "OK"}}}}
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    assert result.imports["phoebus"]["OK"] == {"role": "MINOR"}
    # Replaced whole: the inherited background_color slot does not survive.
    assert result.imports["phoebus"]["Grid"] == {"role": "Grid", "line_color": "OK"}


def test_null_deletes_an_inherited_slot_object(tmp_path):
    result = load_scheme(write(tmp_path, {"id": "fac", "import": {"phoebus": {"Grid": None}}}))
    assert result.meta["errors"] == []
    assert "Grid" not in result.imports["phoebus"]


def test_slot_import_may_target_new_facility_role(tmp_path):
    doc = {
        "id": "fac",
        "roles": {"Mine": "#010203"},
        "import": {"phoebus": {"Grid": {"role": "Grid", "background_color": "Mine"}}},
    }
    result = load_scheme(write(tmp_path, doc))
    assert result.meta["errors"] == []
    assert result.imports["phoebus"]["Grid"]["background_color"] == "Mine"


def test_imports_are_a_deep_copy(tmp_path):
    result = load_scheme(None)
    result.imports["phoebus"]["Grid"]["role"] = "OK"
    assert load_scheme(None).imports["phoebus"]["Grid"]["role"] == "Grid"
