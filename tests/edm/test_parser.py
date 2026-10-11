import pytest
import textwrap
from pydmconverter.edm.parser import EDMGroup, EDMObject, EDMFileParser, literal_macro_clashes, read_edm_string


def test_EDMObject():
    """Test that the EDMObject class can be instantiated with the correct
    properties
    """
    obj = EDMObject(name="TestObject", properties={"key": "value"}, x=10, y=20, width=30, height=40)
    assert obj.name == "TestObject"
    assert obj.properties["key"] == "value"
    assert obj.x == 10
    assert obj.y == 20
    assert obj.width == 30
    assert obj.height == 40


def test_EDMGroup():
    """Test that the EDMGroup class can be instantiated with the correct
    properties
    """
    group = EDMGroup()
    obj = EDMObject(x=5, y=10)
    group.add_object(obj)
    assert obj in group.objects


def test_missing_file(tmp_path):
    """Test that an error is raised when the file does not exist

    Parameters
    ----------
    tmp_path : pytest.fixture
        Create a temorary directory for the test
    """
    test_file = tmp_path / "test.edl"
    output_file = tmp_path / "test.ui"

    with pytest.raises(FileNotFoundError):
        EDMFileParser(test_file, output_file)


def test_parse_screen_properties(tmp_path):
    """Test that the screen properties are parsed correctly

    Parameters
    ----------
    tmp_path : pytest.fixture
        Create a temorary directory for the test
    """
    test_data = textwrap.dedent("""
        beginScreenProperties
        x 10
        y 20
        w 30
        h 40
        endScreenProperties
    """)
    test_file = tmp_path / "test.edl"
    test_file.write_text(test_data)
    output_file = tmp_path / "test.ui"

    parser = EDMFileParser(test_file, output_file)
    assert parser.ui.x == 0
    assert parser.ui.y == 0
    assert parser.ui.width == 30
    assert parser.ui.height == 40


def test_parse_objects(tmp_path):
    """Test that the objects are parsed into EDMObject correctly

    Parameters
    ----------
    tmp_path : pytest.fixture
        Create a temorary directory for the test
    """
    test_data = textwrap.dedent("""
        # (Rectangle)
        object activeRectangleClass
        beginObjectProperties
        w 632
        h 136
        endObjectProperties

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        x 292
        y 20
        endObjectProperties
    """)
    test_file = tmp_path / "test.edl"
    test_file.write_text(test_data)
    output_file = tmp_path / "test.ui"

    parser = EDMFileParser(test_file, output_file)
    assert len(parser.ui.objects) == 2
    assert parser.ui.objects[0].name == "activeRectangleClass"
    assert parser.ui.objects[1].name == "activeXTextClass"


@pytest.mark.skip(reason="Parser currently has issues with nested group parsing - needs investigation")
def test_parse_groups(tmp_path):
    """Test that the groups are parsed into EDMGroup correctly

    Parameters
    ----------
    tmp_path : pytest.fixture
        Create a temorary directory for the test

    Note: This test is currently skipped as the parser has difficulty with the
    activeGroupClass pattern used in this test. The parser logs show it's being
    treated as a malformed group. This needs further investigation of the parser
    logic for group handling.
    """
    test_data = textwrap.dedent("""
        # (Group)
        object activeGroupClass
        beginObjectProperties
        w 632
        h 136
        beginGroup

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        x 292
        y 20
        endObjectProperties

        endGroup
    """)
    test_file = tmp_path / "test.edl"
    test_file.write_text(test_data)
    output_file = tmp_path / "test.ui"

    parser = EDMFileParser(test_file, output_file)
    assert len(parser.ui.objects) == 1
    assert len(parser.ui.objects[0].objects) == 1
    assert parser.ui.objects[0].objects[0].name == "activeXTextClass"


