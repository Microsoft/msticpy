# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""QueryStore class - holds a collection of QuerySources."""
from collections import defaultdict
from os import path
from typing import Any, Dict, Iterable, Set, Union, Optional, List

from ..common.exceptions import MsticpyUserConfigError
from .._version import VERSION
from .query_defns import DataEnvironment, DataFamily
from .data_query_reader import find_yaml_files, read_query_def_file
from .query_source import QuerySource

__version__ = VERSION
__author__ = "Ian Hellen"


def _get_dot_path(elem_path: str, data_map: dict) -> Any:
    """
    Return For dotted attribute, tries to search.

    Parameters
    ----------
    elem_path : str
        The attribute name or prefix.name
    data_map : dict
        The dictionary/map to search through.

    Returns
    -------
    Any
        The attribute value

    Raises
    ------
    KeyError
        If the key/subkey is not found

    """
    # if this is directly in the map return it
    if elem_path in data_map:
        return data_map[elem_path]
    # otherwise partition into prefix and name
    prefix, _, name = elem_path.rpartition(".")
    attrib = data_map.get(prefix)
    if isinstance(attrib, dict) and name in attrib:
        return attrib[name]
    raise KeyError(f"'{elem_path}' not found")


class QueryStore:
    """
    Repository for query definitions for a data environment.

    Attributes
    ----------
    environment: str
        The data environment for the queries.
    data_families: Dict[str, Dict[str, QuerySource]]
        The set of data families and associated queries
        for each.

    """

    def __init__(self, environment: str):
        """
        Intialize a QueryStore for a new environment.

        Parameters
        ----------
        environment : str
            The data environment

        """
        self.environment: str = environment
        self.data_families: Dict[str, Dict[str, QuerySource]] = defaultdict(dict)
        self.data_family_defaults: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def __getattr__(self, name: str):
        """Return the item in dot-separated path `name`."""
        return _get_dot_path(elem_path=name, data_map=self.data_families)

    def __getitem__(self, key: str):
        """Allow query retrieval using dotted key path."""
        return _get_dot_path(elem_path=key, data_map=self.data_families)

    @property
    def query_names(self) -> Iterable[str]:
        """
        Return list of family.query in the store.

        Returns
        -------
        Iterable[str]
            List of queries

        """
        for family in sorted(self.data_families):

            yield from [
                f"{family}.{query}"
                for query in sorted(self.data_families[family].keys())
            ]

    def add_data_source(self, source: QuerySource):
        """
        Add a datasource/query to the store.

        Parameters
        ----------
        source : QuerySource
            The source to add. An existing item with
            the same name will be overwritten

        """
        source.query_store = self
        for family in source.data_families:
            self.data_families[family][source.name] = source
            # we want to update any new defaults for the data family
            self.data_family_defaults[family].update(source.defaults)

            # we also replace the defaults dict in each source with
            # a reference to the data family defaults so that as
            # new files are read in defaults are shared by all sources.
            source.defaults = self.data_family_defaults[family]

            valid, failures = source.validate()
            if not valid:
                raise MsticpyUserConfigError(
                    source.name,
                    failures,
                    title="Error importing query definition file",
                    help_uri=(
                        "https://msticpy.readthedocs.io/en/latest/"
                        + "data_acquisition/DataProviders.html#creating-new-queries"
                    ),
                )

    def add_query(
        self,
        name: str,
        query: str,
        query_paths: Union[str, List[str]],
        description: str = None,
    ):
        """
        Add a query from name/query text.

        Parameters
        ----------
        name : str
            name of the query
        query : str
            The query string
        query_paths : Union[str, List[str]]
            The path/data_family to categorize.
            Multiple paths can be specified. If the path is dotted,
            this will cause the query to be displayed in the corresponding
            hierarchy.
        description : str, optional
            Query description

        """
        prefix = ""
        if "." in name:
            prefix, _, name = name.rpartition(".")

        if isinstance(query_paths, str):
            query_paths = [query_paths]
        if prefix:
            query_paths = [f"{q_path}.{prefix}" for q_path in query_paths]

        src_dict = {"args": {"query": query}, "description": description or name}
        md_dict = {"data_families": query_paths}

        query_source = QuerySource(
            name=name, source=src_dict, defaults={}, metadata=md_dict
        )
        self.add_data_source(query_source)

    def import_file(self, query_file: str):
        """
        Import a yaml data source definition.

        Parameters
        ----------
        query_file : str
            Path to the file to import

        Raises
        ------
        ImportError
            File read error or Syntax or semantic error found in
            the source file.

        """
        sources, defaults, metadata = read_query_def_file(query_file)

        for source_name, source in sources.items():
            new_source = QuerySource(source_name, source, defaults, metadata)
            self.add_data_source(new_source)

    @classmethod  # noqa: MC0001
    def import_files(
        cls, source_path: list, recursive: bool = False
    ) -> Dict[str, "QueryStore"]:
        """
        Import multiple query definition files from directory path.

        Parameters
        ----------
        source_path : str
            The folder containing the yaml definition files.
        recursive : bool, optional
            True to recurse sub-directories
            (the default is False, which only reads from the top level)

        Returns
        -------
        Dict[str, 'QueryStore']
            Dictionary of one or more environments and the
            QueryStore containing the queries for each environment.

        Raises
        ------
        FileNotFoundError
            File read error or Syntax or semantic error found in
            a source file.

        """
        env_stores: Dict[str, QueryStore] = dict()
        for query_dir in source_path:
            if not path.isdir(query_dir):
                raise FileNotFoundError(f"{query_dir} is not a directory")
            for file_path in find_yaml_files(query_dir, recursive):
                try:
                    sources, defaults, metadata = read_query_def_file(str(file_path))
                except ValueError:
                    print(
                        f"{file_path} is not a valid query definition file - skipping."
                    )
                    continue

                for env_value in metadata["data_environments"]:
                    if "." in env_value:
                        env_value = env_value.split(".")[1]
                    environment = DataEnvironment.parse(env_value)
                    if environment == DataEnvironment.Unknown:
                        raise ValueError(f"Unknown environment {env_value}")

                    if environment.name not in env_stores:
                        env_stores[environment.name] = cls(environment=environment.name)
                    for source_name, source in sources.items():
                        new_source = QuerySource(
                            source_name, source, defaults, metadata
                        )
                        env_stores[environment.name].add_data_source(new_source)

        return env_stores

    def get_query(
        self, query_name: str, query_path: Union[str, DataFamily] = None
    ) -> "QuerySource":
        """
        Return query with name `data_family` and `query_name`.

        Parameters
        ----------
        query_name: str
            Name of the query
        query_path: Union[str, DataFamily]
            The data family for the query

        Returns
        -------
        QuerySource
            Query matching name and family.

        """
        if query_path and isinstance(query_path, DataFamily):
            query_path = query_path.name
        if "." in query_name:
            query_parts = query_name.split(".")
            query_container = ".".join(query_parts[:-1])
            query_name = query_parts[-1]
            if query_container in self.data_families:
                query_path = query_container
            elif query_path:
                query_container = ".".join(
                    [query_path, query_container]  # type: ignore
                )
                if query_container in self.data_families:
                    query_path = query_container
        query = self.data_families.get(query_path, {}).get(query_name)  # type: ignore
        if not query:
            raise LookupError(f"Could not find {query_name} in path {query_path}.")
        return query

    def find_query(self, query_name: str) -> Set[Optional[QuerySource]]:
        """
        Return set of queries with name `query_name`.

        Parameters
        ----------
        query_name: str
            Name of the query

        Returns
        -------
        Set[QuerySource]
            Set (distinct) queries matching name.

        """
        return {
            query_dict.get(query_name)
            for family, query_dict in self.data_families.items()
            if query_name in query_dict
        }
