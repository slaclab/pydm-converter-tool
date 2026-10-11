import re
import os
from functools import partial
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable
from pydmconverter.edm.parser_helpers import (
    SearchPaths,
    convert_color_property_to_qcolor,
    normalize_search_paths,
    parse_colors_list,
    resolve_inside,
    search_color_list,
    replace_calc_and_loc_in_edm_content,
    split_edm_path_list,
)
from pydmconverter.ir.source import exception_detail
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IGNORED_PROPERTIES = ("#", "x ", "y ", "w ", "h ", "major ", "minor ", "release ")
# One line of an EDM array tag: an unquoted index, then the value.
_INDEXED_LINE_RE = re.compile(r"^\s*(\d+)(?:\s+(.*?))?\s*$")
# Tags holding PV names (controlPv, visPv, controlPvs, dataPvStr, pv, ...).
_PV_TAG_RE = re.compile(r"\w*(?:Pv|Pvs|PvStr)|pv")
# A quoted EDM value up to its closing quote or line break, escapes included.
_QUOTED_VALUE_RE = re.compile(r'"((?:[^"\\\n]|\\[^\n])*)')
_ESCAPE_RE = re.compile(r"\\(.)")


def read_edm_string(value: str, literal_brace: str | None = None) -> str:
    """Unquote one EDM tag value.

    EDM writes strings in double quotes and escapes ``\\``, ``"``, ``{`` and
    ``}`` with a backslash; its reader skips leading whitespace and the opening
    quote and turns any ``\\x`` into ``x``. A quoted value ends at the first
    unescaped ``"`` or line break (or at the end of the text when the closing
    quote is missing). Spaces inside the quotes are kept, as EDM keeps them
    (``value { "Currently: " }``). A value that doesn't start with a quote keeps
    the old handling: strip spaces, newlines and quotes at both ends, and
    unescape ``\\"``.

    EDM expands only ``$(NAME)`` macros, so ``$\\{VAR\\}`` reads as the literal
    text ``${VAR}`` (a shell variable in a command). With ``literal_brace`` set,
    that brace is replaced by ``literal_brace``, so the text can't be mistaken
    for a ``$(NAME)`` macro, which :meth:`EDMFileParser.modify_text` writes as
    ``${NAME}``.
    """
    text = value.lstrip()
    if not text.startswith('"'):
        return value.strip(' "\n').replace('\\"', '"')
    body = _QUOTED_VALUE_RE.match(text).group(1)
    if literal_brace is None:
        return _ESCAPE_RE.sub(r"\1", body)

    def unescape(match: re.Match) -> str:
        # The character before the backslash is the one already read: "$" in
        # "$\{" and in "\$\{" alike.
        if match.group(1) == "{" and match.start() and body[match.start() - 1] == "$":
            return literal_brace
        return match.group(1)

    return _ESCAPE_RE.sub(unescape, body)


def literal_macro_clashes(text: str) -> list[str]:
    """Names an EDM file uses both as a literal ``$\\{NAME\\}`` (a shell variable,
    which EDM never expands) and as a ``$(NAME)`` macro, given the file's text
    after :meth:`EDMFileParser.modify_text` (which writes the macro as ``${NAME}``).

    Once read, both are ``${NAME}``, so a target that substitutes macros puts the
    macro's value into the shell variable.
    """
    literal = set(re.findall(r"\$\\\{(\w+)\\\}", text))
    return sorted(literal & set(re.findall(r"\$\{(\w+)\}", text)))


class IndexedBlock(list):
    """A brace-block value parsed from EDM ``<index> <value>`` lines.

    Behaves as the compact list of values (what positional consumers always
    saw); ``indices[i]`` is the EDM array index of item ``i``.
    """

    def __init__(self, values=(), indices=()):
        super().__init__(values)
        self.indices = list(indices)


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


def block_list(value) -> list[str]:
    """A brace-block prop value as a list indexed by EDM array index, with ""
    for each entry the file leaves out (``xPv { 1 "X" }`` -> ``["", "X"]``), for
    consumers that pair parallel arrays by position."""
    items = block_items(value)
    values = [""] * (max((index for index, _ in items), default=-1) + 1)
    for index, item in items:
        values[index] = item
    return values


