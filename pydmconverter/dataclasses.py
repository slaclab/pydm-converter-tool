import xml.etree.ElementTree as etree

from dataclasses import dataclass


class XMLConvertible:
    def to_xml(self):
        raise NotImplementedError

    def to_string(self):
        element = self.to_xml()
        return etree.tostring(element, encoding="unicode")


class PyDMFrame:
    pass


class QLabel:
    pass


class PyDMLabel:
    pass


class PyDMLineEdit:
    pass


class PyDMDrawingRectangle:
    pass


class PyDMDrawingEllipse:
    pass


class PyDMShellCommand:
    pass


class PyDMPushButton:
    pass


class PyDMEnumComboBox:
    pass


class PyDMEnumButton:
    pass


class PyDMRelatedDisplayButton:
    pass


class PyDMEDMDisplayButton:
    pass


class PyDMDrawingLine:
    pass


class PyDMDrawingPolyLine:
    pass


class Font:
    pass


class Size:
    pass


@dataclass
class SizePolicy:
    hsizetype: str
    vsizetype: str

    def xml(self):
        pass


class Bool:
    pass


class Layout:
    pass


class StyleSheet:
    pass


class CustomWidget:
    pass
