# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Script to test msticpy extras."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys

__author__ = "Ian Hellen"

base_pkgs = [
    "argon2-cffi",
    "async-generator",
    "atomicwrites",
    "attrs",
    "backcall",
    "bleach",
    "cffi",
    "colorama",
    "decorator",
    "defusedxml",
    "entrypoints",
    "iniconfig",
    "ipykernel",
    "ipython",
    "ipython-genutils",
    "ipywidgets",
    "jedi",
    "Jinja2",
    "jsonschema",
    "jupyter",
    "jupyter-client",
    "jupyter-console",
    "jupyter-core",
    "jupyterlab-pygments",
    "MarkupSafe",
    "mistune",
    "nbclient",
    "nbconvert",
    "nbformat",
    "nest-asyncio",
    "notebook",
    "packaging",
    "pandocfilters",
    "parso",
    "pickleshare",
    "pip",
    "pluggy",
    "prometheus-client",
    "prompt-toolkit",
    "py",
    "pycparser",
    "Pygments",
    "pyparsing",
    "pyrsistent",
    "pytest",
    "python-dateutil",
    "pywin32",
    "pywinpty",
    "pyzmq",
    "qtconsole",
    "QtPy",
    "Send2Trash",
    "setuptools",
    "six",
    "terminado",
    "testpath",
    "toml",
    "tornado",
    "traitlets",
    "wcwidth",
    "webencodings",
    "wheel",
    "widgetsnbextension",
]


# pylint: disable=subprocess-run-check

VERB_ARGS = {"stdout": sys.stdout, "stderr": sys.stderr}


def install_pkg(extra: str, path: str, version: str, verbose: bool):
    """
    Install msticpy with extra from distrib path.

    Parameters
    ----------
    extra : str
        extra to install (default none)
    path : str
        path of the distribution

    """
    sp_run = [
        "python",
        "-m",
        "pip",
        "install",
        "-f",
        f"{path}/dist",
        "msticpy{extra_spec}=={ver}".format(
            extra_spec=f"[{extra}]" if extra else "",
            ver=version,
        ),
    ]

    print(f"Installing msticpy from {path}, extra={extra}")
    start = datetime.now()
    print("start", start)
    print(sp_run)
    if verbose:
        print(" ".join(sp_run))
    subprocess.run(sp_run, check=True, **(VERB_ARGS if verbose else {}))  # type: ignore

    end = datetime.now()
    print("end", end)
    print("duration", end - start)


def reset_pkgs(verbose: bool):
    """Reset enviroment - remove all non-core msticpy packages."""
    sp_run = [
        "python",
        "-m",
        "pip",
        "list",
    ]
    print("Getting currently installed packages")
    proc_call = subprocess.run(sp_run, check=True, capture_output=True)  # type: ignore
    inst_pkgs = proc_call.stdout.decode("utf-8").split("\n")[2:]
    inst_pkgs = {pkg.split()[0] for pkg in inst_pkgs if pkg.strip()}
    remove_pkgs = inst_pkgs - set(base_pkgs)

    sp_run.remove("list")
    sp_run.extend(["uninstall", "-y", *remove_pkgs])
    print("Removing non-core packages")
    print(sp_run)
    if verbose:
        print(" ".join(sp_run))
    subprocess.run(sp_run, **(VERB_ARGS if verbose else {}))  # type: ignore


def show_dist(path: str):
    """List current distributions."""
    dist_vers = Path(path).joinpath("dist").glob("*.tar.gz")
    for dist in dist_vers:
        print(str(dist.name).replace(".tar.gz", ""))


def run_tests(path: str, verbose: bool):
    """Run pytest on `path`."""
    sp_run = ["pytest", path]
    print("Running tests")
    if verbose:
        print(" ".join(sp_run))
    subprocess.run(sp_run, cwd=path, **(VERB_ARGS if verbose else {}))  # type: ignore


def make_dist(path: str, verbose: bool):
    """Create distrib at `path`."""
    sp_run = [
        "python",
        "setup.py",
        "sdist",
        "bdist_wheel",
    ]
    print("Creating distrib wheel")
    if verbose:
        print(" ".join(sp_run))
    subprocess.run(sp_run, cwd=path, **(VERB_ARGS if verbose else {}))


def _add_script_args():
    parser = argparse.ArgumentParser(description="Msticpy extras test script.")
    parser.add_argument(
        "cmd",
        choices=["install", "reset", "test", "makedist", "showdist"],
        help="Run command: [install | reset | test | makedist | showdist]",
    )
    parser.add_argument(
        "--extra",
        "-e",
        required=False,
        default=None,
        help="Name of extra",
    )
    parser.add_argument(
        "--path",
        "-p",
        required=False,
        default="/src/microsoft/msticpy",
        help="Path to root of msticpy repo",
    )
    parser.add_argument(
        "--version",
        "-n",
        required=False,
        help="Version of msticpy to install",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        required=False,
        default=False,
        help="Show full output of commands.",
    )
    return parser


# pylint: disable=invalid-name
if __name__ == "__main__":
    arg_parser = _add_script_args()
    args = arg_parser.parse_args()

    if args.cmd.casefold() == "install":
        install_pkg(args.extra, args.path, args.version, args.verbose)

    if args.cmd.casefold() == "reset":
        reset_pkgs(args.verbose)

    if args.cmd.casefold() == "test":
        run_tests(args.path, args.verbose)

    if args.cmd.casefold() == "makedist":
        make_dist(args.path, args.verbose)

    if args.cmd.casefold() == "showdist":
        show_dist(args.path)
