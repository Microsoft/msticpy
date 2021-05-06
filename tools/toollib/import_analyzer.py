# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Python file import analyzer."""
from pathlib import Path
import re
import sys
from importlib import import_module
from typing import Dict, List, Optional, Set

import networkx as nx

# pylint: disable=relative-beyond-top-level
from .ast_parser import analyze
from . import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


PKG_TOKENS = r"([^#=><\[]+)(?:\[[^\]]+\])?([~=><]+)(.+)"


# pylint: disable=too-few-public-methods
class ModuleImports:
    """Container class for module analysis."""

    def __init__(self):
        """Initialize class."""
        self.internal: Set[str] = set()
        self.external: Set[str] = set()
        self.standard: Set[str] = set()
        self.setup_reqs: Set[str] = set()
        self.missing_reqs: Set[str] = set()
        self.unknown: Set[str] = set()


_PKG_RENAME_NAME = {
    "attr": "attrs",
    "dns": "dnspython",
    "pkg_resources": "setuptools",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "splunklib": "splunk-sdk",
    "vt": "vt-py",
    "vt_graph_api": "vt-graph-api",
    "kqlmagic": "KqlmagicCustom",
}


def _get_setup_reqs(
    package_root: str,
    req_file="requirements.txt",
    extras: Optional[List[str]] = None,
    skip_setup=True,
):
    with open(Path(package_root).joinpath(req_file), "r") as req_f:
        req_list = req_f.readlines()

    setup_pkgs = _extract_pkg_specs(req_list)
    if not skip_setup and not extras:
        try:
            extras = get_extras_from_setup(package_root=package_root, extra="all")
            extra_pkgs = _extract_pkg_specs(extras)
            setup_pkgs = setup_pkgs | extra_pkgs
        except ImportError:
            print("Could not process modifed 'setup.py'")
    setup_versions = {key[0].casefold(): key for key in setup_pkgs}
    setup_reqs = {key[0].casefold(): key[0] for key in setup_pkgs}

    # for packages that do not match top-level names
    # add the mapping
    # create a dictionary so that we can re-map some names
    for src, tgt in _PKG_RENAME_NAME.items():
        if tgt.casefold() in setup_reqs:
            setup_reqs.pop(tgt.casefold())
            setup_reqs[src] = tgt.casefold()
    # Rename Azure packages replace "." with "-"
    az_mgmt_reqs = {
        pkg.replace("-", "."): pkg for pkg in setup_reqs if pkg.startswith("azure-")
    }

    for key, pkg in az_mgmt_reqs.items():
        setup_reqs.pop(pkg)
        setup_reqs[key] = pkg

    return setup_reqs, setup_versions


def get_extras_from_setup(
    package_root: str,
    setup_py: str = "setup.py",
    extra: str = "all",
    include_base: bool = False,
) -> List[str]:
    """
    Return list of extras from setup.py.

    Parameters
    ----------
    package_root : str
        The root folder of the package
    setup_py : str, optional
        The name of the setup file to process, by default "setup.py"
    extra : str, optiona
        The name of the extra to return, by default "all"
    include_base : bool, optional
        If True include install_requires, by default False

    Returns
    -------
    List[str]
        List of package requirements.

    """
    setup_py = str(Path(package_root) / setup_py)

    setup_txt = None
    with open(setup_py, "r") as f_handle:
        setup_txt = f_handle.read()

    srch_txt = "setuptools.setup("
    repl_txt = [
        "def fake_setup(*args, **kwargs):",
        "    pass",
        "",
        "fake_setup(",
    ]
    setup_txt = setup_txt.replace(srch_txt, "\n".join(repl_txt))

    neut_setup_py = Path(package_root) / "neut_setup.py"
    try:
        with open(neut_setup_py, "w") as f_handle:
            f_handle.writelines(setup_txt)

        setup_mod = import_module("neut_setup")
        extras = getattr(setup_mod, "EXTRAS").get(extra)
        if include_base:
            base_install = getattr(setup_mod, "INSTALL_REQUIRES")
            extras.extend(
                [req.strip() for req in base_install if not req.strip().startswith("#")]
            )
        return sorted(list(set(extras)), key=str.casefold)
    finally:
        neut_setup_py.unlink()


