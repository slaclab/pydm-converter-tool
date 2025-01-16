import re


class EDMAbstractObject:
    """EDM Abstract Object class represents an abstract object in .edl files"""

    def __init__(self, x: int = None, y: int = None, width: int = None, height: int = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = {}


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


class EDMObject(EDMAbstractObject):
    """EDM Object class represents an object in .edl files"""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


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
        self.groups = []
        self.objects = []

        self.parse_screen_properties()
        self.parse_objects_and_groups(self.text[self.screen_properties_end :])

    def parse_screen_properties(self):
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            size_properties = self.get_size_properties(screen_prop_text)

            self.screen_properties = EDMScreenProperties(**size_properties)

    def parse_objects_and_groups(self, text):
        pos = 0
        while pos < len(text):
            group_match = self.group_pattern.search(text, pos)
            object_match = self.object_pattern.search(text, pos)

            if object_match and (not group_match or object_match.start() < group_match.start()):
                object_text = object_match.group(2)
                size_properties = self.get_size_properties(object_text)
                name = object_match.group(1)

                obj = EDMObject(name, **size_properties)
                self.objects.append(obj)

                pos = object_match.end()

    def get_size_properties(self, text):
        size_properties = {}
        size_properties["x"] = int(re.search(r"x (\d+)", text).group(1))
        size_properties["y"] = int(re.search(r"y (\d+)", text).group(1))
        size_properties["width"] = int(re.search(r"w (\d+)", text).group(1))
        size_properties["height"] = int(re.search(r"h (\d+)", text).group(1))

        return size_properties
