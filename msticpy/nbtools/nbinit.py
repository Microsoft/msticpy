# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Initialization for Jupyter Notebooks."""
from contextlib import redirect_stdout
import importlib
import io
import os
import sys
import traceback
import warnings
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import ipywidgets as widgets
import pandas as pd
from IPython.core.interactiveshell import InteractiveShell
from IPython.display import HTML, display
from matplotlib import MatplotlibDeprecationWarning

try:
    import seaborn as sns
except ImportError:
    sns = None

from .._version import VERSION
from ..common.check_version import check_version
from ..common.exceptions import MsticpyException, MsticpyUserError
from ..common.pkg_config import get_config, validate_config
from ..common.utility import (
    check_and_install_missing_packages,
    check_kwargs,
    md,
    unit_testing,
    is_ipython,
)
from ..common.wsconfig import WorkspaceConfig
from .user_config import load_user_defaults

__version__ = VERSION
__author__ = "Ian Hellen"


_IMPORT_ERR_MSSG = """
<h2><font color='red'>One or more missing packages detected</h2>
Please correct these by installing the required packages, restart
the kernel and re-run the notebook.</font>
<i>Package error: {err}</i><br>
"""

_IMPORT_MODULE_MSSG = """
<font color='red'>Error import module {module}</font>
"""

_MISSING_PKG_WARN = """
<h3><font color='orange'>Warning {package} is not installed or has an
incorrect version</h3></font>
"""

_HELP_URIS = [
    (
        '<li><a href="https://github.com/Azure/Azure-Sentinel-Notebooks/blob/master/'
        'A%20Getting%20Started%20Guide%20For%20Azure%20Sentinel%20ML%20Notebooks.ipynb"'
        'target="_blank" rel="noopener noreferrer">'
        "Getting Started (notebook)</a></li>"
    ),
    (
        '<li><a href="https://github.com/Azure/Azure-Sentinel-Notebooks/blob/master/'
        'ConfiguringNotebookEnvironment.ipynb"'
        'target="_blank" rel="noopener noreferrer">'
        "Configuring your Notebook environment (notebook)</a></li>"
    ),
    (
        '<li><a href="https://msticpy.readthedocs.io/en/latest/getting_started/'
        'msticpyconfig.html"'
        'target="_blank" rel="noopener noreferrer">'
        "Configuring MSTICPy settings (doc)</a></li>"
    ),
    (
        '<li><a href="https://msticpy.readthedocs.io/en/latest/getting_started/'
        'SettingsEditor.html"'
        'target="_blank" rel="noopener noreferrer">'
        "MSTICPy settings editor (doc)</a></li>"
    ),
    (
        '<li><a href="https://github.com/Azure/Azure-Sentinel-Notebooks/blob/'
        'master/TroubleShootingNotebooks.ipynb"'
        'target="_blank" rel="noopener noreferrer">'
        "Trouble-Shooting Notebooks (notebook)</a></li>"
    ),
]

_MISSING_MPCONFIG_ENV_ERR = f"""
<h3><font color='orange'>Warning: no <i>msticpyconfig.yaml</i> found</h3></font>
The MSTICPYCONFIG environment variable is set but does not point
to a valid file.<br>
Some functionality (such as Threat Intel lookups) will not function without
valid configuration settings.<br>
The following resources will help you set up your configuration:
<ul>{"".join(_HELP_URIS)}</ul>
<br>You can load and run the first two of these from the Azure Sentinel
notebooks tab
"""


_MISSING_MPCONFIG_LOCAL_ERR = f"""
<h3><font color='orange'>Warning: no <i>msticpyconfig.yaml</i> found</h3></font>
No 'msticpyconfig.yaml' was found in the current directory and
the MSTICPYCONFIG environment variable is either not set or does not point
to a valid file.<br>
Some functionality (such as Threat Intel lookups) will not function without
valid configuration settings in this file.<br>
The following resources will help you set up your configuration:
<ul>{"".join(_HELP_URIS)}</ul>
"""


_PANDAS_REQ_VERSION = (0, 25, 0)


def _get_verbose_setting() -> Callable[[Optional[bool]], bool]:
    """Closure for holding trace setting."""
    _verbose_enabled = False

    def _verbose(verbose: Optional[bool] = None) -> bool:
        nonlocal _verbose_enabled
        if verbose is not None:
            _verbose_enabled = verbose
        return _verbose_enabled

    return _verbose


