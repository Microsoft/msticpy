# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Unit test common utilities."""
from contextlib import contextmanager
from pathlib import Path
import os
from typing import Union, Dict, Any, Generator

from filelock import FileLock
from msticpy.common import pkg_config
from msticpy.common.utility import export

__author__ = "Ian Hellen"


@export
def get_test_data_path():
    """Get path to testdata folder."""
    _test_data_folders = [
        d for d, _, _ in os.walk(os.getcwd()) if d.endswith("/tests/testdata")
    ]
    if len(_test_data_folders) == 1:
        return _test_data_folders[0]
    return "./tests/testdata"


TEST_DATA_PATH = get_test_data_path()


# pylint: disable=protected-access
@contextmanager
def custom_mp_config(
    mp_path: Union[str, Path],
    path_check: bool = True,
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to temporarily set MSTICPYCONFIG path.

    Parameters
    ----------
    mp_path : Union[str, Path]
        Path to msticpy config yaml
    check_path : bool
        If False, skip check for existing file
    Yields
    ------
    Dict[str, Any]
        Custom settings.

    Raises
    ------
    FileNotFoundError
        If mp_path does not exist.

    """
    current_path = os.environ.get(pkg_config._CONFIG_ENV_VAR)
    if path_check and not Path(mp_path).is_file():
        raise FileNotFoundError(f"Setting MSTICPYCONFIG to non-existent file {mp_path}")
    try:
        # We need to lock the settings since these are global
        # Otherwise the tests interfere with each other.
        _lock_file_path = "./.mp_settings.lock"
        with FileLock(_lock_file_path):
            os.environ[pkg_config._CONFIG_ENV_VAR] = str(mp_path)
            pkg_config.refresh_config()
            yield pkg_config.settings
    finally:
        if not current_path:
            del os.environ[pkg_config._CONFIG_ENV_VAR]
        else:
            os.environ[pkg_config._CONFIG_ENV_VAR] = current_path
        pkg_config.refresh_config()
