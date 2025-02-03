"""
def testDrawingRectangle():
    target = "\n".join(
        [
            '<widget class="PyDMDrawingRectangle" name="PyDMDrawingRectangle_1">',
            '  <property name="geometry">',
            "    <rect>",
            "      <x>8</x>",
            "      <y>56</y>",
            "      <width>720</width>",
            "      <height>48</height>",
            "    </rect>",
            "  </property>",
            '  <property name="penColor" stdset="0">',
            '    <color alpha="255">',
            "      <red>200</red>",
            "      <green>200</green>",
            "      <blue>200</blue>",
            "    </color>",
            "  </property>",
            '  <property name="brush" stdset="0">',
            '    <brush brushstyle="SolidPattern">',
            '      <color alpha="255">',
            "        <red>200</red>",
            "        <green>200</green>",
            "        <blue>200</blue>",
            "      </color>",
            "    </brush>",
            "  </property>",
            '  <property name="channel" stdset="0">',
            "    <string />",
            "  </property>",
            '  <property name="alarmSensitiveContent" stdset="0">',
            "    <bool>false</bool>",
            "  </property>",
            '  <property name="alarmSensitiveBorder" stdset="0">',
            "    <bool>false</bool>",
            "  </property>",
            "</widget>",
        ]
    )
    drawing = PyDMDrawingRectangle(
        x=8,
        y=56,
        width=720,
        height=48,
        alarm_sensitive_border=False,
        penColor=(200, 200, 200),
        brushColor=(200, 200, 200, 255),
    )
    assert target == drawing.to_string()
"""
