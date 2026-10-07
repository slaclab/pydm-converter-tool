from pydmconverter.edm.converter_helpers import convert_attribute_value, parse_edm_macros
from pydmconverter.edm.menumux import add_menumux_indices
from pydmconverter.edm.parser import EDMObject
from pydmconverter.widgets import PyDMRelatedDisplayButton, PyDMShellCommand


class TestParseEdmMacros:
    """Tests for parse_edm_macros function"""

    def test_simple_macro(self):
        """Test parsing a simple macro with one key-value pair"""
        result = parse_edm_macros("DEVICE=IOC:SYS0:1")
        assert result == {"DEVICE": "IOC:SYS0:1"}

    def test_multiple_macros(self):
        """Test parsing multiple macro key-value pairs"""
        result = parse_edm_macros("P=CAMR:LI20:110,R=:ASYN")
        assert result == {"P": "CAMR:LI20:110", "R": ":ASYN"}

    def test_macro_with_spaces(self):
        """Test parsing macros with spaces around delimiters"""
        result = parse_edm_macros("P = CAMR:LI20:110 , R = :ASYN")
        assert result == {"P": "CAMR:LI20:110", "R": ":ASYN"}

    def test_macro_with_quoted_values(self):
        """Test parsing macros with quoted values"""
        result = parse_edm_macros('P="CAMR:LI20:110",R=":ASYN"')
        assert result == {"P": "CAMR:LI20:110", "R": ":ASYN"}

    def test_macro_with_single_quotes(self):
        """Test parsing macros with single quoted values"""
        result = parse_edm_macros("P='CAMR:LI20:110',R=':ASYN'")
        assert result == {"P": "CAMR:LI20:110", "R": ":ASYN"}

    def test_macro_with_equals_in_value(self):
        """Test parsing macros where value contains '=' character"""
        result = parse_edm_macros("FORMULA=A=B+C,DEVICE=IOC:SYS0:1")
        assert result == {"FORMULA": "A=B+C", "DEVICE": "IOC:SYS0:1"}

    def test_empty_string(self):
        """Test parsing an empty string"""
        result = parse_edm_macros("")
        assert result == {}

    def test_whitespace_only(self):
        """Test parsing a string with only whitespace"""
        result = parse_edm_macros("   ")
        assert result == {}

    def test_none_input(self):
        """Test parsing None input"""
        result = parse_edm_macros(None)
        assert result == {}

    def test_non_string_input(self):
        """Test parsing non-string input"""
        result = parse_edm_macros(123)
        assert result == {}

    def test_macro_with_empty_value(self):
        """Test parsing macro with empty value"""
        result = parse_edm_macros("P=,R=:ASYN")
        assert result == {"P": "", "R": ":ASYN"}

    def test_macro_without_equals(self):
        """Test parsing invalid macro without equals sign (should be skipped with warning)"""
        result = parse_edm_macros("INVALID,P=CAMR:LI20:110")
        assert result == {"P": "CAMR:LI20:110"}
        # The invalid entry should be skipped

    def test_complex_macro(self):
        """Test parsing a complex macro string with multiple special characters"""
        result = parse_edm_macros("PREFIX=IOC:SYS0:1,SUFFIX=:ASYN:PORT,INDEX=0")
        assert result == {
            "PREFIX": "IOC:SYS0:1",
            "SUFFIX": ":ASYN:PORT",
            "INDEX": "0",
        }

    def test_macro_with_colons_and_underscores(self):
        """Test parsing macros with colons and underscores in values"""
        result = parse_edm_macros("P=CAMR:LI20:110:TEST_VALUE,R=:ASYN_PORT:1")
        assert result == {"P": "CAMR:LI20:110:TEST_VALUE", "R": ":ASYN_PORT:1"}

    def test_macro_with_numbers(self):
        """Test parsing macros with numbers in keys and values"""
        result = parse_edm_macros("PV1=IOC:SYS0:1,PV2=IOC:SYS0:2")
        assert result == {"PV1": "IOC:SYS0:1", "PV2": "IOC:SYS0:2"}


class TestIndexedArrayConsumers:
    """Consumers of EDM array properties, whose omitted entries the parser fills with ""."""

    def test_blank_menu_label_takes_its_file_name(self):
        """An omitted label falls back to its entry's file instead of shifting the rest up."""
        obj = EDMObject(
            name="relatedDisplayClass",
            properties={"displayFileName": ["first.edl", "second", "third.edl"], "menuLabel": ["", "Two", "\x18"]},
        )
        widget = PyDMRelatedDisplayButton(name="related")
        titles = convert_attribute_value("menuLabel", obj.properties["menuLabel"], widget, obj, {})
        assert titles == ["first.ui", "Two", "third.ui"]

    def test_blank_command_label_takes_its_command(self):
        obj = EDMObject(name="shellCmdClass", properties={"command": ["viewer.bash", "firefox"]})
        widget = PyDMShellCommand(name="shell")
        assert convert_attribute_value("commandLabel", ["", "Grafana"], widget, obj, {}) == ["viewer.bash", "Grafana"]

    def test_all_blank_labels_are_dropped(self):
        obj = EDMObject(name="relatedDisplayClass", properties={"displayFileName": ["a", "b"]})
        widget = PyDMRelatedDisplayButton(name="related")
        assert convert_attribute_value("menuLabel", ["", "\x18"], widget, obj, {}) is None

    def test_related_display_keeps_empty_file_entries_in_place(self):
        """PyDM skips an empty file by position; ".ui" would be a real (missing) file."""
        widget = PyDMRelatedDisplayButton(name="related")
        widget.displayFileName = ["", "b.edl"]
        filenames = next(p for p in widget.generate_properties() if p.get("name") == "filenames")
        assert [s.text or "" for s in filenames.iter("string")] == ["", "b.ui"]

    def test_menumux_pads_items_omitted_at_the_end(self):
        """value0 and symbolTag stop early when their last entries are empty."""
        obj = EDMObject(
            name="menuMuxClass",
            properties={
                "numItems": "3",
                "symbolTag": ["A", "B"],
                "symbol0": ["", "SECT"],
                "value0": ["LI21", "LI22"],
            },
        )
        add_menumux_indices([obj])
        assert obj.properties["symbolTag"] == ["A", "B", ""]
        assert obj.properties["symbolIndices"] == [["SECT", "SECT"]]
        assert obj.properties["valueIndices"] == [["LI21", "LI22", ""]]
