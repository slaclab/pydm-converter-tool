import xml.etree.ElementTree as etree

from pydmconverter.dataclasses import Bool, Channel, Font, StyleSheet, Text


class OrgTemplate:
    @staticmethod
    def generate() -> etree.Element:
        layout = self.form_layout()
        title_bar = self.title_bar()
        layout.append(title_bar)
        content_frame = self.background_widget()
        layout.append(content_frame)
        return layout

    @staticmethod
    def form_layout() -> etree.Element:
        layout = etree.Element(
            "layout",
            attrib={
                "class": "QVBoxLayout",
                "name": "verticalLayout_3",
            },
        )
        spacing = etree.SubElement(layout, "property", attrib={"name": "spacing"})
        number = etree.SubElement(spacing, "number")
        number.text = "0"
        for name in ["leftMargin", "topMargin", "rightMargin", "bottomMargin"]:
            margin = etree.SubElement(layout, "property", attrib={"name": name})
            number = etree.SubElement(margin, "number")
            number.text = "9" if name == "bottomMargin" else "0"
        return layout

    @staticmethod
    def title_bar() -> etree.Element:
        titlebox_item = etree.Element("item")
        titlebox_frame = etree.SubElement(
            titlebox_item,
            "widget",
            attrib={
                "class": "QFrame",
                "name": "TitleBox",
            },
        )

        sizePolicy = XMLGenerator.sizePolicy("Preferred", "Fixed")
        titlebox_frame.append(sizePolicy)

        titlebox_frame_styleSheet = XMLGenerator.styleSheet(["background-color: rgb(230, 230, 230);"])
        titlebox_frame.append(titlebox_frame_styleSheet)

        frameShape_property = etree.SubElement(
            titlebox_frame,
            "property",
            attrib={
                "name": "frameShape",
            },
        )
        frameShape = etree.SubElement(frameShape_property, "enum")
        frameShape.text = "QFrame::NoFrame"

        frameShadow_property = etree.SubElement(
            titlebox_frame,
            "property",
            attrib={
                "name": "frameShadow",
            },
        )
        frameShadow = etree.SubElement(frameShadow_property, "enum")
        frameShadow.text = "QFrame::Raised"

        hlayout = etree.SubElement(
            titlebox_frame,
            "layout",
            attrib={
                "class": "QHBoxLayout",
                "name": "horizontalLayout_5",
                "stretch": "0,0,0,0,0",
            },
        )
        hlayout_item1 = etree.SubElement(hlayout, "item")
        lcls_label = etree.SubElement(
            hlayout_item1,
            "widget",
            attrib={
                "class": "QLabel",
                "name": "LCLS",
            },
        )
        sizePolicy = XMLGenerator.sizePolicy("Fixed", "Preferred")
        lcls_label.append(sizePolicy)
        font = Font(
            pointsize="22",
            weight="75",
            bold="true",
        )
        lcls_label.append(font)
        lcls_label_styleSheet = XMLGenerator.styleSheet(
            [
                "color: rgb(140, 21, 21);",
                "background-color: rgba(255, 255, 255, 0)",
            ]
        )
        lcls_label.append(lcls_label_styleSheet)
        text = Text("LCLS")
        lcls_label.append(text)

        hlayout_item2 = etree.SubElement(hlayout, "item")
        system_label = etree.SubElement(
            hlayout_item2,
            "widget",
            attrib={
                "class": "QLabel",
                "name": "System",
            },
        )
        sizePolicy = XMLGenerator.sizePolicy("Fixed", "Preferred")
        system_label.append(sizePolicy)
        minimumSize = XMLGenerator.size("minimumSize", "85", "0")
        system_label.append(minimumSize)
        font = Font(
            pointsize="8",
            weight="50",
            bold="false",
        )
        system_label.append(font)
        styleSheet = XMLGenerator.styleSheet(
            [
                "color: rgb(79, 79, 79);",
                "background-color: rgba(255, 255, 255, 0);",
            ]
        )
        system_label.append(styleSheet)
        text = Text("GLOBAL\n&lt;SUBSYSTEM&gt;")
        system_label.append(text)

        hlayout_item3 = etree.SubElement(hlayout, "item")
        title_label = etree.SubElement(
            hlayout_item3,
            "widget",
            attrib={
                "class": "QLabel",
                "name": "Title",
            },
        )
        title_label.append(XMLGenerator.sizePolicy("Expanding", "Preferred"))
        title_label.append(
            Font(
                pointsize="18",
                weight="75",
                bold="true",
            )
        )
        title_label.append(
            XMLGenerator.styleSheet(
                [
                    "color: rgb(55, 55, 55);",
                    "background-color: rgba(120, 120, 120, 0);",
                ]
            )
        )
        title_label.append(Text("&lt;GLOBAL PAGE TITLE&gt;"))
        alignment = etree.SubElement(title_label, "property", attrib={"name": "alignment"})
        set_tag = etree.SubElement(alignment, "set")
        set_tag.text = "Qt::AlignCenter"

        hlayout_item4 = etree.SubElement(hlayout, "item")
        spacer = etree.SubElement(hlayout_item4, "spacer", attrib={"name": "horizontalSpacer_3"})
        orientation = etree.SubElement(spacer, "property", attrib={"name": "orientation"})
        enum = etree.SubElement(orientation, "enum")
        enum.text = "Qt::Horizontal"
        sizeType = etree.SubElement(spacer, "property", attrib={"name": "sizeType"})
        enum = etree.SubElement(sizeType, "enum")
        enum.text = "QSizePolicy::Fixed"
        size = XMLGenerator.size("sizeHint", "85", "20")
        size.set("stdset", "0")
        spacer.append(size)

        hlayout_item5 = etree.SubElement(hlayout, "item")
        env_layout = etree.SubElement(
            hlayout_item5,
            "layout",
            attrib={
                "class": "QVBoxLayout",
                "name": "ClockLayout",
            },
        )
        clock_item = etree.SubElement(env_layout, "item")
        clock_label = etree.SubElement(
            clock_item,
            "widget",
            attrib={
                "class": "PyDMLabel",
                "name": "Clock",
            },
        )
        clock_label.append(XMLGenerator.sizePolicy("Fixed", "Preferred"))
        clock_label.append(XMLGenerator.size("minimumSize", "80", "0"))
        clock_label.append(
            Font(
                pointsize="8",
                italic="true",
            )
        )
        tooltip = etree.SubElement(clock_label, "property", attrib={"name": "toolTip"})
        string = etree.SubElement(tooltip, "string")
        whatsThis = etree.SubElement(clock_label, "property", attrib={"name": "whatsThis"})
        string = etree.SubElement(whatsThis, "string")
        clock_label.append(
            XMLGenerator.styleSheet(
                [
                    "color: rgb(79, 79, 79);",
                    "background-color: rgba(255, 255, 255, 0);",
                ]
            )
        )
        clock_label.append(Text("Clock"))
        alignment = etree.SubElement(clock_label, "property", attrib={"name": "alignment"})
        set_tag = etree.SubElement(alignment, "set")
        set_tag.text = "Qt::AlignRight|Qt::AlignTrailing|Qt::AlignVCenter"
        precision = etree.SubElement(
            clock_label,
            "property",
            attrib={
                "name": "precision",
                "stdset": "0",
            },
        )
        number = etree.SubElement(precision, "number")
        number.text = 0
        clock_label.append(Bool("showUnits", False))
        clock_label.append(Bool("precisionFromPV", True))
        clock_label.append(Bool("alarmSensitiveContent", False))
        clock_label.append(Bool("alarmSensitiveBorder", True))
        clock_label.append(Channel("SIOC:SYS0:AL00:TOD"))
        location_item = etree.SubElement(env_layout, "item")
        location_label = etree.SubElement(
            location_item,
            "widget",
            attrib={
                "class": "PyDMLabel",
                "name": "Location",
            },
        )
        location_label.append(XMLGenerator.sizePolicy("Fixed", "Preferred"))
        location_label.append(XMLGenerator.size("minimumSize", "80", "0"))
        location_label.append(
            Font(
                pointsize="8",
                italic="true",
            )
        )
        tooltip = etree.SubElement(location_label, "property", attrib={"name": "toolTip"})
        string = etree.SubElement(tooltip, "string")
        location_label.append(
            XMLGenerator.styleSheet(
                [
                    "color: rgb(79, 79, 79);",
                    "background-color: rgba(255, 255, 255, 0);",
                ]
            )
        )
        location_label.append(Text("PROD/DEV"))
        alignment = etree.SubElement(location_label, "property", attrib={"name": "alignment"})
        set_tag = etree.SubElement(alignment, "set")
        set_tag.text = "Qt::AlignRight|Qt::AlignTrailing|Qt::AlignVCenter"
        precision = etree.SubElement(
            location_label,
            "property",
            attrib={
                "name": "precision",
                "stdset": "0",
            },
        )
        number = etree.SubElement(precision, "number")
        number.text = "0"
        location_label.append(XMLGenerator.bool("showUnits", False))
        location_label.append(XMLGenerator.bool("precisionFromPV", True))
        location_label.append(XMLGenerator.bool("alarmSensitiveContent", False))
        location_label.append(XMLGenerator.bool("alarmSensitiveBorder", True))
        location_label.append(Channel("SIOC:SYS0:AL00:MODE"))
        return titlebox_item

    @staticmethod
    def background_widget():
        background_item = etree.Element("item")
        frame_widget = etree.SubElement(
            background_item,
            "widget",
            attrib={
                "class": "QFrame",
                "name": "Background",
            },
        )
        tooltip_property = etree.SubElement(frame_widget, "property", attrib={"name": "toolTip"})
        string = etree.SubElement(tooltip_property, "string")
        styleSheet = StyleSheet(
            [
                "QWidget #Background {",
                "background-color: rgb(193, 193, 193);",
                "border-radius: 0px;",
                "}",
            ]
        )
        frame_widget.append(styleSheet.to_xml())
        return background_item
