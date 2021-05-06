# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Miscellaneous helper methods for Jupyter Notebooks."""
import builtins
import difflib
import os
import re
import subprocess  # nosec
import sys
import uuid
import warnings
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import pkg_resources
from deprecated.sphinx import deprecated
from IPython import get_ipython
from IPython.core.display import HTML, display, DisplayHandle
from tqdm import tqdm, tqdm_notebook

from .._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


def export(func: Callable):
    """Decorate function or class to export to __all__."""
    mod = sys.modules[func.__module__]
    if hasattr(mod, "__all__"):
        all_list = getattr(mod, "__all__")
        all_list.append(func.__name__)
    else:
        all_list = [func.__name__]
        setattr(mod, "__all__", all_list)
    return func


@export
def string_empty(string: str) -> bool:
    """Return True if the input string is None or whitespace."""
    return not (bool(string) or isinstance(string, str) and bool(string.strip()))


@export
def is_not_empty(test_object: Any) -> bool:
    """Return True if the test_object is not None or empty."""
    if test_object:
        if isinstance(test_object, str):
            if test_object.strip():
                # test_object is not None AND myString is not empty or blank
                return True
            return False
        return True
    return False


# Toggle Code Cell Contents
_TOGGLE_CODE_STR = """
<form action="javascript:code_toggle()">
    <input type="submit" id="toggleButton" value="Show/Hide Code">
</form>
"""

_TOGGLE_CODE_PREPARE_STR = """
    <script>
    function code_toggle() {
        if ($('div.cell.code_cell.rendered.selected div.input').css('display')!='none'){
            $('div.cell.code_cell.rendered.selected div.input').hide();
        } else {
            $('div.cell.code_cell.rendered.selected div.input').show();
        }
    }
    </script>

"""


@export
def enable_toggle_code():
    """Load JS Function to enable code toggle button."""
    display(HTML(_TOGGLE_CODE_PREPARE_STR))


@export
def toggle_code():
    """Display a toggle button to hide/reveal code cell."""
    display(HTML(_TOGGLE_CODE_STR))


# String escapes
@export
def escape_windows_path(str_path: str) -> str:
    """Escape backslash characters in a string."""
    if is_not_empty(str_path):
        return str_path.replace("\\", "\\\\")
    return str_path


@export
def unescape_windows_path(str_path: str) -> str:
    """Remove escaping from backslash characters in a string."""
    if is_not_empty(str_path):
        return str_path.replace("\\\\", "\\")
    return str_path


@deprecated(reason="Inline Javascript no longer supported", version="0.3.2")
@export
def get_nb_query_param(nb_url_search: str, param: str) -> Optional[str]:
    """
    Get a url query parameter from the search string.

    Parameters
    ----------
    nb_url_search: str
        The URL search string
    param: str
        The parameter name to search for

    Returns
    -------
    Optional[str]
        value of the query string parameter or None if not found.

    """
    qs_regex = r"[\\?&]{param}=(?P<val>[^&#]*)".format(param=param)
    query_string_match = re.search(qs_regex, nb_url_search)
    if query_string_match:
        return query_string_match["val"]
    return None


@deprecated(reason="Inline Javascript no longer supported", version="0.3.2")
@export
def get_nb_query_params(nb_url_search: str) -> dict:
    """
    Get the url query parameters from the search string.

    Parameters
    ----------
    nb_url_search : str
        The URL search string

    Returns
    -------
    dict
        dictionary of the query string parameters.

    """
    nb_params = {}
    query_string_match = re.search(r"\?(?P<qs>[^#]+)#?", nb_url_search)
    if query_string_match:
        for param in query_string_match["qs"].split("&"):
            if "=" in param:
                nb_params[param.split("=")[0]] = param.split("=")[1]
    return nb_params


@deprecated(reason="Inline Javascript no longer supported", version="0.3.2")
@export
def get_notebook_query_string():
    """Execute javascript to publish notebook query string as python variable."""
    HTML(
        """
    <script type="text/javascript">
        IPython.notebook.kernel.execute(
            "nb_query_string='".concat(window.location.search).concat("'"));
    </script>
    """
    )


