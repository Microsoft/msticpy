# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Module docstring."""
import pytest
import pytest_check as check

import pandas as pd
from msticpy.datamodel import entities
from msticpy.datamodel.entities import Host, OSFamily, Url, IpAddress
from msticpy.datamodel.pivot import Pivot

__author__ = "Ian Hellen"

# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def fixture_name():
    """Fixture_docstring."""


def test_entity_merge():
    """Entity comparison and merging."""
    host1 = Host(HostName="host1", DnsDomain="contoso.com", OSFamily=OSFamily.Windows)
    host2 = Host(HostName="host1", DnsDomain="contoso.com", IsDomainJoined=True)
    host3 = Host(HostName="host3", DnsDomain="contoso.com")

    check.not_equal(host1, host2)
    check.not_equal(host1, host3)

    check.is_true(host1.is_equivalent(host2))
    check.is_false(host1.is_equivalent(host3))
    check.is_false(host2.is_equivalent(host3))

    check.is_true(host1.can_merge(host2))
    check.is_false(host1.can_merge(host3))

    host4 = host1.merge(host2)
    check.equal(host4.HostName, "host1")
    check.equal(host4.OSFamily, OSFamily.Windows)
    check.equal(host4.DnsDomain, "contoso.com")
    check.is_true(host4.IsDomainJoined)


def test_url():
    """Test URL get_componennts."""
    URL = "https://www.contoso.com/path#frag?query=xxx"
    url = Url(Url=URL)
    check.equal(url.Url, URL)
    check.equal(url.host, "www.contoso.com")
    check.equal(url.scheme, "https")
    check.equal(url.path, "/path")
    check.equal(url.fragment, "frag?query=xxx")

    url.Url = "https://www.contoso2.com/path2#frag2?query=xxx"
    check.equal(url.host, "www.contoso2.com")
    check.equal(url.scheme, "https")
    check.equal(url.path, "/path2")
    check.equal(url.fragment, "frag2?query=xxx")


def test_pivot_shortcuts():
    """Test pivot function shortcut creation and deletion."""
    Pivot()

    check.is_true(hasattr(IpAddress, "util"))
    util_ctnr = getattr(IpAddress, "util")
    func = getattr(util_ctnr, "ip_type")

    IpAddress.make_pivot_shortcut("util.ip_type", "test_iptype")
    check.is_true(hasattr(IpAddress, "test_iptype"))
    check.equal(func, IpAddress.test_iptype)

    ip_addr = IpAddress(Address="192.168.1.2")

    ip_df = ip_addr.test_iptype()
    check.is_instance(ip_df, pd.DataFrame)

    with pytest.raises(AttributeError):
        IpAddress.make_pivot_shortcut("util.not_defined", "test_iptype")

    with pytest.raises(TypeError):
        IpAddress.make_pivot_shortcut("properties", "test_iptype")

    with pytest.raises(AttributeError):
        IpAddress.make_pivot_shortcut("util.ip_type", "test_iptype")

    IpAddress.make_pivot_shortcut("util.ip_type", "test_iptype", overwrite=True)
    check.is_true(hasattr(IpAddress, "test_iptype"))
    check.equal(func, IpAddress.test_iptype)

    IpAddress.del_pivot_shortcut("test_iptype")
    check.is_false(hasattr(IpAddress, "test_iptype"))
    with pytest.raises(AttributeError):
        IpAddress.del_pivot_shortcut("test_iptype")

    with pytest.raises(TypeError):
        IpAddress.del_pivot_shortcut("properties")


def test_entity_instantiation():
    """Test that we can instantiate all entities."""
    for attrib in dir(entities):
        attr_cls = getattr(entities, attrib)
        if (
            isinstance(attr_cls, type)
            and issubclass(attr_cls, entities.Entity)
            and attr_cls != entities.Entity
        ):
            ent_obj = attr_cls()
            check.greater(len(ent_obj.properties), 0)
            # Check that we can access properties without incident
            for attr in (attr for attr in dir(ent_obj) if not attr.startswith("_")):
                getattr(ent_obj, attr)
