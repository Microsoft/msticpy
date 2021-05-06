# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Test Pivot registered functions."""
import warnings
from collections import namedtuple

import pandas as pd
import pytest
import pytest_check as check
from msticpy.data.query_container import QueryContainer
from msticpy.datamodel import entities
from msticpy.datamodel.pivot import Pivot
from msticpy.sectools import GeoLiteLookup, TILookup

__author__ = "Ian Hellen"

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="session")
def data_providers():
    """Return dict of providers."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return {
            "ti_lookup": TILookup(),
            "geolite": GeoLiteLookup(),
            #  "ip_stack": IPStackLookup(),
        }


def _reset_entities():
    """Clear any query containers in entities."""
    for entity_name in ("Host", "IpAddress", "Account", "Url"):
        entity = getattr(entities, entity_name)
        for attr in dir(entity):
            if isinstance(getattr(entity, attr), QueryContainer):
                delattr(entity, attr)


@pytest.fixture(scope="session")
def _create_pivot(data_providers):
    _reset_entities()
    providers = data_providers.values()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return Pivot(providers=providers)


EntityQuery = namedtuple(
    "EntityQuery",
    "entity, args, attrib, provider, pivot_func, func_param, src_col, exp_col, exp_val",
)

_ENTITY_QUERIES = [
    pytest.param(
        EntityQuery(
            entity="IpAddress",
            args=dict(Address="104.211.30.1"),
            attrib="Address",
            provider="util",
            pivot_func="whois",
            func_param="ip_address",
            src_col="ip",
            exp_col="asn_description",
            exp_val="MICROSOFT-CORP-MSN-AS-BLOCK",
        ),
        id="IpAddress-who_is",
    ),
    pytest.param(
        EntityQuery(
            entity="IpAddress",
            args=dict(Address="104.211.30.1"),
            attrib="Address",
            provider="util",
            pivot_func="ip_type",
            func_param="ip_str",
            src_col="ip",
            exp_col="result",
            exp_val="Public",
        ),
        id="IpAddress-ip_type",
    ),
    pytest.param(
        EntityQuery(
            entity="Process",
            args=dict(
                CommandLine="VGhpcyBpcyBhIHRlc3Qgb2YgYmFzZTY0IGVuY29kZWQgc3RyaW5n"
            ),
            attrib="CommandLine",
            provider="util",
            pivot_func="b64decode",
            func_param="value",
            src_col="cmdline",
            exp_col="decoded_string",
            exp_val="This is a test of base64 encoded string",
        ),
        id="Process-b64decode",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="Url",
            provider="util",
            pivot_func="extract_iocs",
            func_param="value",
            src_col="url",
            exp_col="Observable",
            exp_val="www.contoso.com",
        ),
        id="Url-extract_iocs",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="host",
            provider="util",
            pivot_func="dns_validate_tld",
            func_param="value",
            src_col="host",
            exp_col="result",
            exp_val="True",
        ),
        id="Url-dns_validate_tld",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="host",
            provider="util",
            pivot_func="dns_is_resolvable",
            func_param="value",
            src_col="host",
            exp_col="result",
            exp_val="True",
        ),
        id="Url-dns_is_resolvable",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="host",
            provider="util",
            pivot_func="dns_in_abuse_list",
            func_param="value",
            src_col="host",
            exp_col="result",
            exp_val="False",
        ),
        id="Url-dns_in_abuse_list",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="host",
            provider="util",
            pivot_func="dns_components",
            func_param="value",
            src_col="host",
            exp_col="subdomain",
            exp_val="www",
        ),
        id="Url-dns_components",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="host",
            provider="util",
            pivot_func="url_components",
            func_param="value",
            src_col="host",
            exp_col="host",
            exp_val="www.contoso.com",
        ),
        id="Url-url_components",
    ),
    pytest.param(
        EntityQuery(
            entity="Url",
            args=dict(Url="https://www.contoso.com/path?p1=test"),
            attrib="Url",
            provider="util",
            pivot_func="dns_resolve",
            func_param="value",
            src_col="host",
            exp_col="qname",
            exp_val="www.contoso.com",
        ),
        id="Url-dns_resolve",
    ),
    pytest.param(
        EntityQuery(
            entity="IpAddress",
            args=dict(Address="104.211.30.1"),
            attrib="Address",
            provider="util",
            pivot_func="ip_rev_resolve",
            func_param="value",
            src_col="host",
            exp_col="qname",
            exp_val="104.211.30.1",
        ),
        id="IpAddress-ip_rev_resolve",
    ),
    pytest.param(
        EntityQuery(
            entity="IpAddress",
            args=dict(Address="104.211.30.1"),
            attrib="Address",
            provider="util",
            pivot_func="geoloc",
            func_param="value",
            src_col="ip",
            exp_col="CountryName",
            exp_val="United States",
        ),
        id="IpAddress-geoip_maxmind",
    ),
    # This test sometimes files because of non-responsiveness
    # from ipstack service
    # pytest.param(
    #     EntityQuery(
    #         entity="IpAddress",
    #         args=dict(Address="104.211.30.1"),
    #         attrib="Address",
    #         provider="util",
    #         pivot_func="geoloc_ips",
    #         func_param="value",
    #         src_col="ip",
    #         exp_col="CountryName",
    #         exp_val="United States",
    #     ),
    #     id="IpAddress-geoip_ipstack",
    # ),
]


@pytest.mark.parametrize("test_case", _ENTITY_QUERIES)
def test_entity_attr_funcs_entity(_create_pivot, test_case):
    """Test calling function with entity attributes."""
    # Test entity
    ent_cls = getattr(entities, test_case.entity)
    entity = ent_cls(**(test_case.args))
    func = getattr(getattr(entity, test_case.provider), test_case.pivot_func)
    # Test entity input
    result_df = func(entity)
    check.is_in(test_case.exp_val, result_df.iloc[0][test_case.exp_col])


@pytest.mark.parametrize("test_case", _ENTITY_QUERIES)
def test_entity_attr_funcs_value(_create_pivot, test_case):
    """Test calling function with value."""
    ent_cls = getattr(entities, test_case.entity)
    entity = ent_cls(**(test_case.args))
    func = getattr(getattr(entity, test_case.provider), test_case.pivot_func)
    # Test value input
    val = getattr(entity, test_case.attrib)
    params = {test_case.func_param: val}
    result_df = func(**params)
    check.is_in(test_case.exp_val, result_df.iloc[0][test_case.exp_col])


@pytest.mark.parametrize("test_case", _ENTITY_QUERIES)
def test_entity_attr_funcs_itbl(_create_pivot, test_case):
    """Test calling function with iterable input."""
    ent_cls = getattr(entities, test_case.entity)
    entity = ent_cls(**(test_case.args))
    func = getattr(getattr(entity, test_case.provider), test_case.pivot_func)
    # Test iterable input
    val = [getattr(entity, test_case.attrib)]
    params = {test_case.func_param: val}
    result_df = func(**params)
    check.is_in(test_case.exp_val, result_df.iloc[0][test_case.exp_col])


@pytest.mark.parametrize("test_case", _ENTITY_QUERIES)
def test_entity_attr_funcs_df(_create_pivot, test_case):
    """Test calling function with DF input attributes."""
    ent_cls = getattr(entities, test_case.entity)
    entity = ent_cls(**(test_case.args))
    func = getattr(getattr(entity, test_case.provider), test_case.pivot_func)
    # Test DF input
    val = getattr(entity, test_case.attrib)
    in_df = pd.DataFrame([val], columns=[test_case.src_col])
    result_df = func(data=in_df, src_column=test_case.src_col)
    check.is_in(test_case.exp_val, result_df.iloc[0][test_case.exp_col])
