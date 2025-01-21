import re
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass, field


IGNORED_PROPERTIES = ("x", "y", "w", "h", "major", "minor", "release")


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
    object_pattern = re.compile(r"object (\w+)(?:.*?)beginObjectProperties(.*?)endObjectProperties", re.DOTALL)

    def __init__(self, file_path: str | Path):
        """Creates an instance of EDMFileParser for the given file_path

        Parameters
        ----------
        file_path : str | Path
            EDM file to parse
        """
        self.file_path = file_path

        with open(file_path, "r") as file:
            self.text = file.read()

        self.screen_properties_end = 0
        self.ui = EDMGroup()

        self.parse_screen_properties()
        self.parse_objects_and_groups(self.text[self.screen_properties_end :], self.ui)

    def parse_screen_properties(self) -> None:
        """Get the screen properties from the .edl file and set the UI
        height and width
        """
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            size_properties = self.get_size_properties(screen_prop_text)

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
            group_match = self.group_pattern.search(text, pos)
            object_match = self.object_pattern.search(text, pos)

            if object_match and (not group_match or object_match.start() < group_match.start()):
                name = object_match.group(1)
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                properties = self.get_object_properties(object_text)

                obj = EDMObject(name=name, properties=properties, **size_properties)
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
                break

    @staticmethod
    def get_size_properties(text: str) -> dict:
        """Get the size properties from the given text (x, y, width, height)

        Parameters
        ----------
        text : str
            Text to extract size properties from

        Returns
        -------
        dict
            A dictionary containing the size properties from the text
        """
        size_properties = {}
        size_properties["x"] = int(re.search(r"x (\d+)", text).group(1))
        size_properties["y"] = int(re.search(r"y (\d+)", text).group(1))
        size_properties["width"] = int(re.search(r"w (\d+)", text).group(1))
        size_properties["height"] = int(re.search(r"h (\d+)", text).group(1))

        return size_properties

    @staticmethod
    def get_object_properties(text: str) -> dict:
        """Get the object properties from the given text. This can be any
        property that an EDM Object may use (e.g. fillColor, value, editable).
        Size properties and version information are ignored.

        Parameters
        ----------
        text : str
            Text to extract properties from

        Returns
        -------
        dict
            A dictionary containing the properties of an object
        """
        properties = {}
        for line in text.splitlines():
            if not line or line.startswith(IGNORED_PROPERTIES):
                continue

            # TODO: Parse out multiline properties: value { \n ... \n ... \n }
            try:
                k, v = line.split(maxsplit=1)
            except ValueError:
                k, v = line, True
            properties[k] = v

        return properties


if __name__ == "__main__":
    """Startup code to test the EDMFileParser class"""
    parser = EDMFileParser(Path("../../examples/all_bsy0_main_with_groups.edl"))
    pprint(parser.ui, indent=2)