@export
def check_py_version(min_ver: Tuple = (3, 6)):
    """
    Check that the current python version is not less than `min_ver`.

    Parameters
    ----------
    min_ver : Tuple, optional
        Minimum required version, by default (3,6)

    """
    if isinstance(min_ver, (float, str)):
        min_ver_list = str(min_ver).split(".")
        min_ver = (int(min_ver_list[0]), int(min_ver_list[1]))
    if sys.version_info < min_ver:
        print("Check the Kernel->Change Kernel menu and ensure that Python 3.6")
        print("or later is selected as the active kernel.")
        raise SystemExit(
            "Python %s.%s or later is required.\n" % (min_ver[0], min_ver[1])
        )


@export
def resolve_pkg_path(part_path: str):
    """
    Resolve a path relative to the package.

    Parameters
    ----------
    part_path : str
        Absolute or relative path to resolve.

    """
    if Path(part_path).is_absolute():
        return part_path

    resolved_path = str(Path(__file__).resolve().parent.parent.joinpath(part_path))
    if Path(resolved_path).exists():
        return str(resolved_path)

    searched_paths = list(
        Path(__file__).resolve().parent.parent.glob(str(Path("**").joinpath(part_path)))
    )
    if not searched_paths or len(searched_paths) > 1:
        warnings.warn(f"No path or ambiguous match for {part_path} not found")
        return None
    return str(searched_paths[0])


