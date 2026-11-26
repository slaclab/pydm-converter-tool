import textwrap
import xml.etree.ElementTree as ET

from pydmconverter.edm.converter import convert
from pydmconverter.edm.converter_helpers import handle_button_polygon_overlaps
from pydmconverter.widgets import PyDMRelatedDisplayButton, PyDMDrawingIrregularPolygon


def test_button_touching_polygon_stroke_keeps_its_style_and_order():
    button = PyDMRelatedDisplayButton(name="details", x=141, y=105, width=60, height=20, flat=False)
    polygon = PyDMDrawingIrregularPolygon(name="shape", x=98, y=98, width=44, height=33, penWidth=2)
    widgets = [button, polygon]

    result = handle_button_polygon_overlaps(widgets)

    assert result == [button, polygon]
    assert button.flat is False


def test_button_covering_polygon_stroke_is_flattened_and_raised():
    button = PyDMRelatedDisplayButton(name="details", x=120, y=105, width=30, height=20, flat=False)
    polygon = PyDMDrawingIrregularPolygon(name="shape", x=98, y=98, width=44, height=33, penWidth=2)
    widgets = [button, polygon]

    result = handle_button_polygon_overlaps(widgets)

    assert result == [polygon, button]
    assert button.flat is True


def test_converter_keeps_button_next_to_edm_polygon_raised(tmp_path):
    source = tmp_path / "touch.edl"
    target = tmp_path / "touch.ui"
    source.write_text(
        textwrap.dedent(
            """\
            4 0 1
            beginScreenProperties
            major 4
            minor 0
            release 1
            x 0
            y 0
            w 240
            h 160
            bgColor rgb 65535 65535 65535
            endScreenProperties
            object activeLineClass
            beginObjectProperties
            major 4
            minor 0
            release 1
            x 100
            y 100
            w 40
            h 30
            lineColor rgb 0 0 65535
            fill
            fillColor rgb 48059 48059 48059
            lineWidth 2
            closePolygon
            numPoints 5
            xPoints {
              0 100
              1 140
              2 140
              3 100
              4 100
            }
            yPoints {
              0 100
              1 100
              2 130
              3 130
              4 100
            }
            endObjectProperties
            object relatedDisplayClass
            beginObjectProperties
            major 4
            minor 4
            release 0
            x 141
            y 105
            w 60
            h 20
            fgColor rgb 0 0 0
            bgColor rgb 52428 52428 52428
            topShadowColor rgb 65535 65535 65535
            botShadowColor rgb 26214 26214 26214
            font "helvetica-medium-r-12.0"
            buttonLabel "Details"
            numPvs 4
            numDsps 1
            displayFileName {
              0 "details.edl"
            }
            endObjectProperties
            """
        ),
        encoding="utf-8",
    )

    convert(str(source), str(target))

    root = ET.parse(target).getroot()
    siblings = [
        widget
        for widget in root.findall("./widget/widget/widget")
        if widget.get("class") in {"PyDMRelatedDisplayButton", "PyDMDrawingIrregularPolygon"}
    ]
    assert [widget.get("class") for widget in siblings] == ["PyDMDrawingIrregularPolygon", "PyDMRelatedDisplayButton"]
    flat = siblings[1].find("property[@name='flat']/bool")
    assert flat is None or flat.text == "false"