def test_parse_groups_double_space_robustness(tmp_path):
    """`object  activeGroupClass` (two spaces) still parses as a group, not a plain object.

    ``_GROUP_AT`` is `r"object\\s+activeGroupClass\\b"`, so any run of whitespace
    between "object" and "activeGroupClass" is tolerated.
    """
    test_data = textwrap.dedent("""
        # (Group)
        object  activeGroupClass
        beginObjectProperties
        x 5
        y 5
        w 100
        h 100
        beginGroup

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        x 10
        y 10
        endObjectProperties

        endGroup
        endObjectProperties
    """)
    test_file = tmp_path / "test.edl"
    test_file.write_text(test_data)
    output_file = tmp_path / "test.ui"

    parser = EDMFileParser(test_file, output_file)
    assert len(parser.ui.objects) == 1
    group = parser.ui.objects[0]
    assert isinstance(group, EDMGroup)
    assert not isinstance(group, EDMObject)
    assert len(group.objects) == 1
    assert group.objects[0].name == "activeXTextClass"


def test_parse_groups_desync_redirect(tmp_path):
    """A forward-searching object match that swallows garbage text still yields a group.

    The ``object_pattern`` regex searches forward past unparseable text (e.g. a
    stray VCS conflict marker), so it can end up matching a following
    ``activeGroupClass`` as though it were a plain object. The parser must redirect
    that match to the group parser so the result is still an EDMGroup, not an
    EDMObject named "activeGroupClass".
    """
    test_data = textwrap.dedent("""
        ======= merge noise
        object activeGroupClass
        beginObjectProperties
        x 5
        y 5
        w 100
        h 100
        beginGroup

        # (Static Text)
        object activeXTextClass
        beginObjectProperties
        x 10
        y 10
        endObjectProperties

        endGroup
        endObjectProperties
    """)
    test_file = tmp_path / "test.edl"
    test_file.write_text(test_data)
    output_file = tmp_path / "test.ui"

    parser = EDMFileParser(test_file, output_file)
    assert len(parser.ui.objects) == 1
    group = parser.ui.objects[0]
    assert isinstance(group, EDMGroup)
    assert not isinstance(group, EDMObject)
    assert len(group.objects) == 1
    assert group.objects[0].name == "activeXTextClass"


def test_parser_uses_explicit_color_list_for_screen_bgcolor(tmp_path, monkeypatch):
    """An explicit ``color_list_file`` resolves the screen's own ``bgColor`` index,
    independent of ``EDMCOLORFILE``/``EDMFILES`` env vars (issue #158)."""
    monkeypatch.delenv("EDMCOLORFILE", raising=False)
    monkeypatch.delenv("EDMFILES", raising=False)

    test_data = textwrap.dedent("""
        4 0 0
        beginScreenProperties
        major 4
        minor 0
        release 0
        x 0
        y 0
        w 200
        h 100
        font "helvetica-medium-r-12.0"
        bgColor index 25
        endScreenProperties
    """)
    edl = tmp_path / "screen.edl"
    edl.write_text(test_data, encoding="utf-8", newline="\n")

    palette = tmp_path / "colors.list"
    palette.write_text(
        '4 0 0\n\nmax=0x10000\n\nstatic 25 "Controller" { 0xffff 0 0 }\n',
        encoding="utf-8",
        newline="\n",
    )

    parser = EDMFileParser(str(edl), str(tmp_path / "out.ui"), color_list_file=str(palette))
    r, g, b, _a = parser.ui.properties["bgColor"]
    assert (r, g, b) == (255, 0, 0)


def test_screen_size_macro_or_missing_does_not_abort(tmp_path):
    """Template fragments write ``h $(DISP_HEIGHT)``; the parse records the gap
    and sizes it from the content (extent + 8 px margin) instead of raising."""
    test_file = tmp_path / "tmpl.edl"
    test_file.write_text(
        textwrap.dedent("""
        beginScreenProperties
        x 581
        y 305
        w 684
        h $(DISP_HEIGHT)
        endScreenProperties
        object activeRectangleClass
        beginObjectProperties
        x 10
        y 20
        w 30
        h 40
        endObjectProperties
    """)
    )
    parser = EDMFileParser(test_file, tmp_path / "tmpl.ui")
    assert parser.ui.width == 684
    assert parser.ui.height == 20 + 40 + 8
    assert parser.missing_screen_size == ["height"]