_VERBOSE = _get_verbose_setting()

_NB_IMPORTS = [
    dict(pkg="pandas", alias="pd"),
    dict(pkg="IPython", tgt="get_ipython"),
    dict(pkg="IPython.display", tgt="display"),
    dict(pkg="IPython.display", tgt="HTML"),
    dict(pkg="IPython.display", tgt="Markdown"),
    dict(pkg="ipywidgets", alias="widgets"),
    dict(pkg="pathlib", tgt="Path"),
    dict(pkg="matplotlib.pyplot", alias="plt"),
    dict(pkg="matplotlib", tgt="MatplotlibDeprecationWarning"),
    dict(pkg="seaborn", alias="sns"),
    dict(pkg="numpy", alias="np"),
]
_MP_IMPORTS = [
    dict(pkg="msticpy.data", tgt="QueryProvider"),
    dict(pkg="msticpy.nbtools.foliummap", tgt="FoliumMap"),
    dict(pkg="msticpy.common.utility", tgt="md"),
    dict(pkg="msticpy.common.utility", tgt="md_warn"),
    dict(pkg="msticpy.common.wsconfig", tgt="WorkspaceConfig"),
    dict(pkg="msticpy.datamodel.pivot", tgt="Pivot"),
    dict(pkg="msticpy.datamodel", tgt="entities"),
]
_MP_IMPORT_ALL = [
    dict(module_name="msticpy.nbtools"),
    dict(module_name="msticpy.sectools"),
]

_CONF_URI = (
    "https://msticpy.readthedocs.io/en/latest/getting_started/msticpyconfig.html"
)

_AZNB_GUIDE = (
    "Please run the <i>Getting Started Guide for Azure Sentinel "
    + "ML Notebooks</i> notebook."
)

current_providers: Dict[str, Any] = {}  # pylint: disable=invalid-name


def _pr_output(*args):
    """Send output to IPython display or print."""
    if is_ipython():
        display(HTML(" ".join([*args, "<br>"]).replace("\n", "<br>")))
    else:
        print(*args)


