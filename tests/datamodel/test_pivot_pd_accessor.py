# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Module docstring."""
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest
import pytest_check as check

from msticpy.datamodel import pivot_pd_accessor

from ..unit_test_lib import TEST_DATA_PATH

__author__ = "Ian Hellen"

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def test_df():
    """Fixture_docstring."""
    csv_file = Path(TEST_DATA_PATH).joinpath("host_logons.csv")
    return pd.read_csv(csv_file, index_col=0)


def test_load_accessor(test_df):
    """Function_docstring."""
    check.is_not_none(getattr(test_df, "mp_pivot"))
    check.is_not_none(getattr(test_df.mp_pivot, "run"))
    check.is_not_none(getattr(test_df.mp_pivot, "display"))
    check.is_not_none(getattr(test_df.mp_pivot, "tee"))
    check.is_not_none(getattr(test_df.mp_pivot, "tee_exec"))
    check.is_not_none(getattr(test_df.mp_pivot, "filter"))
    check.is_not_none(getattr(test_df.mp_pivot, "filter_cols"))
    check.is_not_none(getattr(test_df.mp_pivot, "sort"))


def _nop_df(data, **kwargs):
    """Test function for test_pd_run."""
    for key, val in kwargs.items():
        data[key] = val
    return data


def test_pd_run(test_df, capsys):
    """Test mp_pivot.run accessor."""
    res_df = test_df.mp_pivot.run(
        _nop_df, test_col="test_val", verbose=True, debug=True
    )
    check.equal(len(res_df), len(test_df))
    cap_out = capsys.readouterr().out
    check.is_in("rows returned from", cap_out)
    check.is_in("Columns in result", cap_out)
    check.is_in("Parameters:", cap_out)
    check.is_in("test_col", res_df.columns)


def test_pd_display(test_df, capsys):
    """Test mp_pivot.display accessor."""
    test_df.mp_pivot.display(
        _nop_df,
        cols=["Computer", "SubjectUserName", "TargetUserName"],
        query="TargetUserName != 'MSTICAdmin'",
    )
    cap_out = capsys.readouterr().out
    check.is_in("Computer   SubjectUserName TargetUserName", cap_out)
    check.is_not_in("MSTICAdmin", cap_out)
    check.equal(Counter(cap_out.split())["MSTICAlertsWin1"], 12)
    check.equal(len(cap_out.split("\n")), len(test_df) + 1)
    test_df.mp_pivot.display(
        _nop_df,
        cols=["Computer", "SubjectUserName", "TargetUserName"],
        query="TargetUserName != 'MSTICAdmin'",
        head=5,
    )
    cap_out = capsys.readouterr().out
    check.is_in("Computer   SubjectUserName TargetUserName", cap_out)
    check.equal(Counter(cap_out.split())["MSTICAlertsWin1"], 5)


class _IPython:
    """Test class for mocking IPython."""

    def __init__(self):
        self.ns_table = {"user_local": {"test_var": None}}


# For some reason this test works locally but not in pytest
# from the commandline - assuming it's something to do with the
# way the mock class is handled.
@pytest.mark.skip()
def test_tee(test_df, monkeypatch):
    """Test mp_pivot.tee_exec accessor."""
    ipython = _IPython()

    def _m_get_ipython():
        """Path get_ipython."""
        return ipython

    monkeypatch.setattr(pivot_pd_accessor, "get_ipython", _m_get_ipython)

    # with pytest.warns(UserWarning):
    # Try with variable that already exists
    test_df.mp_pivot.tee(var_name="test_var")
    check.is_none(ipython.ns_table["user_local"]["test_var"])

    test_df.mp_pivot.tee(var_name="test_var", clobber=True)
    print(ipython.ns_table["user_local"]["test_var"])
    print(type(ipython.ns_table["user_local"]["test_var"]))

    check.is_instance(ipython.ns_table["user_local"]["test_var"], pd.DataFrame)
    check.is_true(test_df.compare(ipython.ns_table["user_local"]["test_var"]).empty)


def test_tee_exec(test_df):
    """Test mp_pivot.tee_exec accessor."""
    res_df = test_df.mp_pivot.tee_exec("head", 5)
    check.equal(res_df.shape, test_df.shape)
    check.is_true(test_df.compare(res_df).empty)


def test_filter_cols(test_df):
    """Test mp_pivot.filter_cols accessor."""
    res_df = test_df.mp_pivot.filter_cols(cols="Computer")
    check.equal(res_df.shape, (14, 1))

    res_df = test_df.mp_pivot.filter_cols(cols="Target*")
    check.equal(res_df.shape, (14, 4))

    res_df = test_df.mp_pivot.filter_cols(cols=["Computer", "Target*"])
    check.equal(res_df.shape, (14, 5))

    with pytest.raises(ValueError):
        res_df = test_df.mp_pivot.filter_cols(cols=["Missing", "Missing2"])

    res_df = test_df.mp_pivot.filter_cols(cols=["computer", "Target*"], match_case=True)
    check.equal(res_df.shape, (14, 4))

    res_df = test_df.mp_pivot.filter_cols(
        cols=["LogonProcessName", "Target*"], sort_cols=True
    )
    check.equal(res_df.shape, (14, 5))
    check.equal(res_df.columns[0], "LogonProcessName")