# pylint: disable=not-an-iterable, too-many-branches
@export  # noqa: MC0001
def check_and_install_missing_packages(
    required_packages: List[str],
    force_notebook: bool = False,
    user: bool = False,
    upgrade: bool = False,
) -> bool:
    """
    Check and install missing packages from provided list of packages.

    Parameters
    ----------
    required_packages : List[str]
        List of packages to check and install in a current environment
        Note you can add package version constraints by appending them to
        the package name, e.g. `pandas>=1.01`
    force_notebook : bool, optional
        Boolean value to force notebook version of progress bar,
        by default False (autodetect)
    user : bool, optional
        Boolean value to toggle user flag while installing pip packages,
        by default False
    upgrade: bool, option
        If true supply `--upgrade` flag to pip to install the latest
        version (applies to all package in `required_packages`)

    Returns
    -------
    bool :
        True if successful, else False

    """
    missing_packages = []
    if isinstance(required_packages, str):
        if "," in required_packages:
            required_packages = [
                req.strip() for req in required_packages.split(",") if req.strip()
            ]
        else:
            required_packages = [required_packages]
    # Check package requirements against installed set
    for req in required_packages:
        pkg_req = pkg_resources.Requirement.parse(req)
        try:
            found_pkg = pkg_resources.working_set.find(pkg_req)
        except pkg_resources.VersionConflict:
            found_pkg = None
        if found_pkg is None:
            missing_packages.append(req)

    if not missing_packages:
        print("All packages are already installed")
        return True

    print("Missing packages to be installed: ", *missing_packages, sep=" ")
    if is_ipython() or force_notebook:
        pkgbar = tqdm_notebook(missing_packages, desc="Installing...", unit="bytes")
    else:
        pkgbar = tqdm(missing_packages, desc="Installing...", unit="bytes")

    pkg_command = ["install"] if is_ipython() else ["python", "-m", "pip", "install"]
    if user:
        pkg_command.append("--user")
    if upgrade:
        pkg_command.append("--upgrade")
    pkg_success = True
    for package in pkgbar:
        if is_ipython():
            get_ipython().run_line_magic("pip", " ".join(pkg_command + [package]))
        else:
            try:
                subprocess.run(  # nosec
                    pkg_command + [package],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as proc_err:
                print(f"An Error has occured while installing {package}.")
                print(f"Output: {str(proc_err.stdout)}")
                print(f"Errs: {str(proc_err.stderr)}")
                pkg_success = False
        print(f"{package} installed.")

    return pkg_success


# pylint: enable=not-an-iterable, too-many-branches


# pylint: disable=invalid-name
@export
def md(
    string: str,
    styles: Union[str, Iterable[str]] = None,
    disp_id: Optional[Union[bool, DisplayHandle]] = None,
) -> DisplayHandle:
    """
    Display a string as Markdown with optional style.

    Parameters
    ----------
    string : str
        The string to display
    styles : Union[str, Iterable[str]], optional
        A style mnemonic or collection of styles. If multiple styles,
        these can be supplied as an interable of strings or a comma-separated
        string, by default None
    disp_id : Optional[Union[bool, DisplayHandle]], optional
        If True, the function will return a display handle that can be re-used
        in subsequent calls to update the display object.
        If this is previously-created display handle, this is used as the
        target display object to update it with the content of this call,
        by default None

    Returns
    -------
    DisplayHandle
        A handle to the display object that can be used to update the
        contents.

    """
    style_str = ""
    if isinstance(styles, str):
        if "," in styles:
            styles = [style.strip() for style in styles.split(",")]
        else:
            style_str = _F_STYLES.get(styles, "")
    if isinstance(styles, list):
        style_str = ";".join(_F_STYLES.get(style, "") for style in styles)
    content = HTML(f"<p style='{style_str}'>{string}</p>")

    if isinstance(disp_id, bool) and disp_id:
        return display(content, display_id=True)
    if isinstance(disp_id, DisplayHandle):
        return disp_id.update(content)
    display(content)
    return None


# pylint: enable=invalid-name


@export
def md_warn(string: str, disp_id: Optional[DisplayHandle] = None):
    """
    Return string as a warning - orange text prefixed by "Warning".

    Parameters
    ----------
    string : str
        The warning message.
    disp_id : Optional[DisplayHandle], optional
        If True, the function will return a display handle that can be re-used
        in subsequent calls to update the display object.
        If this is previously-created display handle, this is used as the
        target display object to update it with the content of this call,
        by default None

    Returns
    -------
    DisplayHandle
        A handle to the display object that can be used to update the
        contents.

    """
    return md(f"Warning: {string}", "bold, orange, large", disp_id)


@export
def md_error(string: str, disp_id: Optional[DisplayHandle] = None):
    """
    Return string as an error - red text prefixed by "Error".

    Parameters
    ----------
    string : str
        The error message.
    disp_id : Optional[Union[bool, DisplayHandle]], optional
        If True, the function will return a display handle that can be re-used
        in subsequent calls to update the display object.
        If this is previously-created display handle, this is used as the
        target display object to update it with the content of this call,
        by default None

    """
    return md(f"Error: {string}", "bold, orange, large", disp_id)


# Styles available to use in the above Markdown tools.
_F_STYLES = {
    "bold": "font-weight: bold",
    "italic": "font-style: italic",
    "red": "color: red",
    "green": "color: green",
    "blue": "color: blue",
    "large": "font-size: 130%",
    "heading": "font-size: 200%",
}


@export
def is_ipython() -> bool:
    """
    Return True if running in IPython environment.

    Returns
    -------
    bool
        True if running in IPython environment,
        otherwise False

    """
    return bool(get_ipython())


def check_kwarg(arg_name: str, legal_args: List[str]):
    """
    Check argument names against a list.

    Parameters
    ----------
    arg_name : str
        Argument to check
    legal_args : List[str]
        List of possible arguments.

    Raises
    ------
    NameError
        If the argument is not legal. If the `arg_name` is
        a close match to one or more, `legal_args` these are
        returned in the exception.

    """
    if arg_name not in legal_args:
        closest = difflib.get_close_matches(arg_name, legal_args)
        mssg = f"{arg_name} is not a recognized argument or attribute. "
        if len(closest) == 1:
            mssg += f"Closest match is '{closest[0]}'"
        elif closest:
            match_list = [f"'{mtch}'" for mtch in closest]
            mssg += f"Closest matches are {', '.join(match_list)}"
        else:
            mssg += f"Valid options are {', '.join(legal_args)}"
        raise NameError(arg_name, mssg)


def check_kwargs(supplied_args: Dict[str, Any], legal_args: List[str]):
    """
    Check all kwargs names against a list.

    Parameters
    ----------
    supplied_args : Dict[str, Any]
        Arguments to check
    legal_args : List[str]
        List of possible arguments.

    Raises
    ------
    NameError
        If any of the arguments are not legal. If the an arg is
        a close match to one or more `legal_args`, these are
        returned in the exception.

    """
    name_errs = []
    for name in supplied_args:
        try:
            check_kwarg(name, legal_args)
        except NameError as err:
            name_errs.append(err)
    if name_errs:
        raise NameError(name_errs)


_U_TEST_ENV = "MP_UNIT_TEST"


def unit_testing() -> bool:
    """
    Return True if in unit testing.

    Returns
    -------
    bool
        True if in unit testing

    """
    return _U_TEST_ENV in os.environ


# pylint: disable=invalid-name
def set_unit_testing(on: bool = True):
    """
    Set flag env var to indicated that code is being unit-tested.

    Parameters
    ----------
    on : bool, optional
        Turn unit testing flag on or off, by default True

    """
    if on:
        os.environ[_U_TEST_ENV] = "True"
    else:
        os.environ.pop(_U_TEST_ENV, None)


# pylint: enable=invalid-name


def is_valid_uuid(uuid_str: Any) -> bool:
    """
    Return true if `uuid_str` is a value GUID/UUID.

    Parameters
    ----------
    uuid_str : Any
        String to test

    Returns
    -------
    bool
        True if valid GUID/UUID.

    """
    if not uuid_str:
        return False
    try:
        uuid.UUID(uuid_str)
    except (ValueError, TypeError):
        return False
    return True


def valid_pyname(identifier: str) -> str:
    """
    Return legal Python identifier, which doesn't collide with builtins.

    Parameters
    ----------
    identifier : str
        The input identifier

    Returns
    -------
    str
        The cleaned identifier

    """
    builtin_names = set(dir(builtins))
    if identifier in builtin_names:
        identifier = f"{identifier}_bi"
    identifier = re.sub("[^a-zA-Z0-9_]", "_", identifier)
    if identifier[0].isdigit():
        identifier = f"n_{identifier}"
    return identifier


def enum_parse(enum_cls: type, value: str) -> Optional[Enum]:
    """Try to parse a string value to an Enum member."""
    if not issubclass(enum_cls, Enum):
        raise TypeError("Can only be used with classes derived from enum.Enum.")
    if value in enum_cls.__members__:
        return enum_cls.__members__[value]
    val_lc = value.casefold()
    val_map = {name.casefold(): name for name in enum_cls.__members__}
    if val_lc in val_map:
        return enum_cls.__members__[val_map[val_lc]]
    return None


def arg_to_list(arg: Union[str, List[str]], delims=",; ") -> List[str]:
    """
    Convert an optional list/str/str with delims into a list.

    Parameters
    ----------
    arg : Union[str, List[str]]
        A string, delimited string or list
    delims : str, optional
        The default delimiters to use, by default ",; "

    Returns
    -------
    List[str]
        List of string components

    Raises
    ------
    TypeError
        If `arg` is not a string or list

    """
    if isinstance(arg, list):
        return arg
    if isinstance(arg, str):
        for char in delims:
            if char in arg:
                return [item.strip() for item in arg.split(char)]
        return [arg]
    raise TypeError("`arg` must be a string or a list.")


def collapse_dicts(*dicts: Dict[Any, Any]) -> Dict[Any, Any]:
    """Merge multiple dictionaries - later dicts have higher precendence."""
    if len(dicts) < 2:
        return dicts[0] or {}
    out_dict = dicts[0]
    for p_dict in dicts[1:]:
        out_dict = _merge_dicts(out_dict, p_dict)
    return out_dict


def _merge_dicts(dict1: Dict[Any, Any], dict2: Dict[Any, Any]):
    """Merge dict2 into dict1."""
    if not dict2:
        return dict1 or {}
    if not dict1:
        return dict2 or {}
    out_dict = {}
    for key in set().union(dict1, dict2):  # type: Any
        if (
            key in dict1
            and isinstance(dict1[key], dict)
            and key in dict2
            and isinstance(dict2[key], dict)
        ):
            d_val = _merge_dicts(dict1[key], dict2[key])
        elif key in dict2:
            d_val = dict2[key]
        else:
            d_val = dict1[key]
        out_dict[key] = d_val
    return out_dict
