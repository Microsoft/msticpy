# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pivot main library test."""
import warnings
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Optional

import pytest
import pytest_check as check
from msticpy.common.timespan import TimeSpan
from msticpy.data import QueryProvider
from msticpy.data.query_container import QueryContainer
from msticpy.datamodel import entities
from msticpy.datamodel.pivot import Pivot
from msticpy.sectools import GeoLiteLookup, TILookup

__author__ = "Ian Hellen"

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")
# pylint: disable=redefined-outer-name

_KQL_IMP_OK = False
try:
    # pylint: disable=unused-import
    from msticpy.data.drivers import kql_driver

    del kql_driver
    _KQL_IMP_OK = True
except ImportError:
    pass

_SPLUNK_IMP_OK = False
try:
    from msticpy.data.drivers import splunk_driver

    del splunk_driver
    _SPLUNK_IMP_OK = True
except ImportError:
    pass

_IPSTACK_IMP_OK = False
ip_stack_cls: Optional[type]
try:
    from msticpy.sectools import IPStackLookup as ip_stack_cls

    _IPSTACK_IMP_OK = True
except ImportError:
    ip_stack_cls = None

pytestmark = pytest.mark.skipif(not _KQL_IMP_OK, reason="Partial msticpy install")


@pytest.fixture(scope="session")
def data_providers():
    """Return dict of providers."""
    prov_dict = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        if _KQL_IMP_OK:
            prov_dict["az_sent_prov"] = QueryProvider("AzureSentinel")
        prov_dict["mdatp_prov"] = QueryProvider("MDE")
        if _SPLUNK_IMP_OK:
            prov_dict["splunk_prov"] = QueryProvider("Splunk")
        prov_dict["ti_lookup"] = TILookup()
        prov_dict["geolite"] = GeoLiteLookup()

    if _IPSTACK_IMP_OK:
        prov_dict["ip_stack"] = ip_stack_cls()
    return prov_dict


def _reset_entities():
    """Clear any query containers in entities."""
    Pivot.remove_pivot_funcs(entity="all")


PivotTestCase = namedtuple("PivotTestCase", "entity, container, funcs")
_ENTITY_FUNCS = [
    pytest.param(PivotTestCase("Host", "AzureSentinel", 25), id="Host-AzureSentinel"),
    pytest.param(PivotTestCase("Host", "MDE", 2), id="Host-MDE"),
    pytest.param(PivotTestCase("Host", "util", 3), id="Host-util"),
    pytest.param(
        PivotTestCase("IpAddress", "AzureSentinel", 15), id="IpAddress-AzureSentinel"
    ),
    pytest.param(PivotTestCase("IpAddress", "MDE", 2), id="IpAddress-MDE"),
    pytest.param(PivotTestCase("IpAddress", "ti", 8), id="IpAddress-ti"),
    pytest.param(PivotTestCase("IpAddress", "util", 4), id="IpAddress-util"),
    pytest.param(
        PivotTestCase("Account", "AzureSentinel", 16), id="Account-AzureSentinel"
    ),
    pytest.param(PivotTestCase("Account", "MDE", 4), id="Account-MDE"),
    pytest.param(PivotTestCase("Url", "AzureSentinel", 2), id="Url-AzureSentinel"),
    pytest.param(PivotTestCase("Url", "MDE", 2), id="Url-MDE"),
    pytest.param(PivotTestCase("Url", "ti", 4), id="Url-ti"),
    pytest.param(PivotTestCase("Url", "util", 5), id="Url-util"),
]


@pytest.fixture(scope="session")
def _create_pivot_list(data_providers):
    _reset_entities()
    providers = data_providers.values()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return Pivot(providers=providers)


@pytest.mark.parametrize("test_case", _ENTITY_FUNCS)
def test_pivot_providers(_create_pivot_list, test_case):
    """
    Test pivot intialized from provider list.

    Notes
    -----
    Test that the expected number of functions have been added to entities.

    """
    entity = getattr(entities, test_case.entity)
    query_contr = getattr(entity, test_case.container)
    check.is_not_none(query_contr)
    query_attrs = repr(query_contr).split("\n")
    check.greater_equal(len(query_attrs), test_case.funcs)


# # Generate test cases for pivot functions
# def test_gen_tests(_create_pivot):
#     """Function_docstring."""
#     for entity_name in ("Host", "IpAddress", "Account", "Url"):
#         entity = getattr(entities, entity_name)
#         for container in ("AzureSentinel", "Splunk", "MDE", "ti", "util"):
#             query_contr = getattr(entity, container, None)
#             if not query_contr:
#                 continue
#             query_attrs = repr(query_contr).split("\n")
#             piv_case = f'PivotTestCase("{entity_name}", "{container}", {len(query_attrs)})'
#             print(f'    pytest.param({piv_case}, id=f"{entity_name}-{container}"),')
#     assert False


@pytest.fixture(scope="session")
def _create_pivot_ns(data_providers):
    _reset_entities()
    locals().update(data_providers)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return Pivot(namespace=locals())


@pytest.mark.parametrize("test_case", _ENTITY_FUNCS)
def test_pivot_providers_namespace(_create_pivot_ns, test_case):
    """
    Test pivot initialized from globals/namespace.

    Notes
    -----
    Test that the expected number of functions have been added to entities.

    """
    entity = getattr(entities, test_case.entity)
    query_contr = getattr(entity, test_case.container)
    check.is_not_none(query_contr)
    query_attrs = repr(query_contr).split("\n")
    check.greater_equal(len(query_attrs), test_case.funcs)


