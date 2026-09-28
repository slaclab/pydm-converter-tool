import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Sequence
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
# One line of an EDM array tag: an unquoted index, then the value.
_INDEXED_LINE_RE = re.compile(r"^\s*(\d+)(?:\s+(.*?))?\s*$")


def _clean_block_value(value: str) -> str:
    return value.strip(' "').replace('\\"', '"')


class IndexedBlock(list):
    """A brace-block value parsed from EDM ``<index> <value>`` lines.

    Behaves as the compact list of values (what positional consumers always
    saw); ``indices[i]`` is the EDM array index of item ``i``.
    """

    def __init__(self, values=(), indices=()):
        super().__init__(values)
        self.indices = list(indices)

    def by_index(self) -> dict[int, str]:
        """``{EDM index: value}`` (a repeated index keeps the last value, as EDM does)."""
        return dict(zip(self.indices, self))


def block_items(value) -> list[tuple[int, str]]:
    """A brace-block prop value -> ``[(EDM array index, value)]``.

    An :class:`IndexedBlock` keeps the indices the file wrote (``symbols { 2
    "P=X" }`` is entry 2, not 0); another list is numbered by position and a bare
    string is entry 0.
    """
    if isinstance(value, str):
        return [(0, value)]
    if not isinstance(value, list):
        return []
    items = [str(item) for item in value]
    indices = getattr(value, "indices", None)
    if indices is not None and len(indices) == len(items):
        return list(zip(indices, items))
    return list(enumerate(items))


