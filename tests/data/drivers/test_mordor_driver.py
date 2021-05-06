# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Mordor data driver test."""
import contextlib
from datetime import datetime
import glob
import io
import os
from pathlib import Path

import pytest
import pytest_check as check
import pandas as pd


from msticpy.data import QueryProvider
from msticpy.data.drivers.mordor_driver import (
    MordorDriver,
    search_mdr_data,
    download_mdr_file,
)

__author__ = "Ian Hellen"

_SAVE_FOLDER = "mordor_test"
_SAVE_FOLDER2 = "mordor_test2"


@pytest.fixture(scope="session")
def qry_provider():
    """Query Provider fixture."""
    Path(_SAVE_FOLDER).mkdir(exist_ok=True)
    abs_path = Path(".").absolute()

    qry_prov = QueryProvider("Mordor", save_folder=f"./{_SAVE_FOLDER}")
    qry_prov.connect()
    yield qry_prov
    # remove downloaded file on cleanup
    _cleanup_temp_files(_SAVE_FOLDER)
    _cleanup_temp_files(abs_path.joinpath("mordor"))


def _cleanup_temp_files(path):
    # pylint: disable=broad-except
    for file in Path(path).glob("*"):
        if file.exists():
            try:
                file.unlink()
            except Exception:  # nosec
                pass
    if Path(path).is_dir():
        try:
            Path(path).rmdir()
        except Exception:  # nosec
            pass


# pylint: disable=redefined-outer-name, protected-access, global-statement


@pytest.fixture(scope="session")
def mdr_driver(qry_provider):
    """Test fixture to create mordor driver."""
    return qry_provider._query_provider


def test_mordor_load(mdr_driver: MordorDriver):
    """Check basic load of driver."""
    check.is_true(mdr_driver.loaded)
    check.is_true(mdr_driver.connected)
    check.is_false(mdr_driver.use_query_paths)
    check.is_true(mdr_driver.has_driver_queries)

    check.is_instance(mdr_driver.mitre_techniques, pd.DataFrame)
    check.is_instance(mdr_driver.mitre_tactics, pd.DataFrame)
    check.is_in("T1078", mdr_driver.mitre_techniques.index)
    check.is_in("TA0001", mdr_driver.mitre_tactics.index)

    check.is_true(len(mdr_driver.mordor_data) > 50)

    _, first_item = next(iter(mdr_driver.mordor_data.items()))
    check.is_instance(first_item.title, str)
    check.is_instance(first_item.id, str)
    check.is_instance(first_item.author, str)
    check.is_instance(first_item.creation_date, datetime)
    check.is_instance(first_item.files, list)
    check.is_true(len(first_item.files) > 0)
    check.is_instance(first_item.attack_mappings, list)
    for attack in first_item.attack_mappings:
        check.is_in("technique", attack)
        check.is_in("tactics", attack)


def test_mordor_search(mdr_driver: MordorDriver):
    """Test search functionality."""
    results = search_mdr_data(mdr_driver.mordor_data, "AWS")
    check.greater_equal(len(results), 1)

    subset = search_mdr_data(mdr_driver.mordor_data, "Empire")
    check.greater_equal(len(subset), 39)

    emp_power = search_mdr_data(mdr_driver.mordor_data, "Empire+Power")
    check.greater_equal(len(emp_power), 18)
    check.greater_equal(
        len(search_mdr_data(mdr_driver.mordor_data, "Empire, Windows")), 50
    )

    subset_search = search_mdr_data(mdr_driver.mordor_data, "Power", subset=subset)
    check.equal(len(emp_power), len(subset_search))

    result_set = mdr_driver.search_queries("AWS")
    check.greater_equal(len(list(result_set)), 1)
    check.is_true(any(hit for hit in result_set if "small.aws.collection" in hit))


@pytest.mark.skipif(
    not os.environ.get("MSTICPY_TEST_NOSKIP"), reason="Skipped for local tests."
)
def test_mordor_download(mdr_driver: MordorDriver):
    """Test file download."""
    entry_id = "SDWIN-190319021158"
    entry = mdr_driver.mordor_data[entry_id]
    files = entry.get_file_paths()

    file_path = files[0]["file_path"]
    d_frame = download_mdr_file(file_path, save_folder=_SAVE_FOLDER2)

    check.is_instance(d_frame, pd.DataFrame)
    check.greater_equal(len(d_frame), 10)
    _cleanup_temp_files(_SAVE_FOLDER2)


@pytest.mark.skipif(
    not os.environ.get("MSTICPY_TEST_NOSKIP"), reason="Skipped for local tests."
)
def test_mordor_query_provider(qry_provider):
    """Test query functions from query provider."""
    queries = qry_provider.list_queries()
    check.greater_equal(len(queries), 50)

    check.is_true(hasattr(qry_provider, "small"))
    check.is_true(hasattr(qry_provider, queries[0]))

    test_query = "small.windows.credential_access.host.empire_mimikatz_logonpasswords"
    q_func = getattr(qry_provider, test_query)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        q_func("?")
    check.is_in("Query:", output.getvalue())
    check.is_in("Data source:  Mordor", output.getvalue())
    check.is_in("Mordor ID:", output.getvalue())
    check.is_in("Mitre Techniques:", output.getvalue())

    f_path = q_func("print")
    check.is_in("https://raw.githubusercontent.com/OTRF/mordor", f_path)

    d_frame = q_func()
    check.is_instance(d_frame, pd.DataFrame)
    check.greater_equal(len(d_frame), 10)