def _extract_pkg_specs(pkg_specs: List[str]):
    return {
        re.match(PKG_TOKENS, item).groups()  # type: ignore
        for item in pkg_specs
        if re.match(PKG_TOKENS, item) and not item.strip().startswith("#")
    }


def _get_pkg_from_path(pkg_file: str, pkg_root: str):
    module = ""
    py_file = Path(pkg_file)
    rel_path = py_file.relative_to(pkg_root)

    for p_elem in reversed(rel_path.parts):
        if p_elem.endswith(".py"):
            p_elem = p_elem.replace(".py", "")
        module = p_elem + "." + module if module else p_elem
        yield module


# Adapted from code on stackoverflow (url split over 3 lines)
# https://stackoverflow.com/questions/22195382/how-to-check-
# if-a-module-library-package-is-part-of-the-python-standard-library
# /25646050#25646050
def _check_std_lib(modules):
    external = set()
    std_libs = set()
    imp_errors = set()
    paths = {str(Path(p).resolve()).lower() for p in sys.path}
    stdlib_paths = {
        p
        for p in paths
        if p.startswith(sys.prefix.lower()) and "site-packages" not in p
    }
    for mod_name in modules:
        if mod_name not in sys.modules:
            try:
                import_module(mod_name)
            except ImportError:
                imp_errors.add(mod_name)
                continue
            except Exception as err:  # pylint: disable=broad-except
                print(f"Unexpected exception importing {mod_name}")
                print(err)
                imp_errors.add(mod_name)
                continue
        module = sys.modules[mod_name]

        stdlib_module = _check_stdlib_path(module, mod_name, stdlib_paths)
        if stdlib_module:
            std_libs.add(mod_name)
            continue

        parts = mod_name.split(".")
        for i, part in enumerate(parts):
            partial = ".".join(parts[:i] + [part])
            if partial in external or partial in std_libs:
                # already listed or exempted
                break
            if partial in sys.modules and sys.modules[partial]:
                # if match, add as external import
                external.add(mod_name)
                break
    return std_libs, external, imp_errors


def _check_stdlib_path(module, mod_name, stdlib_paths):
    if (
        not module
        or mod_name in sys.builtin_module_names
        or not hasattr(module, "__file__")
    ):
        # an import sentinel, built-in module or not a real module, really
        return mod_name
    # Test the path
    fname = module.__file__
    if fname.endswith(("__init__.py", "__init__.pyc", "__init__.pyo")):
        fname = Path(fname).parent

    if "site-packages" in str(fname).lower():
        return None

    # step up the module path
    while Path(fname) != Path(fname).parent:
        if str(fname).lower() in stdlib_paths:
            # stdlib path, skip
            return mod_name
        fname = Path(fname).parent
    return None


def _get_pkg_modules(pkg_root):
    """Get the list of all modules from file paths."""
    pkg_modules = set()
    for py_file in pkg_root.glob("**/*.py"):
        pkg_modules.update(list(_get_pkg_from_path(py_file, pkg_root)))
        if py_file.name == "__init__.py":
            pkg_modules.update(list(_get_pkg_from_path(py_file.parent, pkg_root)))
    return pkg_modules


def _match_pkg_to_reqs(imports, setup_reqs):
    req_libs = set()
    req_missing = set()
    for imp in imports:
        imp = imp.lower()
        if imp in setup_reqs:
            req_libs.add(setup_reqs[imp])
            continue
        imp_parts = imp.split(".")
        for i in range(1, len(imp_parts)):
            imp_name = ".".join(imp_parts[0:i])

            if imp_name.lower() in setup_reqs:
                req_libs.add(setup_reqs[imp_name])
                break
        else:
            req_missing.add(setup_reqs.get(imp, imp))
    return req_libs, req_missing