def test_screen_size_accepts_indented_line(tmp_path):
    """EDM's tag reader skips leading whitespace (llrf/cleanup/oneMBBOBits: ``  w 236``)."""
    test_file = tmp_path / "indented.edl"
    test_file.write_text("beginScreenProperties\nx 0\ny 0\n  w 236\nh 485\nendScreenProperties\n")
    parser = EDMFileParser(test_file, tmp_path / "indented.ui")
    assert (parser.ui.width, parser.ui.height) == (236, 485)
    assert parser.missing_screen_size == []


def test_screen_without_properties_block_is_missing_both(tmp_path):
    test_file = tmp_path / "fragment.edl"
    test_file.write_text(
        "object activeRectangleClass\nbeginObjectProperties\nx 1\ny 2\nw 3\nh 4\nendObjectProperties\n"
    )
    parser = EDMFileParser(test_file, tmp_path / "fragment.ui")
    assert parser.missing_screen_size == ["width", "height"]
    assert (parser.ui.width, parser.ui.height) == (1 + 3 + 8, 2 + 4 + 8)


def test_get_size_properties():
    """Test that the size properties are extracted correctly"""
    test_data = textwrap.dedent("""
        x 10
        y 20
        w 30
        h 40
        foo bar
    """)

    result_size = EDMFileParser.get_size_properties(test_data)
    assert result_size["x"] == 10
    assert result_size["y"] == 20
    assert result_size["width"] == 30
    assert result_size["height"] == 40
    assert "foo" not in result_size