def init_notebook(
    namespace: Dict[str, Any],
    def_imports: str = "all",
    additional_packages: List[str] = None,
    extra_imports: List[str] = None,
    **kwargs,
) -> bool:
    """
    Initialize the notebook environment.

    Parameters
    ----------
    namespace : Dict[str, Any]
        Namespace (usually globals()) into which imports
        are to be populated.
    def_imports : str, optional
        Import default packages. By default "all".
        Possible values are:
        - "all" - import all packages
        - "nb" - import common notebook packages
        - "msticpy" - import msticpy packages
        - "none" (or any other value) don't load any default packages.
    additional_packages : List[str], optional
        Additional packages to be pip installed,
        by default None.
        Packages are specified by name only or version
        specification (e.g. "pandas>=0.25")
    user_install : bool, optional
        Install packages in the "user" rather than system site-packages.
        Use this option if you cannot or do not want to update the system
        packages.
        You should usually avoid using this option with standard Conda environments.
    extra_imports : List[str], optional
        Additional import definitions, by default None.
        Imports are specified as up to 3 comma-delimited values
        in a string:
        "{source_pkg}, [{import_tgt}], [{alias}]"
        `source_pkg` is mandatory - equivalent to a simple "import xyz"
        statement.
        `{import_tgt}` specifies an object to import from the package
        equivalent to "from source_pkg import import_tgt"
        `alias` allows renaming of the imported object - equivalent to
        the "as alias" part of the import statement.
        If you want to provide just `source_pkg` and `alias` include
        an additional placeholder comma: e.g. "pandas, , pd"
    friendly_exceptions : Optional[bool]
        Setting this to True causes msticpy to hook the notebook
        exception hander. Any exceptions derived from MsticpyUserException
        are displayed but do not produce a stack trace, etc.
        Defaults to system/user settings if no value is supplied.
    verbose : bool, optional
        Display more verbose status, by default False
    no_config_check : bool, optional
        Skip the check for valid configuration.

    Returns
    -------
    bool
        True if successful

    Raises
    ------
    MsticpyException
        If extra_imports data format is incorrect.
        If package with required version check has no version
        information.

    """
    global current_providers  # pylint: disable=global-statement, invalid-name

    check_kwargs(
        kwargs, ["user_install", "friendly_exceptions", "no_config_check", "verbose"]
    )
    user_install: bool = kwargs.pop("user_install", False)
    friendly_exceptions: Optional[bool] = kwargs.pop("friendly_exceptions", None)
    no_config_check: bool = kwargs.pop("no_config_check", False)
    verbose: bool = kwargs.pop("verbose", False)

    _VERBOSE(verbose)

    display(HTML("<hr><h4>Starting Notebook initialization...</h4>"))
    ver_out = io.StringIO()
    with redirect_stdout(ver_out):
        check_version()
        _pr_output(ver_out.getvalue())

    _pr_output("Processing imports....")
    imp_ok = _global_imports(
        namespace, additional_packages, user_install, extra_imports, def_imports
    )

    if no_config_check:
        conf_ok = True
    else:
        _pr_output("Checking configuration....")
        conf_ok, _ = _check_config()

    _pr_output("Setting notebook options....")
    _set_nb_options(namespace)

    if friendly_exceptions is None:
        friendly_exceptions = get_config("msticpy.FriendlyExceptions")
    if friendly_exceptions:
        if verbose:
            _pr_output("Friendly exceptions enabled.")
        InteractiveShell.showtraceback = _hook_ipython_exceptions(
            InteractiveShell.showtraceback
        )

    user_def_out = io.StringIO()
    with redirect_stdout(user_def_out):
        prov_dict = load_user_defaults()
        _pr_output(user_def_out.getvalue())

    if prov_dict:
        namespace.update(prov_dict)
        current_providers = prov_dict
        _pr_output("Autoloaded components:", ", ".join(prov_dict.keys()))

    if not imp_ok or not conf_ok:
        md("<font color='orange'><h3>Notebook setup completed with some warnings.</h3>")
        if not imp_ok:
            md("One or more libraries did not import successfully.")
            md(_AZNB_GUIDE)
        if not conf_ok:
            md("One or more configuration items were missing or set incorrectly.")
            md(
                _AZNB_GUIDE
                + f" and the <a href='{_CONF_URI}'>msticpy configuration guide</a>."
            )
        md("This notebook may still run but with reduced functionality.")
        return False
    display(HTML("<h4>Notebook initialization complete</h4>"))
    return True


def list_default_imports():
    """List the default imports for `init_notebook`."""
    for imp_group in (_NB_IMPORTS, _MP_IMPORTS):
        for imp_item in imp_group:
            if "tgt" in imp_item:
                import_line = f"from {imp_item['pkg']} import {imp_item['tgt']}"
            else:
                import_line = f"import {imp_item['pkg']}"
            if "alias" in imp_item:
                import_line += f" as {imp_item['alias']}"
            _pr_output(import_line)
    for imp_item in _MP_IMPORT_ALL:
        _pr_output(f"from {imp_item['module_name']} import *")


def _extract_pkg_name(
    imp_pkg: Optional[Dict[str, str]] = None,
    pkg: str = None,
    tgt: str = None,
    alias: str = None,
) -> str:
    """Return string representation of package import."""
    if imp_pkg:
        pkg = imp_pkg.get("pkg")
        tgt = imp_pkg.get("tgt")
        alias = imp_pkg.get("alias")
    import_item = f"{pkg}.{tgt}" if tgt else pkg
    if alias:
        import_item = f"{alias} ({import_item})"
    return import_item  # type: ignore