def test_filter(test_df):
    """Test mp_pivot.filter accessor."""
    res_df = test_df.mp_pivot.filter(expr="MSTICAdmin")
    check.equal(len(res_df), 2)

    res_df = test_df.mp_pivot.filter(expr="2361334927")
    check.equal(len(res_df), 3)

    res_df = test_df.mp_pivot.filter(expr="msticadmin", match_case=True)
    check.equal(len(res_df), 0)

    res_df = test_df.mp_pivot.filter(expr=4624, match_case=True)
    check.equal(len(res_df), 14)
    res_df = test_df.mp_pivot.filter(expr=4625, match_case=True)
    check.equal(len(res_df), 0)
    res_df = test_df.mp_pivot.filter(expr="4624", match_case=True, numeric_col=True)
    check.equal(len(res_df), 14)

    with pytest.raises(TypeError):
        res_df = test_df.mp_pivot.filter(expr=["Missing", "Missing2"])


def test_sort(test_df):
    """Test mp_pivot.sort accessor."""
    res_df = test_df.mp_pivot.sort(cols="TargetUserName")
    check.equal(res_df.iloc[0].TargetUserName, "MSTICAdmin")

    res_df = test_df.mp_pivot.sort(cols=["TargetUserName", "Computer"])
    check.equal(res_df.iloc[0].TargetUserName, "MSTICAdmin")

    res_df = test_df.mp_pivot.sort(cols=["TargetUserName", "Computer"], ascending=False)
    check.equal(res_df.iloc[0].TargetUserName, "adm1nistrator")

    res_df = test_df.mp_pivot.sort(cols=["TargetUserName:asc", "Computer"])
    check.equal(res_df.iloc[0].TargetUserName, "MSTICAdmin")

    res_df = test_df.mp_pivot.sort(cols=["TargetUserName:desc", "Computer"])
    check.equal(res_df.iloc[0].TargetUserName, "adm1nistrator")

    res_df = test_df.mp_pivot.sort(cols={"TargetUserName": True, "Computer": False})
    check.equal(res_df.iloc[0].TargetUserName, "MSTICAdmin")

    res_df = test_df.mp_pivot.sort(cols={"TargetUserName": False, "Computer": False})
    check.equal(res_df.iloc[0].TargetUserName, "adm1nistrator")

    res_df = test_df.mp_pivot.sort(
        cols={"TargetUserName": True, "Computer": False}, ascending=False
    )
    check.equal(res_df.iloc[0].TargetUserName, "adm1nistrator")


def test_list_to_rows():
    """Test list_to_rows."""
    test_df = pd.DataFrame(
        {
            "col1": [["1item1", "1item2"], ["1item3", "1item4"], ["1item5"]],
            "col2": [["2item1", "2item2"], ["2item3", "2item4"], ["2item5"]],
            "col3": [1, 2, 3],
        }
    )
    check.equal(len(test_df), 3)
    # on a single column we should get 2 additional rows
    exp_df = test_df.mp_pivot.list_to_rows(cols="col1")
    check.equal(len(exp_df), 5)
    check.equal(exp_df.col1.iloc[0], "1item1")
    # with both col1 and col2, the first two rows will be expanded twice so + 4
    exp_df = test_df.mp_pivot.list_to_rows(cols=["col1", "col2"])
    check.equal(len(exp_df), 9)
    check.equal(exp_df.col1.iloc[0], "1item1")
    check.equal(exp_df.col2.iloc[0], "2item1")


def test_parse_json():
    """Test list_to_rows."""
    test_df = pd.DataFrame(
        {
            "col1": [
                '["1item1", "1item2"]',
                '{"key": ["1item3", "1item4"]}',
                '{"key2": "1item5"}',
            ],
            "col2": [23, "Not JSON", None],
            "col3": [1, 2, 3],
        }
    )
    check.equal(len(test_df), 3)
    # all rows should be converted
    exp_df = test_df.mp_pivot.parse_json(cols="col1")
    check.equal(len(exp_df), 3)
    check.is_instance(exp_df.col1.iloc[0], list)
    check.is_instance(exp_df.col1.iloc[1], dict)
    # rows in col1 are converted, col2 values are not converted
    exp_df = test_df.mp_pivot.parse_json(cols=["col1", "col2"])
    check.equal(len(exp_df), 3)
    check.is_instance(exp_df.col1.iloc[0], list)
    check.is_instance(exp_df.col1.iloc[1], dict)
    check.is_instance(exp_df.col1.iloc[2], dict)
    check.is_instance(exp_df.col2.iloc[0], int)
    check.is_instance(exp_df.col2.iloc[1], str)
    check.equal(exp_df.col2.iloc[2], None)