def edm_int(value) -> int:
    """EDM's integer read of a tag value (strtol semantics): the leading integer, else 0."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else 0


def _read_edm_text(path) -> str:
    """Read an EDM file as text, falling back to Latin-1 when it isn't valid UTF-8."""
    try:
        with open(path, "r") as file:
            return file.read()
    except UnicodeDecodeError as e:
        logger.warning(f"Could not read file as UTF-8 (bad byte at {e.start}): {e}. Switching to Latin-1...")
        with open(path, "r", encoding="latin-1") as file:
            return file.read()


def _resolve_or_none(path: str | Path) -> Path | None:
    """``path`` resolved, or None when it cannot be (e.g. a NUL byte, a symlink loop)."""
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


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
    # True for the group an activeSymbolClass/anaSymbolClass becomes (expanded or a placeholder).
    is_symbol: bool = False

    def add_object(self, obj):
        self.objects.append(obj)


@dataclass
class EDMObject(EDMObjectBase):
    """EDM Object class represents an object in .edl files"""

    name: str = ""
    properties: dict = field(default_factory=dict)


# activeSymbolClass orientation values (symbol.cc orienEnumStr); "original" and anything else leave it as is.
SYMBOL_ORIENTATIONS = ("rotateCW", "rotateCCW", "FlipV", "FlipH")


def _map_line_points(obj: EDMObject, transform: Callable[[int, int], tuple[int, int]]) -> None:
    """Apply ``transform`` to an activeLineClass's points (left alone when malformed)."""
    if obj.name.lower() != "activelineclass":
        return
    x_points, y_points = obj.properties.get("xPoints"), obj.properties.get("yPoints")
    if not isinstance(x_points, list) or not isinstance(y_points, list) or len(x_points) != len(y_points):
        return
    try:
        points = [transform(int(x), int(y)) for x, y in zip(x_points, y_points)]
    except (TypeError, ValueError):
        return
    # In place, so an IndexedBlock keeps its EDM indices.
    x_points[:] = [str(x) for x, _ in points]
    y_points[:] = [str(y) for _, y in points]


def _move_edm_object(obj: EDMObjectBase, dx: int, dy: int) -> None:
    """EDM's move(): shift the rect, a line's points (activeLineClass::updateDimensions)
    and every child of a group or nested symbol (activeGroupClass/activeSymbolClass::move)."""
    obj.x += dx
    obj.y += dy
    if isinstance(obj, EDMGroup):
        for child in obj.objects:
            _move_edm_object(child, dx, dy)
    elif isinstance(obj, EDMObject):
        _map_line_points(obj, lambda px, py: (px + dx, py + dy))


def _reorient_point(orientation: str, ox: int, oy: int, px: int, py: int) -> tuple[int, int]:
    """A point rotated or flipped about (ox, oy) (act_grf.cc rotate/flip, in integers)."""
    if orientation == "rotateCW":
        return ox + oy - py, oy - ox + px
    if orientation == "rotateCCW":
        return ox - oy + py, ox + oy - px
    if orientation == "FlipH":
        return 2 * ox - px, py
    return px, 2 * oy - py  # FlipV


