# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""
User configuration functions.

Loads providers based on user_defaults section in msticpyconfig.yaml

.. parsed-literal::

    UserDefaults:
    # List of query providers to load
        QueryProviders:
            AzureSentinel:
            Default:          # name of the provider listed in AzureSentinel.Workspaces
                alias: azsent   # optional - create "qry_azsent" object in globals
            CyberSoc:
                alias: soc
                connect: False  # optional - do not connect on load
            Splunk:             # add non-sentinel providers like this
            connect: False
            LocalData: local

    # List of other providers/components to load
    LoadComponents:
        TILookup:           # No parameters
        GeoIpLookup:
        provider: GeoLiteLookup   # geoip provider to use
        Notebooklets:       # Load and intialize Notebooklets
        query_provider:   # Pass it this query provider at startup
            AzureSentinel:
            workspace: CyberSoc
        Pivot:              # No parameters
        AzureData:          # auth_methods passed as startup param
        auth_methods: ['cli','interactive']
        AzureSentinelAPI:
        auth_methods: ['env','interactive']
        connect: False   # Load but do not connect


Note: For components that require authentication the default
is to connect after loading. You can skip the connect step by
add connect: False to the entry.
"""
import textwrap
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, Tuple

from .._version import VERSION
from ..common.pkg_config import settings
from ..common.wsconfig import WorkspaceConfig
from ..data.data_providers import QueryProvider

__version__ = VERSION
__author__ = "Ian Hellen"


def load_user_defaults() -> Dict[str, object]:
    """
    Load providers from user defaults in msticpyconfig.yaml.

    Returns
    -------
    Dict[str, object]
        Dict of object name and provider instances.

    """
    user_defaults = settings.get("UserDefaults")
    if not user_defaults:
        return {}
    prov_dict = _load_query_providers(user_defaults)
    prov_dict.update(_load_components(user_defaults, namespace=prov_dict))

    return prov_dict


def _load_query_providers(user_defaults):
    prov_dict = {}
    if "QueryProviders" in user_defaults:
        for prov_name, qry_prov_entry in user_defaults.get("QueryProviders").items():
            if prov_name == "AzureSentinel":
                provs = _load_az_workspaces(prov_name, qry_prov_entry)
                prov_dict.update(provs)
            else:
                obj_name, prov_obj = _load_provider(prov_name, qry_prov_entry)
                prov_dict[obj_name] = prov_obj
    return prov_dict


def _load_components(user_defaults, namespace=None):
    prov_dict = {}
    if "LoadComponents" not in user_defaults:
        return prov_dict
    comps_to_load = user_defaults.get("LoadComponents", {})

    for comp in COMP_LOADERS:
        load_comp_func = COMP_LOADERS.get(comp)
        if comp not in comps_to_load or not load_comp_func:
            continue
        comp_settings = comps_to_load.get(comp)

        if load_comp_func:
            print(f"Loading *{comp}*. ", end="")
            comp_out = StringIO()
            with redirect_stdout(comp_out):
                # We're calling the load_component function defined for each comp
                # and passing the dict of currently loaded providers
                # plus any global namespace passed to us (usually globals())
                obj_name, comp_obj = load_comp_func(
                    comp_settings, local_ns=prov_dict, global_ns=namespace
                )

            prov_dict[obj_name] = comp_obj
            print(f"- as '{obj_name}'")
            if comp_out.getvalue():
                print("   Component output:")
                print(
                    "\n".join(
                        textwrap.wrap(
                            comp_out.getvalue(),
                            replace_whitespace=True,
                            initial_indent="    ",
                            subsequent_indent="    ",
                        )
                    )
                )
        print()
    return prov_dict


def _load_az_workspaces(
    prov_name: str, azsent_prov_entry: Dict[str, Any]
) -> Dict[str, Any]:
    az_provs = {}
    for ws_name, ws_settings in azsent_prov_entry.items():
        print(f"Loading {prov_name}, workspace: {ws_name}")
        alias = ws_settings.get("alias", ws_name)
        connect = ws_settings.get("connect", True)
        obj_name = f"qry_{alias.lower()}"
        print(f"Workspace *{ws_name}* query provider loaded as '{obj_name}'. ", end="")
        prov_obj = QueryProvider(prov_name)

        if connect:
            ws_params = {}
            if ws_name != "Default":
                ws_params = {"workspace": ws_name}
            ws_config = WorkspaceConfig(**ws_params)  # type: ignore
            prov_obj.connect(ws_config.code_connect_str)
            print("Connected.")
        az_provs[obj_name] = prov_obj
    return az_provs


def _load_provider(prov_name: str, qry_prov_entry: Dict[str, Any]) -> Tuple[str, Any]:
    alias = qry_prov_entry.get("alias", prov_name)
    connect = qry_prov_entry.get("connect", True)
    obj_name = f"qry_{alias.lower()}"
    prov_obj = QueryProvider(prov_name)
    print(f"Loaded *{prov_name}* as '{obj_name}'. ", end="")
    if connect:
        prov_obj.connect()
        print("Connected.")
    return obj_name, prov_obj


# pylint: disable=import-outside-toplevel
def _load_ti_lookup(comp_settings=None, **kwargs):
    del comp_settings, kwargs
    from ..sectools.tilookup import TILookup

    return "ti_lookup", TILookup()


def _load_geoip_lookup(comp_settings=None, **kwargs):
    del kwargs
    provider = (
        comp_settings.get("provider") if isinstance(comp_settings, dict) else None
    )
    if provider == "GeoLiteLookup":
        from ..sectools.geoip import GeoLiteLookup

        return "geoip", GeoLiteLookup()
    if provider == "IpStackLookup":
        from ..sectools.geoip import IPStackLookup

        return "geoip", IPStackLookup()
    return None, None


def _load_notebooklets(comp_settings=None, **kwargs):
    nbinit_params = {}
    if comp_settings and isinstance(comp_settings, dict):
        prov_name, prov_args = next(
            iter(comp_settings.get("query_provider", {}).items())
        )
        if prov_name:
            nbinit_params = {"query_provider": prov_name}
        if prov_args:
            nbinit_params.update(
                {f"{prov_name}_{name}": val for name, val in prov_args.items()}
            )
    namespace = kwargs.pop("global_ns", {})
    namespace.update(kwargs.pop("local_ns", {}))
    providers = _get_provider_names(namespace)
    # Add these as additional providers
    providers = [f"+{prov}" for prov in providers]
    nbinit_params.update({"providers": providers, "namespace": namespace})
    try:
        import msticnb

        msticnb.init(**nbinit_params)
        return "nb", msticnb
    except ImportError:
        print("Cannot load MSTIC notebooklets (msticnb) package.")
        print("Please install - 'pip install msticnb'")

    return None, None


def _load_pivot(comp_settings=None, **kwargs):
    del comp_settings
    from ..datamodel.pivot import Pivot

    namespace = kwargs.get("global_ns", {}).copy()
    namespace.update(kwargs.get("local_ns", {}))
    piv_kwargs = {"namespace": namespace}
    pivot = Pivot(**piv_kwargs)
    return "pivot", pivot


def _load_azure_data(comp_settings=None, **kwargs):
    del kwargs
    from ..data.azure_data import AzureData

    az_data = AzureData()
    connect = comp_settings.pop("connect", True)
    connect_args = comp_settings
    if connect:
        az_data.connect(**connect_args)
        print("Connected. ", end="")
    return "az_data", az_data


def _load_azsent_api(comp_settings=None, **kwargs):
    del kwargs
    from ..data.azure_sentinel import AzureSentinel

    az_sent = AzureSentinel()
    connect = comp_settings.pop("connect", True)
    connect_args = comp_settings
    if connect:
        az_sent.connect(**connect_args)
        print("Connected. ", end="")
    return "azs_api", az_sent


# providers loaded in order specified
# Do not alter the order unless you know what dependencies
# are between the different providers.
COMP_LOADERS = {
    "TILookup": _load_ti_lookup,
    "GeoIpLookup": _load_geoip_lookup,
    "AzureData": _load_azure_data,
    "AzureSentinelAPI": _load_azsent_api,
    "Pivot": _load_pivot,  # Pivots loaded after most providers
    "Notebooklets": _load_notebooklets,  # Notebooklets calls add_pivots
}


def _get_provider_names(prov_dict):
    providers = []
    for _, obj in prov_dict.items():
        if isinstance(obj, QueryProvider) and obj.connected:
            providers.append(obj.environment.casefold())
        else:
            cls_name = obj.__class__.__name__
            if cls_name in COMP_LOADERS and cls_name != "Pivot":
                providers.append(cls_name.casefold())
    return providers