def _global_imports(  # noqa: MC0001
    namespace: Dict[str, Any],
    additional_packages: List[str] = None,
    user_install: bool = False,
    extra_imports: List[str] = None,
    def_imports: str = "all",
):
    import_list = []
    try:
        if def_imports.casefold() in ["all", "nb"]:
            for imp_pkg in _NB_IMPORTS:
                if sns is None and imp_pkg.get("pkg") == "seaborn":
                    continue
                _imp_from_package(nm_spc=namespace, **imp_pkg)
                import_list.append(_extract_pkg_name(imp_pkg))
            _check_and_reload_pkg(namespace, pd, _PANDAS_REQ_VERSION, "pd")

        if def_imports.casefold() in ["all", "msticpy"]:
            for imp_pkg in _MP_IMPORTS:
                _imp_from_package(nm_spc=namespace, **imp_pkg)
                import_list.append(_extract_pkg_name(imp_pkg))
            for imp_pkg in _MP_IMPORT_ALL:
                _imp_module_all(nm_spc=namespace, **imp_pkg)
                import_list.append(_extract_pkg_name(imp_pkg))

        if additional_packages:
            pkg_success = check_and_install_missing_packages(
                additional_packages, user=user_install
            )
            if not pkg_success:
                _pr_output("One or more packages failed to install.")
                _pr_output(
                    "Please re-run init_notebook() with the parameter user_install=True."
                )
            # We want to force import lib to see anything that we've
            # just installed.
            importlib.invalidate_caches()
        if extra_imports:
            import_list.extend(
                _import_extras(nm_spc=namespace, extra_imports=extra_imports)
            )

        if import_list:
            _pr_output("Imported:", ", ".join(imp for imp in import_list if imp))
        return True
    except ImportError as imp_err:
        display(HTML(_IMPORT_ERR_MSSG.format(err=imp_err)))
        return False


def _check_config() -> Tuple[  # noqa: MC0001
    bool, Optional[Tuple[List[str], List[str]]]
]:
    config_ok = True
    errs, warns = [], []
    warning_issued = False
    mp_path = os.environ.get("MSTICPYCONFIG")
    if mp_path and not Path(mp_path).exists():
        # Env var configured but invalid path
        warns = ["MSTICPYCONFIG path is invalid"]
        display(HTML(_MISSING_MPCONFIG_ENV_ERR))
        warning_issued = True
    mp_path = mp_path or "./msticpyconfig.yaml"
    if not Path(mp_path).exists():
        warns = ["MSTICPYCONFIG not found"]
        if not warning_issued:
            display(HTML(_MISSING_MPCONFIG_LOCAL_ERR))
        config_ok = False
    else:
        try:
            std_out_cap = io.StringIO()
            with redirect_stdout(std_out_cap):
                errs, warns = validate_config(config_file=mp_path)
            if errs or warns:
                _pr_output(std_out_cap.getvalue())
            if errs:
                config_ok = False
        # pylint: disable=broad-except
        except Exception as err:
            config_ok = False
            errs.append(f"Exception while checking configuration:\n{err}")
            _pr_output(f"Exception while checking configuration:\n{type(err)} - {err}")
            _pr_output("\n".join(traceback.format_tb(err.__traceback__)))
            _pr_output("Please report this to msticpy@microsoft.com")
        # pylint: enable=broad-except
    # If we haven't found a config, try loading WorkspaceConfig
    if not config_ok:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            std_out_cap = io.StringIO()
            with redirect_stdout(std_out_cap):
                ws_config = WorkspaceConfig(interactive=False)
            if not std_out_cap.getvalue():
                _pr_output(std_out_cap.getvalue())
        config_ok = ws_config.config_loaded
    if not config_ok:
        errs.append("No valid configuration for Azure Sentinel found.")
        _pr_output("No valid configuration for Azure Sentinel found.")
    return config_ok, (errs, warns)