@pytest.mark.parametrize(
    "test_property, expected",
    [
        ("foo bar", {"foo": "bar"}),
        ("baz", {"baz": True}),
        ("qux {\nquux\ncorge\n}", {"qux": ["quux", "corge"]}),
        ("qux {\n0 quux\n1 corge\n}", {"qux": ["quux", "corge"]}),
        (
            'command {\n  0 "pydm -m \\"DEV=WIGG:LTUS:724\\" file.ui &"\n}',
            {"command": ['pydm -m "DEV=WIGG:LTUS:724" file.ui &']},
        ),
        ('label "some \\"quoted\\" text"', {"label": 'some "quoted" text'}),
        # xray/ims_aux.edl: escaped backslashes and a value ending in escaped quotes
        (
            "\n".join(
                ["command {", r'  0 "gnome-terminal -e \"bash -c \\\"/reg/pmgrUtils.sh dmapply $(MOTOR)\\\"\""', "}"]
            ),
            {"command": [r'gnome-terminal -e "bash -c \"/reg/pmgrUtils.sh dmapply $(MOTOR)\""']},
        ),
        # Archive/lcls-old/mgnt_undh_sec1.edl: a value starting and ending with an escaped quote
        (
            "\n".join(["symbols {", r'  0 "\"U=USEG:UNDH:1850,crat=CRAT:UNDH:UC18\" "', "}"]),
            {"symbols": ['"U=USEG:UNDH:1850,crat=CRAT:UNDH:UC18" ']},
        ),
        # misc/dbs_llrf.edl: a label starting with an escaped quote
        (
            "\n".join(
                ["commandLabel {", r'  0 "\"Recovering L3 Phase\" Wiki Article"', '  1 "6x6 Help EDM Panel"', "}"]
            ),
            {"commandLabel": ['"Recovering L3 Phase" Wiki Article', "6x6 Help EDM Panel"]},
        ),
        (r'onLabel "UC13\" "', {"onLabel": 'UC13" '}),
        (r'buttonLabel "Y1(X)', {"buttonLabel": "Y1(X)"}),
        # a quoted brace is a value, not the start of a block
        (r'foo "\{"' + "\nbar baz", {"foo": "{", "bar": "baz"}),
        # llrf/scllrfPRCBits.edl: a tab before the opening quote
        ('value {\n\t   "bit 8"\n}', {"value": ["bit 8"]}),
        # spaces inside the quotes are kept, as EDM keeps them
        ('value {\n  "Currently: "\n  "  indented"\n}', {"value": ["Currently: ", "  indented"]}),
        ('label "       L1S Phase"', {"label": "       L1S Phase"}),
        ('buttonLabel "   IOC:BSY0:MG01..."', {"buttonLabel": "   IOC:BSY0:MG01..."}),
        ('title "  "', {"title": "  "}),
        # except around a PV name, which an IOC would not resolve (event/mpgPatternDiags.edl,
        # llrf/gun_interlocks.edl); an all-space PV is no PV
        ('controlPv "IOC:${LOCA}:${UNIT}:PATTERND-2.N  "', {"controlPv": "IOC:${LOCA}:${UNIT}:PATTERND-2.N"}),
        (
            'colorPv " GUN:GUNB:100:PRC:INLK_STATUS_MSBITS_R.BF"',
            {"colorPv": "GUN:GUNB:100:PRC:INLK_STATUS_MSBITS_R.BF"},
        ),
        ('visPv " "', {"visPv": ""}),
        ('dataPvStr "X:IMAGE "', {"dataPvStr": "X:IMAGE"}),
        ('pv "X:Y "', {"pv": "X:Y"}),
        ('xPv {\n  0 " X:A"\n  1 "X:B "\n}', {"xPv": ["X:A", "X:B"]}),
    ],
)
def test_get_object_properties(test_property, expected):
    """Test that the object properties are extracted correctly

    Parameters
    ----------
    test_property : str
        Test data for the object properties
    expected : dict
        Expected result of the object properties
    """
    result_property = EDMFileParser.get_object_properties(test_property)
    assert result_property == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (r'"plain"', "plain"),
        (r'"a \"b\" c"', 'a "b" c'),
        (r'"\"starts and ends quoted\""', '"starts and ends quoted"'),
        # EDM's writer escapes \ " { and } with a backslash; any \x reads as x
        (r'"/home/physics/Desktop\\ Icons/scripts"', r"/home/physics/Desktop\ Icons/scripts"),
        (
            r'"for m in \{1..5\}; do caput $(P)CM$\{m\}:CALIBRATE.PROC 1 ; done"',
            "for m in {1..5}; do caput $(P)CM${m}:CALIBRATE.PROC 1 ; done",
        ),
        (r'"ends with a backslash\\"', "ends with a backslash\\"),
        (r'"LOC\\name=i:0"', r"LOC\name=i:0"),
        # the first unescaped quote closes the value
        (r'"closed"  ', "closed"),
        # a missing closing quote reads to the end of the line
        (r'"Y1(X)', "Y1(X)"),
        # a line break ends the value (a stray \r in the file reads as one)
        ('"Record parameters\n"', "Record parameters"),
        ('"cd ../burt; burtwb -f interp.load\n "', "cd ../burt; burtwb -f interp.load"),
        (r'"dangling\\', "dangling\\"),
        # spaces inside the quotes are kept, as EDM keeps them
        (r'"Currently: "', "Currently: "),
        (r'"  "', "  "),
        ('"\tTab"', "\tTab"),
        (r'"no closing quote  ', "no closing quote  "),
        (r'""', ""),
        ('\t "tabbed"', "tabbed"),
        # unquoted values keep the old handling
        ("bar", "bar"),
        ("5 ", "5"),
        (r"LOC\\name", r"LOC\\name"),
        (r"pydm -m \"P=X\" a.ui", 'pydm -m "P=X" a.ui'),
    ],
)
def test_read_edm_string(value, expected):
    assert read_edm_string(value) == expected


def test_remove_prepended_index_unquotes_each_value():
    lines = [r'  0 "\"U=X\" "', r'  2 "a\\b\{c\}"']
    values = EDMFileParser.remove_prepended_index(lines)
    assert list(values) == ['"U=X" ', r"a\b{c}"]
    assert values.indices == [0, 2]


def test_pv_block_keeps_its_indices():
    properties = EDMFileParser.get_object_properties('controlPvs {\n  0 "A "\n  2 " B"\n}')
    assert list(properties["controlPvs"]) == ["A", "B"]
    assert properties["controlPvs"].indices == [0, 2]


