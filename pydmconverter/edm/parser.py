import re
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass, field
from pydmconverter.edm.parser_helpers import convert_color_property_to_qcolor, parse_colors_list, search_color_list
import os


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
    #object_pattern = re.compile(r"object (\w+)(?:.*?)beginObjectProperties(.*?)endObjectProperties", re.DOTALL)
    object_pattern = re.compile(
        r"object\s+(\w+)\s*beginObjectProperties\s*(.*?)\s*endObjectProperties(?=\s*(?:#.*?)?(?:object|\s*$))", 
        re.DOTALL | re.MULTILINE
    )


    def __init__(self, file_path: str | Path):
        """Creates an instance of EDMFileParser for the given file_path

        Parameters
        ----------
        file_path : str | Path
            EDM file to parse
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r") as file:
            self.text = file.read()

        self.screen_properties_end = 0
        self.ui = EDMGroup()

        self.parse_screen_properties()
        self.trial_parse_objects_and_groups(self.text[self.screen_properties_end :], self.ui)

    def parse_screen_properties(self) -> None:
        """Get the screen properties from the .edl file and set the UI
        height and width
        """
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            size_properties = self.get_size_properties(screen_prop_text)
            other_properties = self.get_object_properties(screen_prop_text)
            if "bgColor" in other_properties:
                color_list_filepath = search_color_list()
                #color_list_dict = {"index0": "black"} 
                #color_list_filepath = os.getenv("COLORS_LIST_FILE")
                #parse_colors_list(color_list_filepath) #TODO
                color_list_dict = {
    "version": {
        "major": 4,
        "minor": 0,
        "release": 0,
    },
    "blinkms": 750,
    "columns": 5,
    "max": 0x10000,  # or 65536
    "alias": {
        "trace0": "red",
        "trace1": "green",
    },
    "static": {
        25: {
            "name": "Controller",
            "rgb": [0, 0, 65535],
        },
        26: {
            "name": "blinking red",
            "rgb": [65535, 0, 0, 41120, 0, 0],
        },
        27: {
            "name": "dark green",
            "rgb": [45055, 45055, 0],
        },
    },
    "rules": {
        100: {
            "name": "exampleRule",
            "conditions": [
                {
                    "condition": "=100 || =200",
                    "color": "strange",
                },
                # ... (3 other condition entries here) ...
                {
                    "condition": "default",
                    "color": "green",
                },
            ]
        }
    },
    "menumap": ["blinking red", "Controller", "dark green"],
    "alarm": {
        "disconnected": "dark green",
        "invalid": "blinking red",
        "minor": "Controller",
        "major": "red",
        "noalarm": "*",
    }
}
                edmColor = other_properties["bgColor"]
                other_properties["bgColor"] = convert_color_property_to_qcolor(edmColor, color_data=color_list_dict)
            self.ui.properties = other_properties

            self.ui.height = size_properties["height"]
            self.ui.width = size_properties["width"]

    def trial_parse_objects_and_groups(self, text: str, parent_group: EDMGroup) -> None:
        pos = 0
        while pos < len(text):
            # Skip whitespace and comments
            while pos < len(text) and (text[pos].isspace() or text[pos] == '#'):
                if text[pos] == '#':
                    while pos < len(text) and text[pos] != '\n':
                        pos += 1
                else:
                    pos += 1
            if pos >= len(text):
                break

            # Handle groups manually
            if text[pos:].lstrip().startswith("object activeGroupClass"):
                group_start = pos

                begin_obj_props = text.find("beginObjectProperties", group_start)
                begin_group_idx = text.find("beginGroup", begin_obj_props)
                end_group_idx = self.find_matching_end_group(text, begin_group_idx)
                end_obj_props = text.find("endObjectProperties", end_group_idx)

                #print("here232", begin_obj_props, begin_group_idx, end_group_idx, end_obj_props)
                # Ensure all markers are present
                if begin_obj_props == -1 or end_obj_props == -1 or begin_group_idx == -1:
                    #print("here8", begin_obj_props, end_obj_props, begin_group_idx)
                    #print("here9", text, "here9", end_obj_props)
                    snippet = text[pos:pos + 100].strip()
                    #print(f"Skipping malformed group at {pos}, snippet: {snippet}")
                    #breakpoint()
                    pos += 1
                    continue

                # Get matching endGroup (handles nesting)
                end_group_idx = self.find_matching_end_group(text, begin_group_idx)
                if end_group_idx == -1:
                    print(f"Could not find matching endGroup at {pos}")
                    pos += 1
                    continue

                # OPTIONAL trailing endObjectProperties
                extra_end_props = text.find("endObjectProperties", end_group_idx)
                group_end = extra_end_props + len("endObjectProperties") if (
                    extra_end_props != -1 and extra_end_props < text.find("object", end_group_idx)
                ) else end_group_idx + len("endGroup")

                # Extract header and body
                group_header = text[begin_obj_props + len("beginObjectProperties"):end_obj_props]
                group_body = text[begin_group_idx + len("beginGroup"):end_group_idx]
                print("blah", end_obj_props, "blah2", group_header, "blah3", group_body)

                size_props = self.get_size_properties(group_header)
                properties = self.get_object_properties(group_header)

                group = EDMGroup(**size_props)
                group.properties = properties

                self.trial_parse_objects_and_groups(group_body, group)
                parent_group.add_object(group)
                pos = group_end
                continue

            # Try matching a regular object
            object_match = self.object_pattern.search(text, pos)
            if object_match:
                name = object_match.group(1)
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                properties = self.get_object_properties(object_text)


                obj = EDMObject(name=name, properties=properties, **size_properties)
                parent_group.add_object(obj)

                pos = object_match.end()
            else:
                # Could not parse anything at this location
                snippet = text[pos:pos + 100]#.strip()
                print(f"Unrecognized text at pos {pos}: '{snippet}'")
                #breakpoint()
                pos = text.find('\n', pos) if '\n' in text[pos:] else len(text)



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
            group_match = self.group_pattern.search(text, pos)
            object_match = self.object_pattern.search(text, pos)

            if object_match and (not group_match or object_match.start() < group_match.start()):
                name = object_match.group(1)
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                properties = self.get_object_properties(object_text)

                obj = EDMObject(name=name, properties=properties, **size_properties)
                """if name == "activeMenuButtonClass":
                    print("here457")
                    print(name)
                    print(object_text)
                    print(obj)
                    breakpoint()"""
                parent_group.add_object(obj)

                pos = object_match.end()
            elif group_match:
                group_text = group_match.group(1)
                size_properties = self.get_size_properties(group_text)

                group = EDMGroup(**size_properties)
                self.parse_objects_and_groups(group_text, group)
                parent_group.add_object(group)

                pos = group_match.end()
            else:
                print(f"Unmatched text starting at {pos}:\n{text[pos:pos+200]}")
                #breakpoint()
                pos = text.find('\n', pos)
                break

    @staticmethod
    def get_size_properties(text: str) -> dict[str, int]:
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
            match = re.search(rf"{prop[0]} (\d+)", text)
            if not match:
                continue
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


if __name__ == "__main__":
    """Startup code to test the EDMFileParser class"""
    parser = EDMFileParser(Path("../../examples/all_bsy0_main_with_groups.edl"))
    pprint(parser.ui, indent=2)