def _set_nb_options(namespace):
    namespace["WIDGET_DEFAULTS"] = {
        "layout": widgets.Layout(width="95%"),
        "style": {"description_width": "initial"},
    }

    # Some of our dependencies (networkx) still use deprecated Matplotlib
    # APIs - we can't do anything about it, so suppress them from view
    warnings.simplefilter("ignore", category=MatplotlibDeprecationWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    if sns:
        sns.set()
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.max_colwidth", 100)
    # Set option on AML to display DataFrames with Schema
    if os.environ.get("APPSETTING_WEBSITE_SITE_NAME") == "AMLComputeInstance":
        pd.set_option("display.html.table_schema", True)
    os.environ["KQLMAGIC_LOAD_MODE"] = "silent"
    # Kqlmagic config will use AZ CLI login if available
    os.environ["KQLMAGIC_CONFIGURATION"] = "try_azcli_login=True"


def _import_extras(nm_spc: Dict[str, Any], extra_imports: List[str]):
    added_imports = []
    if isinstance(extra_imports, str):
        extra_imports = [extra_imports]
    for imp_spec in extra_imports:
        params: List[Optional[str]] = [None, None, None]
        for idx, param in enumerate(imp_spec.split(",")):
            params[idx] = param.strip() or None

        if params[0] is None:
            raise MsticpyException(
                f"First parameter in extra_imports is mandatory: {imp_spec}"
            )
        _imp_from_package(nm_spc=nm_spc, pkg=params[0], tgt=params[1], alias=params[2])
        added_imports.append(
            _extract_pkg_name(pkg=params[0], tgt=params[1], alias=params[2])
        )
    return added_imports


def _imp_module(nm_spc: Dict[str, Any], module_name: str, alias: str = None):
    """Import named module and assign to global alias."""
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        display(HTML(_IMPORT_MODULE_MSSG.format(module=module_name)))
        return None
    if alias:
        nm_spc[alias] = mod
    else:
        nm_spc[module_name] = mod
    if _VERBOSE():  # type: ignore
        _pr_output(f"{module_name} imported (alias={alias})")
    return mod


def _imp_module_all(nm_spc: Dict[str, Any], module_name):
    """Import all from named module add to globals."""
    try:
        imported_mod = importlib.import_module(module_name)
    except ImportError:
        display(HTML(_IMPORT_MODULE_MSSG.format(module=module_name)))
        return
    for item in dir(imported_mod):
        if item.startswith("_"):
            continue
        nm_spc[item] = getattr(imported_mod, item)
    if _VERBOSE():  # type: ignore
        _pr_output(f"All items imported from {module_name}")


def _imp_from_package(
    nm_spc: Dict[str, Any], pkg: str, tgt: str = None, alias: str = None
):
    """Import object or submodule from `pkg`."""
    if not tgt:
        return _imp_module(nm_spc=nm_spc, module_name=pkg, alias=alias)
    try:
        # target could be a module
        obj = importlib.import_module(f".{tgt}", pkg)
    except (ImportError, ModuleNotFoundError):
        # if not, it must be an attribute (class, func, etc.)
        try:
            mod = importlib.import_module(pkg)
        except ImportError:
            display(HTML(_IMPORT_MODULE_MSSG.format(module=pkg)))
            return None
        obj = getattr(mod, tgt)
    if alias:
        nm_spc[alias] = obj
    else:
        nm_spc[tgt] = obj
    if _VERBOSE():  # type: ignore
        _pr_output(f"{tgt} imported from {pkg} (alias={alias})")
    return obj


def _check_and_reload_pkg(
    nm_spc: Dict[str, Any], pkg: Any, req_version: Tuple[int, ...], alias: str = None
):
    """Check package version matches required version and reload."""
    warn_mssg = []
    pkg_name = pkg.__name__
    if not hasattr(pkg, "__version__"):
        raise MsticpyException(f"Package {pkg_name} has no version data.")
    pkg_version = tuple(int(v) for v in pkg.__version__.split("."))
    if pkg_version < req_version:
        display(HTML(_MISSING_PKG_WARN.format(package=pkg_name)))
        if not unit_testing():
            resp = input("Install the package now? (y/n)")  # nosec
        else:
            resp = "y"
        if resp.casefold().startswith("y"):
            warn_mssg.append(f"{pkg_name} was installed or upgraded.")
            pip_ver = ".".join([str(elem) for elem in req_version])
            pkg_spec = f"{pkg_name}>={pip_ver}"
            check_and_install_missing_packages(required_packages=[pkg_spec], user=True)

            if pkg_name in sys.modules:
                importlib.reload(pkg)
            else:
                _imp_module(nm_spc, pkg_name, alias=alias)
    if _VERBOSE():  # type: ignore
        _pr_output(f"{pkg_name} imported version {pkg.__version__}")
    return warn_mssg


def _hook_ipython_exceptions(func):
    """Hooks the `func` and bypasses it if exception is MsticpyUserException."""

    @wraps(func)
    def showtraceback(*args, **kwargs):
        """Replace IPython showtraceback."""
        # extract exception type, value and traceback
        e_type, _, _ = sys.exc_info()
        if e_type is not None and issubclass(e_type, MsticpyUserError):
            return None
        # otherwise run the original hook
        value = func(*args, **kwargs)
        return value

    return showtraceback
