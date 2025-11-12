import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from pydmconverter.edm.parser_helpers import (
    convert_color_property_to_qcolor,
    parse_colors_list,
    search_color_list,
    replace_calc_and_loc_in_edm_content,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IGNORED_PROPERTIES = ("#", "x ", "y ", "w ", "h ", "major ", "minor ", "release ")


@dataclass
class EDMObjectBase:
    """EDM Abstract Object class represents an abstract object in .edl files"""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class EDMGroup(EDMObjectBase):
    """EDM Group class represents a group in .edl files"""

    objects: list[EDMObjectBase] = field(default_factory=list)
    properties: dict = field(default_factory=dict)

    def add_object(self, obj):
        self.objects.append(obj)


@dataclass
class EDMObject(EDMObjectBase):
    """EDM Object class represents an object in .edl files"""

    name: str = ""
    properties: dict = field(default_factory=dict)


class EDMFileParser:
    """EDMFileParser class parses .edl files and creates a tree of
    EDMObjects and EDMGroups"""

    screen_prop_pattern = re.compile(r"beginScreenProperties(.*)endScreenProperties", re.DOTALL)
    group_pattern = re.compile(r"object activeGroupClass(.*)endGroup", re.DOTALL)
    object_pattern = re.compile(
        r"object\s+(\w+(?::\w+)?)\s*beginObjectProperties\s*(.*?)\s*endObjectProperties(?=\s*(?:#.*?)?(?:object|\s*$))",
        re.DOTALL | re.MULTILINE,
    )
    # object_pattern = re.compile(
    #    r"object\s+(\w+)\s*beginObjectProperties\s*(.*?)\s*endObjectProperties(?=\s*(?:#.*?)?(?:object|\s*$))",
    #    re.DOTALL | re.MULTILINE,
    # )

    def __init__(self, file_path: str | Path, output_file_path: str | Path):
        """Creates an instance of EDMFileParser for the given file_path

        Parameters
        ----------
        file_path : str | Path
            EDM file to parse
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        self.file_path = file_path
        self.output_file_path = output_file_path

        try:
            with open(file_path, "r") as file:
                self.text = file.read()
        except UnicodeDecodeError as e:
            logger.warning(f"Could not read file as UTF-8 (bad byte at {e.start}): {e}. Switching to Latin-1...")
            with open(file_path, "r", encoding="latin-1") as file:
                self.text = file.read()
        self.modify_text(file_path)

        self.screen_properties_end = 0
        self.ui = EDMGroup()

        self.parse_screen_properties()
        self.parse_objects_and_groups(self.text[self.screen_properties_end :], self.ui)

    def modify_text(self, file_path) -> str:  # unnecessary return
        # Replace $(!W) with a marker
        self.text = self.text.replace("$(!W)", "__UNIQUE__")

        self.text = self.text.replace(
            "$(!A)", ""
        )  # remove global macros TODO: In edm, these macros (!W) and (!A) are used to specify the scope of the macros (outside of a specific screen) this may need to be resolved more cleanly later
        pattern = r"\\*\$\(([^)]+)\)"
        self.text = re.sub(pattern, r"${\1}", self.text)
        self.text, _, _ = replace_calc_and_loc_in_edm_content(self.text, file_path)
        return self.text

    def parse_screen_properties(self) -> None:
        """Get the screen properties from the .edl file and set the UI
        height and width
        """
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            size_properties = self.get_size_properties(screen_prop_text, strict=True)
            other_properties = self.get_object_properties(screen_prop_text)
            if "bgColor" in other_properties:
                color_list_filepath = search_color_list()
                color_list_dict = parse_colors_list(color_list_filepath)

                edmColor = other_properties["bgColor"]
                other_properties["bgColor"] = convert_color_property_to_qcolor(edmColor, color_data=color_list_dict)
            self.ui.properties = other_properties

            self.ui.height = size_properties["height"]
            self.ui.width = size_properties["width"]

    def parse_objects_and_groups(self, text: str, parent_group: EDMGroup) -> None:
        """Recursively parse the given text into a tree of EDMObjects and
        EDMGroups. The parsed EDMObjects and EDMGroups are added to the
        given parent_group, which is the root EDMGroup of the tree.
        Parameters
        ----------
        text : str
            Text from the file to be parsed
        parent_group : EDMGroup
            Parent EDMGroup to add the parsed EDMObjects and EDMGroups to
        """
        pos = 0
        while pos < len(text):
            # Skip whitespace and comments
            while pos < len(text) and (text[pos].isspace() or text[pos] == "#"):
                if text[pos] == "#":
                    while pos < len(text) and text[pos] != "\n":
                        pos += 1
                else:
                    pos += 1
            if pos >= len(text):
                break

            if text[pos:].lstrip().startswith("object activeGroupClass"):
                group_start = pos

                begin_obj_props = text.find("beginObjectProperties", group_start)
                begin_group_idx = text.find("beginGroup", begin_obj_props)
                end_group_idx = self.find_matching_end_group(text, begin_group_idx)
                end_obj_props = text.find("endObjectProperties", end_group_idx)

                if begin_obj_props == -1 or end_obj_props == -1 or begin_group_idx == -1:
                    snippet = text[pos : pos + 100].strip()
                    print(f"Skipping malformed group at {pos}, snippet: {snippet}")
                    pos += 1
                    continue

                end_group_idx = self.find_matching_end_group(text, begin_group_idx)
                if end_group_idx == -1:
                    print(f"Could not find matching endGroup at {pos}")
                    pos += 1
                    continue

                # get rid of trailing endObjectProperties
                extra_end_props = text.find("endObjectProperties", end_group_idx)
                group_end = (
                    extra_end_props + len("endObjectProperties")
                    if (extra_end_props != -1 and extra_end_props < text.find("object", end_group_idx))
                    else end_group_idx + len("endGroup")
                )
                group_header = (
                    text[begin_obj_props + len("beginObjectProperties") : begin_group_idx]
                    + text[end_group_idx + len("endGroup") : end_obj_props]
                )
                group_body = text[begin_group_idx + len("beginGroup") : end_group_idx]

                size_props = self.get_size_properties(group_header)
                properties = self.get_object_properties(group_header)

                group = EDMGroup(**size_props)
                group.properties = properties

                self.parse_objects_and_groups(group_body, group)
                parent_group.add_object(group)
                pos = group_end
                continue

            # Try matching a regular object
            object_match = self.object_pattern.search(text, pos)
            if object_match:
                name = object_match.group(1).replace(":", "")  # remove colons from name (causes issues with PyDM)
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                properties = self.get_object_properties(object_text)

                if name.lower() == "activesymbolclass" or name.lower() == "anasymbolclass":
                    obj = self.get_symbol_group(properties=properties, size_properties=size_properties)
                else:
                    obj = EDMObject(name=name, properties=properties, **size_properties)
                parent_group.add_object(obj)

                pos = object_match.end()
            else:
                snippet = text[pos : pos + 100]
                print(f"Unrecognized text at pos {pos}: '{snippet}'")
                pos = text.find("\n", pos) if "\n" in text[pos:] else len(text)

    def get_symbol_group(
        self, properties: dict[str, bool | str | list[str]], size_properties: dict[str, int]
    ) -> EDMGroup:
        """
        Generate an EDMGroup made up of child EDMGroups each representing a symbol.
        These EDMGroups are mapped from the inner groups within the activesymbolclass
        embedded file.

        Parameters
        ----------
        properties : dict[str, bool | str | list[str]]
            The activesymbolclass properties used to generate the output EDM Group
        size_properties : dict[str, int]
            The coordinate and size_properties of the activesymbolclass

        Returns
        ----------
        EDMGroup
            A group representing a collection of ActiveSymbolclass groups
        """
        embedded_file = properties.get("file")
        if not embedded_file:
            print("No embedded file specified in properties.")
            return EDMGroup()
        if not embedded_file.endswith(".edl"):
            embedded_file += ".edl"
        edm_paths = os.environ.get("EDMDATAFILES", ".").split(":")
        embedded_text = None
        for path in edm_paths:
            full_path = Path(path) / embedded_file
            if full_path.is_file():
                with open(full_path, "r") as file:
                    embedded_text = file.read()
                break
        if embedded_text is None:
            return EDMGroup()

        temp_group = EDMGroup()
        match = self.screen_prop_pattern.search(embedded_text)
        if match:
            screen_properties_end = match.end()

        num_pvs = properties["numPvs"]
        self.parse_objects_and_groups(embedded_text[screen_properties_end:], temp_group)
        self.resize_symbol_groups(temp_group, size_properties)
        self.add_symbol_properties(temp_group, properties)
        if "orientation" in properties:
            self.reorient_symbol_groups(temp_group, properties["orientation"], size_properties)
        if "minValues" not in properties or "maxValues" not in properties:
            ranges = None
        else:
            ranges = self.generate_pv_ranges(properties)
        self.remove_extra_groups(temp_group, ranges)
        if num_pvs == 0 or num_pvs == "0":
            self.remove_symbol_groups(temp_group, ranges)
        elif ranges is not None:
            self.populate_symbol_pvs(temp_group, properties, ranges)
        return temp_group

    def resize_symbol_groups(self, temp_group: EDMGroup, size_properties: dict[str, int]) -> None:
        """
        Given a group of symbol groups, modify the coordinates of each
        object within the symbol groupsto be in relation to the coordinates
        of the new file rather than from the embedded file.

        Parameters
        ----------
        temp_group: EDMGroup
            The EDMGroup making up each symbol group whose objects will be modified
        size_properties : dict[str, int]
            The coordinate and size_properties of the activesymbolclass
        """
        for sub_group in temp_group.objects:
            for sub_object in sub_group.objects:
                sub_object.x = sub_object.x - sub_group.x + size_properties["x"]
                sub_object.y = sub_object.y - sub_group.y + size_properties["y"]
            sub_group.x = size_properties["x"]
            sub_group.y = size_properties[
                "y"
            ]  # The group resizing is needed to reorient symbol groups for rotations later

    def reorient_symbol_groups(self, temp_group: EDMGroup, orientation: str, size_properties: dict[str, int]) -> None:
        """
        Given a group of symbol groups, change the orientation of each object
        within the symbol groups (rotateCW, rotateCCW, FlipV, FlipH) either
        flipping or rotating these objects about their respective symbol group.

        Parameters
        ----------
        temp_group: EDMGroup
            The EDMGroup making up each symbol group whose objects will be modified
        orientation : str
            The orientation instruction to flip or rotate
        size_properties : dict[str, int]
            The coordinate and size_properties of the activesymbolclass

        Returns
        ----------
        EDMGroup
            A group representing a collection of ActiveSymbolclass groups
        """
        if orientation == "FlipV":
            for sub_group in temp_group.objects:
                for sub_object in sub_group.objects:
                    if sub_object.name.lower() == "activearcclass":
                        sub_object.properties["startAngle"] = str(-int(sub_object.properties["startAngle"]))
                        sub_object.properties["totalAngle"] = str(-int(sub_object.properties["totalAngle"]))
                    if sub_object.name.lower() == "activelineclass":
                        for i in range(len(sub_object.properties["yPoints"])):
                            sub_object.properties["yPoints"][i] = str(
                                int(sub_object.height) - int(sub_object.properties["yPoints"][i]) + int(sub_object.y)
                            )
                    sub_object.y = int(sub_object.height) + int(sub_object.y) - int(sub_group.height)

        if orientation == "FlipH":
            for sub_group in temp_group.objects:
                for sub_object in sub_group.objects:
                    if sub_object.name.lower() == "activearcclass":
                        sub_object.properties["startAngle"] = str(-int(sub_object.properties["startAngle"]))
                    if sub_object.name.lower() == "activelineclass":
                        for i in range(len(sub_object.properties["xPoints"])):
                            sub_object.properties["xPoints"][i] = str(
                                int(sub_object.width) - int(sub_object.properties["xPoints"][i]) + int(sub_object.x)
                            )
                    sub_object.x = int(size_properties["x"]) - int(sub_object.x)
        if orientation == "rotateCW":
            for sub_group in temp_group.objects:
                group_cx = sub_group.x + sub_group.width / 2
                group_cy = sub_group.y + sub_group.height / 2

                for sub_object in sub_group.objects:
                    if sub_object.name.lower() == "activearcclass":
                        sub_object.properties["startAngle"] = str((int(sub_object.properties["startAngle"]) - 90) % 360)

                    obj_cx = sub_object.x + sub_object.width / 2
                    obj_cy = sub_object.y + sub_object.height / 2

                    rel_x = obj_cx - group_cx
                    rel_y = obj_cy - group_cy

                    new_rel_x = -rel_y
                    new_rel_y = rel_x

                    new_cx = group_cx + new_rel_x
                    new_cy = group_cy + new_rel_y

                    sub_object.x = int(new_cx - sub_object.height // 2)  # width/height swap
                    sub_object.y = int(new_cy - sub_object.width // 2)

                    sub_object.width, sub_object.height = sub_object.height, sub_object.width

                    if "xPoints" in sub_object.properties and "yPoints" in sub_object.properties:
                        for i in range(len(sub_object.properties["xPoints"])):
                            px = int(sub_object.properties["xPoints"][i])
                            py = int(sub_object.properties["yPoints"][i])

                            rel_px = px - group_cx
                            rel_py = py - group_cy

                            new_rel_px = rel_py
                            new_rel_py = -rel_px

                            sub_object.properties["xPoints"][i] = str(group_cx + new_rel_px)
                            sub_object.properties["yPoints"][i] = str(group_cy + new_rel_py)

        if orientation == "rotateCCW":
            for sub_group in temp_group.objects:
                group_cx = sub_group.x + sub_group.width / 2
                group_cy = sub_group.y + sub_group.height / 2

                for sub_object in sub_group.objects:
                    if sub_object.name.lower() == "activearcclass":
                        sub_object.properties["startAngle"] = str((int(sub_object.properties["startAngle"]) + 90) % 360)

                    obj_cx = sub_object.x + sub_object.width / 2
                    obj_cy = sub_object.y + sub_object.height / 2

                    rel_x = obj_cx - group_cx
                    rel_y = obj_cy - group_cy

                    new_rel_x = rel_y
                    new_rel_y = -rel_x

                    new_cx = group_cx + new_rel_x
                    new_cy = group_cy + new_rel_y

                    sub_object.x = int(new_cx - sub_object.height // 2)  # width/height swap
                    sub_object.y = int(new_cy - sub_object.width // 2)

                    sub_object.width, sub_object.height = sub_object.height, sub_object.width

                    if "xPoints" in sub_object.properties and "yPoints" in sub_object.properties:
                        for i in range(len(sub_object.properties["xPoints"])):
                            px = int(sub_object.properties["xPoints"][i])
                            py = int(sub_object.properties["yPoints"][i])

                            rel_px = px - group_cx
                            rel_py = py - group_cy

                            new_rel_px = rel_py
                            new_rel_py = -rel_px

                            sub_object.properties["xPoints"][i] = str(group_cx + new_rel_px)
                            sub_object.properties["yPoints"][i] = str(group_cy + new_rel_py)

    def remove_extra_groups(self, temp_group: EDMGroup, ranges: list[list[str]]) -> None:
        """
        Given a group of symbol groups, remove extra groups that are outside
        of the ranges given. (if there are more groups than ranges, the extra
        groups are removed) Also, if there are no ranges, only include the first
        group.

        Parameters
        ----------
        temp_group: EDMGroup
            The EDMGroup making up each symbol group whose objects will be modified
        ranges: list[list[str]]
            A list encompassing the ranges (mainly the len(ranges) is important)
        """
        if ranges is None:
            temp_group.objects = temp_group.objects[:1]
            return
        while len(temp_group.objects) > len(ranges):
            print(f"removed symbol group: {temp_group.objects.pop()}")

    def remove_symbol_groups(self, temp_group: EDMGroup, ranges: list[list[str]]) -> None:
        """
        Given a group of symbol groups, remove all groups whose ranges do not include 1.
        (This is done when no pvs are given and only the "1" group should be displayed)

        Parameters
        ----------
        temp_group: EDMGroup
            The EDMGroup making up each symbol group whose objects will be modified
        ranges: list[list[str]]
            A list encompassing the ranges (mainly the len(ranges) is important)
        """
        for i in range(
            len(ranges) - 1, -1, -1
        ):  # going backwards so I do not need to change indices when deleting objects
            min_range = ranges[i][0] or float("-inf")
            max_range = ranges[i][1] or float("inf")
            if float(min_range) > 1 or float(max_range) <= 1:
                temp_group.objects.pop(i)

    def generate_pv_ranges(
        self, properties: dict[str, bool | str | list[str]]
    ) -> list[list[int, int]]:  # Should pass in minValues, maxValues, num_states in directly instead of properties
        """
        Given minValues and maxValues (through properties), generate the ranges
        that the min/maxValues represent.

        Parameters
        ----------
        properties: dict[str, bool | str | list[str]]
            Object properties from the activesymbolclass

        Returns
        ----------
        list[list[int, int]]
            The list of pv ranges
        """
        min_values = properties["minValues"]
        max_values = properties["maxValues"]
        num_states = int(properties["numStates"])
        ranges = [[None, None] for _ in range(num_states)]
        for i in range(len(min_values)):
            separated_value = min_values[i].split(" ")
            if len(separated_value) == 1:
                ranges[i][0] = separated_value[0]
            elif len(separated_value) == 2:
                ranges[int(separated_value[0])][0] = separated_value[1]
            else:
                raise ValueError(f"Malformed minValue attribute: {min_values}")
        for i in range(len(max_values)):
            separated_value = max_values[i].split(" ")
            if len(separated_value) == 1:
                ranges[i][1] = separated_value[0]
            elif len(separated_value) == 2:
                ranges[int(separated_value[0])][1] = separated_value[1]
            else:
                raise ValueError(f"Malformed maxValue attribute: {max_values}")
        return ranges

    def populate_symbol_pvs(
        self, temp_group: EDMGroup, properties: dict[str, bool | str | list[str]], ranges: list[list[str]]
    ) -> None:
        """
        Given a group of symbol groups, add visPvs to each group based on their
        respective ranges. This will determine which group will appear based on
        the value of the pv connected to this activeSymbolClass.

        Parameters
        ----------
        temp_group: EDMGroup
            Group of groups whose objects will be modified
        properties: dict[str, bool | str | list[str]]
            Object properties from the activesymbolclass
        ranges: list[list[str]]
            The ranges taht determine the visPv ranges
        """
        num_states = int(properties["numStates"])
        if len(properties["controlPvs"]) > 1:
            print(f"This symbol object has more than one pV: {properties}")
        for i in range(
            min(len(temp_group.objects), num_states)
        ):  # TODO: Figure out what happens when numStates < temp_group.objects
            temp_group.objects[i].properties["symbolMin"] = ranges[i][0]
            temp_group.objects[i].properties["symbolMax"] = ranges[i][1]

    def add_symbol_properties(self, temp_group: EDMGroup, properties: dict[str, bool | str | list[str]]) -> None:
        """
        Add properties to each sub object within a symbol group. (isSymbol and symbolChannel)
        These are used to determine if the symbol should hide when symbolChannel is disconnected.

        Parameters
        ----------
        temp_group: EDMGroup
            Group of groups whose objects will be modified
        properties: dict[str, bool | str | list[str]]
            Object properties from the activesymbolclass
        """
        if "controlPvs" in properties:
            symbol_channel = properties["controlPvs"][0]
        else:
            symbol_channel = None

        for sub_group in temp_group.objects:
            for sub_object in sub_group.objects:
                sub_object.properties["isSymbol"] = True
                sub_object.properties["symbolChannel"] = symbol_channel

    def find_matching_end_group(self, text: str, begin_group_pos: int) -> int:
        """Find the matching endGroup for a beginGroup, handling nested groups"""
        pos = begin_group_pos + len("beginGroup")
        group_depth = 1

        while pos < len(text) and group_depth > 0:
            # Look for beginGroup
            begin_group_next = text.find("beginGroup", pos)
            end_group_next = text.find("endGroup", pos)

            if end_group_next == -1:
                return -1

            if begin_group_next != -1 and begin_group_next < end_group_next:
                group_depth += 1
                pos = begin_group_next + len("beginGroup")
            else:
                group_depth -= 1
                if group_depth == 0:
                    return end_group_next
                pos = end_group_next + len("endGroup")

        return -1

    @staticmethod
    def get_size_properties(text: str, strict: bool = False) -> dict[str, int]:
        """Get the size properties from the given text (x, y, width, height)

        Parameters
        ----------
        text : str
            Text to extract size properties from

        Returns
        -------
        dict : str, int
            A dictionary containing the size properties from the text
        """
        size_properties = {}
        for prop in ["x", "y", "width", "height"]:
            match = re.search(rf"^{prop[0]}\s+(-?\d+)", text, re.M)
            if not match and strict:
                raise ValueError(f"Missing required property '{prop}' in widget.")

            if not match:
                """match_macro = re.search(rf"^{prop[0]}\\s+(\\$\\{{[A-Za-z_][A-Za-z0-9_]*\\}})", text, re.M)
                if not match_macro:
                    raise ValueError(f"Missing required property '{prop}' in widget.")
                size_properties[prop] = match_macro.group(1)"""
                print(
                    f"Missing size property (likely a macro): {prop}"
                )  # TODO: Come back and use the improved solution
                size_properties[prop] = 1
                # raise ValueError(f"Missing required property '{prop}' in widget.")
            else:
                size_properties[prop] = int(match.group(1))

        return size_properties

    @classmethod
    def get_object_properties(cls, text: str) -> dict[str, bool | str | list[str]]:
        """Get the object properties from the given text. This can be any
        property that an EDM Object may use (e.g. fillColor, value, editable).
        Size properties and version information are ignored.

        Parameters
        ----------
        text : str
            Text to extract properties from

        Returns
        -------
        dict : str, bool | str | list[str]
            A dictionary containing the properties of an object
        """
        in_multi_line = False
        multi_line_key = None
        multi_line_prop = []
        properties = {}

        for line in text.splitlines():
            if not line or line.startswith(IGNORED_PROPERTIES):
                continue

            if in_multi_line:
                if line == "}":
                    in_multi_line = False
                    cleaned_prop = cls.remove_prepended_index(multi_line_prop)
                    properties[multi_line_key] = cleaned_prop
                    multi_line_prop = []
                else:
                    multi_line_prop.append(line.strip(' "'))
                continue

            try:
                k, v = line.split(maxsplit=1)
                v = v.strip(' "')
            except ValueError:
                k, v = line, True

            if v == "{":
                in_multi_line = True
                multi_line_key = k
            else:
                properties[k] = v

        return properties

    @staticmethod
    def remove_prepended_index(lines: list[str]) -> list[str]:
        """Removes the prepended indices from the given multi-line property value

        Parameters
        ----------
        lines : list[str]
            List of lines in a multi-line property value to remove the prepended indices from

        Returns
        -------
        list[str]
            Lines of the multi-line property value with the prepended indices removed
        """
        indices = []
        values = []

        def check_sequential(indices):
            """Check if the list of indices is sequential starting from 0"""
            return indices == list(range(len(indices)))

        for line in lines:
            try:
                k, v = line.split(maxsplit=1)
                indices.append(int(k))
                values.append(v.strip(' "'))
            except ValueError:
                return lines

        if not check_sequential(indices):
            return lines
        return values
