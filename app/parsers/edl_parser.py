import re


class EDLAbstractObject:
    def __init__(self, x: int = None, y: int = None, width: int = None, height: int = None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = {}


class EDLScreenProperties(EDLAbstractObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EDLGroup(EDLAbstractObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objects = []

    def add_object(self, obj):
        self.objects.append(obj)

    def get_objects(self):
        return self.objects


class EDLObject(EDLAbstractObject):
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

        self.groups = []
        self.objects = []

    def parse_objects(self):
        pass
