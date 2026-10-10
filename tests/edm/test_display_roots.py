"""SLAC display roots: a related display or embedded window that names a display
by its absolute path under the site's display root gets the path below the root,
which PyDM finds through PYDM_DISPLAYS_PATH (an absolute name only finds itself)."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydm.widgets import PyDMEmbeddedDisplay as QtEmbeddedDisplay

from pydmconverter.edm.converter import convert
from pydmconverter.edm.display_roots import map_display_roots, root_relative
from pydmconverter.edm.parser import EDMFileParser, block_items
from pydmconverter.react import convert_to_ir

LCLS = "/usr/local/lcls/tools/edm/display"
FACET = "/usr/local/facet/tools/edm/display"
ROOTS = (LCLS, FACET)

HEADER = """\
4 0 1
beginScreenProperties
major 4
minor 0
release 1
x 0
y 0
w 400
h 300
endScreenProperties
"""


def obj(edm_class, body, x=10, y=10, w=80, h=20):
    return (
        f"object {edm_class}\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        f"x {x}\ny {y}\nw {w}\nh {h}\n{body}endObjectProperties\n"
    )


def block(name, entries):
    """An EDM array tag from {EDM index: value}."""
    lines = "\n".join(f'  {index} "{value}"' for index, value in entries.items())
    return f"{name} {{\n{lines}\n}}\n"


def related(files, symbols=None, **geometry):
    body = f'buttonLabel "Open"\nnumDsps {max(files) + 1}\n' + block("displayFileName", files)
    if symbols:
        body += block("symbols", symbols)
    return obj("relatedDisplayClass", body, **geometry)


def file_pip(file, **geometry):
    return obj("activePipClass", f'displaySource "file"\nfile "{file}"\n', **geometry)


def menu_pip(files, file_pv=r"LOC\\sel=i:0", **geometry):
    body = f'displaySource "menu"\nfilePv "{file_pv}"\nnumDsps {max(files) + 1}\n' + block("displayFileName", files)
    return obj("activePipClass", body, **geometry)


def group(*objects):
    return (
        "object activeGroupClass\nbeginObjectProperties\nmajor 4\nminor 0\nrelease 0\n"
        "x 0\ny 200\nw 100\nh 40\nbeginGroup\n" + "".join(objects) + "endGroup\nendObjectProperties\n"
    )


def write_screen(path, *objects):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "".join(objects))
    return path


@pytest.mark.parametrize(
    "name, expected",
    [
        (f"{LCLS}/misc/steeringpanels/steer_li21_xcor.edl", "misc/steeringpanels/steer_li21_xcor.edl"),
        (f"{FACET}/facet/lea_pps_ndr_main.edl", "facet/lea_pps_ndr_main.edl"),
        # EDM appends .edl to a name without it (misc/tuningPalette/tuningPalette.edl).
        (f"{LCLS}/misc/tuningPalette/tuningPalette", "misc/tuningPalette/tuningPalette"),
        (f"{LCLS}//misc/x.edl", "misc/x.edl"),
        ("//usr/local//lcls/tools/edm/display/misc/x.edl", "misc/x.edl"),
        (f"{LCLS}/$(area)/$(dev)_main.edl", "$(area)/$(dev)_main.edl"),
        (f"{LCLS}/misc/x.edl;P=A", "misc/x.edl;P=A"),
        (f"{FACET}/facet/../vac/x.edl", "facet/../vac/x.edl"),
    ],
)
def test_names_under_a_root_become_root_relative(name, expected):
    assert root_relative(name, ROOTS) == expected


def test_root_with_a_trailing_slash():
    assert root_relative(f"{LCLS}/misc/x.edl", (LCLS + "/",)) == "misc/x.edl"


@pytest.mark.parametrize(
    "name",
    [
        "x.edl",
        "misc/x.edl",
        "",
        "/home/oxygen/MOONEY/x.edl",
        "/usr/local/lcls/tools/edm/displays/x.edl",
        f"{LCLS}x.edl",
        LCLS,
        f"{LCLS}/",
        f"{LCLS}/../x.edl",
        f"{LCLS}/misc/../../x.edl",
        "$(ROOT)/misc/x.edl",
        "usr/local/lcls/tools/edm/display/misc/x.edl",
    ],
)
def test_other_names_are_unchanged(name):
    assert root_relative(name, ROOTS) == name


def test_map_display_roots_rewrites_only_display_names(tmp_path):
    source = write_screen(
        tmp_path / "screen.edl",
        related({0: f"{LCLS}/misc/a.edl", 1: "b.edl", 3: f"{FACET}/facet/c.edl"}, symbols={3: "P=X"}),
        file_pip(f"{LCLS}/misc/d.edl", y=40),
        menu_pip({1: f"{LCLS}/misc/e.edl", 2: "/home/oxygen/MOONEY/f.edl"}, y=70),
        group(related({0: f"{LCLS}/misc/g.edl"})),
        obj("activePngClass", f'file "{LCLS}/misc/camera.png"\n', y=100),
    )
    parser = EDMFileParser(str(source), str(tmp_path / "screen.ui"))
    map_display_roots(parser.ui, ROOTS)
    button, file_window, menu_window, grouped, png = parser.ui.objects

    # A block keeps its EDM indices, which pair symbols[i] with displayFileName[i].
    assert block_items(button.properties["displayFileName"]) == [(0, "misc/a.edl"), (1, "b.edl"), (3, "facet/c.edl")]
    assert file_window.properties["file"] == "misc/d.edl"
    assert block_items(menu_window.properties["displayFileName"]) == [
        (1, "misc/e.edl"),
        (2, "/home/oxygen/MOONEY/f.edl"),
    ]
    assert grouped.objects[0].properties["displayFileName"] == ["misc/g.edl"]
    assert png.properties["file"] == f"{LCLS}/misc/camera.png"


def ui_filenames(ui_path):
    """{widget class: [file names]} of the converted screen's related display
    buttons and embedded displays."""
    found = {}
    for widget in ET.parse(ui_path).getroot().iter("widget"):
        for name in ("filenames", "filename"):
            element = widget.find(f"property[@name='{name}']")
            if element is not None:
                values = [s.text for s in element.iter("string")]
                found.setdefault(widget.get("class"), []).extend(values)
    return found


def ir_files(screen):
    found = {}
    stack = [screen.root]
    while stack:
        node = stack.pop()
        if "file" in node.props:
            found.setdefault(node.type, []).append(node.props["file"])
        for rule in node.rules:
            found.setdefault(f"{node.type} rule", []).extend(c.value for c in rule.conditions)
        stack.extend(node.children)
    return found


@pytest.fixture
def screen(tmp_path):
    return write_screen(
        tmp_path / "screen.edl",
        related({0: f"{LCLS}/misc/a.edl"}),
        file_pip(f"{LCLS}/misc/steeringpanels/steer_li21_xcor.edl", y=40),
        menu_pip({0: f"{FACET}/facet/e.edl", 1: "f.edl"}, y=70, w=200, h=100),
    )


def test_slac_site_writes_root_relative_ui_names(screen, tmp_path):
    convert(str(screen), str(tmp_path / "slac.ui"), site="slac")
    convert(str(screen), str(tmp_path / "plain.ui"))
    slac, plain = ui_filenames(tmp_path / "slac.ui"), ui_filenames(tmp_path / "plain.ui")
    assert slac["PyDMRelatedDisplayButton"] == ["misc/a.ui"]
    assert plain["PyDMRelatedDisplayButton"] == [f"{LCLS}/misc/a.ui"]
    # The menu window shows its starting entry, 0.
    assert sorted(slac["PyDMEmbeddedDisplay"]) == ["facet/e.ui", "misc/steeringpanels/steer_li21_xcor.ui"]
    assert sorted(plain["PyDMEmbeddedDisplay"]) == [
        f"{FACET}/facet/e.ui",
        f"{LCLS}/misc/steeringpanels/steer_li21_xcor.ui",
    ]


def test_slac_site_maps_menu_window_tab_pages(tmp_path):
    # A choice button on a menu window becomes tabs, one page per entry, built
    # from copies of the window's entries: they must carry the mapped names.
    files = {0: f"{LCLS}/misc/steeringpanels/xsteeringpanel.edl", 1: f"{LCLS}/misc/steeringpanels/ysteeringpanel.edl"}
    source = write_screen(
        tmp_path / "screen.edl",
        menu_pip(files, file_pv=r"LOC\\sel=e:0,X,Y", x=4, y=24, w=380, h=260),
        obj("activeChoiceButtonClass", 'controlPv "LOC\\\\sel=e:0"\norientation "horizontal"\n', x=12, y=4, w=200),
    )
    convert(str(source), str(tmp_path / "screen.ui"), site="slac")
    assert ET.parse(tmp_path / "screen.ui").getroot().find(".//widget[@class='QTabWidget']") is not None
    assert ui_filenames(tmp_path / "screen.ui")["PyDMEmbeddedDisplay"] == [
        "misc/steeringpanels/xsteeringpanel.ui",
        "misc/steeringpanels/ysteeringpanel.ui",
    ]


def test_slac_site_writes_root_relative_ir_refs(screen):
    slac, plain = ir_files(convert_to_ir(screen, site="slac")), ir_files(convert_to_ir(screen))
    assert slac["related-display-button"] == ["misc/a.screen.json"]
    assert plain["related-display-button"] == [f"{LCLS}/misc/a.screen.json"]
    assert sorted(slac["embedded-display"]) == [
        "facet/e.screen.json",
        "misc/steeringpanels/steer_li21_xcor.screen.json",
    ]
    assert sorted(plain["embedded-display"]) == [
        f"{FACET}/facet/e.screen.json",
        f"{LCLS}/misc/steeringpanels/steer_li21_xcor.screen.json",
    ]
    assert slac["embedded-display rule"] == ["facet/e.screen.json", "f.screen.json"]
    assert plain["embedded-display rule"] == [f"{FACET}/facet/e.screen.json", "f.screen.json"]


def test_embedded_display_loads_from_the_display_path(tmp_path, qtbot, monkeypatch):
    # The parent sits outside the converted root and is opened from elsewhere, so
    # only PYDM_DISPLAYS_PATH can find the child (misc/integratedSteeringPanel.edl
    # embeds misc/steeringpanels/xsteeringpanel.edl this way).
    from pydm.display import load_file

    root = tmp_path / "display"
    child = write_screen(root / "misc" / "steeringpanels" / "child.edl", obj("activeXTextClass", 'value {\n  "x"\n}\n'))
    convert(str(child), str(child.with_suffix(".ui")), site="slac")
    parent = write_screen(tmp_path / "elsewhere" / "parent.edl", file_pip(f"{LCLS}/misc/steeringpanels/child.edl"))
    convert(str(parent), str(parent.with_suffix(".ui")), site="slac")
    monkeypatch.setenv("PYDM_DISPLAYS_PATH", str(root))
    monkeypatch.chdir(tmp_path / "elsewhere")

    window = load_file(str(parent.with_suffix(".ui")), target=None)
    qtbot.addWidget(window)
    window.show()
    (display,) = window.findChildren(QtEmbeddedDisplay)
    qtbot.waitUntil(lambda: display.embedded_widget is not None, timeout=3000)
    # As paths: on Windows PyDM joins the search directory and the name with "/".
    assert Path(display.embedded_widget.loaded_file()) == root / "misc" / "steeringpanels" / "child.ui"
