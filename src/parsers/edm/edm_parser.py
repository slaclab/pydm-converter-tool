import re
from pprint import pprint, pformat


class EDMAbstractObject:
    """EDM Abstract Object class represents an abstract object in .edl files"""

    def __init__(self, x: int = None, y: int = None, width: int = None, height: int = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return f"{self.__class__.__name__}({self.x}, {self.y}, {self.width}, {self.height})"


class EDMScreenProperties(EDMAbstractObject):
    """EDM Screen Properties class represents the screen properties in .edl files"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EDMGroup(EDMAbstractObject):
    """EDM Group class represents a group in .edl files"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objects = []

    def add_object(self, obj):
        self.objects.append(obj)

    def get_objects(self):
        return self.objects

    def __repr__(self):
        repr_str = super().__repr__()[:-1]
        repr_str += f", objects: {pformat(self.objects, indent=2)})"
        return repr_str


class EDMObject(EDMAbstractObject):
    """EDM Object class represents an object in .edl files"""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.properties = {}

    def add_property(self, key, value=True):
        self.properties[key] = value

    def __repr__(self):
        repr_str = super().__repr__()[:-1]
        repr_str += f", name: {self.name}, properties: {pformat(self.properties, indent=2)})"
        return repr_str


class EDMFileParser:
    screen_prop_pattern = re.compile(r"beginScreenProperties(.*)endScreenProperties", re.DOTALL)
    group_pattern = re.compile(r"# \(Group\)(.*?)endGroup", re.DOTALL)
    object_pattern = re.compile(r"# \(([^)]+)\)(.*?)endObjectProperties", re.DOTALL)

    def __init__(self, file_path):
        self.file_path = file_path

        with open(file_path, "r") as file:
            self.text = file.read()

        self.screen_properties = None
        self.screen_properties_end = 0
        self.objects = []
        self.ui = EDMGroup(x=0, y=0)

        self.parse_screen_properties()
        self.parse_objects_and_groups(self.text[self.screen_properties_end :], self.ui)

    def parse_screen_properties(self):
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            size_properties = self.get_size_properties(screen_prop_text)

            self.ui.height = size_properties["height"]
            self.ui.width = size_properties["width"]

    def parse_objects_and_groups(self, text, parent_group: EDMGroup):
        edm_item = None
        pos = 0
        while pos < len(text):
            group_match = self.group_pattern.search(text, pos)
            object_match = self.object_pattern.search(text, pos)

            if object_match and (not group_match or object_match.start() < group_match.start()):
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                name = object_match.group(1)

                obj = EDMObject(name, **size_properties)
                edm_item = obj

                pos = object_match.end()
            elif group_match:
                group_text = group_match.group(1)
                size_properties = self.get_size_properties(group_text)

                group = EDMGroup(**size_properties)
                group.add_object(self.parse_objects_and_groups(group_text, group))
                edm_item = group

                pos = group_match.end()
            else:
                break

            if edm_item is not None and edm_item not in self.objects:
                parent_group.add_object(edm_item)
                self.objects.append(edm_item)

    def get_size_properties(self, text):
        size_properties = {}
        size_properties["x"] = int(re.search(r"x (\d+)", text).group(1))
        size_properties["y"] = int(re.search(r"y (\d+)", text).group(1))
        size_properties["width"] = int(re.search(r"w (\d+)", text).group(1))
        size_properties["height"] = int(re.search(r"h (\d+)", text).group(1))

        return size_properties


if __name__ == "__main__":
    parser = EDMFileParser("../../../examples/all_bsy0_main.edl")
    pprint(parser.ui, indent=2, width=1)
