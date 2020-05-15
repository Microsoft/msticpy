# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Local Data Driver class - for testing and demos."""
from pathlib import Path
from typing import Union, Any, Dict, Optional, List

import pandas as pd

from .driver_base import DriverBase
from ...common.utility import export
from ..._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


@export
class LocalDataDriver(DriverBase):
    """LocalDataDriver class to execute kql queries."""

    def __init__(self, connection_str: str = None, **kwargs):
        """
        Instantiaite LocalDataDriver and optionally connect.

        Parameters
        ----------
        connection_str : str, optional
            Connection string (not used)

        """
        del connection_str
        self._debug = kwargs.get("debug", False)
        super().__init__()

        # If data paths specified, use these
        data_paths = kwargs.get("data_paths")
        if data_paths:
            self._paths: List[str] = [path.strip() for path in data_paths]
        else:
            self._paths = ["."]

        self.data_files: Dict[str, str] = self._get_data_paths()
        self._schema: Dict[str, Any] = {}
        self._loaded = True
        self._connected = True

    def _get_data_paths(self) -> Dict[str, str]:
        """Read files in data paths."""
        data_files = {}
        for path in self._paths:
            for pattern in ["**/*.pkl", "**/*.csv"]:
                data_files.update(
                    {
                        str(file_path.name).casefold(): str(file_path)
                        for file_path in Path(path).resolve().glob(pattern)
                    }
                )
        return data_files

    def connect(self, connection_str: Optional[str] = None, **kwargs):
        """
        Connect to data source.

        Parameters
        ----------
        connection_str : str
            Connect to a data source

        """
        del connection_str
        self._connected = True
        print("Connected.")

    @property
    def schema(self) -> Dict[str, Dict]:
        """
        Return current data schema of connection.

        Returns
        -------
        Dict[str, Dict]
            Data schema of current connection.

        """
        if self._schema:
            return self._schema
        for df_fname in self.data_files:
            test_df = self.query(df_fname)
            if not isinstance(test_df, pd.DataFrame):
                continue
            df_schema = test_df.dtypes
            self._schema[df_fname] = {
                key: dtype.name for key, dtype in df_schema.to_dict().items()
            }

        return self._schema

    def query(self, query: str) -> Union[pd.DataFrame, Any]:
        """
        Execute query string and return DataFrame of results.

        Parameters
        ----------
        query : str
            The kql query to execute

        Returns
        -------
        Union[pd.DataFrame, results.ResultSet]
            A DataFrame (if successfull) or
            Kql ResultSet if an error.

        """
        file_path = self.data_files.get(query.casefold())
        if not file_path:
            raise FileNotFoundError(f"Data file for query {query} not found.")
        if file_path.endswith("csv"):
            return pd.read_csv(
                file_path, infer_datetime_format=True, parse_dates=["TimeGenerated"]
            )
        data_df = pd.read_pickle(file_path)
        if isinstance(data_df, pd.DataFrame):
            return data_df
        return f"{query} is not a DataFrame ({file_path})."

    def query_with_results(self, query, **kwargs):
        """Return query with fake results."""
        return self.query(query, **kwargs), "OK"
