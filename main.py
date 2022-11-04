import re
import sys
from csv import writer
from csv import reader

# make sure there is a file entered
try:
    input_file = sys.argv[1]
except:
    print("ERROR: missing a file to convert")
    print("expected input:")
    print("$ edm_to_pydm edmFile.edl")
    # exits the program if there is no file entered
    sys.exit(1)

# add more to make sure input is a .edl file
if not input_file.endswith('.edl'):
    print("ERROR: wrong file type! Enter .edl file type!")
    sys.exit(1)

print("Success!")


class Converters(object):
    def __init__(self, input_file):
        with open(input_file, 'r') as edm:
            self.edmfiles = edm.readlines()

            # background widget convert function

    def Display_Properties_Converter(self):

        # use flag method to read only for displsy properties
        screen_flag = "no"

        with open(input_file[:-4] + ".ui", 'w') as pydm:
            for edmfile in self.edmfiles:

                if edmfile.startswith('4 0 1'):
                    screen_flag = "screen"
                    pydm.writelines(
                        '<?xml version="1.0" encoding="UTF-8"?>\n<ui version="4.0">\n<class>Form</class>\n<widget class="QWidget" name="Form">\n<property name="geometry">\n<rect>\n<x>0</x>\n<y>0</y>\n')

                # take out the screen sizes as variable to write same size in pydm file
                if edmfile.startswith('w ') and screen_flag != "no":
                    w_position = edmfile[2:]
                    # print(w_position)
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                elif edmfile.startswith('h ') and screen_flag != "no":
                    h_position = edmfile[2:]
                    # print(h_position)
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n</property>\n')

                # find the name of the title to write same name in pydm file
                elif edmfile.startswith('title'):
                    screen_title = edmfile[7:-2]

                    # print(str(screen_title))
                    screen_title = screen_title.replace("\n", "")
                    pydm.writelines('<property name="windowTitle">\n')

                    # method to change it into macro w ${}
                    macro = r"\$(\()(.+?)(\))"
                    result = re.sub(macro, r"${\2}", screen_title)

                    pydm.writelines("<string>" + str(result) + "</string>\n")
                    pydm.writelines('</property>\n')

                # end of the background screen flag
                if edmfile.startswith('endScreenProperties'):
                    screen_flag = "no"

    # Static Text to QLabel Convert function
    def Static_Text_Converter(self):
        # use flag method to read only for static text properties
        widget_flag = "none"

        # counting the number of label
        label_count = 1
        static_text_value_flag = False

        with open(input_file[:-4] + ".ui", 'a') as pydm:
            for edmfile in self.edmfiles:

                # beginning text of the flag method
                if edmfile.startswith('object activeXTextClass'):
                    widget_flag = "static_text"

                    # method to give unique name for the label(increment the value title)
                    pydm.writelines('<widget class="QLabel" name="label_' + str(
                        label_count) + '">\n<property name="geometry">\n<rect>\n')
                    label_count = label_count + 1

                # take out the screen sizes as variable to write same size in pydm file
                if edmfile.startswith('x ') and widget_flag != "none":
                    x_position = edmfile[2:]
                    # print(x_position)
                    x_position = x_position.replace("\n", "")
                    pydm.writelines("<x>" + x_position + "</x>\n")

                elif edmfile.startswith('y ') and widget_flag != "none":
                    y_position = edmfile[2:]
                    # print(y_position)
                    y_position = y_position.replace("\n", "")
                    pydm.writelines("<y>" + y_position + "</y>\n")

                elif edmfile.startswith('w ') and widget_flag != "none":
                    w_position = edmfile[2:]
                    # print(w_position)
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                elif edmfile.startswith('h ') and widget_flag != "none":
                    h_position = edmfile[2:]
                    # print(h_position)
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n')

                # use second flag inside of first flag to find the value title
                elif edmfile.startswith('value') and widget_flag != "none":
                    static_text_value_flag = True
                    continue
                elif static_text_value_flag:
                    static_text_title = edmfile[3:-2]

                    # print(str(static_text_title))
                    pydm.writelines('</property>\n')
                    pydm.writelines('<property name="text">\n')

                    # method to change it into macro w ${}
                    macro = r"\$(\()(.+?)(\))"
                    result = re.sub(macro, r"${\2}", static_text_title)

                    pydm.writelines("<string>" + str(result) + "</string>\n")
                    static_text_value_flag = False

                # take out the font size and cut off extra string to use same font size in pydm file
                elif edmfile.startswith('font "') and widget_flag != "none":
                    fontline = edmfile[:-4]
                    fontsize = '-'.join(fontline.split('-')[3:])
                    # subtract 3 from fontsize(pydm font is larger than edm)
                    fontsize = int(fontsize) - 5
                    pydm.writelines('</property>\n<property name="font">\n<font>\n')
                    pydm.writelines('<pointsize>' + str(fontsize) + '</pointsize>\n')

                    italic_search = '-'.join(fontline.split('-')[2:])

                    # method to search for italic and bold
                    if italic_search.__contains__('i') and fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n<weight>75</weight>\n<bold>true</bold>\n</font>\n')
                    # method to search for italic itself
                    elif italic_search.__contains__('i') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n</font>\n')

                    # method to search for bold itself
                    elif fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<weight>75</weight>\n<bold>true</bold>\n</font>\n')

                    elif italic_search.__contains__('r') and widget_flag != "none":
                        pydm.writelines('</font>\n')

                # assign the differnt boader
                elif edmfile.startswith('border') and widget_flag != "none":
                    pydm.writelines('</property>\n<property name="frameShape">\n<enum>QFrame::Box</enum>\n')

                # assign the align if there's an alignment
                elif edmfile.startswith('fontAlign') and widget_flag != "none":
                    align_search = edmfile[:]
                    pydm.writelines('</property>\n<property name="alignment">\n')

                    if align_search.__contains__('center') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignCenter</set>\n')
                    if align_search.__contains__('left') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignLeft</set>\n')
                    if align_search.__contains__('right') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignRight</set>\n')

                    # close this properties w the ending lines
                elif edmfile.startswith('endObjectProperties') and widget_flag != "none":
                    pydm.writelines('</property>\n')
                    pydm.writelines("</widget>\n")

                # end text for flag method
                if edmfile.startswith('endObjectProperties'):
                    widget_flag = "none"

            if label_count > 0:
                pydm.writelines

    # Text Update to PydmLabel Convert function
    def Text_Update_Converter(self):
        # use flag method to read only for static text properties
        widget_flag = "none"

        # counting the number of label
        global PydmLabel_count
        PydmLabel_count = 1
        text_update_value_flag = False

        with open(input_file[:-4] + ".ui", 'a') as pydm:
            for edmfile in self.edmfiles:

                # beginning text of the flag method
                if edmfile.startswith('object TextupdateClass'):
                    widget_flag = "text update"

                    # method to give unique name for the label(increment the value title)
                    pydm.writelines('<widget class="PyDMLabel" name="PyDMLabel_' + str(
                        PydmLabel_count) + '">\n<property name="geometry">\n<rect>\n')
                    PydmLabel_count = PydmLabel_count + 1

                # take out the screen sizes as variable to write same size in pydm file
                if edmfile.startswith('x ') and widget_flag != "none":
                    x_position = edmfile[2:]
                    # print(x_position)
                    x_position = x_position.replace("\n", "")
                    pydm.writelines("<x>" + x_position + "</x>\n")

                elif edmfile.startswith('y ') and widget_flag != "none":
                    y_position = edmfile[2:]
                    # print(y_position)
                    y_position = y_position.replace("\n", "")
                    pydm.writelines("<y>" + y_position + "</y>\n")

                elif edmfile.startswith('w ') and widget_flag != "none":
                    w_position = edmfile[2:]
                    # print(w_position)
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                elif edmfile.startswith('h ') and widget_flag != "none":
                    h_position = edmfile[2:]
                    # print(h_position)
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n')

                # take out the controlPV value and put it into channel
                elif edmfile.startswith('controlPv ') and widget_flag != "none":
                    PV = edmfile[11:-2]
                    PV = PV.replace("\n", "")
                    pydm.writelines(
                        '</property>\n<property name="alarmSensitiveContent" stdset="0">\n<bool>true</bool>\n')
                    pydm.writelines('</property><property name="channel" stdset="0">\n')
                    macro = r"\$(\()(.+?)(\))"
                    result = re.sub(macro, r"${\2}", PV)
                    pydm.writelines('<string>' + str(result) + '</string>\n')

                elif edmfile.startswith('displayMode') and widget_flag != "none":
                    d_m = edmfile[:]
                    pydm.writelines('</property>\n<property name="displayFormat" stdset="0">')

                    # deafault, decimal, hex, engineer, exp
                    if d_m.__contains__('decimal') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Decimal</enum>\n')
                    if d_m.__contains__('hex') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Hex</enum>\n')
                    # if d_m.__contains__('engineer') and widget_flag !="none":
                    # pydm.writelines('<enum>PyDMLabel::Hex</enum>\n')
                    if d_m.__contains__('exp') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Exponential</enum>\n')

                    # take out the font size and cut off extra string to use same font size in pydm file
                elif edmfile.startswith('font "') and widget_flag != "none":
                    fontline = edmfile[:-4]
                    fontsize = '-'.join(fontline.split('-')[3:])
                    # subtract 3 from fontsize(pydm font is larger than edm)
                    fontsize = int(fontsize) - 3
                    pydm.writelines('</property>\n<property name="font">\n<font>\n')
                    pydm.writelines('<pointsize>' + str(fontsize) + '</pointsize>\n')

                    italic_search = '-'.join(fontline.split('-')[2:])

                    # method to search for italic and bold
                    if italic_search.__contains__('i') and fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n<weight>75</weight>\n<bold>true</bold>\n</font>\n')
                    # method to search for italic itself
                    elif italic_search.__contains__('i') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n</font>\n')

                    # method to search for bold itself
                    elif fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<weight>75</weight>\n<bold>true</bold>\n</font>\n')

                    elif italic_search.__contains__('r') and widget_flag != "none":
                        pydm.writelines('</font>\n')

                # assign the align if there's an alignment
                elif edmfile.startswith('fontAlign') and widget_flag != "none":
                    align_search = edmfile[:]
                    pydm.writelines('</property>\n<property name="alignment">\n')

                    if align_search.__contains__('center') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignCenter</set>\n')
                    if align_search.__contains__('left') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignLeft</set>\n')
                    if align_search.__contains__('right') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignRight</set>\n')

                # assign the linewidth and boarder
                elif edmfile.startswith('lineWidth') and widget_flag != "none":
                    l_w = edmfile[10]
                    pydm.writelines('</property>\n<property name="lineWidth">\n<number>' + l_w + '</number>\n')

                # close this properties w the ending lines
                elif edmfile.startswith('endObjectProperties') and widget_flag != "none":
                    pydm.writelines('</property>\n')
                    pydm.writelines("</widget>\n")

                # end text for flag method
                if edmfile.startswith('endObjectProperties'):
                    widget_flag = "none"

    # Text Control to PydmLineEdit Convert function
    def Text_Control_Converter(self):
        # use flag method to read only for static text properties
        widget_flag = "none"

        # counting the number of label
        global LineEdit_count
        LineEdit_count = 1
        text_control_value_flag = False

        with open(input_file[:-4] + ".ui", 'a') as pydm:
            for edmfile in self.edmfiles:

                # beginning text of the flag method
                if edmfile.startswith('object activeXTextDspClass'):
                    widget_flag = "text control"

                    # method to give unique name for the label(increment the value title)
                    pydm.writelines('<widget class="PyDMLineEdit" name="PyDMLineEdit_' + str(
                        LineEdit_count) + '">\n<property name="geometry">\n<rect>\n')
                    LineEdit_count = LineEdit_count + 1

                # take out the screen sizes as variable to write same size in pydm file
                if edmfile.startswith('x ') and widget_flag != "none":
                    x_position = edmfile[2:]
                    # print(x_position)
                    x_position = x_position.replace("\n", "")
                    pydm.writelines("<x>" + x_position + "</x>\n")

                elif edmfile.startswith('y ') and widget_flag != "none":
                    y_position = edmfile[2:]
                    # print(y_position)
                    y_position = y_position.replace("\n", "")
                    pydm.writelines("<y>" + y_position + "</y>\n")

                elif edmfile.startswith('w ') and widget_flag != "none":
                    w_position = edmfile[2:]
                    # print(w_position)
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                elif edmfile.startswith('h ') and widget_flag != "none":
                    h_position = edmfile[2:]
                    # print(h_position)
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n')

                # take out the controlPV value and put it into channel
                elif edmfile.startswith('controlPv ') and widget_flag != "none":
                    PV = edmfile[11:-2]
                    PV = PV.replace("\n", "")
                    pydm.writelines('</property><property name="channel" stdset="0">\n')
                    macro = r"\$(\()(.+?)(\))"
                    result = re.sub(macro, r"${\2}", PV)
                    pydm.writelines('<string>' + str(result) + '</string>\n')

                elif edmfile.startswith('displayMode') and widget_flag != "none":
                    d_m = edmfile[:]
                    pydm.writelines('</property>\n<property name="displayFormat" stdset="0">')

                    # deafault, float, Gfloat, Exponential, Decimal, Hex, String
                    if d_m.__contains__('exponential') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Exponential</enum>\n')
                    if d_m.__contains__('decimal') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Decimal</enum>\n')
                    if d_m.__contains__('hex') and widget_flag != "none":
                        pydm.writelines('<enum>PyDMLabel::Hex</enum>\n')
                    # if d_m.__contains__('engineer') and widget_flag !="none":
                    # pydm.writelines('<enum>PyDMLabel::Hex</enum>\n')

                # take out the font size and cut off extra string to use same font size in pydm file
                elif edmfile.startswith('font "') and widget_flag != "none":
                    fontline = edmfile[:-4]
                    fontsize = '-'.join(fontline.split('-')[3:])
                    # subtract 3 from fontsize(pydm font is larger than edm)
                    fontsize = int(fontsize) - 3
                    pydm.writelines('</property>\n<property name="font">\n<font>\n')
                    pydm.writelines('<pointsize>' + str(fontsize) + '</pointsize>\n')

                    italic_search = '-'.join(fontline.split('-')[2:])

                    # method to search for italic and bold
                    if italic_search.__contains__('i') and fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n<weight>75</weight>\n<bold>true</bold>\n</font>\n')
                    # method to search for italic itself
                    elif italic_search.__contains__('i') and widget_flag != "none":
                        pydm.writelines('<italic>true</italic>\n</font>\n')

                    # method to search for bold itself
                    elif fontline.__contains__('bold') and widget_flag != "none":
                        pydm.writelines('<weight>75</weight>\n<bold>true</bold>\n</font>\n')

                    elif italic_search.__contains__('r') and widget_flag != "none":
                        pydm.writelines('</font>\n')

                # assign the align if there's an alignment
                elif edmfile.startswith('fontAlign') and widget_flag != "none":
                    align_search = edmfile[:]
                    pydm.writelines('</property>\n<property name="alignment">\n')

                    if align_search.__contains__('center') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignCenter</set>\n')
                    if align_search.__contains__('left') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignLeft</set>\n')
                    if align_search.__contains__('right') and widget_flag != "none":
                        pydm.writelines('<set>Qt::AlignRight</set>\n')

                    # close this properties w the ending lines
                elif edmfile.startswith('endObjectProperties') and widget_flag != "none":
                    pydm.writelines('</property>\n')
                    pydm.writelines("</widget>\n")

                # end text for flag method
                if edmfile.startswith('endObjectProperties'):
                    widget_flag = "none"

    # convert rectangle to pyqtFrame
    def Rec(self):
        # use flag method to read only for rectangle properties
        widget_flag = "none"

        # counting the number of rectangle
        global rec_count
        rec_count = 1

        with open(input_file[:-4] + ".ui", 'a') as pydm:
            for edmfile in self.edmfiles:

                # beginning text of the flag method
                if edmfile.startswith('object activeRectangleClass'):
                    widget_flag = "rectangle"

                    # method to give unique name for the label(increment the value title)
                    pydm.writelines('<widget class="PyDMDrawingRectangle" name="PyDMDrawingRectangle_' + str(
                        rec_count) + '"><property name="geometry">\n<rect>\n')
                    rec_count = rec_count + 1

                # take out the screen sizes as variable to write same size in pydm file
                if edmfile.startswith('x ') and widget_flag != "none":
                    x_position = edmfile[2:]
                    # print(x_position)
                    x_position = x_position.replace("\n", "")
                    pydm.writelines("<x>" + x_position + "</x>\n")

                elif edmfile.startswith('y ') and widget_flag != "none":
                    y_position = edmfile[2:]
                    # print(y_position)
                    y_position = y_position.replace("\n", "")
                    pydm.writelines("<y>" + y_position + "</y>\n")

                elif edmfile.startswith('w ') and widget_flag != "none":
                    w_position = edmfile[2:]
                    # print(w_position)
                    w_position = w_position.replace("\n", "")
                    pydm.writelines("<width>" + w_position + "</width>\n")

                elif edmfile.startswith('h ') and widget_flag != "none":
                    h_position = edmfile[2:]
                    # print(h_position)
                    h_position = h_position.replace("\n", "")
                    pydm.writelines("<height>" + h_position + "</height>\n")
                    pydm.writelines('</rect>\n')

                # close this properties w the ending lines
                elif edmfile.startswith('endObjectProperties') and widget_flag != "none":
                    pydm.writelines('</property>\n')
                    pydm.writelines("</widget>\n")

                # end text for flag method
                if edmfile.startswith('endObjectProperties'):
                    widget_flag = "none"

    # convert all the widget names, pv, x and y for .csv file function
    def UnConvertable(self):
        widget_name = ()
        pv = ""
        x = ()
        y = ()
        file = ""
        file_flag = False
        macros = ""
        macros_flag = False
        shell_command = ""
        shell_command_flag = False
        header = ['Widget Type', 'PV', 'x', 'y', 'File', 'Macros', 'Shell Command']

        with open(input_file[:-4] + ".csv", 'w') as csvfile:
            csv_writer = writer(csvfile)
            csv_writer.writerow(header)

            # take out the lines that start with specific char and assign the variables
            for edmfile in self.edmfiles:
                if edmfile.startswith('#'):
                    widget_name = edmfile[3:-2]
                # print(widget_name)

                elif edmfile.startswith('x'):
                    x = edmfile[2:-1]
                # print(x)

                elif edmfile.startswith('y'):
                    y = edmfile[2:-1]
                # print(y)

                elif edmfile.startswith('controlPv'):
                    pv = edmfile[11:-2]
                # print(pv)

                # use flag to print file, macros and shell command
                elif edmfile.startswith('displayFileName'):
                    file_flag = True
                    continue
                elif file_flag:
                    file = edmfile[5:-2]
                    file_flag = False
                # print(file)

                elif edmfile.startswith('symbols'):
                    macros_flag = True
                    continue
                elif macros_flag:
                    macros = edmfile[5:-2]
                    macros_flag = False
                # print(macros)

                elif edmfile.startswith('command'):
                    shell_command_flag = True
                    continue
                elif shell_command_flag:
                    shell_command = edmfile[5:-2]
                    shell_command_flag = False
                # print(shell_command)

                # to avoid writing file repeated method
                elif edmfile.startswith("endObjectProperties"):
                    csv_writer.writerow([widget_name] + [pv] + [x] + [y] + [file] + [macros] + [shell_command])
                    pv = ""
                    file = ""
                    macros = ""
                    shell_command = ""

        csvfile.close()

    # remove the converted widgets from .csv file function
    def csv_remove_Convertable(self):
        lines = list()
        st = 'Static Text'
        tu = 'Text Update'
        tc = 'Text Control'
        rec = 'Rectangle'
        with open(input_file[:-4] + ".csv", 'r') as csvfile:
            csv_reader = reader(csvfile)

            for row in csv_reader:
                lines.append(row)

                # remove all widgets that are converted
                for field in row:
                    if field == st:
                        lines.remove(row)
                    elif field == tu:
                        lines.remove(row)
                    elif field == tc:
                        lines.remove(row)
                    elif field == rec:
                        lines.remove(row)

        with open(input_file[:-4] + ".csv", 'w') as csvfile:
            csv_writer = writer(csvfile)
            csv_writer.writerows(lines)

    # adding the ending xml lines to close the file
    def end_xml(self):
        with open(input_file[:-4] + ".ui", 'a') as pydm:
            pydm.writelines("</widget>\n")
            # label_count starts from 1(hence >=2)
            if PydmLabel_count >= 2 or LineEdit_count >= 2 or rec_count >= 2:
                pydm.writelines("<customwidgets>\n")
                if PydmLabel_count >= 2:
                    pydm.writelines(
                        "<customwidget>\n<class>PyDMLabel</class>\n<extends>QLabel</extends>\n<header>pydm.widgets.label</header>\n</customwidget>\n")
                if LineEdit_count >= 2:
                    pydm.writelines(
                        "<customwidget>\n<class>PyDMLineEdit</class>\n<extends>QLineEdit</extends>\n<header>pydm.widgets.line_edit</header>\n</customwidget>\n")
                if rec_count >= 2:
                    pydm.writelines(
                        "<customwidget>\n<class>PyDMFrame</class>\n<extends>QFrame</extends>\n<header>pydm.widgets.frame</header>\n<container>1</container>\n</customwidget>\n")
                # if PydmLabel_count >= 2 or LineEdit_count >= 2:
                pydm.writelines("</customwidgets>\n")
            pydm.writelines('<resources/>\n<connections/>\n</ui>\n')

    # calling the functions


run = Converters(input_file)
run.Display_Properties_Converter()
run.Rec()
run.Static_Text_Converter()
run.Text_Update_Converter()
run.Text_Control_Converter()
run.end_xml()
run.UnConvertable()
run.csv_remove_Convertable()