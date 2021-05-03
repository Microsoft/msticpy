#  -------------------------------------------------------------------------
#  Copyright (c) juju4. All rights reserved.
#  Licensed under the MIT License. See License.txt in the project root for
#  license information.
#  --------------------------------------------------------------------------
"""Sumologic Driver class."""
from datetime import datetime, timedelta
import re
import sys
import time
from typing import Any, Tuple, Union, Dict, Iterable, Optional

import pandas as pd
from sumologic.sumologic import SumoLogic
from requests.exceptions import ConnectionError as ConnError, HTTPError

from .driver_base import DriverBase, QuerySource
from ..._version import VERSION
from ...common.utility import export, check_kwargs
from ...common.exceptions import (
    MsticpyConnectionError,
    MsticpyNotConnectedError,
    MsticpyUserConfigError,
)
from ...common.provider_settings import get_provider_settings, ProviderSettings

__version__ = VERSION
__author__ = "juju4"


SUMOLOGIC_CONNECT_ARGS = {
    "connection_str": "(string) The url endpoint (the default is 'https://api.us2.sumologic.com/api').",
    "accessid": "(string) The Sumologic accessid, which is used to "
    + "authenticate on Sumologic instance.",
    "accesskey": "(string) The matching Sumologic accesskey.",
}