def _reorient_edm_object(obj: EDMObjectBase, orientation: str, ox: int, oy: int) -> None:
    """Rotate or flip ``obj`` about (ox, oy) as EDM's rotate()/flip() do.

    The rect is transformed as activeGraphicClass does (a rotation swaps width and
    height). A group then transforms each child about the same origin
    (activeGroupClass), a line its points (activeLineClass) and an arc its start
    angle (activeArcClass); an arc's flip never calls the base flip, so its rect
    stays put. A nested symbol is left alone: activeSymbolClass/aniSymbolClass
    rotate() and flip() only post "Symbol rotate --> No-op".
    """
    if isinstance(obj, EDMGroup) and obj.is_symbol:
        warnings = obj.properties.setdefault("symbolWarnings", [])
        warnings.append(
            f"EDM ignores orientation {orientation} for a symbol inside a symbol (symbol rotate/flip is a no-op); "
            "left as drawn"
        )
        return
    is_arc = isinstance(obj, EDMObject) and obj.name.lower() == "activearcclass"
    if not (is_arc and orientation in ("FlipH", "FlipV")):
        x0, y0 = _reorient_point(orientation, ox, oy, obj.x, obj.y)
        x1, y1 = _reorient_point(orientation, ox, oy, obj.x + obj.width, obj.y + obj.height)
        obj.x, obj.y, obj.width, obj.height = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
    if isinstance(obj, EDMGroup):
        for child in obj.objects:
            _reorient_edm_object(child, orientation, ox, oy)
    elif is_arc:
        start = edm_int(obj.properties.get("startAngle", 0))
        total = edm_int(obj.properties.get("totalAngle", 0))
        start = {
            "rotateCW": start - 90,
            "rotateCCW": start + 90,
            "FlipH": 180 - start - total,
            "FlipV": -start - total,
        }[orientation]
        obj.properties["startAngle"] = str(start % 360)
    elif isinstance(obj, EDMObject):
        _map_line_points(obj, partial(_reorient_point, orientation, ox, oy))


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
        color_list_file: str | None = None,
        search_paths: SearchPaths = None,
        confine_file_refs: bool = False,
        literal_brace: str | None = None,
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
        color_list_file : str, optional
            Explicit path to an EDM ``colors.list`` palette used to resolve the
            screen's own ``bgColor``. Falls back to ``EDMCOLORFILE``,
            ``$EDMFILES/colors.list``, then ``/etc/edm/colors.list`` when omitted.
        search_paths : str | Path | Sequence[str | Path], optional
            Extra directories searched for symbol files (activeSymbolClass) and
            calc.list, after the file's own directory and before EDMDATAFILES
            (e.g. the original directory of an upload staged in a temp dir).
        confine_file_refs : bool, optional
            For untrusted input: read a symbol file only from inside the file's own
            directory or one of ``search_paths``. A ``file`` name may use
            subdirectories or ``..`` as long as it resolves inside one of those
            directories (not necessarily the one it was joined to). An absolute name,
            or one that resolves outside all of them (``..``, or a symlink pointing
            elsewhere), is rejected before any existence check and leaves an empty
            group. EDMDATAFILES (and its ``.`` default, the CWD) is not searched, so
            the caller names every directory a symbol may come from.
        literal_brace : str, optional
            Written in place of the ``{`` of a literal ``${VAR}`` in a value (see
            :func:`read_edm_string`). The react/IR target passes a marker so the
            IR builder doesn't declare ``VAR`` as a macro; the default keeps
            ``${VAR}``.
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        self.file_path = file_path
        self.output_file_path = output_file_path
        self.calc_list_file = calc_list_file
        self.calc_reuse_short = calc_reuse_short
        self.color_list_file = color_list_file
        self.search_paths = normalize_search_paths(search_paths)
        self.confine_file_refs = confine_file_refs
        # Directories a confined symbol file must resolve inside (any one of them),
        # resolved once here; a root that cannot be resolved is left out.
        self._allowed_roots: list[Path] = []
        if confine_file_refs:
            roots = (_resolve_or_none(root) for root in [Path(file_path).parent, *self.search_paths])
            self._allowed_roots = [root for root in roots if root is not None]
        # (resolved path, text) of each symbol file keyed by the normalized symbol file
        # name (None when not found). Only lookups are cached, never a cycle outcome:
        # whether a symbol includes itself depends on where it is used.
        self._symbol_files: dict[str, tuple[Path, str] | None] = {}
        # Symbol file names a confined lookup rejected as outside the search paths.
        self._symbols_outside: set[str] = set()
        # Resolved paths of the display and of the symbol files being expanded, to stop
        # a symbol file that includes itself (directly or through others).
        self._symbol_stack: list[Path] = [_resolve_or_none(file_path) or Path(file_path)]
        self.literal_brace = literal_brace

        self.text = _read_edm_text(file_path)
        self.modify_text(file_path)

        self.screen_properties_end = 0
        self.ui = EDMGroup()
        # Screen dimensions ("width"/"height") the file does not declare as integers;
        # sized from the content (see parse_screen_properties and size_missing_from_content).
        self.missing_screen_size: list[str] = []

        self.parse_screen_properties()
        self.parse_objects_and_groups(self.text[self.screen_properties_end :], self.ui)
        self.size_missing_from_content()

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
        all, does not abort the parse: the dimension is recorded in
        ``missing_screen_size`` and sized from the content once the objects are
        parsed (:meth:`size_missing_from_content`).
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
            other_properties = self.get_object_properties(screen_prop_text, literal_brace=self.literal_brace)
            if "bgColor" in other_properties:
                color_list_filepath = search_color_list(self.color_list_file)
                color_list_dict = parse_colors_list(color_list_filepath)

                edmColor = other_properties["bgColor"]
                other_properties["bgColor"] = convert_color_property_to_qcolor(edmColor, color_data=color_list_dict)
            self.ui.properties = other_properties
        else:
            self.missing_screen_size = ["width", "height"]

    def size_missing_from_content(self) -> None:
        """Size each dimension in ``missing_screen_size`` from the content.

        The dimension becomes the top-level content extent (max ``x + width`` /
        ``y + height`` over the screen's objects and groups, ignoring zero-size
        ones) plus the IR builder's 8 px margin, so the .ui window is not 0-sized.
        ``missing_screen_size`` is kept: the IR adapter still passes None for these
        dimensions and lets the builder size them the same way.
        """
        sized = [obj for obj in self.ui.objects if obj.width and obj.height]
        margin = 8  # IRBuilder.build_screen's MARGIN
        if "width" in self.missing_screen_size:
            self.ui.width = max((obj.x + obj.width for obj in sized), default=0) + margin
        if "height" in self.missing_screen_size:
            self.ui.height = max((obj.y + obj.height for obj in sized), default=0) + margin

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
                properties = self.get_object_properties(object_text, literal_brace=self.literal_brace)

                if name.lower() == "activesymbolclass" or name.lower() == "anasymbolclass":
                    obj = self.get_symbol_group(properties=properties, size_properties=size_properties)
                    obj.is_symbol = True
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
        properties = self.get_object_properties(group_header, literal_brace=self.literal_brace)

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
        embedded file. A symbol file that is not found, is outside the search paths
        (``confine_file_refs``) or includes itself (directly or through other symbol
        files) gives an empty group whose properties say why.

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
            # An empty value means the symbol named no file.
            return EDMGroup(**size_properties, properties={"symbolFileNotFound": ""})
        if not embedded_file.endswith(".edl"):
            embedded_file += ".edl"
        if embedded_file not in self._symbol_files:
            self._symbol_files[embedded_file] = self._find_symbol_file(embedded_file)
        found = self._symbol_files[embedded_file]
        if embedded_file in self._symbols_outside:
            return EDMGroup(**size_properties, properties={"symbolFileOutsideSearchPaths": embedded_file})
        if found is None:
            # Keep the symbol's rect and name the missing file so the IR adapter can
            # attach a node warning (nothing may disappear silently).
            return EDMGroup(**size_properties, properties={"symbolFileNotFound": embedded_file})
        symbol_path, embedded_text = found
        if symbol_path in self._symbol_stack:
            # Expanding it again would never end (it used to raise RecursionError).
            logger.warning(
                f"Symbol file {embedded_file!r} includes itself (directly or through another symbol); not expanded"
            )
            return EDMGroup(**size_properties, properties={"symbolFileRecursive": embedded_file})

        self._symbol_stack.append(symbol_path)
        # Symbol expansion runs at parse time, outside the adapter's per-object
        # isolation: whatever a malformed symbol file or object does, the screen
        # keeps the symbol's rect with a warning instead of failing.
        try:
            return self._expand_symbol(embedded_file, embedded_text, properties, size_properties)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not abort the screen
            logger.warning(f"Symbol file {embedded_file!r} could not be expanded", exc_info=True)
            return EDMGroup(
                **size_properties,
                properties={
                    "symbolWarnings": [
                        f"EDM symbol file '{embedded_file}' could not be expanded "
                        f"({type(exc).__name__}: {exception_detail(exc)}); symbol not rendered"
                    ]
                },
            )
        finally:
            self._symbol_stack.pop()

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
            # symbol.cc createFromFile: if ( numStates < 1 ) numStates = 1;
            num_states = max(1, edm_int(properties.get("numStates")))
            self.reorient_symbol_groups(temp_group, properties["orientation"], size_properties, num_states)
        if not has_control:
            # symbol.cc: controlExists = 0 -> index = 1; drawActive draws state 1 only.
            # Pick it from the full state list: remove_extra_groups keeps only
            # state 0 when the file has no minValues/maxValues.
            temp_group.objects = temp_group.objects[1:2]
        else:
            if "minValues" not in properties and "maxValues" not in properties:
                ranges = None
            else:
                ranges = self.generate_pv_ranges(properties)
            self.remove_extra_groups(temp_group, ranges)
            if ranges is not None:
                self.populate_symbol_pvs(temp_group, properties, ranges)
        if warnings:
            temp_group.properties["symbolWarnings"] = warnings
        return temp_group

    def _find_symbol_file(self, embedded_file: str) -> tuple[Path, str] | None:
        """
        Look up a symbol file and read it.

        Parameters
        ----------
        embedded_file : str
            The symbol file name as written in the display, with its ``.edl`` suffix.

        Returns
        -------
        tuple[Path, str] | None
            The file's resolved path (the unresolved one when it cannot be resolved)
            and its text, or None when it is not found. A confined lookup that finds
            no candidate inside the allowed roots also adds the name to
            ``_symbols_outside``.
        """
        # EDM resolves symbol files beside the calling display first, then along
        # EDMDATAFILES (explicit search_paths go before it). Confined lookups skip
        # EDMDATAFILES.
        edm_paths: list[str] = [str(Path(self.file_path).parent), *self.search_paths]
        if not self.confine_file_refs:
            edm_paths.extend(split_edm_path_list(os.environ.get("EDMDATAFILES", ".")))
        any_in_bounds = False
        for path in edm_paths:
            if self.confine_file_refs:
                # Decided on the path alone, before any existence check, so a rejection
                # says nothing about whether the file exists.
                full_path = resolve_inside(path, embedded_file, self._allowed_roots)
                if full_path is None:
                    continue
                any_in_bounds = True
            else:
                full_path = Path(path) / embedded_file
            if full_path.is_file():
                resolved = full_path if self.confine_file_refs else _resolve_or_none(full_path) or full_path
                return resolved, _read_edm_text(full_path)
        if self.confine_file_refs and not any_in_bounds:
            logger.warning(f"Symbol file {embedded_file!r} is outside the search paths; not read")
            self._symbols_outside.add(embedded_file)
        else:
            logger.warning(
                f"Symbol file {embedded_file!r} not found beside the display, on the search paths or on EDMDATAFILES"
            )
        return None

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
            # symbol.cc readSymbolFile: each state child is move()d by the symbol's
            # offset from its state group, nested groups and line points included.
            dx = size_properties["x"] - sub_group.x
            dy = size_properties["y"] - sub_group.y
            for sub_object in sub_group.objects:
                _move_edm_object(sub_object, dx, dy)
            sub_group.x = size_properties["x"]
            sub_group.y = size_properties["y"]

    def reorient_symbol_groups(
        self, temp_group: EDMGroup, orientation: str, size_properties: dict[str, int], num_states: int = 1
    ) -> None:
        """
        Given a group of symbol groups, rotate (rotateCW, rotateCCW) or flip
        (FlipV, FlipH) every state group and everything in it, nested groups
        included, about the symbol's midpoint (symbol.cc createFromFile calls
        rotateInternal/flipInternal at getXMid(), getYMid()). The symbol's rect
        comes from the first ``num_states`` groups only, the ones EDM reads.

        Parameters
        ----------
        temp_group: EDMGroup
            The EDMGroup making up each symbol group whose objects will be modified
        orientation : str
            The orientation instruction to flip or rotate
        size_properties : dict[str, int]
            The coordinate and size_properties of the activesymbolclass
        num_states : int
            The symbol's numStates (at least 1); groups past it don't size the symbol
        """
        if orientation not in SYMBOL_ORIENTATIONS or not temp_group.objects:
            return
        # readSymbolFile reads only the first numStates groups and leaves the symbol
        # as wide and tall as the largest of those (w = maxW; h = maxH); the converter
        # never scales a symbol to its saved size, so that is its rect.
        read = temp_group.objects[:num_states]
        ox = size_properties["x"] + max(state.width for state in read) // 2
        oy = size_properties["y"] + max(state.height for state in read) // 2
        for state in temp_group.objects:
            _reorient_edm_object(state, orientation, ox, oy)

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
    def get_object_properties(cls, text: str, literal_brace: str | None = None) -> dict[str, bool | str | list[str]]:
        """Get the object properties from the given text. This can be any
        property that an EDM Object may use (e.g. fillColor, value, editable).
        Size properties and version information are ignored.

        Parameters
        ----------
        text : str
            Text to extract properties from
        literal_brace : str, optional
            Passed on to :func:`read_edm_string`

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
                    cleaned_prop = cls.remove_prepended_index(multi_line_prop, literal_brace)
                    properties[multi_line_key] = cls._trim_pv_value(multi_line_key, cleaned_prop)
                    multi_line_prop = []
                else:
                    multi_line_prop.append(line)
                continue

            try:
                k, v = line.split(maxsplit=1)
            except ValueError:
                properties[line] = True
                continue

            # A bare "{" opens a block; a quoted one ("\{" in EDM) is a value.
            if v.strip() == "{":
                in_multi_line = True
                multi_line_key = k
            else:
                properties[k] = cls._trim_pv_value(k, read_edm_string(v, literal_brace))

        return properties

    @property
    def literal_braces(self) -> bool:
        """Whether the display or a symbol file read so far has a literal
        ``$\\{`` that :func:`read_edm_string` marks when ``literal_brace`` is set."""
        texts = [self.text, *(found[1] for found in self._symbol_files.values() if found)]
        return any("$\\{" in text for text in texts)

    @staticmethod
    def _trim_pv_value(key: str, value):
        """Trim the spaces around a PV-name tag's value (or each value of a block).

        EDM keeps them and passes the name to Channel Access as written, where an
        IOC fails to resolve a name with a leading or trailing space (an all-space
        name counts as no PV). Trimming keeps the channel the display meant.
        """
        if not _PV_TAG_RE.fullmatch(key):
            return value
        if isinstance(value, IndexedBlock):
            return IndexedBlock([item.strip() for item in value], value.indices)
        if isinstance(value, list):
            return [item.strip() for item in value]
        return value.strip()

    @staticmethod
    def remove_prepended_index(lines: list[str], literal_brace: str | None = None) -> list[str]:
        """Clean the raw lines of a multi-line (brace-block) property value.

        EDM writes array tags (``displayFileName``, ``symbols``, ``minValues``,
        ``xPoints``, ...) as ``<index> <value>`` lines, and may skip indices
        (``symbols { 2 "P=X" }``) or start at 1. When every line carries an
        unquoted leading index and at least one line also carries a value, the
        values are returned as an :class:`IndexedBlock` whose ``indices`` keep
        each value's EDM index, so consumers can align parallel arrays (a related
        display's ``symbols[i]`` belongs to its ``displayFileName[i]``). Otherwise
        (quoted text such as ``value { "1 GeV" }``, or bare numbers such as
        ``value { 5 }``) every line is kept as text. Values are unquoted with
        :func:`read_edm_string` either way.

        In an indexed block, a line without a leading index continues the
        previous entry (a quoted value spanning lines, ``0 "Label`` then ``"``),
        and a repeated index replaces the earlier entry, as EDM's array read does.

        Parameters
        ----------
        lines : list[str]
            The raw lines between ``{`` and ``}``
        literal_brace : str, optional
            Passed on to :func:`read_edm_string`

        Returns
        -------
        list[str]
            The cleaned values (an :class:`IndexedBlock` for an indexed block)
        """
        lines = [line for line in lines if line.strip()]
        # Match stripped lines so a trailing space after a bare number ("5 ") does
        # not read as an index with an empty value.
        matches = [_INDEXED_LINE_RE.match(line.strip()) for line in lines]
        # A block of bare numbers (``value { 5 }``) is text, not indices with no
        # values; ``symbols { 0 "" }`` is still indexed (its value is empty).
        if lines and matches[0] and any(match.group(2) is not None for match in matches if match):
            entries: dict[int, str] = {}
            for line, match in zip(lines, matches):
                if match:
                    index = int(match.group(1))
                    entries[index] = match.group(2) or ""
                else:
                    entries[index] += "\n" + line.strip()
            # read_edm_string ends a value continued onto the next line at the line break.
            return IndexedBlock([read_edm_string(value, literal_brace) for value in entries.values()], list(entries))
        return [read_edm_string(line, literal_brace) for line in lines]
