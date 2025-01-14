import os
import re
from typing import Dict, List, Optional, Tuple


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
        CALC1 ...
        # ...
        <calc_name>
        [@rewrite_rule]
        <expression>
        # ...

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

    if not os.path.isfile(calc_list_path):
        return calc_dict

    with open(calc_list_path, "r") as f:
        lines = [line.strip() for line in f]

    i = 0
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
      - 'CALC\\{A+B}(pv1, pv2)'

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
    pattern = r"^CALC\\([^(\s]+)\(([^)]*)\)$"
    match = re.match(pattern, edm_pv.strip())
    if not match:
        raise ValueError(f"Invalid CALC PV syntax: '{edm_pv}'")

    name_or_expr = match.group(1)
    arg_string = match.group(2).strip()

    arg_list: List[str] = []
    if arg_string:
        arg_list = [arg.strip() for arg in arg_string.split(",")]

    is_inline_expr = False
    if name_or_expr.startswith("{") and name_or_expr.endswith("}"):
        is_inline_expr = True
        name_or_expr = name_or_expr[1:-1]

    return name_or_expr, arg_list, is_inline_expr


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
    default_prefix: str = "channel://",
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
        identifier = "inline_expr"
    else:
        calc_name = name_or_expr
        if calc_name not in calc_dict:
            raise ValueError(f"Calculation '{calc_name}' is not defined in calc_dict. ")

        rewrite_rule, expression = calc_dict[calc_name]
        if expression is None:
            raise ValueError(f"Calculation '{calc_name}' in calc_dict has no expression defined.")

        if rewrite_rule:
            arg_list = apply_rewrite_rule(rewrite_rule, arg_list)

        identifier = calc_name

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

    if "$(" in content and ")" in content:
        content = content.split(")", 1)[-1]

    try:
        name, type_and_value = content.split("=", 1)
    except ValueError:
        raise ValueError("Invalid EDM format: Missing '=' separator")

    try:
        type_char, value = type_and_value.split(":", 1)
    except ValueError:
        raise ValueError("Invalid EDM format: Missing ':' separator")

    type_mapping = {
        "d": "float",
        "i": "int",
        "s": "str",
        "e": "int",  # mapping enum to int by default
    }

    edm_type = type_char.lower()
    pydm_type = type_mapping.get(edm_type)
    if pydm_type is None:
        raise ValueError(f"Unsupported type character: {type_char}")

    if value.strip().upper() == "RAND()":
        raise NotImplementedError("Special function RAND() is not supported yet.")

        # a calc pv would have to be returned instead of a local pv
        # pydm_string = f"calc://{name}?var=loc://temp&expr=np.random.rand()"
        # an invisible widget with the definiation of a temp local pv would have to be added to the screen as well
        # temp_pv_string = "loc://temp?type=float&init=0.0"

    else:
        pydm_string = f"loc://{name}?type={pydm_type}&init={value}"

    return pydm_string