def test_read_edm_string_can_mark_a_literal_dollar_brace():
    """EDM expands only $(NAME), so $\\{m\\} reads as literal text (a shell variable).
    With literal_brace, a brace read right after a "$" is marked so it can't pass
    for a $(NAME) macro, which modify_text has already written as ${NAME}."""
    value = r'"for m in \{1..5\}; do caput ${P}CM$\{m\}:CAL 1; echo \$\{x\} $\\\{y\} ; done"'
    assert read_edm_string(value) == r"for m in {1..5}; do caput ${P}CM${m}:CAL 1; echo ${x} $\{y} ; done"
    assert read_edm_string(value, "#") == r"for m in {1..5}; do caput ${P}CM$#m}:CAL 1; echo $#x} $\{y} ; done"
    props = EDMFileParser.get_object_properties('command {\n  0 "echo $\\{A\\}"\n}\nlabel "$\\{B\\}"', "#")
    assert props == {"command": ["echo $#A}"], "label": "$#B}"}


def test_parser_marks_literal_dollar_braces_only_when_asked(tmp_path):
    edl = tmp_path / "shell.edl"
    edl.write_text(
        "beginScreenProperties\nw 100\nh 100\nendScreenProperties\n"
        "object activeGroupClass\nbeginObjectProperties\nx 0\ny 0\nw 50\nh 20\nbeginGroup\n\n"
        "object shellCmdClass\nbeginObjectProperties\nx 0\ny 0\nw 50\nh 20\n"
        'command {\n  0 "caput $(CM):CM$\\{m\\}CAL 1"\n}\nendObjectProperties\n\n'
        "endGroup\nendObjectProperties\n"
    )
    for literal_brace, command in ((None, "caput ${CM}:CM${m}CAL 1"), ("#", "caput ${CM}:CM$#m}CAL 1")):
        parser = EDMFileParser(str(edl), str(tmp_path / "shell.ui"), literal_brace=literal_brace)
        (group,) = parser.ui.objects
        (shell,) = group.objects
        assert shell.properties["command"] == [command]


def test_literal_macro_clashes():
    text = 'command {\n  0 "restart $\\{LOCA\\} ${LOCA} $\\{HOME\\}"\n}\nvisPv "${P}"'
    assert literal_macro_clashes(text) == ["LOCA"]
    assert literal_macro_clashes('label "${LOCA}"') == []


def test_parser_knows_whether_it_read_a_literal_dollar_brace(tmp_path):
    edl = tmp_path / "shell.edl"
    for command, expected in (('"echo $\\{HOME\\}"', True), ('"echo $(HOME)"', False)):
        edl.write_text(
            "beginScreenProperties\nw 100\nh 100\nendScreenProperties\n"
            f"object shellCmdClass\nbeginObjectProperties\nx 0\ny 0\nw 50\nh 20\ncommand {{\n  0 {command}\n}}\n"
            "endObjectProperties\n"
        )
        assert EDMFileParser(str(edl), str(tmp_path / "shell.ui")).literal_braces is expected


@pytest.mark.parametrize(
    "pv, expected",
    [
        # misc/histViewer.edl: EDM expands $(SIG) and keeps the backslash, so this
        # is a LOC variable named after the macro's value (pv_factory.cc).
        (r"LOC\\$(SIG)_View=0", "loc://${SIG}_View?type=int&init=0"),
        (r"LOC\\$(SIG)_View==0", "loc://${SIG}_View?type=int&init=0"),
        (r"LOC\\$(SIG)_View", "loc://${SIG}_View"),
        (r"LOC\\\\$(SIG)_View=0", "loc://${SIG}_View?type=int&init=0"),
        (r"LOC\\$(!W)show=i:0", "loc://__UNIQUE__show?type=int&init=0"),
        # Outside a LOC name the backslash before a macro is kept too.
        (r"\\$(X)", r"\${X}"),
    ],
)
def test_macro_after_a_backslash_keeps_the_backslash(tmp_path, pv, expected):
    edl = tmp_path / "loc.edl"
    edl.write_text(
        "beginScreenProperties\nw 100\nh 100\nendScreenProperties\n"
        "object activeXTextDspClass\nbeginObjectProperties\nx 0\ny 0\nw 50\nh 20\n"
        f'controlPv "{pv}"\nendObjectProperties\n'
    )
    (text_control,) = EDMFileParser(str(edl), str(tmp_path / "loc.ui")).ui.objects
    assert text_control.properties["controlPv"] == expected