def edm_int(value) -> int:
    """EDM's integer read of a tag value (strtol semantics): the leading integer, else 0."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else 0


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
    # Used with re.Pattern.match(text, pos) (a pos arg avoids slicing a huge string).
    _GROUP_AT = re.compile(r"object\s+activeGroupClass\b")
    object_pattern = re.compile(
        r"object\s+(\w+(?::\w+)?)\s*beginObjectProperties\s*(.*?)\s*endObjectProperties(?=\s*(?:#.*?)?(?:object|\s*$))",
        re.DOTALL | re.MULTILINE,
    )
    # object_pattern = re.compile(
    #    r"object\s+(\w+)\s*beginObjectProperties\s*(.*?)\s*endObjectProperties(?=\s*(?:#.*?)?(?:object|\s*$))",
    #    re.DOTALL | re.MULTILINE,
    # )

    def __init__(
        self,
        file_path: str | Path,
        output_file_path: str | Path,
        calc_list_file: str | None = None,
        calc_reuse_short: bool = True,
        search_paths: Sequence[str | Path] | None = None,
    ):
        """Creates an instance of EDMFileParser for the given file_path

        Parameters
        ----------
        file_path : str | Path
            EDM file to parse
        calc_list_file : str, optional
            Explicit path to a calc.list file used to resolve named CALC PVs
        calc_reuse_short : bool, optional
            Emit short ``calc://<id>`` reuse forms after a calc's first
            appearance (PyDM plugin semantics). The react/IR target passes
            False so every occurrence keeps its full query for formula hoisting.
        search_paths : Sequence[str | Path], optional
            Extra directories searched for symbol files (activeSymbolClass) and
            calc.list, after the file's own directory and before EDMDATAFILES
            (e.g. the original directory of an upload staged in a temp dir).
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        self.file_path = file_path
        self.output_file_path = output_file_path
        self.calc_list_file = calc_list_file
        self.calc_reuse_short = calc_reuse_short
        self.search_paths = [str(path) for path in search_paths or ()]

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
        # Screen dimensions ("width"/"height") the file does not declare as integers;
        # left at 0 for the caller to size from the content (see parse_screen_properties).
        self.missing_screen_size: list[str] = []

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
        self.text, _, _ = replace_calc_and_loc_in_edm_content(
            self.text,
            file_path,
            self.calc_list_file,
            calc_reuse_short=self.calc_reuse_short,
            search_paths=self.search_paths,
        )
        return self.text

    def parse_screen_properties(self) -> None:
        """Get the screen properties from the .edl file and set the UI
        height and width.

        A ``w``/``h`` that is missing or not an integer (template fragments write
        ``h $(DISP_HEIGHT)``), or a file with no ``beginScreenProperties`` block at
        all, does not abort the parse: the dimension stays 0 and is recorded in
        ``missing_screen_size`` so the caller can size it from the content.
        """
        match = self.screen_prop_pattern.search(self.text)
        if match:
            screen_prop_text = match.group(1)
            self.screen_properties_end = match.end()
            for prop in ("width", "height"):
                value = self._find_size(screen_prop_text, prop[0])
                if value is None:
                    logger.warning(f"Screen property '{prop[0]}' is missing or not an integer")
                    self.missing_screen_size.append(prop)
                else:
                    setattr(self.ui, prop, value)
            other_properties = self.get_object_properties(screen_prop_text)
            if "bgColor" in other_properties:
                color_list_filepath = search_color_list()
                color_list_dict = parse_colors_list(color_list_filepath)

                edmColor = other_properties["bgColor"]
                other_properties["bgColor"] = convert_color_property_to_qcolor(edmColor, color_data=color_list_dict)
            self.ui.properties = other_properties
        else:
            self.missing_screen_size = ["width", "height"]

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

            if self._GROUP_AT.match(text, pos):
                new_pos = self._parse_group_at(text, pos, parent_group)
                if new_pos == -1:
                    pos += 1
                    continue
                pos = new_pos
                continue

            # Try matching a regular object
            object_match = self.object_pattern.search(text, pos)
            if object_match:
                name = object_match.group(1).replace(":", "")  # remove colons from name (causes issues with PyDM)
                object_text = object_match.group(2)

                # The object regex searches forward past unparseable text (e.g. stray
                # VCS conflict markers seen in real corpora), so it can end up matching
                # a following group as though it were a plain object. Redirect to the
                # group parser so groups stay groups; only fall back to the generic
                # EDMObject path if the redirect itself fails (nothing may disappear
                # silently).
                if name.lower() == "activegroupclass":
                    new_pos = self._parse_group_at(text, object_match.start(), parent_group)
                    if new_pos != -1:
                        pos = new_pos
                        continue

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
                logger.warning(f"Unrecognized text at pos {pos}: '{snippet}'")
                pos = text.find("\n", pos) if "\n" in text[pos:] else len(text)

    def _parse_group_at(self, text: str, group_start: int, parent_group: EDMGroup) -> int:
        """Parse one ``object activeGroupClass ... endGroup`` block starting at ``group_start``.

        Returns the position just past the parsed group on success, or ``-1`` when the
        group is malformed (unbalanced/missing markers) — callers preserve the original
        warning + "advance by one and retry" behavior on failure.
        """
        begin_obj_props = text.find("beginObjectProperties", group_start)
        begin_group_idx = text.find("beginGroup", begin_obj_props)
        end_group_idx = self.find_matching_end_group(text, begin_group_idx)
        end_obj_props = text.find("endObjectProperties", end_group_idx)

        if begin_obj_props == -1 or end_obj_props == -1 or begin_group_idx == -1:
            snippet = text[group_start : group_start + 100].strip()
            logger.warning(f"Skipping malformed group at {group_start}, snippet: {snippet}")
            return -1

        end_group_idx = self.find_matching_end_group(text, begin_group_idx)
        if end_group_idx == -1:
            logger.warning(f"Could not find matching endGroup at {group_start}")
            return -1

        # get rid of trailing endObjectProperties
        extra_end_props = text.find("endObjectProperties", end_group_idx)
        next_object_pos = text.find("object", end_group_idx)
        group_end = (
            extra_end_props + len("endObjectProperties")
            if (extra_end_props != -1 and (next_object_pos == -1 or extra_end_props < next_object_pos))
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
        return group_end

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
            logger.warning("No embedded file specified in properties.")
            return EDMGroup()
        if not embedded_file.endswith(".edl"):
            embedded_file += ".edl"
        # EDM resolves symbol files beside the calling display first, then along
        # EDMDATAFILES (explicit search_paths go before it). Split on ":" only when
        # it is not a Windows drive colon (":" followed by a path separator), and
        # accept ";" separators too.
        edm_paths: list[str] = [str(Path(self.file_path).parent), *self.search_paths]
        datafiles = os.environ.get("EDMDATAFILES", ".")
        for chunk in datafiles.split(";"):
            edm_paths.extend(p for p in re.split(r":(?![\\/])", chunk) if p)
        embedded_text = None
        for path in edm_paths:
            full_path = Path(path) / embedded_file
            if full_path.is_file():
                raw = full_path.read_bytes()
                try:
                    embedded_text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    embedded_text = raw.decode("latin-1")
                break
        if embedded_text is None:
            logger.warning(f"Symbol file {embedded_file!r} not found beside the display or on EDMDATAFILES")
            # Keep the symbol's rect and name the missing file so the IR adapter can
            # attach a node warning (nothing may disappear silently).
            return EDMGroup(**size_properties, properties={"symbolFileNotFound": embedded_file})

        # Symbol expansion runs at parse time, outside the adapter's per-object
        # isolation: whatever a malformed symbol file or object does, the screen
        # keeps the symbol's rect with a warning instead of failing.
        try:
            return self._expand_symbol(embedded_file, embedded_text, properties, size_properties)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not abort the screen
            logger.warning(f"Symbol file {embedded_file!r} could not be expanded", exc_info=True)
            detail = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else ""
            return EDMGroup(
                **size_properties,
                properties={
                    "symbolWarnings": [
                        f"EDM symbol file '{embedded_file}' could not be expanded "
                        f"({type(exc).__name__}: {detail}); symbol not rendered"
                    ]
                },
            )

    def _expand_symbol(
        self,
        embedded_file: str,
        embedded_text: str,
        properties: dict[str, bool | str | list[str]],
        size_properties: dict[str, int],
    ) -> EDMGroup:
        """Explode a symbol file into one child group per state (EDM symbol.cc readSymbolFile).

        EDM reads the file's top-level objects in order as the states and stops at
        the first one that is not a group (states read so far are kept). A symbol
        with no control PV (``numPvs`` 0 or absent, EDM's default, or a blank
        ``controlPvs`` entry) draws state 1 only.
        """
        temp_group = EDMGroup()
        warnings: list[str] = []
        match = self.screen_prop_pattern.search(embedded_text)
        screen_properties_end = match.end() if match else 0
        self.parse_objects_and_groups(embedded_text[screen_properties_end:], temp_group)
        states: list[EDMGroup] = []
        for obj in temp_group.objects:
            if not isinstance(obj, EDMGroup):
                warnings.append(
                    f"EDM symbol file '{embedded_file}' has a {getattr(obj, 'name', 'non-group')} object where "
                    f"state {len(states)} should be a group; EDM stops reading states there"
                )
                break
            states.append(obj)
        temp_group.objects = states

        num_pvs = edm_int(properties.get("numPvs", 0))
        control_pvs = [pv for _, pv in block_items(properties.get("controlPvs"))]
        has_control = 0 < num_pvs <= len(control_pvs) and all(pv.strip() for pv in control_pvs[:num_pvs])
        self.resize_symbol_groups(temp_group, size_properties)
        self.add_symbol_properties(temp_group, properties)
        if "orientation" in properties:
            self.reorient_symbol_groups(temp_group, properties["orientation"], size_properties)
        if "minValues" not in properties and "maxValues" not in properties:
            ranges = None
        else:
            ranges = self.generate_pv_ranges(properties)
        self.remove_extra_groups(temp_group, ranges)
        if not has_control:
            # symbol.cc: controlExists = 0 -> index = 1; drawActive draws state 1 only.
            temp_group.objects = temp_group.objects[1:2]
        elif ranges is not None:
            self.populate_symbol_pvs(temp_group, properties, ranges)
        if warnings:
            temp_group.properties["symbolWarnings"] = warnings
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
            logger.debug(f"Removed symbol group: {temp_group.objects.pop()}")

    def generate_pv_ranges(
        self, properties: dict[str, bool | str | list[str]]
    ) -> list[list[str]]:  # Should pass in minValues, maxValues, num_states in directly instead of properties
        """
        Given minValues and maxValues (through properties), generate the ranges
        that the min/maxValues represent.

        EDM (symbol.cc) reads both as arrays indexed by state number, so an entry
        lands on the state its index names (``minValues { 1 "1" }`` is state 1)
        and a state the file leaves out keeps EDM's default 0.

        Parameters
        ----------
        properties: dict[str, bool | str | list[str]]
            Object properties from the activesymbolclass

        Returns
        ----------
        list[list[str]]
            ``[min, max]`` per state
        """
        num_states = edm_int(properties.get("numStates"))
        ranges = [["0", "0"] for _ in range(num_states)]
        for column, key in ((0, "minValues"), (1, "maxValues")):
            for index, value in block_items(properties.get(key)):
                if 0 <= index < num_states:
                    ranges[index][column] = value
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
        num_states = edm_int(properties.get("numStates"))
        if len(block_items(properties.get("controlPvs"))) > 1:
            logger.warning(f"This symbol object has more than one pV: {properties}")
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
        control_pvs = [pv for _, pv in sorted(block_items(properties.get("controlPvs")))]
        symbol_channel = control_pvs[0] if control_pvs else None

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
            value = EDMFileParser._find_size(text, prop[0])
            if value is None and strict:
                raise ValueError(f"Missing required property '{prop}' in widget.")

            if value is None:
                """match_macro = re.search(rf"^{prop[0]}\\s+(\\$\\{{[A-Za-z_][A-Za-z0-9_]*\\}})", text, re.M)
                if not match_macro:
                    raise ValueError(f"Missing required property '{prop}' in widget.")
                size_properties[prop] = match_macro.group(1)"""
                logger.warning(
                    f"Missing size property (likely a macro): {prop}"
                )  # TODO: Come back and use the improved solution
                size_properties[prop] = 1
                # raise ValueError(f"Missing required property '{prop}' in widget.")
            else:
                size_properties[prop] = value

        return size_properties

    @staticmethod
    def _find_size(text: str, key: str) -> int | None:
        """Integer value of the ``x``/``y``/``w``/``h`` line in ``text``, or None when
        absent or not an integer. EDM's tag reader skips leading whitespace, so an
        indented ``  w 236`` counts."""
        match = re.search(rf"^[ \t]*{key}\s+(-?\d+)", text, re.M)
        return int(match.group(1)) if match else None

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
                    multi_line_prop.append(line)
                continue

            try:
                k, v = line.split(maxsplit=1)
                v = v.strip(' "').replace('\\"', '"')
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
        """Clean the raw lines of a multi-line (brace-block) property value.

        EDM writes array tags (``displayFileName``, ``symbols``, ``minValues``,
        ``xPoints``, ...) as ``<index> <value>`` lines, and may skip indices
        (``symbols { 2 "P=X" }``) or start at 1. When every line carries an
        unquoted leading index, the values are returned as an
        :class:`IndexedBlock` whose ``indices`` keep each value's EDM index, so
        consumers can align parallel arrays (a related display's ``symbols[i]``
        belongs to its ``displayFileName[i]``). Otherwise (quoted text such as
        ``value { "1 GeV" }``) every line is kept as text. Values lose their
        surrounding quotes and ``\\"`` escapes either way.

        Parameters
        ----------
        lines : list[str]
            The raw lines between ``{`` and ``}``

        Returns
        -------
        list[str]
            The cleaned values (an :class:`IndexedBlock` for an indexed block)
        """
        lines = [line for line in lines if line.strip()]
        matches = [_INDEXED_LINE_RE.match(line) for line in lines]
        if lines and all(matches):
            return IndexedBlock(
                [_clean_block_value(match.group(2) or "") for match in matches],
                [int(match.group(1)) for match in matches],
            )
        return [_clean_block_value(line) for line in lines]