def _fake_provider_connected(provider):
    # Lie to the query provider so that it will allow the call
    # pylint: disable=protected-access
    provider._query_provider._loaded = True
    provider._query_provider._connected = True
    # pylint: enable=protected-access


class _TimeObj:
    def __init__(self, start, end):
        self.start = start
        self.end = end


def test_pivot_time(data_providers):
    """Function_docstring."""
    providers = data_providers.values()
    end = datetime.utcnow()
    start = end - timedelta(1)
    timespan = TimeSpan(start=start, end=end)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        pivot = Pivot(providers=providers, timespan=timespan)
    check.equal(pivot.start, start)
    check.equal(pivot.end, end)

    end = end - timedelta(1)
    start = start - timedelta(1)
    # Test different ways of setting the time
    timespan = TimeSpan(start=start, end=end)
    pivot.timespan = timespan
    check.equal(pivot.start, start)
    check.equal(pivot.end, end)

    pivot.timespan = _TimeObj(start=timespan.start, end=timespan.end)
    check.equal(pivot.start, start)
    check.equal(pivot.end, end)

    pivot.set_timespan(timespan)
    check.equal(pivot.start, start)
    check.equal(pivot.end, end)

    pivot.set_timespan(start=timespan.start, end=timespan.end)
    check.equal(pivot.start, start)
    check.equal(pivot.end, end)

    # Make sure the values provided to queries match.
    _fake_provider_connected(data_providers["az_sent_prov"])

    query = entities.Host.AzureSentinel.wevt_processes(host_name="test", print=True)
    check.is_in(start.isoformat(), query)
    check.is_in(end.isoformat(), query)


EntityQuery = namedtuple("EntityQuery", "entity, args, provider, pivot_func, expected")
_ENTITY_QUERIES = [
    pytest.param(
        EntityQuery(
            "Host",
            dict(HostName="testhost", DnsDomain="contoso.com"),
            "AzureSentinel",
            "wevt_processes",
            'Computer has "testhost.contoso.com"',
        ),
        id="Host",
    ),
    pytest.param(
        EntityQuery(
            "Account",
            dict(Name="testacct"),
            "AzureSentinel",
            "wevt_logons",
            'where Account has "testacct"',
        ),
        id="Account",
    ),
    pytest.param(
        EntityQuery(
            "IpAddress",
            dict(Address="192.168.1.2"),
            "AzureSentinel",
            "hb_heartbeat",
            '| where ComputerIP == "192.168.1.2"',
        ),
        id="IpAddress",
    ),
]


@pytest.mark.parametrize("test_case", _ENTITY_QUERIES)
def test_entity_attr_funcs(_create_pivot_ns, test_case):
    """Test calling function with entity attributes."""
    # Test entity
    ent_cls = getattr(entities, test_case.entity)
    entity = ent_cls(test_case.args)
    _fake_provider_connected(_create_pivot_ns.get_provider("AzureSentinel"))
    func = getattr(getattr(entity, test_case.provider), test_case.pivot_func)
    query = func(entity, print_query=True)
    check.is_in(test_case.expected, query)


def test_misc_functions(_create_pivot_ns):
    """Test some additional methods of pivot.py."""
    check.greater(len(_create_pivot_ns.providers), 2)
    t_span = TimeSpan(end=datetime.utcnow(), period="1D")
    _create_pivot_ns.edit_query_time(timespan=t_span)
    check.equal(_create_pivot_ns.start, t_span.start)
    check.equal(_create_pivot_ns.end, t_span.end)
    check.equal(_create_pivot_ns.timespan, t_span)


_ENTITY_PIVOTS = [
    pytest.param(entities.Host, 25, id="Host"),
    pytest.param(entities.IpAddress, 25, id="IpAddress"),
    pytest.param(entities.Account, 20, id="Account"),
]


@pytest.mark.parametrize("entity, expected_funcs", _ENTITY_PIVOTS)
def test_entity_list_piv_functions(_create_pivot_list, entity, expected_funcs):
    """Test the pivot_funcs property."""
    check.greater(len(entity.get_pivot_list()), expected_funcs)


def _get_piv_attrs(entity):
    return [
        attr
        for attr in dir(entity)
        if hasattr(getattr(entity, attr), "pivot_properties")
        or type(getattr(entity, attr)).__name__ == "QueryContainer"
    ]


def test_remove_pivots(_create_pivot_ns):
    """Test remove pivots function."""
    piv_attrs = _get_piv_attrs(entities.Host)
    check.is_true(piv_attrs)

    with pytest.raises(ValueError):
        Pivot.remove_pivot_funcs(entity="TestEntity")

    piv_attrs = _get_piv_attrs(entities.Host)
    check.is_true(piv_attrs)

    Pivot.remove_pivot_funcs(entity="Host")
    piv_attrs = _get_piv_attrs(entities.Host)
    check.is_false(piv_attrs)

    piv_attrs = _get_piv_attrs(entities.IpAddress)
    check.is_true(piv_attrs)
    Pivot.remove_pivot_funcs(entity="all")
    piv_attrs = _get_piv_attrs(entities.IpAddress)
    check.is_false(piv_attrs)
