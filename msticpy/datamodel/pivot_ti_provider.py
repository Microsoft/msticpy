# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pivot TI Provider helper functions."""
from collections import defaultdict
from typing import Callable, Dict, Optional, Set, Tuple, Type

import pandas as pd

from .._version import VERSION
from ..data.query_container import QueryContainer
from ..sectools import TILookup
from . import entities
from .pivot_register import PivotRegistration, create_pivot_func

__version__ = VERSION
__author__ = "Ian Hellen"

IOC_TYPES = {"ipv4", "ipv6", "dns", "file_hash", "url"}

TI_ENTITY_ATTRIBS: Dict[str, Tuple[Type, str]] = {
    "ipv4": (entities.IpAddress, "Address"),
    "ipv6": (entities.IpAddress, "Address"),
    "ip": (entities.IpAddress, "Address"),
    "dns": (entities.Dns, "DomainName"),
    "file_hash": (entities.File, "file_hash"),
    "file_path": (entities.File, "file_hash"),
    "url": (entities.Url, "Url"),
}


def add_ioc_queries_to_entities(ti_lookup: TILookup, container: str = "ti", **kwargs):
    """
    Add TI functions to entities.

    Parameters
    ----------
    ti_lookup : TILookup
        TILookup instance.
    container : str
        The name of the container to add query functions to

    """
    ioc_queries = create_ti_pivot_funcs(ti_lookup)
    for ioc, ioc_funcs in ioc_queries.items():
        if "debug" in kwargs:
            print(ioc, ioc_funcs)
        entity, _ = TI_ENTITY_ATTRIBS[ioc]
        if entity:
            for f_name, func in ioc_funcs.items():
                if "debug" in kwargs:
                    print(ioc, f_name, func)
                query_container = getattr(entity, container, None)
                if not query_container:
                    query_container = QueryContainer()
                    setattr(entity, container, query_container)
                setattr(query_container, f_name, func)

                # Create shortcuts for non-provider-specific funcs
                if f_name.endswith(ioc):
                    short_func_name = f"ti{f_name}"
                    setattr(entity, short_func_name, func)


def create_ti_pivot_funcs(ti_lookup: TILookup):
    """Create the TI Pivot functions."""
    ioc_type_supp = _get_supported_ioc_types(ti_lookup)
    ioc_queries: Dict[str, Dict[str, Callable[..., pd.DataFrame]]] = defaultdict(dict)

    # Add functions for ioc types that will call all providers
    # Non-IP types
    ioc_queries.update(_get_non_ip_functions(ioc_type_supp, ti_lookup))
    # Special case for ipv4 and ipv6 - we want to merge these into "ip" if these are equivalent
    ioc_queries.update(_get_ip_functions(ioc_type_supp, ti_lookup))

    # Add functions for provider-specific lookup function names
    # These have a "_provider_name" suffix
    for prov, ioc_set in ioc_type_supp.items():
        for ioc in ioc_set:
            ioc_name = _merged_ip_ioc_type(ioc, ti_lookup.loaded_providers.get(prov))
            if not ioc_name:
                continue
            _, func_name, func = _create_lookup_func(ti_lookup, ioc, ioc, [prov])
            func_name = f"{func_name}_{prov}"
            ioc_queries[ioc][func_name] = func
    return ioc_queries


def _get_supported_ioc_types(ti_lookup: TILookup) -> Dict[str, Set[str]]:
    return {
        ti_prov_name: set(ti_prov.supported_types) & IOC_TYPES
        for ti_prov_name, ti_prov in ti_lookup.loaded_providers.items()
    }


def _prov_ipv4v6_equal(ti_provider) -> bool:
    if not ti_provider:
        return False
    ti_queries = ti_provider.ioc_query_defs
    return ti_queries.get("ipv4") is not None and (
        ti_queries.get("ipv6") is None
        or ti_queries.get("ipv4") == ti_queries.get("ipv6")
    )


def _merged_ip_ioc_type(ioc, ti_provider) -> Optional[str]:
    if ioc == "ipv4" and _prov_ipv4v6_equal(ti_provider):
        return "ip"
    if ioc == "ipv6" and _prov_ipv4v6_equal(ti_provider):
        return None
    return ioc


def _create_lookup_func(
    ti_lookup: TILookup, ioc, ioc_name, providers
) -> Tuple[str, str, Callable[..., pd.DataFrame]]:

    suffix = f"_{ioc_name}"
    short_func_name = f"lookup{suffix}"
    func_name = f"{short_func_name}_{ioc_name}"
    params_dict = {"providers": providers, "ioc_type": ioc}

    entity_cls, entity_attr = TI_ENTITY_ATTRIBS[ioc]

    pivot_reg = PivotRegistration(
        src_func_name=ti_lookup.lookup_iocs.__name__,
        input_type="dataframe",
        entity_map={entity_cls.__name__: entity_attr},
        func_df_param_name="data",
        func_df_col_param_name="obs_col",
        func_out_column_name="Ioc",
        func_static_params=params_dict,
    )
    return (
        func_name,
        short_func_name,
        create_pivot_func(target_func=ti_lookup.lookup_iocs, pivot_reg=pivot_reg),
    )


def _get_non_ip_functions(ioc_type_supp, ti_lookup):
    """Get functions for non-IP IoC types."""
    ioc_queries = defaultdict(dict)
    for ioc in IOC_TYPES - {"ipv4", "ipv6"}:
        supporting_provs = [
            prov for prov, supp_types in ioc_type_supp.items() if ioc in supp_types
        ]
        _, func_name, func = _create_lookup_func(ti_lookup, ioc, ioc, supporting_provs)
        ioc_queries[ioc][func_name] = func
    return ioc_queries


def _get_ip_functions(ioc_type_supp, ti_lookup):
    """Get functions for IP IoC Types."""
    # Special case for ipv4 and ipv6
    # we want to merge these into "ip" if these are equivalent
    ioc_queries = defaultdict(dict)
    # Special case for ipv4 and ipv6 - we want to merge these into "ip" if these are equivalent
    ip_types = {"ipv4", "ipv6"}
    ip_all_provs = [
        prov for prov, supp_types in ioc_type_supp.items() if ip_types & supp_types
    ]

    # Register providers where IP v4 and v6 are equivalent, or only support ipv4, as "ip"
    ip_gen_provs = [
        prov
        for prov in ip_all_provs
        if _prov_ipv4v6_equal(ti_lookup.loaded_providers.get(prov))
        or "ipv6" not in ioc_type_supp[prov]
    ]

    _, func_name, func = _create_lookup_func(ti_lookup, "ipv4", "ip", ip_gen_provs)
    ioc_queries["ip"][func_name] = func

    # Also register IP v4 and v6 specific queries
    ip_v4_provs = [
        prov
        for prov in ip_all_provs
        if "ipv4" in ioc_type_supp[prov]
        if prov not in ip_gen_provs
    ]
    _, func_name, func = _create_lookup_func(ti_lookup, "ipv4", "ipv4", ip_v4_provs)
    ioc_queries["ipv4"][func_name] = func

    ip_v6_provs = [
        prov
        for prov in ip_all_provs
        if "ipv6" in ioc_type_supp[prov]
        if prov not in ip_gen_provs
    ]
    _, func_name, func = _create_lookup_func(ti_lookup, "ipv6", "ipv6", ip_v6_provs)
    ioc_queries["ipv6"][func_name] = func

    return ioc_queries
