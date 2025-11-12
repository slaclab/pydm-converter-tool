import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydmconverter.custom_types import RGBA

logger = logging.getLogger(__name__)


def search_calc_list(file_path: str) -> str:
    """
    search for a calc.list file and return the path if found, returns None if no calc.list exists.

    This function reads a file, filters out comment lines (lines starting with
    '#') and empty lines, and assumes each definition in the file is specified
    by two consecutive non-comment lines:

    Parameters
    ----------
    file_path : str
        The path to a file whose directory will be searched for 'calc.list'.

    Returns
    -------
    Optional[str]
        The full path to the found 'calc.list' file, in either the local directory or in $EDMFILES, as a string if it exists;
        otherwise, None.
    """
    directory = os.path.dirname(file_path)
    local_calc_list = os.path.join(directory, "calc.list")

    if os.path.isfile(local_calc_list):
        return directory

    edmfiles = os.environ.get("EDMFILES", "")
    global_calc_list = os.path.join(edmfiles, "calc.list")

    if edmfiles and os.path.isfile(global_calc_list):
        return global_calc_list

    return None


def parse_calc_list(calc_list_path: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """
    Parse an EPICS-style calc.list file and return a dictionary mapping
    calculation names to a tuple of (rewrite_rule, expression).

    The file format typically looks like:
        ```
        CALC1 ...
        # ...
        <calc_name>
        [@rewrite_rule]
        <expression>
        # ...
        ```
    Parameters
    ----------
    calc_list_path : str
        Path to the calc.list file.

    Returns
    -------
    Dict[str, Tuple[Optional[str], Optional[str]]]
        A dictionary with keys as calculation names (e.g. 'sum', 'diff') and
        values as a 2-tuple (rewrite_rule, expression). Both are optional:
        rewrite_rule may be None if not present, and expression may also be None
        if the file has incomplete entries.
    """
    calc_dict: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    if calc_list_path is None or not os.path.isfile(calc_list_path):
        return calc_dict

    with open(calc_list_path, "r") as f:
        lines = [line.strip() for line in f]

    i = 1  # first line of file should be ignored
    while i < len(lines):
        line = lines[i]

        if not line or line.startswith("#"):
            i += 1
            continue

        calc_name = line
        i += 1

        rewrite_rule: Optional[str] = None
        expression: Optional[str] = None

        while i < len(lines) and (not lines[i] or lines[i].startswith("#")):
            i += 1

        if i < len(lines) and lines[i].startswith("@"):
            rewrite_rule = lines[i][1:].strip()
            i += 1

        while i < len(lines) and (not lines[i] or lines[i].startswith("#")):
            i += 1

        if i < len(lines):
            expression = lines[i]
            i += 1

        calc_dict[calc_name] = (rewrite_rule, expression)

    return calc_dict


def parse_calc_pv(edm_pv: str) -> Tuple[str, List[str], bool]:
    """
    Parse an EDM-style CALC PV reference and extract the calculation name (or inline
    expression), list of arguments, and whether it's an inline expression (curly braces).

    EDM CALC PV examples:
      - 'CALC\\sum(pv1, pv2)'
      - 'CALC\\\\{A+B\\}(pv1, pv2)'
      - 'CALC\\\\{(A)\\}($(P)$(R)Acquire)'

    Parameters
    ----------
    edm_pv : str
        The EDM-style CALC PV string to parse. For example, 'CALC\\sum(pv1, pv2)'.

    Returns
    -------
    calc_name_or_expr : str
        The calculation name (e.g. 'sum') or inline expression (e.g. 'A+B').
    arg_list : List[str]
        The list of arguments, e.g. ['pv1', 'pv2'].
    is_inline_expr : bool
        True if the EDM PV used inline curly brace syntax (e.g. '{A+B}'),
        False otherwise.

    Raises
    ------
    ValueError
        If the given edm_pv string doesn't match the expected CALC syntax.
    """

    expr_part, args_part = get_calc_groups(edm_pv)
    name_or_expr = clean_escape_characters(expr_part).strip()
    arg_string = clean_escape_characters(args_part)

    arg_list: List[str] = []
    if arg_string:
        arg_list = [arg.strip() for arg in arg_string.split(",")]
        for i in range(len(arg_list)):
            if arg_list[i].startswith("LOC\\"):
                arg_list[i] = loc_conversion(arg_list[i])

    is_inline_expr = False
    if name_or_expr.startswith("{") and name_or_expr.endswith("}"):
        is_inline_expr = True
        name_or_expr = name_or_expr[1:-1]
    return name_or_expr, arg_list, is_inline_expr


def get_calc_groups(edm_pv: str) -> Tuple[str]:
    prefix = "CALC\\"
    if not edm_pv.startswith(prefix):
        raise ValueError(f"Not a CALC PV: {edm_pv}")

    edm_pv = edm_pv[len(prefix) :]
    if "(" not in edm_pv and ")" not in edm_pv:
        return edm_pv, ""

    depth = 0
    end_idx = -1
    for i in range(len(edm_pv) - 1, -1, -1):
        if edm_pv[i] == ")":
            depth += 1
        elif edm_pv[i] == "(":
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    if end_idx == -1:
        logger.info(
            f"Fixing Invalid CALC PV format (unbalanced parens): {edm_pv}"
        )  # TODO: Comeback to see if I should fix this in the EDM file too

        edm_pv += ")"
        end_idx = edm_pv.rfind("(")
        # raise ValueError(f"Invalid CALC PV format (unbalanced parens): {edm_pv}")
    return edm_pv[:end_idx], edm_pv[end_idx + 1 : -1]


def clean_escape_characters(expr: str) -> str:
    """
    Remove extra \' characters from CALC/LOC expressions.

    Parameters
    ----------
    expression : str
        The expression to be cleaned.

    Returns
    -------
    str
        The new expression with \\s removed.
    """
    expr = expr.lstrip("\\")
    expr = expr.replace(r"\{", "{").replace(r"\}", "}")
    # TODO: If more \ removal cases are needed, add them here

    return expr


def apply_rewrite_rule(rewrite_rule: str, arg_list: List[str]) -> List[str]:
    """
    Apply a rewrite rule to an argument list. Rewrite rules often look like
    '$(A),$(A).SEVR', which can expand a single argument into multiple arguments
    by replacing placeholders.

    For example:
        rewrite_rule = '$(A),$(A).SEVR'
        arg_list = ['myPV']
      => new_args = ['myPV', 'myPV.SEVR']

    Parameters
    ----------
    rewrite_rule : str
        The rewrite rule, without the leading '@' (e.g. '$(A),$(A).SEVR').
    arg_list : List[str]
        The list of arguments to which we apply the rule.

    Returns
    -------
    List[str]
        A new list of arguments produced by the rewrite rule.
    """
    placeholders = "ABCDEFGHIJKL"

    arg_map = {}
    for i, arg_val in enumerate(arg_list):
        if i < len(placeholders):
            arg_map[placeholders[i]] = arg_val

    new_args = []

    for part in rewrite_rule.split(","):
        result = part

        for letter, val in arg_map.items():
            result = result.replace("$(" + letter + ")", val)
        new_args.append(result)

    return new_args


def translate_calc_pv_to_pydm(
    edm_pv: str,
    calc_dict: Optional[Dict[str, Tuple[Optional[str], Optional[str]]]] = None,
    default_prefix: str = "ca://",
) -> str:
    """
    Translate an EDM-style CALC PV (e.g., 'CALC\\sum(pv1, pv2)') into
    a PyDM calc plugin address, e.g.:

      calc://my_variable_name?A=channel://pv1&B=channel://pv2&expr=A+B

    Parameters
    ----------
    edm_pv : str
        The CALC PV in EDM syntax. For instance, "CALC\\sum(pv1, pv2)"
        or "CALC\\{A-B}(myPv, 10.5)".
    calc_dict : dict, optional
        A dictionary mapping calculation names to (rewrite_rule, expression).
        Typically from `parse_calc_list()`. This is required if the CALC PV
        references a named calc (e.g. 'sum') that is defined in a calc.list file.
        If the CALC PV uses an inline expression ({A+B}), this dictionary
        may be omitted.
    default_prefix : str, optional
        A prefix to apply to each argument if it doesn't already include a protocol.
        Defaults to 'channel://'.

    Returns
    -------
    str
        A PyDM calc plugin address string in the format:
        'calc://<identifier>?A=channel://pv1&B=channel://pv2&expr=A+B'.

    Raises
    ------
    ValueError
        If the named calculation does not exist in the provided `calc_dict`.
    """
    if calc_dict is None:
        calc_dict = {}
    name_or_expr, arg_list, is_inline_expr = parse_calc_pv(edm_pv)

    if is_inline_expr:
        expression = name_or_expr
        # identifier = "inline_expr"
        identifier = f"calc_{hash(edm_pv)}"
    else:
        calc_name = name_or_expr
        if calc_name == "sum2":  # convert sum2 to sum (sum2 is not in calc_dict)
            calc_name = "sum"
        if calc_name not in calc_dict:
            print(calc_dict)
            raise ValueError(f"Calculation '{calc_name}' is not defined in calc_dict. {arg_list}")
            # logger.warning(f"Calculation '{calc_name}' is not defined in calc_dict. {arg_list}")
            # return "failed CALC"
        rewrite_rule, expression = calc_dict[calc_name]
        if expression is None:
            raise ValueError(f"Calculation '{calc_name}' in calc_dict has no expression defined.")

        if rewrite_rule:
            arg_list = apply_rewrite_rule(rewrite_rule, arg_list)

        identifier = calc_name

    expression = reformat_calc_expression(expression)
    letters = "ABCDEFGHIJKL"
    var_map = {}
    for i, arg in enumerate(arg_list):
        if i < len(letters):
            var_map[letters[i]] = arg

    query_pairs = []
    for letter, arg_val in var_map.items():
        if not any(arg_val.startswith(proto) for proto in ("ca://", "pva://", "channel://")):
            arg_val = f"{default_prefix}{arg_val}"
        query_pairs.append(f"{letter}={arg_val}")

    query_pairs.append(f"expr={expression}")

    query_str = "&".join(query_pairs)
    pydm_calc_address = f"calc://{identifier}?{query_str}"

    return pydm_calc_address


def reformat_calc_expression(exp):
    """
    Convert EPICS calc expression operators to Python equivalents.

    EPICS calc uses different operators than Python:
    - ^ for exponentiation (Python uses **)
    - # for not equal (Python uses !=)
    """
    # Exponentiation: ^ -> **
    exp = exp.replace("^", "**")

    # Not equal: # -> !=
    exp = exp.replace("#", "!=")

    return exp


def loc_conversion(edm_string: str) -> str:
    """
    Convert an EDM local PV string to a PyDM local variable string, mapping types to supported PyDM types.

    Supported PyDM types:
    - int
    - float
    - str
    - array (numpy.ndarray)

    Enum ('e') is mapped to int for simplicity in this conversion.

    Parameters
    ----------
    edm_string : str
        EDM local PV string to be converted. Expected format is:
        "LOC\\name=type:value" (with optional scope modifiers and ignoring special functions).

    Returns
    -------
    pydm_string : str
        Corresponding PyDM string in the format:
        "loc://<name>?type=<mapped_type>&init=<value>".

    Raises
    ------
    ValueError
        If the EDM string does not start with 'LOC\\' or if it lacks the proper format.
    """
    prefix = "LOC\\"
    if not edm_string.startswith(prefix):
        raise ValueError("Provided string does not start with 'LOC\\'")

    content = edm_string[len(prefix) :]

    # if "$(" in content and ")" in content:
    #    content = content.split(")", 1)[-1]

    type_mapping = {
        "d": "float",
        "i": "int",
        "s": "str",
        "e": "int",  # mapping enum to int
    }

    try:
        name, type_and_value = content.split("=", 1)
        name = name.lstrip("\\")
        type_and_value = type_and_value.lstrip("=")  # for edgecases with ==
    except ValueError:
        name = content.lstrip("\\")
        return f"loc://{name}"
        # raise ValueError("Invalid EDM format: Missing '=' separator")

    try:
        type_char, value = type_and_value.split(":", 1)
    except ValueError:
        try:
            if (
                len(type_and_value) > 1 and type_and_value[0] in type_mapping and type_and_value[1] == ","
            ):  # ex. type_and_value=i,10
                value = type_and_value[2:]
                type_char = type_and_value[0]
            elif type_and_value in type_mapping:  # value is one of the mapped characters
                value = ""
                type_char = type_and_value
            else:
                int(type_and_value)  # testing if this is a proper int
                value = type_and_value
                type_char = "i"
            """if type_and_value.startswith("d,"):
                value = type_and_value[2:]
                float(value)
                type_char = "d"
            elif type_and_value.startswith("i,"):
                value = type_and_value[2:]
                int(value)
                type_char = "i"
            elif type_and_value == "s,":
                value = type_and_value[2:]
                type_char = "s"
            """
        except ValueError:
            try:
                float(type_and_value)
                value = type_and_value
                type_char = "d"
            except ValueError:
                # print("Invalid EDM format: Missing ':' separator and not an integer (enter c to continue)")
                print(f"name: {name}")
                print(f"value: {type_and_value}")
                raise ValueError("Invalid EDM format: Missing ':' separator and not an integer")

    edm_type = type_char.lower()
    if edm_type.isdigit():
        value = edm_type
        edm_type = "i"
    pydm_type = type_mapping.get(edm_type)
    if pydm_type is None:
        # logger.warning(f"Unsupported type character: {type_char}")
        # return f"No loc here"
        if edm_type and len(edm_type) > 1:
            edm_type = "s"
            value = type_and_value
            print(type_and_value)
            breakpoint()
        else:
            raise ValueError(f"Unsupported type character: {type_char}")

    if value.strip().upper() == "RAND()":
        raise NotImplementedError("Special function RAND() is not supported yet.")

        # a calc pv would have to be returned instead of a local pv
        # pydm_string = f"calc://{name}?var=loc://temp&expr=np.random.rand()"
        # an invisible widget with the definiation of a temp local pv would have to be added to the screen as well
        # temp_pv_string = "loc://temp?type=float&init=0.0"

    elif edm_type == "e":
        value_arr: List[str] = value.split(",")
        init: str = value_arr[0]
        enum_string: List[str] = value_arr[1:]
        pydm_string = f"loc://{name}?type={pydm_type}&init={init}&enum_string={enum_string}"
    else:
        pydm_string = f"loc://{name}?type={pydm_type}&init={value}"

    return pydm_string


def replace_calc_and_loc_in_edm_content(
    edm_content: str, filepath: str
) -> Tuple[str, Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """
    Replace both CALC\\...(...) and LOC\\...=... references in the EDM file content
    with PyDM equivalents. The first time each unique reference appears, the
    replacement is the full PyDM string; subsequent appearances use the short form.

    Parameters
    ----------
    edm_content : str
        The full text of the EDM file, as a single string.
    filepath : str
        path of the given edm file

    Returns
    -------
    new_content : str
        The EDM content after all CALC and LOC references have been replaced.
    encountered_calcs : Dict[str, Dict[str, str]]
        A dictionary of all encountered CALC references, mapping the original
        EDM reference to {"full": ..., "short": ...}.
    encountered_locs : Dict[str, Dict[str, str]]
        A dictionary of all encountered LOC references, similarly mapping each
        unique original LOC reference to "full" and "short" addresses.
    """
    calc_list_path = search_calc_list(filepath)
    calc_dict = parse_calc_list(calc_list_path)

    encountered_calcs: Dict[str, Dict[str, str]] = {}
    encountered_locs: Dict[str, Dict[str, str]] = {}

    calc_pattern = re.compile(r'"(CALC\\\\[^"]+)"')

    def replace_calc_match(match: re.Match) -> str:
        edm_pv = match.group(1)
        if edm_pv not in encountered_calcs:
            full_url = translate_calc_pv_to_pydm(edm_pv, calc_dict=calc_dict)
            short_url = full_url.split("?", 1)[0]
            encountered_calcs[edm_pv] = {"full": full_url, "short": short_url}
            return full_url
        else:
            return encountered_calcs[edm_pv]["short"]

    new_content = calc_pattern.sub(replace_calc_match, edm_content)

    # loc_pattern = re.compile(r'LOC\\+[^=]+=[dies]:[^"]*')]
    loc_pattern = re.compile(r'"(LOC\\[^"]+)"')

    def replace_loc_match(match: re.Match) -> str:
        edm_pv = match.group(1)
        if edm_pv not in encountered_locs:
            if "=" not in edm_pv:  # For case when calling pvs (with no =)
                cleaned_pv = re.sub(r"^LOC\\+", "", edm_pv)
                full_url = f"loc://{cleaned_pv}"
                short_url = full_url
            else:
                full_url = loc_conversion(edm_pv)  # TODO: remove the ifs later
                if full_url:
                    short_url = full_url.split("?", 1)[0]
                else:
                    full_url, short_url = "", ""
            encountered_locs[edm_pv] = {"full": full_url, "short": short_url}
            return full_url
        elif "=" in edm_pv:
            return encountered_locs[edm_pv]["full"]
        return encountered_locs[edm_pv]["short"]

    new_content = loc_pattern.sub(replace_loc_match, new_content)

    return new_content, encountered_calcs, encountered_locs


def search_color_list(cli_color_file=None) -> str | None:
    """
    Attempt to find the EDM color file by the following priority:

    1. CLI argument (cli_color_file), if provided.
    2. EDMCOLORFILE env variable (absolute path).
    3. EDMFILES env variable + "colors.list".
    4. Default path: "/etc/edm/colors.list".

    Parameters
    ----------
    cli_color_file : str or None, optional
        A file path passed via command line argument.
        If this is provided and valid, it overrides other checks.

    Returns
    -------
    str or None
        The path to the EDM color file if found, else None.
    """
    if cli_color_file and os.path.isfile(cli_color_file):
        return cli_color_file

    edmc = os.environ.get("EDMCOLORFILE")
    if edmc and os.path.isfile(edmc):
        return edmc

    edmfiles = os.environ.get("EDMFILES")
    if edmfiles:
        candidate = os.path.join(edmfiles, "colors.list")
        if os.path.isfile(candidate):
            return candidate

    default_path = "/etc/edm/colors.list"
    if os.path.isfile(default_path):
        return default_path

    return None


def parse_colors_list(filepath: str) -> Dict[str, Any]:
    """
    Parse an EDM `colors.list` file into a structured Python dictionary.

    Parameters
    ----------
    filepath : str
        Path to the `colors.list` file.

    Returns
    -------
    Dict[str, Any]
        A dictionary representing the parsed content of the `colors.list` file.

        Keys
        ----
        version : Dict[str, int]
            Dictionary containing {"major", "minor", "release"}.
        blinkms : int or None
            The blink period in milliseconds.
        columns : int or None
            Number of columns in the color palette.
        max : int or None
            The maximum RGB component value + 1 (e.g. 256 or 0x10000).
        alias : Dict[str, str]
            Maps an alias name to a (static or rule-based) color name.
        static : Dict[int, Dict[str, Union[str, List[int]]]]
            Static color definitions keyed by their numeric index.
            Each value is a dictionary containing:
              - "name": str
              - "rgb": List[int]  (3 values) or 6 values if blinking
        rules : Dict[int, Dict[str, Any]]
            Rule definitions keyed by their numeric index.
            Each value is a dictionary containing:
              - "name": str
              - "conditions": List[Dict[str, str]]
                Each condition has:
                  - "condition": str  (e.g. ">0 && <10" or "default")
                  - "color": str
        menumap : List[str]
            List of color names as displayed in the color name menu.
        alarm : Dict[str, str]
            Alarm color configuration. Keys are alarm states, values are color names.

    Notes
    -----
    - The first non-comment, non-empty line must be the version line: e.g. "4 0 0".
    - The parser assumes a well-formed file. If your file structure differs, you may need to
      handle additional edge cases (e.g. malformed lines, trailing braces, etc.).
    - A “blinking” static color has six numeric components for its two RGB states.
    - A rule line has the form: rule <index> <name> { ... }.
    - The menumap and alarm blocks must each be enclosed in braces.
    - The alias lines have the form: alias <alias_name> <color_name>.
    """

    re_comment = re.compile(r"^\s*#")
    re_setting = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*=\s*([^\s]+)")
    re_alias = re.compile(r"^\s*alias\s+(\S+)\s+(.+)$")

    # Regex for static color definitions:
    # e.g. static 25 Controller { 0 0 65535 }
    # or   static 26 "blinking red" { 65535 0 0 41120 0 0 }
    # Captures: index, name, content inside braces
    re_static = re.compile(r"^\s*static\s+(\d+)\s+\"?([^\"{]+)\"?\s*\{\s*([^}]*)\}")

    # Regex for rule definitions:
    # e.g. rule 100 exampleRule {
    #        =100 || =200 : strange
    #        default      : green
    #      }
    re_rule_header = re.compile(r"^\s*rule\s+(\d+)\s+(.*?){?\s*$")

    parsed_data: Dict[str, Any] = {
        "version": {},
        "blinkms": None,
        "columns": None,
        "max": None,
        "alias": {},
        "static": {},
        "rules": {},
        "menumap": [],
        "alarm": {},
    }

    if filepath is None:
        return parsed_data

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    def skip_blanks_and_comments(idx: int) -> int:
        while idx < len(lines):
            line_stripped = lines[idx].strip()
            if not line_stripped or re_comment.match(line_stripped):
                idx += 1
            else:
                break
        return idx

    idx = 0
    idx = skip_blanks_and_comments(idx)
    if idx >= len(lines):
        raise ValueError("File is empty or missing version line.")

    first_line = lines[idx].strip()
    idx += 1

    version_parts = first_line.split()
    if len(version_parts) != 3:
        raise ValueError("Version line must have exactly three integers: e.g. '4 0 0'.")

    parsed_data["version"] = {
        "major": int(version_parts[0]),
        "minor": int(version_parts[1]),
        "release": int(version_parts[2]),
    }

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1

        if not line or re_comment.match(line):
            continue

        match_setting = re_setting.match(line)
        if match_setting:
            key, value_str = match_setting.groups()
            try:
                if value_str.startswith("0x"):
                    value_int = int(value_str, 16)
                else:
                    value_int = int(value_str)
                parsed_data[key] = value_int
            except ValueError:
                parsed_data[key] = value_str
            continue

        match_alias = re_alias.match(line)
        if match_alias:
            alias_name, color_name = match_alias.groups()
            color_name = color_name.strip().strip('"')
            parsed_data["alias"][alias_name] = color_name
            continue

        match_static = re_static.match(line)
        if match_static:
            idx_str, color_name, rgb_str = match_static.groups()
            color_index = int(idx_str)
            color_name = color_name.strip()
            rgb_vals_str = rgb_str.replace(",", " ")
            rgb_vals = rgb_vals_str.split()

            def convert_val(v: str) -> int:
                v = v.strip()
                return int(v, 16) if v.startswith("0x") else int(v)

            rgb_nums = [convert_val(v) for v in rgb_vals]

            parsed_data["static"][color_index] = {
                "name": color_name,
                "rgb": rgb_nums,
            }
            continue

        match_rule = re_rule_header.match(line)
        if match_rule:
            rule_index_str, rule_name_part = match_rule.groups()
            rule_index = int(rule_index_str)
            rule_name_part = rule_name_part.strip()

            if rule_name_part.endswith("{"):
                rule_name_part = rule_name_part[:-1].strip()

            conditions = []
            if "{" not in line:
                idx = skip_blanks_and_comments(idx)

            while idx < len(lines):
                inner_line = lines[idx].strip()
                idx += 1
                if not inner_line or re_comment.match(inner_line):
                    continue
                if inner_line.startswith("}"):
                    break

                parts = inner_line.split(":")
                if len(parts) == 2:
                    condition_str = parts[0].strip()
                    color_str = parts[1].strip().strip('"')
                    conditions.append(
                        {
                            "condition": condition_str,
                            "color": color_str,
                        }
                    )

            parsed_data["rules"][rule_index] = {"name": rule_name_part, "conditions": conditions}
            continue

        if line.startswith("menumap"):
            idx = skip_blanks_and_comments(idx)
            while idx < len(lines):
                inner_line = lines[idx].strip()
                idx += 1
                if inner_line.startswith("}"):
                    break
                if not inner_line or re_comment.match(inner_line):
                    continue
                color_name = inner_line.strip().strip('"')
                parsed_data["menumap"].append(color_name)
            continue

        if line.startswith("alarm"):
            idx = skip_blanks_and_comments(idx)
            while idx < len(lines):
                inner_line = lines[idx].strip()
                idx += 1
                if inner_line.startswith("}"):
                    break
                if not inner_line or re_comment.match(inner_line):
                    continue
                alarm_parts = inner_line.split(":")
                if len(alarm_parts) == 2:
                    alarm_state = alarm_parts[0].strip()
                    color_name = alarm_parts[1].strip().strip('"')
                    parsed_data["alarm"][alarm_state] = color_name
            continue

        logging.warning(f"Unrecognized line in colors.list: '{line}'")

    for possible_key in ("blinkms", "columns", "max"):
        if possible_key in parsed_data:
            parsed_data[possible_key] = parsed_data[possible_key]
        else:
            parsed_data[possible_key] = None

    return parsed_data


def get_color_by_index(color_data: Dict[str, Any], index: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the color definition from color_data using an index string like 'index 3'.

    Args:
        color_data (Dict[str, Any]): The parsed colors.list data.
        index (str): The color index string, e.g., 'index 3'.

    Returns:
        Optional[Dict[str, Any]]: The corresponding color dictionary (expected to have an 'rgb' key)
                                  or None if not found.
    """
    match = re.match(r"index\s+(\d+)", index)
    if match:
        idx = int(match.group(1))
        color = color_data.get("static", {}).get(idx)
        if not color:
            logger.warning(f"Color index {idx} not found in colors.list.")
        return color
    logger.warning(f"Invalid color index format: '{index}'.")
    return None


def get_color_by_rgb(colorStr: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the color definition from color_data using an rgb string like 'rgb 0 0 0'.

    Args:
        colorStr (str): The color index string, e.g., 'rgb 0 0 0'.

    Returns:
        Optional[Dict[str, Any]]: The corresponding color dictionary (expected to have an 'rgb' key)
                                  or None if not found.
    """
    color_list: list[str] = colorStr.split(" ")
    output_dict = {}
    output_dict["rgb"] = [int(s) for s in color_list[1:]]  # get ints from list excluding 'rgb' at index 0

    return output_dict


def convert_color_property_to_qcolor(fillColor: str, color_data: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    """
    Convert the EDM 'fillColor', 'bgColor', 'fgColor' property into a tuple representing RGBA values.

    Returns:
        Optional[Tuple[int, int, int, int]]: A tuple (red, green, blue, alpha) or None.
    """
    if fillColor.startswith("rgb"):
        color_info = get_color_by_rgb(fillColor)
    else:
        color_info = get_color_by_index(color_data, fillColor)
    if not color_info:
        logger.warning(f"Could not find a color for fillColor '{fillColor}'. Using default gray.")
        return (128, 128, 128, 255)

    rgb = color_info.get("rgb")
    if not rgb or len(rgb) < 3:
        logger.warning(f"Invalid RGB data for color '{fillColor}': {rgb}")
        return (128, 128, 128, 255)
    red, green, blue = rgb[:3]
    alpha = 255

    max_val = color_data.get("max", 256)
    rgbMax = max(rgb)
    if rgbMax > 256:
        # Scale from 0-65535 to 0-255
        red = int(red * 255 / (max_val - 1))
        green = int(green * 255 / (max_val - 1))
        blue = int(blue * 255 / (max_val - 1))

    # result = (red, green, blue, alpha)
    result = RGBA(r=red, g=green, b=blue, a=alpha)
    logger.info(f"Converted {fillColor} to color: {result}")

    return result