def analyze_imports(
    package_root: str,
    package_name: str,
    req_file: str = "requirements.txt",
    extras: Optional[List[str]] = None,
    process_setup_py: bool = True,
) -> Dict[str, ModuleImports]:
    """
    Analyze imports for package.

    Parameters
    ----------
    package_root : str
        The path containing the package and requirements.txt
    package_name : str
        The name of the package (subfolder name)
    req_file : str, optional
        Name of the requirements file,
        by default "requirements.txt"
    extras : List[str]
        A list of extras not specified in requirements file.
    process_setup_py : bool, optional
        If True try to parse setup.py for extras.

    Returns
    -------
    Dict[str, ModuleImports]
        A dictionary of modules and imports

    """
    setup_reqs, _ = _get_setup_reqs(
        package_root, req_file, extras, skip_setup=(not process_setup_py)
    )
    pkg_root = Path(package_root) / package_name
    all_mod_imports: Dict[str, ModuleImports] = {}
    pkg_modules = _get_pkg_modules(pkg_root)

    pkg_py_files = list(pkg_root.glob("**/*.py"))
    print(f"processing {len(pkg_py_files)} modules")
    for py_file in pkg_py_files:
        module_imports = _analyze_module_imports(py_file, pkg_modules, setup_reqs)
        # add the external imports for the module
        mod_name = ".".join(py_file.relative_to(pkg_root).parts)
        all_mod_imports[mod_name] = module_imports

    return all_mod_imports


def _analyze_module_imports(py_file, pkg_modules, setup_reqs):
    file_analysis = analyze(py_file)

    # create a set of all imports
    all_imports = {file.strip() for file in file_analysis["imports"] if file}
    all_imports.update(
        file.strip() for file in file_analysis["imports_from"].keys() if file
    )

    if None in all_imports:
        all_imports.remove(None)  # type: ignore

    module_imports = ModuleImports()
    module_imports.internal = set(all_imports) & pkg_modules
    # remove known modules from the current package
    # to get the list of external imports
    ext_imports = set(all_imports) - pkg_modules
    (
        module_imports.standard,
        module_imports.external,
        module_imports.unknown,
    ) = _check_std_lib(ext_imports)

    module_imports.setup_reqs, module_imports.missing_reqs = _match_pkg_to_reqs(
        module_imports.external, setup_reqs
    )
    return module_imports


def print_module_imports(modules: Dict[str, ModuleImports], imp_type="setup_reqs"):
    """
    Print module imports of type.

    Parameters
    ----------
    modules : Dict[str, ModuleImports]
        Dictionary of module imports
    imp_type : str, optional
        import type, by default "setup_reqs"

    """
    for py_mod_name, py_mod in modules.items():
        print(py_mod_name, getattr(py_mod, imp_type))


def build_import_graph(modules: Dict[str, ModuleImports]) -> nx.Graph:
    """
    Build Networkx graph of imports.

    Parameters
    ----------
    modules : Dict[str, ModuleImports]
        Dictionary of module imports

    Returns
    -------
    nx.Graph
        Networkx DiGraph

    """
    req_imports = {mod: attribs.setup_reqs for mod, attribs in modules.items()}
    import_graph = nx.DiGraph()
    for py_mod, mod_imps in req_imports.items():
        for imp in mod_imps:
            import_graph.add_node(py_mod, n_type="module", degree=len(mod_imps))
            import_graph.add_node(imp, n_type="import")
            import_graph.add_edge(py_mod, imp)

    for node, attr in import_graph.nodes(data=True):
        if attr["n_type"] == "import":
            imp_nbrs = len(list(import_graph.predecessors(node)))
            import_graph.add_node(node, n_type="import", degree=imp_nbrs)

    return import_graph