@export
class SumologicDriver(DriverBase):
    """Driver to connect and query from Sumologic."""

    _SUMOLOGIC_REQD_ARGS = ["connection_str", "accessid", "accesskey"]
    _CONNECT_DEFAULTS: Dict[str, Any] = {
        "connection_str": "https://api.us2.sumologic.com/api"
    }
    _TIME_FORMAT = '"%Y-%m-%d %H:%M:%S.%6N"'
    checkinterval = 10
    timeout = 300

    def __init__(self, **kwargs):
        """Instantiate Sumologic Driver."""
        super().__init__()
        self.service = None
        self._loaded = True
        self._connected = False
        self._debug = kwargs.get("debug", False)
        self.public_attribs = {
            "client": self.service,
            "saved_searches": self._saved_searches,
            "fired_alerts": self._fired_alerts,
        }
        self.formatters = {"datetime": self._format_datetime, "list": self._format_list}

    def connect(self, connection_str: str = None, **kwargs):
        """
        Connect to Sumologic via sumologic-sdk.

        Parameters
        ----------
        connection_str :
            Sumologic API url endpoint. default: https://api.us2.sumologic.com/api

        Other Parameters
        ----------------
        kwargs :
            Connection parameters can be supplied as keyword parameters.

        Notes
        -----
        Default configuration is read from the DataProviders/Sumologic
        section of msticpyconfig.yaml, if available.

        """
        cs_dict = self._get_connect_args(connection_str, **kwargs)

        arg_dict = {
            key: val for key, val in cs_dict.items() if key in SUMOLOGIC_CONNECT_ARGS
        }
        try:
            # https://github.com/SumoLogic/sumologic-python-sdk/blob/master/scripts/search-job.py
            self.service = SumoLogic(
                arg_dict["accessid"], arg_dict["accesskey"], arg_dict["connection_str"]
            )
        except ConnError as err:
            raise MsticpyConnectionError(
                f"Authentication error connecting to Sumologic: {err}",
                title="Sumologic connection",
                help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
            ) from err
        except HTTPError as err:
            raise MsticpyConnectionError(
                f"Communication error connecting to Sumologic: {err}",
                title="Sumologic connection",
                help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
            ) from err
        except Exception as err:
            raise MsticpyConnectionError(
                f"Error connecting to Sumologic: {err}",
                title="Sumologic connection",
                help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
            ) from err
        self._connected = True
        print("connected with accessid {}".format(arg_dict["accessid"]))

    def _get_connect_args(
        self, connection_str: Optional[str], **kwargs
    ) -> Dict[str, Any]:
        """Check and consolidate connection parameters."""
        cs_dict: Dict[str, Any] = self._CONNECT_DEFAULTS
        # Fetch any config settings
        cs_dict.update(self._get_config_settings())
        # If a connection string - parse this and add to config
        if kwargs:
            # if connection args supplied as kwargs
            cs_dict.update(kwargs)
            check_kwargs(cs_dict, list(SUMOLOGIC_CONNECT_ARGS.keys()))

        missing_args = set(self._SUMOLOGIC_REQD_ARGS) - cs_dict.keys()
        if missing_args:
            raise MsticpyUserConfigError(
                "One or more connection parameters missing for Sumologic connector",
                ", ".join(missing_args),
                f"Required parameters are {', '.join(self._SUMOLOGIC_REQD_ARGS)}",
                "All parameters:",
                *[f"{arg}: {desc}" for arg, desc in SUMOLOGIC_CONNECT_ARGS.items()],
                title="no Sumologic connection parameters",
            )
        return cs_dict

    def _query(
        self, query: str, query_source: QuerySource = None, **kwargs
    ) -> Union[pd.DataFrame, Any]:
        """
        Execute Sumologic query and retrieve results.

        Parameters
        ----------
        query : str
            Sumologic query to execute

        Other Parameters
        ----------------
        kwargs :
            Are passed to Sumologic
            days: Search the past X days.
            start_time: A datetime() object representing the start of the search
                    window. If used without end_time, the end of the search
                    window is the current time.
            end_time: A datetime() object representing the end of the search window.
                  If used without start_time, the search start will be the earliest
                  time in the index.
            timezone: timezone used for time range search
            byreceipttime:  if time reference should used _receiptTime (time when Sumologic
                        got message) instead of _messageTime (time present in log message).
            limit: An integer describing the max number of search results to return.
            forcemessagesresults: Force results to be raw messages even if aggregated query.
            verbosity: Provide more verbose state. from 0 least verbose to 4 most one.
            checkinterval: interval in seconds to check if results are gathered
            timeout: timeout in seconds when gathering results

        Returns
        -------
        Union[pd.DataFrame, Any]
            Query results in a dataframe.
            or query response if an error.

        """
        del query_source
        if not self._connected:
            raise self._create_not_connected_err()

        verbosity = kwargs.pop("verbosity", 0)
        timezone = kwargs.pop("timezone", "UTC")
        byreceipttime = kwargs.pop("byreceipttime", False)
        forcemessagesresults = kwargs.pop("forcemessagesresults", False)
        self.checkinterval = kwargs.pop("checkinterval", 10)
        self.timeout = kwargs.pop("timeout", 300)

        if "days" in kwargs:
            end = datetime.now()
            end_time = end.strftime("%Y-%m-%dT%H:%M:%S")
            start_time = end - timedelta(days=kwargs["days"])
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        elif "start_time" in kwargs and "end_time" not in kwargs:
            end = datetime.now()
            end_time = end.strftime("%Y-%m-%dT%H:%M:%S")
            start_time = kwargs["start_time"].strftime("%Y-%m-%dT%H:%M:%S")
        elif "days" not in kwargs and "start_time" not in kwargs:
            print("Error! require either days, either start_time")
            sys.exit(1)
        elif "end_time" in kwargs and "start_time" in kwargs:
            end_time = kwargs["end_time"].strftime("%Y-%m-%dT%H:%M:%S")
            start_time = kwargs["start_time"].strftime("%Y-%m-%dT%H:%M:%S")

        # default to unlimited query unless count is specified
        if "limit" in kwargs:
            query += "| limit {0}".format(kwargs["limit"])
        limit = kwargs.pop("limit", 10000)

        if verbosity >= 1:
            print(
                "INFO: from {0} to {1}, timezone {2}".format(
                    start_time, end_time, timezone
                )
            )
        if verbosity >= 2:
            print("DEBUG: query {0}".format(query))
            print("DEBUG: byreceipttime {0}".format(byreceipttime))
            from timeit import default_timer as timer

            timer_start = timer()
        try:
            searchjob = self.service.search_job(
                query, start_time, end_time, timezone, byreceipttime
            )
        except HTTPError as err:
            raise MsticpyConnectionError(
                f"Communication error connecting to Sumologic: {err}",
                title="Sumologic submit search_job",
                help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
            ) from err
        except Exception as err:
            raise MsticpyConnectionError(
                f"Failed to submit search job: {err}",
                title="Sumologic submit search job",
                help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
            ) from err
        if verbosity >= 2:
            print("DEBUG: search job {0}".format(searchjob))

        status = self.service.search_job_status(searchjob)
        if verbosity >= 2:
            print("DEBUG: status {0}".format(status))
        time_counter = 0
        while status["state"] != "DONE GATHERING RESULTS":
            if status["state"] == "CANCELLED":
                break
            status = self.service.search_job_status(searchjob)
            if verbosity >= 4:
                print(
                    "DEBUG: pending results, state {0}. slept {1}s. sleeping extra {2}s until {3}s".format(
                        status["state"], time_counter, self.checkinterval, self.timeout
                    )
                )
            if time_counter < self.timeout:
                time.sleep(self.checkinterval)
                time_counter += self.checkinterval
            else:
                print(
                    "WARN: wait more than timeout {0}. stopping. Use timeout argument to wait longer.".format(self.timeout)
                )
                break

        print(status["state"])

        if verbosity >= 2:
            print("DEBUG: search performance:{0}".format(str(timer() - timer_start)))
            print(
                "DEBUG: messages or records? {0}".format(
                    re.search(r"\|\s*count", query, re.IGNORECASE)
                )
            )
        if status["state"] == "DONE GATHERING RESULTS" and (
            not re.search(r"\|\s*count", query, re.IGNORECASE) or forcemessagesresults
        ):
            # Non-aggregated results, Messages only
            count = status["messageCount"]
            limit2 = (
                count if count < limit and count != 0 else limit
            )  # compensate bad limit check
            try:
                result = self.service.search_job_messages(searchjob, limit=limit2)
                return result["messages"]
            except HTTPError as err:
                raise MsticpyConnectionError(
                    f"Communication error connecting to Sumologic: {err}",
                    title="Sumologic search_job_messages",
                    help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
                ) from err
            except Exception as err:
                raise MsticpyConnectionError(
                    f"Failed to get search messages: {err}",
                    title="Sumologic connection",
                    help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
                ) from err
        elif status["state"] == "DONE GATHERING RESULTS":
            # Aggregated results
            count = status["recordCount"]
            limit2 = (
                count if count < limit and count != 0 else limit
            )  # compensate bad limit check
            try:
                result = self.service.search_job_records(searchjob, limit=limit2)
                return result["records"]
            except HTTPError as err:
                raise MsticpyConnectionError(
                    f"Communication error connecting to Sumologic: {err}",
                    title="Sumologic search_job_records",
                    help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
                ) from err
            except Exception as err:
                raise MsticpyConnectionError(
                    f"Failed to get search records: {err}",
                    title="Sumologic connection",
                    help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
                ) from err

        return []

    def query(
        self, query: str, query_source: QuerySource = None, **kwargs
    ) -> Union[pd.DataFrame, Any]:
        """
        Execute Sumologic query and retrieve results.

        Parameters
        ----------
        query : str
            Sumologic query to execute

        Other Parameters
        ----------------
        kwargs :
            Are passed to Sumologic
            days: Search the past X days.
            start_time: A datetime() object representing the start of the search
                    window. If used without end_time, the end of the search
                    window is the current time.
            end_time: A datetime() object representing the end of the search window.
                  If used without start_time, the search start will be the earliest
                  time in the index.
            timeZone: timezone used for time range search
            byReceiptTime:  if time reference should used _receiptTime (time when Sumologic
                        got message) instead of _messageTime (time present in log message).
            limit: An integer describing the max number of search results to return.
            forceMessagesResults: Force results to be raw messages even if aggregated query.
            verbosity: Provide more verbose state. from 0 least verbose to 4 most one.
            normalize: If set to True, fields containing structures (i.e. subfields)
                   will be flattened such that each field has it's own column in
                   the dataframe. If False, there will be a single column for the
                   structure, with a JSON string encoding all the contents.
            exporting: Export result to file.
            export_path: file path for exporte results.

        Returns
        -------
        Union[pd.DataFrame, Any]
            Query results in a dataframe.
            or query response if an error.

        """
        results = list()
        verbosity = kwargs.get("verbosity", 0)
        normalize = kwargs.pop("normalize", True)
        exporting = kwargs.pop("exporting", False)
        export_path = kwargs.pop("export_path", "")

        for hit in self._query(query, **kwargs):
            results.append(hit)

        if verbosity >= 3:
            print("DEBUG: {0}".format(results))
        if normalize:
            dataframe_res = pd.json_normalize(results)
        else:
            dataframe_res = pd.DataFrame(results)

        for col in dataframe_res.columns:
            if col in ("map._count", "map._timeslice"):
                dataframe_res[col] = pd.to_numeric(dataframe_res[col])

        if exporting and export_path.endswith(".xlsx"):
            if verbosity >= 2:
                print("DEBUG: Exporting results to excel file {0}".format(export_path))
            dataframe_res.to_excel(export_path, index=False)
        elif exporting and export_path.endswith(".csv"):
            if verbosity >= 2:
                print("DEBUG: Exporting results to csv file {0}".format(export_path))
            dataframe_res.to_csv(export_path, index=False)

        return dataframe_res

    def query_with_results(self, query: str, **kwargs) -> Tuple[pd.DataFrame, Any]:
        """
        Execute query string and return DataFrame of results.

        Parameters
        ----------
        query : str
            Query to execute against Sumologic instance.

        Returns
        -------
        Union[pd.DataFrame,Any]
            A DataFrame (if successful) or
            the underlying provider result if an error occurs.

        """

    @property
    def service_queries(self) -> Tuple[Dict[str, str], str]:
        """
        Return dynamic queries available on connection to service.

        Returns
        -------
        Tuple[Dict[str, str], str]
            Dictionary of query_name, query_text.
            Name of container to add queries to.

        """
        if not self.connected:
            raise self._create_not_connected_err()
        if hasattr(self.service, "saved_searches") and self.service.saved_searches:
            queries = {
                search.name.strip().replace(" ", "_"): f"search {search['search']}"
                for search in self.service.saved_searches
            }
            return queries, "SavedSearches"
        return {}, "SavedSearches"

    @property
    def _saved_searches(self) -> Union[pd.DataFrame, Any]:
        """
        Return list of saved searches in dataframe.

        Returns
        -------
        pd.DataFrame
            Dataframe with list of saved searches with name and query columns.

        """
        if self.connected:
            return self._get_saved_searches()
        return None

    def _get_saved_searches(self) -> Union[pd.DataFrame, Any]:
        """
        Return list of saved searches in dataframe.

        Returns
        -------
        pd.DataFrame
            Dataframe with list of saved searches with name and query columns.

        """
        if not self.connected:
            raise self._create_not_connected_err()
        savedsearches = self.service.saved_searches

        out_df = pd.DataFrame(columns=["name", "query"])

        namelist = []
        querylist = []
        for savedsearch in savedsearches:
            namelist.append(savedsearch.name.replace(" ", "_"))
            querylist.append(savedsearch["search"])
        out_df["name"] = namelist
        out_df["query"] = querylist

        return out_df

    @property
    def _fired_alerts(self) -> Union[pd.DataFrame, Any]:
        """
        Return list of fired alerts in dataframe.

        Returns
        -------
        pd.DataFrame
            Dataframe with list of fired alerts with alert name and count columns.

        """
        if self.connected:
            return self._get_fired_alerts()
        return None

    def _get_fired_alerts(self) -> Union[pd.DataFrame, Any]:
        """
        Return list of fired alerts in dataframe.

        Returns
        -------
        pd.DataFrame
            Dataframe with list of fired alerts with alert name and count columns.

        """
        if not self.connected:
            raise self._create_not_connected_err()
        firedalerts = self.service.fired_alerts

        out_df = pd.DataFrame(columns=["name", "count"])

        alert_names = []
        alert_counts = []
        for alert in firedalerts:
            alert_names.append(alert.name)
            alert_counts.append(alert.count)
        out_df["name"] = alert_names
        out_df["count"] = alert_counts

        return out_df

    # Parameter Formatting methods
    @staticmethod
    def _format_datetime(date_time: datetime) -> str:
        """Return datetime-formatted string."""
        return f'"{date_time.isoformat(sep=" ")}"'

    @staticmethod
    def _format_list(param_list: Iterable[Any]) -> str:
        """Return formatted list parameter."""
        fmt_list = [f'"{item}"' for item in param_list]
        return ",".join(fmt_list)

    # Read values from configuration
    @staticmethod
    def _get_config_settings() -> Dict[Any, Any]:
        """Get config from msticpyconfig."""
        data_provs = get_provider_settings(config_section="DataProviders")
        sumologic_settings: Optional[ProviderSettings] = data_provs.get("Sumologic")
        return getattr(sumologic_settings, "args", {})

    @staticmethod
    def _create_not_connected_err():
        return MsticpyNotConnectedError(
            "Please run the connect() method before running this method.",
            title="not connected to Sumologic.",
            help_uri="https://msticpy.readthedocs.io/en/latest/DataProviders.html",
        )
