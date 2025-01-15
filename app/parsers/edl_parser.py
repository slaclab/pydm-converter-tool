import re


class EDLAbstractObject:
    """EDL Abstract Object class represents an abstract object in .edl files"""
    def __init__(self, x: int = None, y: int = None, width: int = None, height: int = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = {}


class EDLScreenProperties(EDLAbstractObject):
    """EDL Screen Properties class represents the screen properties in .edl files"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EDLGroup(EDLAbstractObject):
    """EDL Group class represents a group in .edl files"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objects = []

    def add_object(self, obj):
        self.objects.append(obj)

    def get_objects(self):
        return self.objects


class EDLObject(EDLAbstractObject):
    """EDL Object class represents an object in .edl files"""
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


class EDLFileParser:
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
        self.parse_objects_and_groups(self.text[self.screen_properties_end:])

    def parse_screen_properties(self):
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()

            x = int(re.search(r"x (\d+)", screen_prop_text).group(1))
            y = int(re.search(r"y (\d+)", screen_prop_text).group(1))
            width = int(re.search(r"w (\d+)", screen_prop_text).group(1))
            height = int(re.search(r"h (\d+)", screen_prop_text).group(1))

            self.screen_properties = EDLScreenProperties(x, y, width, height)

    def parse_objects_and_groups(self, text):
        pass
