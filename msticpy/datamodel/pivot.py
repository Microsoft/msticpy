# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pivot functions main module."""
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Optional, Type

import pkg_resources
from IPython import get_ipython

from .._version import VERSION
from ..common.timespan import TimeSpan
from ..data import QueryProvider
from ..nbtools.nbwidgets import QueryTime
from ..sectools import TILookup

# pylint: disable=unused-import
from . import pivot_pd_accessor  # noqa: F401
from .pivot_browser import PivotBrowser
from .pivot_data_queries import add_data_queries_to_entities
from .pivot_register import PivotRegistration
from .pivot_register_reader import add_unbound_pivot_function, register_pivots
from .pivot_ti_provider import add_ioc_queries_to_entities
from . import entities

__version__ = VERSION
__author__ = "Ian Hellen"

_DEF_PIVOT_REG_FILE = "resources/mp_pivot_reg.yaml"


# Import IPython magic if in an IPython environment
if get_ipython():
    from . import txt_df_magic  # noqa: F401


class Pivot:
    """Pivot environment loader."""

    current: Optional["Pivot"] = None

    def __init__(
        self,
        namespace: Dict[str, Any] = None,
        providers: Iterable[Any] = None,
        timespan: Optional[TimeSpan] = None,
    ):
        """
        Instantiate a Pivot environment.

        Parameters
        ----------
        namespace : Dict[str, Any], optional
            To search for and use any current providers, specify
            `namespace=globals()`, by default None
        providers : Iterable[Any], optional
            A list of query providers, TILookup or other providers to
            use (these will override providers of the same type read
            from `namespace`), by default None
        timespan : Optional[TimeSpan], optional
            The default timespan used by providers that require
            start and end times. By default the time range is initialized
            to be 24 hours prior to the load time.

        """
        self.__class__.current = self
        self._query_time: QueryTime
        if timespan is not None:
            self.timespan = timespan
        else:
            self._query_time = self._get_default_query_time("day", 1)

        # acquire current providers
        self._providers: Dict[str, Any] = {}
        self.reload_pivots(namespace=namespace, providers=providers)

    def reload_pivots(
        self,
        namespace: Dict[str, Any] = None,
        providers: Iterable[Any] = None,
        clear_existing: bool = True,
    ):
        """
        Load or reload Pivot functions from environment and/or providers list.

        Parameters
        ----------
        namespace : Dict[str, Any], optional
            To search for and use any current providers, specify
            `namespace=globals()`, by default None
        providers : Iterable[Any], optional
            A list of query providers, TILookup or other providers to
            use (these will override providers of the same type read
            from `namespace`), by default None
        clear_existing : bool
            Reloads pivot functions without clearing existing pivot
            assignments. Any pivot functions with conflicting names will
            be overwritten by the reload operation.
            The default is True.

        """
        if clear_existing:
            self.remove_pivot_funcs(entity="all")

        self._get_all_providers(namespace, providers)

        # load and assign functions for data queries
        data_provs = (
            prov for prov in self._providers.values() if isinstance(prov, QueryProvider)
        )
        for prov in data_provs:
            add_data_queries_to_entities(prov, self.get_timespan)

        # load TI functions
        add_ioc_queries_to_entities(self.get_provider("TILookup"), container="ti")

        # Add pivots from config registry
        register_pivots(
            file_path=self._get_def_pivot_reg(), container="util", namespace=namespace
        )

    def _get_all_providers(
        self,
        namespace: Dict[str, Any] = None,
        providers: Iterable[Any] = None,
    ):
        self._get_query_providers(namespace=namespace, providers=providers)
        self._providers["TILookup"] = (
            self._get_provider_by_type(
                namespace=namespace, providers=providers, provider_type=TILookup
            )
            or TILookup()
        )

    def _get_query_providers(
        self,
        namespace: Dict[str, Any] = None,
        providers: Iterable[Any] = None,
    ):
        """Update the current list of loaded providers."""
        if namespace:
            # return just one provider for each data env.
            # Use the last one in the namespace
            self._providers.update(
                {
                    prov.environment: prov
                    for prov in namespace.values()
                    if isinstance(prov, QueryProvider)
                }
            )
        if providers:
            self._providers.update(
                {
                    prov.environment: prov
                    for prov in providers
                    if isinstance(prov, QueryProvider)
                }
            )

    def add_query_provider(self, prov: QueryProvider):
        """
        Add pivot functions from provider.

        Parameters
        ----------
        prov : QueryProvider
            Query provider.

        """
        add_data_queries_to_entities(prov, self.get_timespan)

    @staticmethod
    def _get_provider_by_type(
        provider_type: Type,
        namespace: Dict[str, Any] = None,
        providers: Iterable[Any] = None,
    ) -> Any:
        if providers:
            ti_provs = [prov for prov in providers if isinstance(prov, provider_type)]
            if ti_provs:
                return ti_provs[0]
        if namespace:
            ns_providers = [
                prov for prov in namespace.values() if isinstance(prov, provider_type)
            ]
            if ns_providers:
                return ns_providers[-1]
        return None

    @staticmethod
    def _get_def_pivot_reg():
        return pkg_resources.resource_filename("msticpy", _DEF_PIVOT_REG_FILE)

    @property
    def providers(self) -> Dict[str, Any]:
        """
        Return the current set of loaded providers.

        Returns
        -------
        Dict[str, Any]
            provider_name, provider_instance

        """
        return self._providers

    def get_provider(self, name: str) -> Any:
        """
        Get a provider by type name.

        Parameters
        ----------
        name : str
            The name of the provider type.

        Returns
        -------
        Any
            An instance of the provider or None
            if the Pivot environment does not have one.

        """
        return self._providers.get(name)

    def edit_query_time(self, timespan: Optional[TimeSpan] = None):
        """
        Display a QueryTime widget to get the timespan.

        Parameters
        ----------
        timespan : Optional[TimeSpan], optional
            Pre-populate the timespan shown by the QueryTime editor,
            by default None

        """
        self._query_time = QueryTime(
            timespan=timespan or self.timespan,
            label="Set time range for pivot functions.",
        )
        self._query_time.display()

    @staticmethod
    def _get_default_query_time(units: str = "day", before: int = 1):
        return QueryTime(
            origin_time=datetime.utcnow(),
            before=before,
            after=0,
            label="Set time range for pivot functions.",
            units=units,
        )

    @property
    def start(self):
        """Return current start time for queries."""
        return self._query_time.start

    @property
    def end(self):
        """Return current end time for queries."""
        return self._query_time.end

    @property
    def timespan(self) -> TimeSpan:
        """
        Return the current timespan.

        Returns
        -------
        TimeSpan
            The current timespan

        """
        return TimeSpan(start=self.start, end=self.end)

    @timespan.setter
    def timespan(self, value: Any):
        """
        Set the pivot timespan.

        Parameters
        ----------
        value : Optional[Any], optional
            Timespan object or something convertible to
            a TimeSpan, by default None

        """
        if isinstance(value, TimeSpan):
            timespan = value
        elif value is not None:
            timespan = TimeSpan(value)
        self._query_time = QueryTime(
            timespan=timespan,
            label="Set time range for pivot functions.",
        )

    def set_timespan(self, value: Optional[Any] = None, **kwargs):
        """
        Set the pivot timespan.

        Parameters
        ----------
        value : Optional[Any], optional
            Timespan object or something convertible to
            a TimeSpan, by default None

        Other Parameters
        ----------------
        kwargs
            Key/value arguments passed to Timespan constructor.

        """
        if isinstance(value, TimeSpan):
            timespan = value
        elif value is not None:
            timespan = TimeSpan(value)
        else:
            timespan = TimeSpan(**kwargs)
        self.timespan = timespan

    def get_timespan(self) -> TimeSpan:
        """Return the timespan as a TimeSpan object."""
        return TimeSpan(start=self.start, end=self.end)

    @staticmethod
    def register_pivot_providers(
        pivot_reg_path: str,
        namespace: Dict[str, Any] = None,
        def_container: str = "custom",
        force_container: bool = False,
    ):
        """
        Register pivot functions from configuration file.

        Parameters
        ----------
        pivot_reg_path : str
            Path to config yaml file
        namespace : Dict[str, Any], optional
            Namespace to search for existing instances of classes, by default None
        def_container : str, optional
            Container name to use for entity pivot functions, by default "other"
        force_container : bool, optional
            Force `container` value to be used even if entity definitions have
            specific setting for a container name, by default False

        Raises
        ------
        ValueError
            An entity specified in the config file is not recognized.

        """
        register_pivots(
            pivot_reg_path,
            def_container=def_container,
            force_container=force_container,
            namespace=namespace,
        )

    @staticmethod
    def add_pivot_function(
        func: Callable[[Any], Any],
        pivot_reg: "PivotRegistration" = None,
        container: str = "other",
        **kwargs,
    ):
        """
        Add a pivot function to entities.

        Parameters
        ----------
        func : Callable[[Any], Any]
            The function to add
        pivot_reg : PivotRegistration, optional
            Pivot registration object, by default None
        container : str, optional
            The name of the container into which the function
            should be added, by default "other"

        Other Parameters
        ----------------
        kwargs
            If `pivot_reg` is not supplied you can specify required
            pivot registration parameters via keyword arguments. You must
            specify `input_type` (str) and `entity_map` (dict of entity_name,
            entity_attribute pairs)

        See Also
        --------
        PivotRegistration

        """
        add_unbound_pivot_function(
            func=func, pivot_reg=pivot_reg, container=container, **kwargs
        )

    @staticmethod
    def remove_pivot_funcs(entity: str):
        """
        Remove pivot functions from one or all entities.

        Parameters
        ----------
        entity : str
            entity class name or "all" to remove all pivot functions.

        Raises
        ------
        ValueError
            If entity is not a recognized entity class.

        """
        all_entities = dir(entities)
        if entity != "all":
            if entity not in all_entities:
                raise ValueError(f"Entity name '{entity}' not found.")
            entity_names = [entity]
        else:
            entity_names = all_entities
        for entity_name in entity_names:
            entity_cls = getattr(entities, entity_name)
            for attr in dir(entity_cls):
                attr_obj = getattr(entity_cls, attr)
                if type(attr_obj).__name__ == "QueryContainer":
                    delattr(entity_cls, attr)
                if callable(attr_obj) and hasattr(attr_obj, "pivot_properties"):
                    delattr(entity_cls, attr)

    @staticmethod
    def browse():
        """Return PivotBrowser."""
        return PivotBrowser()
