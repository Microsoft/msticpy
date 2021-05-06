# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Test query_functions module."""
import warnings
from datetime import datetime, timedelta
from functools import partial

import pandas as pd
import pytest
import pytest_check as check
from msticpy.common.timespan import TimeSpan
from msticpy.data import QueryProvider
from msticpy.data.query_container import QueryContainer
from msticpy.datamodel import entities
from msticpy.datamodel.pivot_data_queries import (
    PivotQueryFunctions,
    add_queries_to_entities,
    _create_pivot_func,
)

_KQL_IMP_OK = False
try:
    # pylint: disable=unused-import
    from msticpy.data.drivers import kql_driver

    del kql_driver
    _KQL_IMP_OK = True
except ImportError:
    pass

__author__ = "Ian Hellen"


@pytest.fixture(scope="module")
def azure_sentinel():
    """Fixture to get loaded Azure Sentinel Provider."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return QueryProvider("AzureSentinel")


@pytest.mark.skipif(not _KQL_IMP_OK, reason="Partial msticpy install")
def test_create_query_functions(azure_sentinel):
    """Test basic creation of query functions class."""
    az_qry_funcs = PivotQueryFunctions(azure_sentinel)

    check.greater_equal(len(az_qry_funcs.param_usage), 30)
    check.greater_equal(len(az_qry_funcs.query_params), 70)


@pytest.mark.skipif(not _KQL_IMP_OK, reason="Partial msticpy install")
def test_query_functions_methods(azure_sentinel):
    """Test attributes of retrieved functions."""
    az_qry_funcs = PivotQueryFunctions(azure_sentinel)

    ip_addr_q_params = list(az_qry_funcs.get_queries_and_types_for_param("ip_address"))
    host_queries = list(az_qry_funcs.get_queries_for_param("host_name"))

    check.greater_equal(len(ip_addr_q_params), 4)
    check.greater_equal(len(host_queries), 20)

    func_name, func_family, func = [
        q_tup for q_tup in host_queries if q_tup[0] == "get_info_by_hostname"
    ][0]
    check.is_instance(func, partial)
    check.is_true(callable(func))

    q_params = az_qry_funcs.query_params.get(f"{func_family}.{func_name}")
    # expected results
    # all=['table', 'query_project', 'start', 'end', 'subscription_filter',
    #  'add_query_items', 'host_name', 'host_op'],
    # required=['host_name'],
    # full_required=['start', 'end', 'host_name']
    check.is_in("start", q_params.all)
    check.is_in("host_name", q_params.required)
    check.is_in("host_name", q_params.full_required)
    check.is_in("start", q_params.full_required)
    check.is_in("end", q_params.full_required)

    param_attrs = az_qry_funcs.get_param_attrs("ip_address")
    # Expected return
    # [ParamAttrs(type='str', query='get_info_by_ipaddress', family='Heartbeat',
    #  required=True),
    # ParamAttrs(type='str', query='list_logons_for_source_ip', family='LinuxSyslog',
    #  required=True),
    # ParamAttrs(type='str', query='get_host_for_ip', family='Network',
    #  required=True),
    # ParamAttrs(type='str', query='get_heartbeat_for_ip', family='Network',
    #  required=True)]
    check.is_in(param_attrs[0].type, ("str", "list", "datetime"))
    check.is_true(param_attrs[0].required)
    check.is_not_none(param_attrs[0].query)
    check.is_not_none(param_attrs[0].family)


# Support functions and classes
def _dummy_func(**kwargs):
    kwargs.pop("start", None)
    kwargs.pop("end", None)
    return pd.DataFrame(pd.Series(kwargs)).T


class _PType:
    def __init__(self, p_type):
        self.type = p_type

    def __repr__(self):
        return f"PType({self.type})"


def _get_timespan():
    end = datetime.utcnow()
    return TimeSpan(start=(end - timedelta(1)), end=end)


def _generate_test_data(**kwargs):
    """Generate test data for iterable funcs."""
    # Generate function settings
    func_params = {kw: _PType(arg[0]) for kw, arg in kwargs.items()}
    # Generate test params
    params = {}
    for kword, arg in kwargs.items():
        if arg[1] > 1:
            p_vals = [f"{kword}_val{num}" for num in range(arg[1])]
        else:
            p_vals = f"{kword}_val0"
        params[kword] = p_vals

    # Generate test DataFrame
    list_lens = [len(value) for value in params.values() if isinstance(value, list)]
    min_len = min(list_lens) if list_lens else 1
    series = []
    for row_num in range(min_len):
        row_dict = {
            param: value[row_num] if isinstance(value, list) else value
            for param, value in params.items()
        }

        series.append(pd.Series(row_dict))

    return func_params, params, pd.DataFrame(series)


_WRAP_TEST_CASES = [
    pytest.param(
        {"p1": ("str", 1), "p2": ("str", 1)}, {"shape": (1, 2)}, id="simple values"
    ),
    pytest.param(
        {"p1": ("str", 1), "p2": ("str", 1)},
        {"param": ("other_param", "something_else"), "shape": (1, 3)},
        id="simple values + static param",
    ),
    pytest.param(
        {"p1": ("str", 1), "p2": ("list", 3), "p3": ("list", 4)},
        {"shape": (3, 3)},
        id="two lists",
    ),
    pytest.param(
        {"p1": ("str", 1), "p2": ("list", 3), "p3": ("str", 4)},
        {"shape": (3, 3)},
        id="one list + func iterator param",
    ),
]


@pytest.mark.parametrize("test_input, expected", _WRAP_TEST_CASES)
def test_create_pivot_func(test_input, expected):
    """Test wrapper creation for data queries."""
    attrib_map = {"p1": "p1", "p2": "p2", "p3": "p3", "p4": "p4"}

    # generate test data
    f_params, params, test_df = _generate_test_data(**test_input)
    call_data_query = _create_pivot_func(
        _dummy_func, f_params, attrib_map, _get_timespan
    )
    add_params = (
        {expected["param"][0]: expected["param"][1]} if "param" in expected else {}
    )
    result_df = call_data_query(**params, **add_params)

    check.equal(result_df.shape, expected["shape"])
    if add_params:
        check.is_in(expected["param"][0], result_df)
        check.equal(result_df.iloc[0][expected["param"][0]], expected["param"][1])
        result_df = result_df.drop(columns=[expected["param"][0]])
    check.is_true(test_df.compare(result_df).empty)


_WRAP_TEST_CASES_DF = [
    pytest.param(
        {"p1": ("str", 1), "p2": ("list", 3), "p3": ("list", 4)},
        {"shape": (3, 3)},
        id="dataframe input",
    ),
    pytest.param(
        {"p1": ("str", 1), "p2": ("list", 3), "p3": ("list", 4)},
        {"param": ("p4", "p4_val"), "shape": (3, 4)},
        id="dataframe input + static param",
    ),
]


@pytest.mark.parametrize("test_input, expected", _WRAP_TEST_CASES_DF)
def test_create_pivot_func(test_input, expected):
    """Test wrapper creation for data queries."""
    attrib_map = {"p1": "p1", "p2": "p2", "p3": "p3", "p4": "p4"}

    # simple test with scalar params
    f_params, params, test_df = _generate_test_data(**test_input)
    call_data_query = _create_pivot_func(
        _dummy_func, f_params, attrib_map, _get_timespan
    )
    add_params = (
        {expected["param"][0]: expected["param"][1]} if "param" in expected else {}
    )
    # We're only expecting column names as values for kwargs
    params = {p_name: p_name for p_name in params}
    params.update({"data": test_df})
    result_df = call_data_query(**params, **add_params)

    check.equal(result_df.shape, expected["shape"])
    if add_params:
        check.is_in(expected["param"][0], result_df)
        check.equal(result_df.iloc[0][expected["param"][0]], expected["param"][1])
        result_df = result_df.drop(columns=[expected["param"][0]])
    check.is_true(test_df.compare(result_df).empty)


_ENT_QUERY_FUNC = [
    (entities.Host, 25),
    (entities.Account, 16),
    (entities.IpAddress, 12),
    (entities.Process, 7),
    (entities.Url, 2),
    (entities.Dns, 2),
    (entities.AzureResource, 2),
]


@pytest.mark.skipif(not _KQL_IMP_OK, reason="Partial msticpy install")
@pytest.mark.parametrize("entity, expected", _ENT_QUERY_FUNC)
def test_add_queries_to_entities(entity, expected, azure_sentinel):
    """Test query functions successfully added to entities."""
    az_qry_funcs = PivotQueryFunctions(azure_sentinel)
    add_queries_to_entities(az_qry_funcs, "data", _get_timespan)

    check.is_true(hasattr(entity, "data"))
    f_container = getattr(entity, "data")
    check.is_instance(f_container, QueryContainer)
    funcs = [func for func in dir(f_container) if not func.startswith("_")]
    check.greater_equal(len(funcs), expected)

    for func_name in funcs:
        func = getattr(f_container, func_name)
        check.equal(func.__qualname__, "_create_pivot_func.<locals>.wrapped_query_func")
        check.is_in("Parameters", func.__doc__)
