#!/usr/bin/env python
"""
edm_to_pydm
converts an edm .edl file to a pydm .ui file and a .csv file for widgets that do not yet have a conversion function

Instructions to add a new widget (ctrl + f Step n)
1. in __init__() add a counter to count the amount of times your widget appears in a screen
2. in main_converter() add a case for when your widget appears in the edm file
3. add the custom widget properties to end_xml() if applicable
4. write a converter function for your widget taking in the arguments {Your_Widget}_counter and widget_string
   Add the definition for this at the end of the widget converter functions
   Many converter functions exist, many are applicable to your widget

"""
import math
import re
import sys
import os
import argparse
from csv import writer
import textwrap
import fnmatch

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''
        converts an edm {file}.edl file to a pydm {file}_autogen.ui file and a .csv file for widgets that do not yet have a conversion function

        conversion guide with solutions to common conversion problems
        -----------------------------------------------
        PyDMFrame

        All widgets in an EDM group are placed into a PyDMFrame, this works for many layers of goups
        -----------------------------------------------
        QLabel

        "Static Text" without a Visibility PV
        -----------------------------------------------
        PyDMLabel
        If nothing is showing in the label or it is different form Edm change the displayFormat property

        "Static Text" with a Visibility PV
        "Text Update"
        "Text Control" with editable not selected
        "Text Monitor"
        -----------------------------------------------
        PyDMLineEdit
        If nothing is showing in the label or it is different form Edm change the displayFormat property

        "Text Entry"
        "Text Control" with editable selected
        -----------------------------------------------
        PyDMDrawingRectangle

        "Rectangle"
        -----------------------------------------------
        PyDMDrawingEllipse

        "Circle"
        -----------------------------------------------
        PyDMShellCommand

        "Shell Command"
        -----------------------------------------------
        PyDMPushButton

        "Message Button" with Button Type = Push
        -----------------------------------------------
        PyDMEnumComboBox

        "Message Button" with Button Type = Toggle
        -----------------------------------------------
        PyDMRelatedDisplayButton

        "Related Display" with no options used
        -----------------------------------------------
        PyDMEDMDisplayButton

        "Related Display" with -e or --edm-related option used
        -----------------------------------------------
        PyDMDrawingLine

        "Lines" with only two points (one line)
        -----------------------------------------------
        PyDMDrawingPolyLine

        "Lines" with more than two points (two or more lines)
        -----------------------------------------------
        ''')
)

parser.add_argument("-o", "--original-file-name", action='store_true',
                    help="If chosen the resulting file will be named {file}.ui rather than {file}_autogen.ui")
parser.add_argument("-e", "--edm-related", action='store_true',
                    help="If chosen all related displays buttons will convert to PyDMEDMRelatedDisplay widgets, converts to PyDMRelatedDisplay widgets by default")
parser.add_argument("-r", "--recursive", action='store_true',
                    help="Converts all .edl files in a given directory tree to pydm .ui files")
parser.add_argument("-n", "--no-csv", action='store_true', help="No csv file with overflow widgets is created")
parser.add_argument("-f", "--font-decrease", type=int, default=5,
                    help="EDM font is larger than PyDM font, ammount to decrease the font by, defaults to 5")
parser.add_argument("input_file",
                    help="Path to edm file to convert.  Needs to be .edl.  If -r option is used all .edl files in given directory tree will be converted")
args = parser.parse_intermixed_args()

# make sure file argument is a .edl file
if not args.recursive:
    if not args.input_file.endswith('.edl'):
        print("edm_to_pydm.py: error: wrong file type: .edl file type required")
        sys.exit(1)


class Converters(object):
    def __init__(self, input_file):
        with open(input_file, 'r') as edm:
            self.edmfile = edm.readlines()

        self.PydmLabel_count = 0
        self.LineEdit_count = 0
        self.Label_count = 0
        self.Rectangle_count = 0
        self.Circle_count = 0
        self.Shell_Command_count = 0
        self.Group_count = 0
        self.Push_Button_count = 0
        self.Enum_Combo_Box_count = 0
        self.Pydm_Related_count = 0
        self.Edm_Related_count = 0
        self.Widget_Line_count = 0
        self.Poly_Line_count = 0
        self.Enum_Button_count = 0
        self.group_positions = ['0,0']

        # should probably find a way to not hard code this file, but have it stick, so other labs can use it?, and so it works on prod? &TOOLS did not work :(
        try:
            self.edm_color_in_xml = self.color_dic_gen("/afs/slac/g/lcls/tools/edm/config/colors.list")
            on_mcc = True
        except:
            print("not on mcclogin")
            on_mcc = False

        if not on_mcc:
            try:
                self.edm_color_in_xml = self.color_dic_gen("/usr/local/lcls/tools/edm/config/colors.list")
            except:
                print("not on prod")
                sys.exit(1)

    def macro_trans(self, string):
        """"
        Transphorm the macro signature in a string from $(macro) to ${macro}

        Parameters
        ----------
        string : string
            string that will have it's macro signature converted

        Returns
        -------
        result : string
            parameter string that has converted macro signature

        ex: string = "text $(macro) text (note)"
            result = "text ${macro} text (note)"
        """
        macro = r"\$(\()(.+?)(\))"
        result = re.sub(macro, r"${\2}", string)
        return result

    def color_dic_gen(self, color_file):
        """
        Input colors.list file from edm.  This file is used for defining colors in edm.
        used once to generate the dictionary wich is then used to convert the colors to xml
        This will probably have to be configured for different labs

        Parameters
        ----------
        color_file : string
            file path to color.list file used by edm to define colors by number, it's basicaly a dictionary that needs some cleaning

        Returns
        -------
        color_dictionary : dictionary
            dictionary that holds the xml rgb for the related color code in edm
            ex:
            "0" = "<red>255</red>
                   <green>255</green>
                   <blue>255</blue>"
        """
        color_dictionary = {}
        with open(color_file, "r") as edmColorsFile:
            for line in edmColorsFile:
                if line.startswith("static"):
                    splitComment = line.split("#")
                    splitColorTitle = splitComment[0].split("\"")
                    reconverged = splitColorTitle[0] + splitColorTitle[2]
                    cleanLine = re.sub("[^0-9| ]", "", reconverged)
                    color_list = cleanLine.split()

                    for i in range(1, color_list.__len__()):
                        color_list[i] = int(int(color_list[i]) / 257)

                    color_dictionary.update({
                                                f"{color_list[0]}": f"<red>{color_list[1]}</red>\n<green>{color_list[2]}</green>\n<blue>{color_list[3]}</blue>\n"})
        return color_dictionary

    def alignment_converter(self, edmline, pydm):
        """
        converts the alignment properties in edm to pydm
        AlignVCenter is default in pydm, not explicitly adding it introduces a bug though, so it is included here

        """

        pydm.writelines('<property name="alignment">\n')

        if edmline.__contains__('center'):
            pydm.writelines('<set>Qt::AlignCenter|Qt::AlignVCenter</set>\n</property>\n')

        if edmline.__contains__('left'):
            pydm.writelines('<set>Qt::AlignLeft|Qt::AlignVCenter</set>\n</property>\n')

        if edmline.__contains__('right'):
            pydm.writelines('<set>Qt::AlignRight|Qt::AlignVCenter</set>\n</property>\n')

    def geometry_converter(self, edmline, pydm):
        """
        Adds the x position, y position, height, and width of a widget from edm to the geometry property in pydm

        """

        prop = edmline.strip().split()
        if prop[0] == 'x':
            pydm.writelines('<property name="geometry">\n<rect>\n')
            group_position = self.group_positions[len(self.group_positions) - 1].split(',')
            prop[1] = int(prop[1]) - int(group_position[0])

        if prop[0] == 'y':
            group_position = self.group_positions[len(self.group_positions) - 1].split(',')
            prop[1] = int(prop[1]) - int(group_position[1])

        if prop[0] == 'w':
            prop[0] = 'width'
            if float(prop[1]) < 5:
                prop[1] = 5
        elif prop[0] == 'h':
            prop[0] = 'height'
            if float(prop[1]) < 5:
                prop[1] = 5
        lines = [f"<{prop[0]}>{prop[1]}</{prop[0]}>\n"]
        if prop[0] == 'height':
            lines.append("</rect>\n")
            lines.append("</property>\n")
        pydm.writelines(lines)

    def str_to_list(self, str1):
        """
        Turn a string into a list broken apart by the new line character
        """
        list1 = list(str1.split("\n"))
        return list1

    def xml_escape_characters(self, string):
        """
        Converts litterals to escape characters in xml
        '&' -> '&amp;'
        '<' -> '&lt;'
        '>' -> '&gt;'
        '"' -> '&quot;'
        ''' -> '&apos;'
        Parameters
        ----------
        string : string
            The string that needs it's literal characters converted to xml escape characters

        Returns
        -------
        string : string
            The input string with it's literal characters converted to xml escape characters

        example
        -------
        string = self.xml_escape_characters(string)
        """
        string = string.replace("&", "&amp;")
        string = string.replace("<", "&lt;")
        string = string.replace(">", "&gt;")
        string = string.replace("\\\"", "&quot;")
        string = string.replace("'", "&apos;")
        return string

    def font_converter(self, edmline, pydm):
        """
        Adds the font size, italics, and bold
        """

        fontline = edmline
        fontlist = fontline.strip("\"").split("-")
        fontsize_str = fontlist[3]
        fontsize_str = fontsize_str.replace(".0", "")
        # subtract from fontsize(pydm font is larger than edm)
        fontsize = int(fontsize_str) - args.font_decrease
        pydm.writelines('<property name="font">\n<font>\n')
        pydm.writelines('<pointsize>' + str(fontsize) + '</pointsize>\n')

        italic_search = '-'.join(fontline.split('-')[2:])

        # method to search for italic and bold
        if italic_search.__contains__('i') and fontline.__contains__('bold'):
            pydm.writelines(["<italic>true</italic>\n",
                             "<weight>75</weight>\n",
                             "<bold>true</bold>\n",
                             "</font>\n",
                             "</property>\n"])
        # method to search for only italic
        elif italic_search.__contains__('i'):
            pydm.writelines('<italic>true</italic>\n</font>\n</property>\n')

        # method to search for only bold
        elif fontline.__contains__('bold'):
            pydm.writelines('<weight>75</weight>\n<bold>true</bold>\n</font>\n</property>\n')

        elif italic_search.__contains__('r'):
            pydm.writelines('</font>\n</property>\n')

    def pv_converter(self, edmline, pydm):
        """
        Adds the control pv into the control pv in pydm, could be expanded for none control pvs
        """
        prop = edmline.strip().split()
        pv = prop[1].strip('"')
        cleaned_pv = self.macro_trans(pv)
        lines = ["<property name=\"channel\" stdset=\"0\">\n",
                 f"<string>{cleaned_pv}</string>\n",
                 "</property>\n"]
        pydm.writelines(lines)

    def alarm_sensitive_content_converter(self, widget_string, pydm):
        """
        Adds the alarmSensitiveContent property to a pydm widget
        """
        if widget_string.__contains__("fillAlarm") or widget_string.__contains__("fgAlarm"):
            pydm.writelines(["<property name=\"alarmSensitiveContent\" stdset=\"0\">\n",
                             "<bool>true</bool>\n",
                             "</property>\n"])
        else:
            pydm.writelines(["<property name=\"alarmSensitiveContent\" stdset=\"0\">\n",
                             "<bool>false</bool>\n",
                             "</property>\n"])

    def alarm_sensitive_border_converter(self, widget_string, pydm):
        """
        Adds the alarmSensitiveBorder property to a pydm widget
        """
        if widget_string.__contains__("lineAlarm") or widget_string.__contains__("fgAlarm"):
            pydm.writelines(["<property name=\"alarmSensitiveBorder\" stdset=\"0\">\n",
                             "<bool>true</bool>\n",
                             "</property>\n"])
        else:
            pydm.writelines(["<property name=\"alarmSensitiveBorder\" stdset=\"0\">\n",
                             "<bool>false</bool>\n",
                             "</property>\n"])

    def forground_color_converter(self, edmline, pydm):
        """
        Writes the forground color property for the widget
        for a lot of widgets the "forground color" is the "penColor" (boarder color)

        Parameters
        ----------
        edmline : string
            The current line the widget converter is looking at in the edm file
        pydm : file
            pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        if edmline.startswith("lineColor"):
            line_list = edmline.split()
            color_index = line_list[2]
            pydm.writelines(["<property name=\"penStyle\" stdset=\"0\">\n",
                             "<enum>Qt::SolidLine</enum>\n"
                             "</property>\n"
                             "<property name=\"penColor\" stdset=\"0\">"
                             "<color>\n",
                             f"{self.edm_color_in_xml.get(color_index)}",
                             "</color>\n</property>\n"])

    def background_color_converter(self, edmline, pydm, widget_string):
        """
        Writes the background color property for the widget

        Parameters
        ----------
        edmline : string
            The current line the widget converter is looking at in the edm file
        pydm : file
            pydm file the widget gets writen to
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n
            needed as not all of the fill and fillColor properties are not on the same line
            in the edm file

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        if widget_string.__contains__("fill\n") and edmline.startswith("fillColor"):
            # brush = fill
            line_list = edmline.split()
            color_index = line_list[2]
            pydm.writelines(["<property name=\"brush\" stdset=\"0\">\n",
                             "<brush brushstyle=\"SolidPattern\">\n",
                             "<color alpha=\"255\">\n",
                             f"{self.edm_color_in_xml.get(color_index)}",
                             "</color>\n</brush>\n</property>\n"])
        elif edmline.startswith("fillColor"):
            # brush != fill
            line_list = edmline.split()
            color_index = line_list[2]
            pydm.writelines(["<property name=\"brush\" stdset=\"0\">\n",
                             "<brush brushstyle=\"NoBrush\">\n",
                             "<color alpha=\"255\">\n",
                             f"{self.edm_color_in_xml.get(color_index)}",
                             "</color>\n</brush>\n</property>\n"])

    def line_width_converter(self, edmline, pydm):
        """
        Writes the penWidth (PYDM) property for the widget from the lineWidth (EDM) property

        Parameters
        ----------
        edmline : string
            All of the display mode properites from the edm widget in string form
        pydm : pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        temp = edmline.split(" ")
        pydm.writelines(["<property name=\"penWidth\" stdset=\"0\">\n",
                         f"<double>{temp[1]}</double>\n"
                         "</property>\n"])

    def line_style_converter(self, edmline, pydm):
        """
        Converts the line style
        """
        if edmline.__contains__("dash"):
            pydm.writelines(["<property name=\"penStyle\" stdset=\"0\">\n",
                             "<enum>Qt::DashLine</enum>\n"
                             "</property>\n"])

    def button_label_converter(self, edmline, pydm):
        """
        Writes the button label property for the widget

        Parameters
        ----------
        edmline : string
            All of the display mode properites from the edm widget in string form
        pydm : pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        label_line = str(edmline)
        # this should be changed so that other properties can be replaced in edm
        # not nessisary if "buttonLabel" is the only edm line needed to flag on
        label_list = label_line.split("\"")

        # removes the quotes from the button label
        label = label_list[1]
        label = label.replace("...", "")
        label = self.xml_escape_characters(label)
        label = self.macro_trans(label)
        lines = ["<property name=\"text\">\n",
                 f"<string>{label}</string>\n",
                 "</property>\n"]
        pydm.writelines(lines)

    def display_mode_converter(self, edmline, pydm):
        """
        Writes the display mode property for the widget

        Parameters
        ----------
        edmline : string
            All of the display mode properites from the edm widget in string form
        pydm : pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        pydm.writelines('<property name="displayFormat" stdset="0">\n')

        # deafault, decimal, hex, engineer, exp
        if edmline.__contains__('decimal'):
            pydm.writelines('<enum>PyDMLabel::Decimal</enum>\n</property>\n')
        elif edmline.__contains__('hex'):
            pydm.writelines('<enum>PyDMLabel::Hex</enum>\n</property>\n')
        elif edmline.__contains__('engineer') or edmline.__contains__('exp'):
            pydm.writelines('<enum>PyDMLabel::Exponential</enum>\n</property>\n')
        elif edmline.__contains__('string'):
            pydm.writelines('<enum>PyDMLabel::String</enum>\n</property>\n')
        else:
            pydm.writelines('<enum>PyDMLabel::Default</enum>\n</property>\n')

    def display_mode_edit_converter(self, edmline, pydm):
        """
        Writes the display mode property for the widget

        Parameters
        ----------
        edmline : string
            All of the display mode properites from the edm widget in string form
        pydm : pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        pydm.writelines('<property name="displayFormat" stdset="0">\n')

        # deafault, decimal, hex, engineer, exp
        if edmline.__contains__('decimal'):
            pydm.writelines('<enum>PyDMLineEdit::Decimal</enum>\n</property>\n')
        elif edmline.__contains__('hex'):
            pydm.writelines('<enum>PyDMLineEdit::Hex</enum>\n</property>\n')
        elif edmline.__contains__('engineer') or edmline.__contains__('exp'):
            pydm.writelines('<enum>PyDMLineEdit::Exponential</enum>\n</property>\n')
        elif edmline.__contains__('string'):
            pydm.writelines('<enum>PyDMLineEdit::String</enum>\n</property>\n')
        else:
            pydm.writelines('<enum>PyDMLineEdit::Default</enum>\n</property>\n')

    def visibility_converter(self, visibility_string, pydm):
        """
        Writes the visiblity rules for the widget

        Parameters
        ----------
        visibility_string : string
            All of the visibility properites from the edm widget in string form, separated by \n
        pydm : pydm file the widget gets writen to

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        if visibility_string.__contains__("visMax"):
            has_vis_max = True
        else:
            has_vis_max = False

        if visibility_string.__contains__("visMin"):
            has_vis_min = True
        else:
            has_vis_min = False

        if visibility_string.__contains__("visInvert"):
            vis_invert = 'not '
        else:
            vis_invert = ''

        visibility_list = self.str_to_list(visibility_string)
        for edmline in visibility_list:
            if edmline.startswith("visMax"):
                temp_max = edmline.strip().split()
                vis_max = temp_max[1].strip('"')

            if edmline.startswith("visMin"):
                temp_min = edmline.strip().split()
                vis_min = temp_min[1].strip('"')

            if edmline.startswith('visPv'):
                temp_pv = edmline.strip().split()
                clean_temp_pv = temp_pv[1].strip('"')
                vis_pv = self.macro_trans(clean_temp_pv)

        if vis_pv.__contains__('CALC'):
            print(vis_pv)
        else:
            pydm.writelines(["<property name=\"rules\" stdset=\"0\">\n<string>[{",
                             "&quot;name&quot;: &quot;visibility_from_edm&quot;, ",
                             "&quot;property&quot;: &quot;Visible&quot;, ",
                             "&quot;initial_value&quot;: &quot;True&quot;, "])
            if has_vis_min and has_vis_max:
                pydm.writelines(
                    f"&quot;expression&quot;: &quot;{vis_invert}ch[0] &gt;={vis_min} and ch[0] &lt; {vis_max}&quot;, ")
            elif has_vis_min and not has_vis_max:
                pydm.writelines(f"&quot;expression&quot;: &quot;{vis_invert}ch[0] &gt;={vis_min}&quot;, ")
            elif not has_vis_min and has_vis_max:
                pydm.writelines(f"&quot;expression&quot;: &quot;{vis_invert}ch[0] &lt; {vis_max}&quot;, ")
            elif not has_vis_min and not has_vis_max:
                pydm.writelines(f"&quot;expression&quot;: &quot;ch[0]&quot;, ")
                # print("widget has visability pv, but no expression")

            pydm.writelines(["&quot;channels&quot;: [{",
                             f"&quot;channel&quot;: &quot;{vis_pv}&quot;, ",
                             "&quot;trigger&quot;: true, "
                             "&quot;use_enum&quot;: false}]}]</string>\n</property>\n"])

    def main_converter(self):
        """
        Main conversion function, all conversion occures in this function
        Converts all properties to do with the from
        Reads in one widget at a time, converting it to a string
        Uses the widget string to identify the which widget it should be converted into, and calls appropriate conversion function
        If the widget is unconvertable converts it adds it to a csv file

        Parameters
        ----------
        none : uses the global variable edm_file

        Returns
        -------
        none : writes to the pydm_file
        """

        in_screen_prop = False  # True if reading in screen properties from edm, False otherwise

        # counters for each widget type
        # necissary for unique widget names in pydm
        # Step 1

        line_count = 0

        with open(pydm_file, 'w') as pydm:
            for i, edmline in enumerate(self.edmfile):

                if edmline.startswith('4 0 1'):
                    in_screen_prop = True
                    pydm.writelines(["<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n",
                                     "<ui version=\"4.0\">\n",
                                     "<class>Form</class>\n",
                                     "<widget class=\"QWidget\" name=\"Form\">\n"
                                     "<property name=\"geometry\">\n"
                                     "<rect>\n<x>0</x>\n<y>0</y>\n"])

                # convert screen width
                if edmline.startswith('w ') and in_screen_prop:
                    w_position = edmline[2:]
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                # convert screen height
                elif edmline.startswith('h ') and in_screen_prop:
                    h_position = edmline[2:]
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n</property>\n')

                # convert screen title
                elif edmline.startswith('title') and in_screen_prop:
                    screen_title = edmline[7:-2]
                    screen_title = screen_title.replace("\n", "")
                    pydm.writelines('<property name="windowTitle">\n')

                    # method to change it into macro w ${}
                    macro = r"\$(\()(.+?)(\))"
                    result = re.sub(macro, r"${\2}", screen_title)

                    pydm.writelines("<string>" + str(result) + "</string>\n")
                    pydm.writelines('</property>\n')

                # end of screen properties
                # set in_screen_prop to false so non-screen properties are not converted
                if edmline.startswith('endScreenProperties'):
                    in_screen_prop = False
                    line_count = i

        self.widgets_converter(line_count)

        self.end_xml()

    def widgets_converter(self, line_count):
        """
        Parameters
        ----------
        line_count : int
            The line of the edm file that the screen properties ends at

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        is_in_widget = False
        is_first_unconvertable = True
        is_in_group = False
        is_in_group_visibility = False

        # start looking at edm file after the screen properties
        for edmline in self.edmfile[line_count:]:

            # Convert each widget into a string, determin what type of widget it should be converted into, then convert it
            # Denotes the begining of converting the EDM widget into a string
            # Clears the widget_string
            # using the "# (" is a little scary, but it is necessary for the unconvertalbe function to get the more inteligable name of the widget
            # migth change back to "object" to make sure only objects are accounted for
            if edmline.startswith('# (') and not edmline.startswith('# (Group)'):
                is_in_widget = True
                widget_string = edmline
            elif is_in_widget and not edmline.startswith('# ('):
                widget_string = widget_string + edmline
            elif edmline.startswith('# (Group)'):
                is_in_group = True
                group_string = edmline
            elif is_in_group and not edmline.startswith('# (Group)'):
                group_string = group_string + edmline
                if edmline.startswith('h '):
                    self.Group_count = self.Group_count + 1
                    self.group_converter(group_string)

            if edmline.startswith('endGroup'):
                is_in_group_visibility = True
                visibility_string = ""
            if is_in_group_visibility:
                visibility_string = visibility_string + '\n' + edmline
                if edmline.startswith('endObjectProperties'):
                    pydm = open(pydm_file, 'a')
                    if visibility_string.__contains__('visPv'):
                        self.visibility_converter(visibility_string, pydm)
                    pydm.writelines("</widget>\n")
                    pydm.close()
                    self.group_positions.pop()
                    is_in_group_visibility = False

            # Step 2
            # when endObjectProperties is found convert the widget into pydm
            if is_in_widget and edmline.startswith('endObjectProperties'):
                is_in_widget = False

                # figure out what type of widget it is and call appropriate converter function
                # if widget_string.__contains__('object TextupdateClass') or widget_string.__contains__('object activeXTextDspClass:noedit'):
                if widget_string.__contains__('object TextupdateClass'):
                    self.PydmLabel_count = self.PydmLabel_count + 1
                    self.pydm_label_converter(widget_string)

                elif widget_string.__contains__('object activeXTextDspClass') and not widget_string.__contains__(
                        'editable'):
                    self.PydmLabel_count = self.PydmLabel_count + 1
                    self.pydm_label_converter(widget_string)

                elif widget_string.__contains__('object activeXTextDspClass') and widget_string.__contains__(
                        'editable'):
                    self.LineEdit_count = self.LineEdit_count + 1
                    self.pydm_line_edit_converter(widget_string)

                elif widget_string.__contains__('object TextentryClass'):
                    self.LineEdit_count = self.LineEdit_count + 1
                    self.pydm_line_edit_converter(widget_string)

                elif widget_string.__contains__('object activeXTextClass') and not widget_string.__contains__('visPv'):
                    self.Label_count = self.Label_count + 1
                    self.static_text_converter(widget_string)

                elif widget_string.__contains__('object activeXTextClass') and widget_string.__contains__('visPv'):
                    self.PydmLabel_count = self.PydmLabel_count + 1
                    self.pydm_label_converter(widget_string)

                elif widget_string.__contains__('object activeRectangleClass'):
                    self.Rectangle_count = self.Rectangle_count + 1
                    self.rectangle_converter(widget_string)

                elif widget_string.__contains__('object activeCircleClass'):
                    self.Circle_count = self.Circle_count + 1
                    self.circle_converter(widget_string)

                elif widget_string.__contains__('object shellCmdClass'):
                    self.Shell_Command_count = self.Shell_Command_count + 1
                    self.shell_command_converter(widget_string)

                elif widget_string.__contains__('object activeMessageButtonClass') and not widget_string.__contains__(
                        'toggle'):
                    self.Push_Button_count = self.Push_Button_count + 1
                    self.button_converter(widget_string)

                elif widget_string.__contains__('object activeMessageButtonClass') and widget_string.__contains__(
                        'toggle'):
                    self.Enum_Combo_Box_count = self.Enum_Combo_Box_count + 1
                    self.enum_combo_box_converter(widget_string)

                elif widget_string.__contains__('object activeMenuButtonClass'):
                    self.Enum_Combo_Box_count = self.Enum_Combo_Box_count + 1
                    self.enum_combo_box_converter(widget_string)

                elif widget_string.__contains__("object relatedDisplayClass") and not args.edm_related:
                    self.Pydm_Related_count = self.Pydm_Related_count + 1
                    self.pydm_related_converter(widget_string)

                elif widget_string.__contains__("object relatedDisplayClass"):
                    # no count increment becuase it could also be converted to shell command
                    self.edm_related_converter(widget_string)

                elif widget_string.__contains__("object activeLineClass"):
                    # no count increment because it could be converted into PyDMDrawingLine or PyDMDrawingPolyLine
                    self.line_converter(widget_string)

                elif widget_string.__contains__("object activeChoiceButtonClass"):
                    self.Enum_Button_count = self.Enum_Button_count + 1
                    self.enum_button_converter(widget_string)


                # Step 2 Add the case for your widget in an elif statement directly above this comment
                # needs to be elif directly above this for the else statement below to work
                else:
                    if not args.no_csv:
                        self.UnConvertable(widget_string, is_first_unconvertable)
                    if is_first_unconvertable:
                        is_first_unconvertable = False

    def group_converter(self, group_string):

        group_list = self.str_to_list(group_string)
        pydm = open(pydm_file, 'a')
        for edmline in group_list:

            # method to give unique name for the label(increment the value title)
            if edmline.startswith('object'):
                pydm.writelines([f"<widget class=\"PyDMFrame\" name=\"PyDMFrame_{self.Group_count}\">\n"])

            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)
                if edmline.startswith('x'):
                    temp = edmline.split(' ')
                    x_position = temp[1]

                if edmline.startswith('y'):
                    temp = edmline.split(' ')
                    y_position = temp[1]

                    self.group_positions.append(f"{x_position},{y_position}")
        pydm.close()

    # Static Text to QLabel Convert function
    def static_text_converter(self, widget_string):
        """
        Converts the widget given to it into a QLabel

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        in_text = False
        textLines = []
        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')

        # method to give unique name for the label(increment the value title)
        pydm.writelines([f"<widget class=\"QLabel\" name=\"label_{self.Label_count}\">\n"])

        for edmline in widget_list:

            # take out the screen sizes as variable to write same size in pydm file
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # compile the static text entry as it stretches over multiple lines in edm
            elif edmline.startswith('value {') or in_text:
                if edmline.startswith('}'):
                    in_text = False
                    pydm.writelines('<property name="text">\n<string>')
                    for line_number, textLine in enumerate(textLines):
                        if line_number > 0:
                            pydm.writelines("\n")
                        pydm.writelines(f"{textLine}")
                    pydm.writelines('</string>\n</property>\n')

                elif not edmline.startswith('value {'):
                    textLine = edmline[3:-1]
                    textLine = self.macro_trans(textLine)
                    textLine = self.xml_escape_characters(textLine)
                    textLines.append(textLine)

                if edmline.startswith('value {'):
                    in_text = True

            # take out the font size and cut off extra string to use same font size in pydm file
            elif edmline.startswith('font "'):
                self.font_converter(edmline, pydm)

            # assign the differnt boader
            elif edmline.startswith('border'):
                pydm.writelines('<property name="frameShape">\n<enum>QFrame::Box</enum>\n</property>\n')

            elif edmline.startswith('fontAlign'):
                self.alignment_converter(edmline, pydm)

            # close this properties w the ending lines
            elif edmline.startswith('endObjectProperties'):
                pydm.writelines("</widget>\n")

        pydm.close()

    # Text Update to PydmLabel Convert function
    def pydm_label_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMLabel

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file
        """
        if widget_string.__contains__('object activeXTextClass'):
            textLines = []
        in_text = False
        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')

        pydm.writelines([f"<widget class=\"PyDMLabel\" name=\"PyDMLabel_{self.PydmLabel_count}\">\n"])

        self.alarm_sensitive_content_converter(widget_string, pydm)

        self.alarm_sensitive_border_converter(widget_string, pydm)

        for edmline in widget_list:

            # take out the screen sizes as variable to write same size in pydm file
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith("controlPv "):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith('format '):
                self.display_mode_converter(edmline, pydm)

            # take out the font size and cut off extra string to use same font size in pydm file
            elif edmline.startswith('font "'):
                self.font_converter(edmline, pydm)

            elif edmline.startswith('fontAlign'):
                self.alignment_converter(edmline, pydm)

            # assign the linewidth and boarder
            elif edmline.startswith('lineWidth'):
                l_w = edmline.split(" ")
                pydm.writelines('<property name="lineWidth">\n<number>' + l_w[1] + '</number>\n</property>\n')

            elif edmline.startswith('showUnits'):
                pydm.writelines("<property name=\"showUnits\" stdset=\"0\">\n<bool>true</bool>\n</property>")

            # for static text that needs to be a PyDMLabel because it has visibility rules
            # don't want it to even consider this code if it is not a static text widget in edm
            elif (edmline.startswith('value {') or in_text) and widget_string.__contains__('object activeXTextClass'):
                if edmline.startswith('}'):
                    in_text = False
                    pydm.writelines('<property name="text">\n<string>')
                    for line_number, textLine in enumerate(textLines):
                        if line_number > 0:
                            pydm.writelines("\n")
                        pydm.writelines(f"{textLine}")
                    pydm.writelines('</string>\n</property>\n')

                elif not edmline.startswith('value {'):
                    textLine = edmline[3:-1]
                    textLine = self.macro_trans(textLine)
                    textLine = self.xml_escape_characters(textLine)
                    textLines.append(textLine)

                if edmline.startswith('value {'):
                    in_text = True

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget and add visibility rules if they exist
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    # Text Control to PydmLineEdit Convert function
    def pydm_line_edit_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMLineEdit

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        # counting the number of label
        text_control_value_flag = False
        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')

        for edmline in list(widget_list):
            if edmline.startswith('object'):
                # method to give unique name for the label(increment the value title)
                pydm.writelines('<widget class="PyDMLineEdit" name="PyDMLineEdit_' + str(self.LineEdit_count) + '">\n')

            # take out the screen sizes as variable to write same size in pydm file
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith('controlPv '):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith('displayMode'):
                self.display_mode_edit_converter(edmline, pydm)

            # take out the font size and cut off extra string to use same font size in pydm file
            elif edmline.startswith('font "'):
                self.font_converter(edmline, pydm)

            elif edmline.startswith('fontAlign'):
                self.alignment_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget and add visibility rules if they exist
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    def rectangle_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMDrawingRectangle

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')

        # Give unique name for the rectangle
        pydm.writelines(
            [f"<widget class=\"PyDMDrawingRectangle\" name=\"PyDMDrawingRectangle_{self.Rectangle_count}\">\n"])

        self.alarm_sensitive_content_converter(widget_string, pydm)

        self.alarm_sensitive_border_converter(widget_string, pydm)

        for edmline in widget_list:
            # take out the screen sizes as variable to write same size in pydm file
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith('alarmPv '):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith('lineColor'):
                self.forground_color_converter(edmline, pydm)

            elif edmline.startswith('fillColor'):
                self.background_color_converter(edmline, pydm, widget_string)

            elif edmline.startswith('lineWidth'):
                self.line_width_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPv'):
                visibility_string = visibility_string + '\n' + edmline

            # close this properties w the ending lines
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    def circle_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMDrawingEllipse

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')

        # Give unique name for the Circle
        pydm.writelines([f"<widget class=\"PyDMDrawingEllipse\" name=\"PyDMDrawingEllipse_{self.Circle_count}\">\n"])

        self.alarm_sensitive_content_converter(widget_string, pydm)

        self.alarm_sensitive_border_converter(widget_string, pydm)

        for edmline in widget_list:
            # take out the screen sizes as variable to write same size in pydm file
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith('alarmPv '):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith('lineColor'):
                self.forground_color_converter(edmline, pydm)

            elif edmline.startswith('fillColor'):
                self.background_color_converter(edmline, pydm, widget_string)

            elif edmline.startswith('lineWidth'):
                self.line_width_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline

            # close this properties w the ending lines
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    def shell_command_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMShellCommand

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file

        """

        widget_list = self.str_to_list(widget_string)
        in_commandLabel = False
        in_command = False
        commandLabels = []
        commands = []
        pydm = open(pydm_file, 'a')
        for edmline in widget_list:

            if edmline.startswith('object shellCmdClass'):
                # Give unique name to the widget
                pydm.writelines(
                    [f"<widget class=\"PyDMShellCommand\" name=\"PyDMShellCommand_{self.Shell_Command_count}\">\n"])

            # convert the geometry of the widget (x position, y position, height, and width
            elif edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            # collect command labels into a string then convert to pydm
            elif edmline.startswith('commandLabel {') or in_commandLabel:

                # write to pydm file at the end of the command label block, otherwise collect the command label from the edm file
                if edmline.startswith('}'):
                    in_commandLabel = False

                    # add commandLabels to pydm
                    pydm.writelines("<property name=\"titles\" stdset=\"0\">\n<stringlist>\n")
                    for commandLabel in commandLabels:
                        self.xml_escape_characters
                        pydm.writelines([f"<string>{commandLabel}</string>\n"])
                    pydm.writelines("</stringlist>\n</property>\n")

                # if not at the beginning or end of command lable block, add the command to commandLabels
                elif not edmline.startswith('commandLabel {'):
                    prop = edmline[5:-1]
                    commandLabels.append(prop)

                # if at the beginnign of the command label block set the in_commandLabel flag to True
                if edmline.startswith('commandLabel {'):
                    in_commandLabel = True

            # collect commands into a string then convert to pydm
            elif edmline.startswith('command {') or in_command:

                # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                if edmline.startswith('}'):
                    in_command = False

                    # add commands to pydm
                    pydm.writelines("<property name=\"commands\" stdset=\"0\">\n<stringlist>\n")
                    for command in commands:
                        command = command.replace('&', '&amp;')
                        pydm.writelines("<string>" + command + "</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

                # if not at the begining of or end of the command block, add the command to commands
                elif not edmline.startswith('command {'):
                    prop = edmline[5:-1]
                    prop = prop.replace("\\\"", "\"")  # xml escape characters?
                    commands.append(prop)
                # if at the beginnign of the command block set the in_commandLabel flag to True
                if edmline.startswith('command {'):
                    in_command = True

            # convert the text on the button of the shell command
            elif edmline.startswith('buttonLabel'):
                self.button_label_converter(edmline, pydm)

                if widget_string.__contains__("pydm"):
                    print(
                        edmline + ":  Contains a command to launch a pydm screen, advised to change this to a PyDMRelatedDisplayButton")

            # Close the widget at the end of the edm properites
            elif edmline.startswith('endObjectProperties'):
                pydm.writelines("</widget>\n")

        pydm.close()

    def button_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMPushButton

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file

        """

        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')
        pydm.writelines([f"<widget class=\"PyDMPushButton\" name=\"PyDMPushButton_{self.Push_Button_count}\">\n"])

        for edmline in widget_list:

            # convert the geometry of the widget (x position, y position, height, and width
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            elif edmline.startswith("pressValue") and edmline.__contains__("\""):
                # get pressValue
                temp_list = edmline.strip("\"").split()
                press_value = temp_list[1].strip("\"")
                pydm.writelines(["<property name=\"pressValue\" stdset=\"0\">\n",
                                 f"<string>{press_value}</string>\n",
                                 "</property>\n"])

            elif edmline.startswith("releaseValue") and edmline.__contains__("\""):
                # get releaseValue
                temp_list = edmline.split("\"")
                release_value = temp_list[1]
                pydm.writelines(["<property name=\"releaseValue\" stdset=\"0\">\n",
                                 f"<string>{release_value}</string>\n",
                                 "</property>\n"])

            # use onLabel, offLabel,

            elif edmline.startswith("onLabel"):
                # get onLabel
                self.button_label_converter(edmline, pydm)

            elif edmline.startswith("offLabel") and not widget_string.__contains__("onLabel"):
                # get offLabel
                self.button_label_converter(edmline, pydm)

            elif edmline.startswith('controlPv '):
                self.pv_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget at the end of the edm properites
            elif edmline.startswith('endObjectProperties'):
                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    def enum_combo_box_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMEnumComboBox

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file

        """

        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')
        pydm.writelines(
            [f"<widget class=\"PyDMEnumComboBox\" name=\"PyDMEnumComboBox_{self.Enum_Combo_Box_count}\">\n"])
        for edmline in widget_list:
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)
            elif edmline.startswith('controlPv '):
                self.pv_converter(edmline, pydm)
            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline
            elif edmline.startswith('endObjectProperties'):
                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")

        pydm.close()

    def pydm_related_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMEnumComboBox

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file

        """
        widget_list = self.str_to_list(widget_string)
        in_files = False
        in_labels = False
        in_macros = False
        files = []
        labels = []
        macros = []
        pydm = open(pydm_file, 'a')
        pydm.writelines([
                            f"<widget class=\"PyDMRelatedDisplayButton\" name=\"PyDMRelatedDisplayButton_{self.Pydm_Related_count}\">\n"])
        for edmline in widget_list:
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            elif edmline.startswith('displayFileName {') or in_files:

                # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                if edmline.startswith('}'):
                    in_files = False

                    # add commands to pydm
                    pydm.writelines("<property name=\"filenames\" stdset=\"0\">\n<stringlist>\n")
                    for display_file in files:
                        display_file = self.xml_escape_characters(display_file)
                        display_file = str(self.macro_trans(display_file))
                        pydm.writelines("<string>" + display_file + "</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

                # if not at the begining of or end of the command block, add the command to commands
                elif not edmline.startswith('displayFileName {'):
                    prop = edmline[5:-1]
                    prop = self.xml_escape_characters(prop)

                    prop_list = prop.split('.')

                    files.append(prop_list[0])
                # if at the beginnign of the command block set the in_commandLabel flag to True
                if edmline.startswith('displayFileName {'):
                    in_files = True

            elif edmline.startswith('menuLabel {') or in_labels:

                # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                if edmline.startswith('}'):
                    in_labels = False

                    # add commands to pydm
                    pydm.writelines("<property name=\"titles\" stdset=\"0\">\n<stringlist>\n")
                    for display_label in labels:
                        display_label = self.xml_escape_characters(display_label)
                        display_label = self.macro_trans(display_label)
                        pydm.writelines("<string>" + display_label + "</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

                # if not at the begining of or end of the command block, add the command to commands
                elif not edmline.startswith('menuLabel {'):
                    prop = edmline[5:-1]
                    prop = self.xml_escape_characters(prop)
                    prop = self.macro_trans(prop)
                    labels.append(prop)

                # if at the beginnign of the command block set the in_commandLabel flag to True
                if edmline.startswith('menuLabel {'):
                    in_labels = True

            elif edmline.startswith('symbols {') or in_macros:

                # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                if edmline.startswith('}'):
                    in_macros = False

                    # add commands to pydm
                    pydm.writelines("<property name=\"macros\" stdset=\"0\">\n<stringlist>\n")
                    for macro in macros:
                        macro = self.xml_escape_characters(macro)
                        macro = self.macro_trans(macro)
                        pydm.writelines("<string>" + macro + "</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

                # if not at the begining of or end of the command block, add the command to commands
                elif not edmline.startswith('symbols {'):
                    prop = edmline[5:-1]
                    prop = self.xml_escape_characters(prop)
                    macros.append(prop)
                # if at the beginnign of the command block set the in_commandLabel flag to True
                if edmline.startswith('symbols {'):
                    in_macros = True
            elif edmline.startswith('buttonLabel'):
                self.button_label_converter(edmline, pydm)
            elif edmline.startswith('endObjectProperties'):
                pydm.writelines(["<property name=\"openInNewWindow\" stdset=\"0\">\n",
                                 "<bool>true</bool>\n",
                                 "</property>\n"])

                pydm.writelines("</widget>\n")

        pydm.close()

    def edm_related_converter(self, widget_string):
        """
        Converts the widget given to it into a PyDMEnumComboBox

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file in string form, separated by \n

        Returns
        -------
        none : writes to pydm (.ui) file

        """
        widget_list = self.str_to_list(widget_string)
        in_files = False
        in_labels = False
        in_macros = False
        macros_are_too_long = False
        files = []
        labels = []
        macros = []

        for edmline in widget_list:
            if edmline.startswith('symbols {') or in_macros:
                if edmline.startswith('symbols {'):
                    in_macros = True
                elif edmline.startswith('}'):
                    in_macros = False
                elif len(edmline) > 150:
                    macros_are_too_long = True

        if not macros_are_too_long:
            pydm = open(pydm_file, 'a')
            self.Edm_Related_count = self.Edm_Related_count + 1
            pydm.writelines(
                [f"<widget class=\"PyDMEDMDisplayButton\" name=\"PyDMEDMDisplayButton_{self.Edm_Related_count}\">\n"])
            for edmline in widget_list:
                if edmline.startswith(("x ", "y ", "w ", "h ")):
                    self.geometry_converter(edmline, pydm)

                elif edmline.startswith('displayFileName {') or in_files:

                    # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                    if edmline.startswith('}'):
                        in_files = False

                        # add commands to pydm
                        pydm.writelines("<property name=\"filenames\" stdset=\"0\">\n<stringlist>\n")
                        for display_file in files:
                            display_file = self.xml_escape_characters(display_file)
                            display_file = str(self.macro_trans(display_file))
                            pydm.writelines("<string>" + display_file + "</string>\n")
                        pydm.writelines("</stringlist>\n</property>\n")

                    # if not at the begining of or end of the command block, add the command to commands
                    elif not edmline.startswith('displayFileName {'):
                        prop = edmline[5:-1]
                        prop = self.xml_escape_characters(prop)

                        prop_list = prop.split('.')

                        files.append(prop_list[0])
                    # if at the beginnign of the command block set the in_commandLabel flag to True
                    if edmline.startswith('displayFileName {'):
                        in_files = True

                elif edmline.startswith('menuLabel {') or in_labels:

                    # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                    if edmline.startswith('}'):
                        in_labels = False

                        # add commands to pydm
                        pydm.writelines("<property name=\"titles\" stdset=\"0\">\n<stringlist>\n")
                        for display_label in labels:
                            display_label = self.xml_escape_characters(display_label)
                            display_label = self.macro_trans(display_label)
                            pydm.writelines("<string>" + display_label + "</string>\n")
                        pydm.writelines("</stringlist>\n</property>\n")

                    # if not at the begining of or end of the command block, add the command to commands
                    elif not edmline.startswith('menuLabel {'):
                        prop = edmline[5:-1]
                        prop = self.xml_escape_characters(prop)
                        labels.append(prop)
                    # if at the beginnign of the command block set the in_commandLabel flag to True
                    if edmline.startswith('menuLabel {'):
                        in_labels = True

                elif edmline.startswith('symbols {') or in_macros:

                    # write to pydm file at the end of the command block, otherwise collect the command from the edm file
                    if edmline.startswith('}'):
                        in_macros = False

                        # add commands to pydm
                        pydm.writelines("<property name=\"macros\" stdset=\"0\">\n<stringlist>\n")
                        for macro in macros:
                            macro = self.xml_escape_characters(macro)
                            macro = self.macro_trans(macro)
                            pydm.writelines("<string>" + macro + "</string>\n")
                        pydm.writelines("</stringlist>\n</property>\n")

                    # if not at the begining of or end of the command block, add the command to commands
                    elif not edmline.startswith('symbols {'):
                        prop = edmline[5:-1]
                        prop = self.xml_escape_characters(prop)
                        macros.append(prop)
                    # if at the beginnign of the command block set the in_commandLabel flag to True
                    if edmline.startswith('symbols {'):
                        in_macros = True
                elif edmline.startswith('buttonLabel'):
                    self.button_label_converter(edmline, pydm)
                elif edmline.startswith('endObjectProperties'):

                    pydm.writelines("</widget>\n")

            pydm.close()


        else:
            # make a shell command
            # will be a bit more intensive than making a normal shell command or a related display
            # as the macros and the file names will need to be added togetehr
            # edm -x -m "macros=macros" filename.edl
            self.Shell_Command_count = self.Shell_Command_count + 1
            pydm = open(pydm_file, 'a')
            pydm.writelines(
                [f"<widget class=\"PyDMShellCommand\" name=\"PyDMShellCommand_{self.Shell_Command_count}\">\n"])
            for edmline in widget_list:
                if edmline.startswith(("x ", "y ", "w ", "h ")):
                    self.geometry_converter(edmline, pydm)

                elif edmline.startswith('displayFileName {') or in_files:

                    # write to pydm file at the end of the file name block, otherwise collect the file names from the edm file
                    if edmline.startswith('}'):
                        in_files = False

                    # if not at the begining of or end of the file name block, add the file name to files
                    elif not edmline.startswith('displayFileName {'):
                        display_file = edmline[5:-1]
                        display_file = self.xml_escape_characters(display_file)
                        display_file = str(self.macro_trans(display_file))

                        files.append(display_file)
                    # if at the beginnign of the file name block set the in_files flag to True
                    if edmline.startswith('displayFileName {'):
                        in_files = True

                elif edmline.startswith('menuLabel {') or in_labels:

                    # write to pydm file at the end of the label block, otherwise collect the label from the edm file
                    if edmline.startswith('}'):
                        in_labels = False

                    # if not at the begining of or end of the label block, add the label to labels
                    elif not edmline.startswith('menuLabel {'):
                        display_label = edmline[5:-1]
                        display_label = self.xml_escape_characters(display_label)
                        display_label = str(self.macro_trans(display_label))
                        labels.append(display_label)

                    # if at the beginnign of the labels block set the in_label flag to True
                    if edmline.startswith('menuLabel {'):
                        in_labels = True

                elif edmline.startswith('symbols {') or in_macros:

                    # write to pydm file at the end of the macros block, otherwise collect the macros from the edm file
                    if edmline.startswith('}'):
                        in_macros = False

                    # if not at the begining of or end of the macros block, add the macros to macros
                    elif not edmline.startswith('symbols {'):
                        macro = edmline[5:-1]
                        macro = self.xml_escape_characters(macro)
                        macro = str(self.macro_trans(macro))
                        macros.append(macro)

                    # if at the beginnign of the macros block set the in_macros flag to True
                    if edmline.startswith('symbols {'):
                        in_macros = True

                elif edmline.startswith('buttonLabel'):
                    self.button_label_converter(edmline, pydm)
                elif edmline.startswith('endObjectProperties'):
                    # write all the properties to make a shell command :)
                    pydm.writelines("<property name=\"titles\" stdset=\"0\">\n<stringlist>\n")
                    for label in labels:
                        pydm.writelines([f"<string>{label}</string>\n"])
                    pydm.writelines("</stringlist>\n</property>\n")

                    # add commands to pydm
                    pydm.writelines("<property name=\"commands\" stdset=\"0\">\n<stringlist>\n")
                    for x, display_file in enumerate(files):
                        command = "edm -x -m &quot;" + str(macros[x]) + "&quot; " + str(display_file)
                        pydm.writelines("<string>" + command + "</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

                    pydm.writelines("</widget>\n")

            pydm.close()

    def line_converter(self, widget_string):
        """docstring :)"""

        y_points = []
        x_points = []
        widget_list = widget_string.split("}")
        x_points_temp = widget_list[0].split("{")
        y_points_temp = widget_list[1].split("{")

        x_points_temp2 = self.str_to_list(x_points_temp[1])
        x_points_temp2 = x_points_temp2[1:-1]
        for point in x_points_temp2:
            x_points.append(point[4:])

        y_points_temp2 = self.str_to_list(y_points_temp[1])
        y_points_temp2 = y_points_temp2[1:-1]
        for point in y_points_temp2:
            y_points.append(point[4:])
        if len(x_points) == 2:
            self.Widget_Line_count = self.Widget_Line_count + 1
            self.real_line_converter(widget_string, x_points, y_points)
        elif len(x_points) > 2:
            self.Poly_Line_count = self.Poly_Line_count + 1
            self.poly_line_converter(widget_string, x_points, y_points)

    def real_line_converter(self, widget_string, x_points, y_points):
        """
        empty docstring :)
        """
        widget_list = self.str_to_list(widget_string)

        if y_points[0] == y_points[1]:
            angle = 0
        elif x_points[0] == x_points[1]:
            angle = 90
        else:
            angle = math.degrees(
                math.atan((float(y_points[0]) - float(y_points[1])) / (float(x_points[1]) - float(x_points[0]))))

        pydm = open(pydm_file, 'a')
        pydm.writelines([f"<widget class=\"PyDMDrawingLine\" name=\"PyDMDrawingLine_{self.Widget_Line_count}\">\n"])
        for edmline in widget_list:
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)

            elif edmline.startswith("numPoints 2"):
                pydm.writelines(["<property name=\"rotation\" stdset=\"0\">\n",
                                 f"<double>{angle}</double>\n",
                                 "</property>\n"])

            elif edmline.startswith('lineWidth'):
                self.line_width_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith('alarmPv '):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith("arrows"):

                # edm and pydm define arrows in different ways, so need to figure out where the first edm point is
                # and define the arrowStartPoint and arrowEndPoint acordingly
                if edmline.__contains__("\"from\""):

                    if int(x_points[1]) > int(x_points[0]):
                        pydm.writelines(["<property name=\"arrowStartPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(x_points[1]) < int(x_points[0]):
                        pydm.writelines(["<property name=\"arrowEndPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(y_points[1]) < int(y_points[0]):
                        pydm.writelines(["<property name=\"arrowStartPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(y_points[1]) > int(y_points[0]):
                        pydm.writelines(["<property name=\"arrowEndPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])


                elif edmline.__contains__("\"to\""):

                    if int(x_points[1]) < int(x_points[0]):
                        pydm.writelines(["<property name=\"arrowStartPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(x_points[1]) > int(x_points[0]):
                        pydm.writelines(["<property name=\"arrowEndPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(y_points[1]) > int(y_points[0]):
                        pydm.writelines(["<property name=\"arrowStartPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])
                    elif int(y_points[1]) < int(y_points[0]):
                        pydm.writelines(["<property name=\"arrowEndPoint\" stdset=\"0\">\n",
                                         "<bool>true</bool>\n",
                                         "</property>\n"])

                elif edmline.__contains__("\"both\""):
                    pydm.writelines(["<property name=\"arrowEndPoint\" stdset=\"0\">\n",
                                     "<bool>true</bool>\n",
                                     "</property>\n"])
                    pydm.writelines(["<property name=\"arrowStartPoint\" stdset=\"0\">\n",
                                     "<bool>true</bool>\n",
                                     "</property>\n"])

            elif edmline.startswith("lineStyle"):
                self.line_style_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget and add visibility rules if they exist
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")
        pydm.close

    def poly_line_converter(self, widget_string, x_points, y_points):
        """
        empty docstring :)
        yes I am taunting you future self
        That was very rude past self :(
        """
        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')
        pydm.writelines(
            [f"<widget class=\"PyDMDrawingPolyline\" name=\"PyDMDrawingPolyline_{self.Poly_Line_count}\">\n"])

        for edmline in widget_list:
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)
                if edmline.startswith("x"):
                    x_position = edmline[2:]
                elif edmline.startswith("y"):
                    y_position = edmline[2:]
                elif edmline.startswith("h"):
                    for index, x in enumerate(x_points):
                        x_points[index] = int(x) - int(x_position)
                    for index, y in enumerate(y_points):
                        y_points[index] = int(y) - int(y_position)
                    pydm.writelines("<property name=\"points\">\n<stringlist>\n")
                    for index, x_point in enumerate(x_points):
                        pydm.writelines(f"<string>{x_point}, {y_points[index]}</string>\n")
                    pydm.writelines("</stringlist>\n</property>\n")

            elif edmline.startswith('lineWidth'):
                self.line_width_converter(edmline, pydm)

            # take out the controlPV value and put it into channel
            elif edmline.startswith('alarmPv '):
                self.pv_converter(edmline, pydm)

            elif edmline.startswith("lineStyle"):
                self.line_style_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget and add visibility rules if they exist
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")
        pydm.close

    def enum_button_converter(self, widget_string):
        """

        """
        widget_list = self.str_to_list(widget_string)
        pydm = open(pydm_file, 'a')
        # set margins
        pydm.writelines([f"<widget class=\"PyDMEnumButton\" name=\"PyDMEnumButton_{self.Enum_Button_count}\">\n"])

        # set all the margins so things convert nicely
        pydm.writelines("<property name=\"marginTop\" stdset=\"0\">\n<number>0</number>\n</property>\n")
        pydm.writelines("<property name=\"marginBottom\" stdset=\"0\">\n<number>0</number>\n</property>\n")
        pydm.writelines("<property name=\"marginLeft\" stdset=\"0\">\n<number>0</number>\n</property>\n")
        pydm.writelines("<property name=\"marginRight\" stdset=\"0\">\n<number>0</number>\n</property>\n")
        pydm.writelines("<property name=\"horizontalSpacing\" stdset=\"0\">\n<number>2</number>\n</property>\n")
        pydm.writelines("<property name=\"verticalSpacing\" stdset=\"0\">\n<number>2</number>\n</property>\n")

        for edmline in widget_list:
            if edmline.startswith(("x ", "y ", "w ", "h ")):
                self.geometry_converter(edmline, pydm)


            # check horizontal or vertical
            elif edmline.startswith('orientation "horizontal"'):
                pydm.writelines(
                    "<property name=\"orientation\" stdset=\"0\">\n<enum>Qt::Horizontal</enum>\n</property>\n")

            elif edmline.startswith("controlPv "):
                self.pv_converter(edmline, pydm)

            # next two elif's make a string with all the visibility properties
            elif edmline.startswith('visPv'):
                visibility_string = edmline
            elif edmline.startswith('vis') and widget_string.__contains__('visPV'):
                visibility_string = visibility_string + '\n' + edmline

            # Close the widget and add visibility rules if they exist
            elif edmline.startswith('endObjectProperties'):

                # if the widget has visibility pvs convert them
                if widget_string.__contains__('visPv'):
                    self.visibility_converter(visibility_string, pydm)
                pydm.writelines("</widget>\n")
        pydm.close()

    # Step 3
    # add you new widget converter function above here

    def UnConvertable(self, widget_string, is_first_unconvertable):
        """
        Adds widgets that don't have conversion functions to a csv file

        Parameters
        ----------
        widget_string : string
            All of the widget properites from the edm file
        is_first_unconvertable : bool
            If the widget is the first unconvertable widget the data lable row of the cvs file is writen

        Returns
        -------
        none : writes to cvs file
        """

        widget_list = self.str_to_list(widget_string)

        widget_name = ()
        pv = ""
        x = ()
        y = ()
        widget_file = ""
        file_flag = False
        macros = ""
        macros_flag = False

        if is_first_unconvertable:
            with open(csv_file, 'w') as csvfile:
                csv_writer = writer(csvfile)
                csv_writer.writerow(['Widget Type', 'PV', 'x', 'y', 'File', 'Macros'])

        with open(csv_file, 'a') as csvfile:
            csv_writer = writer(csvfile)

            if is_first_unconvertable:
                csv_writer.writerow(['Widget Type', 'PV', 'x', 'y', 'File', 'Macros'])

            # take out the lines that start with specific char and assign the variables
            for edmline in widget_list:
                if edmline.startswith('#'):
                    widget_name = edmline[3:-1]

                elif edmline.startswith('x'):
                    x = edmline[2:-1]


                elif edmline.startswith('y'):
                    y = edmline[2:-1]

                elif edmline.startswith('controlPv'):
                    pv = edmline[11:-2]

                # use flag to print file, macros and shell command
                elif edmline.startswith('displayFileName'):
                    file_flag = True
                    continue
                elif file_flag:
                    widget_file = edmline[5:-2]
                    file_flag = False

                elif edmline.startswith('symbols'):
                    macros_flag = True
                    continue
                elif macros_flag:
                    macros = edmline[5:-2]
                    macros_flag = False

                # to avoid writing file repeated method
                elif edmline.startswith("endObjectProperties"):
                    csv_writer.writerow([widget_name] + [pv] + [x] + [y] + [widget_file] + [macros])
                    pv = ""
                    widget_file = ""
                    macros = ""

        csvfile.close()

    # Add the closing XML lines, and custom widget declarations
    # Not necessary to only add these if and only if your widget is in the edm screen being converted
    # Probably cleaner to add these if and only if the widget is in the edm screen
    def end_xml(self):

        """
        Adds the lines that declares custom widgets

        Parameters
        ----------
        none
            Could add parameters that make sure only widgets that are in the display are added
            Not really necessary to do so

        Returns
        -------
        none : writes to pydm (.ui) file
        """

        with open(pydm_file, 'a') as pydm:
            pydm.writelines("</widget>\n")
            pydm.writelines("<customwidgets>\n")

            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMLabel</class>\n",
                             "<extends>QLabel</extends>\n",
                             "<header>pydm.widgets.label</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMLineEdit</class>\n",
                             "<extends>QLineEdit</extends>\n",
                             "<header>pydm.widgets.line_edit</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMFrame</class>\n",
                             "<extends>QFrame</extends>\n",
                             "<header>pydm.widgets.frame</header>\n",
                             "<container>1</container>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMDrawingRectangle</class>\n",
                             "<extends>QWidget</extends>\n",
                             "<header>pydm.widgets.drawing</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMDrawingEllipse</class>\n",
                             "<extends>QWidget</extends>\n",
                             "<header>pydm.widgets.drawing</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMShellCommand</class>\n",
                             "<extends>QPushButton</extends>\n",
                             "<header>pydm.widgets.shell_command</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMPushButton</class>\n",
                             "<extends>QPushButton</extends>\n",
                             "<header>pydm.widgets.pushbutton</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMEnumComboBox</class>\n",
                             "<extends>QComboBox</extends>\n",
                             "<header>pydm.widgets.enum_combo_box</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMRelatedDisplayButton</class>\n",
                             "<extends>QPushButton</extends>\n",
                             "<header>pydm.widgets.related_display_button</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMEDMDisplayButton</class>\n",
                             "<extends>PyDMRelatedDisplayButton</extends>\n",
                             "<header>edmbutton.edm_button</header>\n",
                             "<container>1</container>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMDrawingLine</class>\n",
                             "<extends>QWidget</extends>\n",
                             "<header>pydm.widgets.drawing</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMDrawingPolyline</class>\n",
                             "<extends>QWidget</extends>\n",
                             "<header>pydm.widgets.drawing</header>\n",
                             "</customwidget>\n"])
            pydm.writelines(["<customwidget>\n",
                             "<class>PyDMEnumButton</class>\n",
                             "<extends>QWidget</extends>\n",
                             "<header>pydm.widgets.enum_button</header>\n",
                             "</customwidget>\n"])

            # Step 3
            # add the custom widget properties directly above this comment
            pydm.writelines("</customwidgets>\n")
            pydm.writelines(["<resources/>\n",
                             "<connections/>\n",
                             "</ui>\n"])


# not sure exactly how this works but it does: :)
# found it online
def locate(patterns, root=os.curdir, recursive=True):
    """
    Not sure exactly how this works but it does :)
    Found it online https://stackoverflow.com/questions/56668038/how-to-implement-a-recursive-option-on-a-python-script

    Parameters
    ----------
    patterns : list
        patterns to search for recursivly in a file tree
    root : string
        directory used as root for searc of files that have any of the provided patterns
    recursive : bool
        Not sure, think it only does stuff in the current directory and dose not go down the file tree if it is false

    Returns
    -------
    files : list
        list of files, I don't think it is named files

    example
    -------
    if args.recursive:
        for file in locate(['*.edl'], root=args.input_file):
            print("Converting: " + file)
            pydm_file = file[:-4] + ".ui"
            csv_file = file[:-4] + ".csv"
            run = Converters(file)
            run.main_converter()
    """
    folder = os.path.expanduser(root) if root.startswith('~') else root
    folder = os.path.abspath(folder)

    if not os.path.exists(folder) or not os.path.isdir(folder):
        raise ValueError('{} ({})'.format('Not a folder:', folder))

    for pattern in patterns:
        if recursive:
            for path, _, files in os.walk(folder, followlinks=True):
                for filename in fnmatch.filter(files, pattern):
                    yield os.path.join(path, filename)
        else:
            for filename in fnmatch.filter(os.listdir(folder), pattern):
                yield os.path.join(folder, filename)


if args.recursive:
    for file in locate(['*.edl'], root=args.input_file):
        print("Converting: " + file)
        if args.original_file_name:
            pydm_file = file[:-4] + ".ui"
        else:
            pydm_file = file[:-4] + "_autogen.ui"
        csv_file = file[:-4] + ".csv"
        run = Converters(file)
        run.main_converter()
else:
    print("Converting: " + args.input_file)
    if args.original_file_name:
        pydm_file = args.input_file[:-4] + ".ui"
    else:
        pydm_file = args.input_file[:-4] + "_autogen.ui"
    csv_file = args.input_file[:-4] + ".csv"
    run = Converters(args.input_file)
    run.main_converter()
print("Success!")
