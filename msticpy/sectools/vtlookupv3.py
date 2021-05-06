"""VirusTotal v3 API."""
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Set

import pandas as pd
from IPython.display import HTML, display

from ..common.exceptions import MsticpyImportExtraError
from ..common.provider_settings import get_provider_settings

try:
    import vt
    from vt_graph_api import VTGraph
    from vt_graph_api import errors as vt_graph_errs
except ImportError as imp_err:
    raise MsticpyImportExtraError(
        "Cannot use this feature without vt-py and vt-graph-api packages installed.",
        title="Error importing VirusTotal modules.",
        extra="vt3",
    ) from imp_err


class MsticpyVTNoDataError(Exception):
    """No data returned from VT API."""


class MsticpyVTGraphSaveGraphError(Exception):
    """Could not save VT Graph."""


class VTEntityType(Enum):
    """VTEntityType: Enum class for VirusTotal entity types."""

    FILE = "file"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    URL = "url"


class ColumnNames(Enum):
    """Column name enum for DataFrame output."""

    ID = "id"
    TYPE = "type"
    DETECTIONS = "detections"
    SCANS = "scans"
    SOURCE = "source"
    TARGET = "target"
    RELATIONSHIP_TYPE = "relationship_type"
    SOURCE_TYPE = "source_type"
    TARGET_TYPE = "target_type"


class VTObjectProperties(Enum):
    """Enum for VT Object properties."""

    ATTRIBUTES = "attributes"
    RELATIONSHIPS = "relationship"
    LAST_ANALYSIS_STATS = "last_analysis_stats"
    MALICIOUS = "malicious"


def _make_sync(future):
    """Wait for an async call, making it sync."""
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        # Generate an event loop if there isn't any.
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop.run_until_complete(future)


class VTLookupV3:
    """VTLookupV3: VirusTotal lookup of IoC reports."""

    _SUPPORTED_VT_TYPES: Set[VTEntityType] = {
        VTEntityType.FILE,
        VTEntityType.URL,
        VTEntityType.IP_ADDRESS,
        VTEntityType.DOMAIN,
    }

    _MAPPING_TYPES_ENDPOINT: Dict[VTEntityType, str] = {
        VTEntityType.FILE: "files",
        VTEntityType.URL: "urls",
        VTEntityType.IP_ADDRESS: "ip_addresses",
        VTEntityType.DOMAIN: "domains",
    }

    _BASIC_PROPERTIES_PER_TYPE: Dict[VTEntityType, Set[str]] = {
        VTEntityType.FILE: {
            "type_description",
            "size",
            "first_submission_date",
            "last_submission_date",
            "times_submitted",
            "meaningful_name",
        },
        VTEntityType.URL: {
            "first_submission_date",
            "last_submission_date",
            "times_submitted",
        },
        VTEntityType.IP_ADDRESS: {"date", "country", "asn", "as_owner"},
        VTEntityType.DOMAIN: {"id", "creation_date", "last_update_date", "country"},
    }

    @property
    def supported_vt_types(self) -> List[str]:
        """
        Return list of VirusTotal supported IoC type names.

        Returns
        -------
        List[str]:
            List of VirusTotal supported IoC type names.

        """
        return [str(i_type) for i_type in self._SUPPORTED_VT_TYPES]

    @classmethod
    def _get_endpoint_name(cls, vt_type: str) -> str:
        if VTEntityType(vt_type) not in cls._SUPPORTED_VT_TYPES:
            raise KeyError(f"Property type {vt_type} not supported")

        return cls._MAPPING_TYPES_ENDPOINT[VTEntityType(vt_type)]

    @classmethod
    def _parse_vt_object(cls, vt_object: vt.object.Object) -> pd.DataFrame:
        obj_dict = vt_object.to_dict()
        if VTObjectProperties.ATTRIBUTES.value in obj_dict:
            attributes = obj_dict[VTObjectProperties.ATTRIBUTES.value]
            vt_type = VTEntityType(vt_object.type)
            if vt_type not in cls._SUPPORTED_VT_TYPES:
                raise KeyError(f"Property type {vt_type} not supported")
            obj = {
                key: attributes[key]
                for key in cls._BASIC_PROPERTIES_PER_TYPE[vt_type]
                if key in attributes
            }
            vt_df = pd.json_normalize(data=[obj])
            last_analysis_stats = attributes[
                VTObjectProperties.LAST_ANALYSIS_STATS.value
            ]
            vt_df[ColumnNames.DETECTIONS.value] = last_analysis_stats[
                VTObjectProperties.MALICIOUS.value
            ]
            vt_df[ColumnNames.SCANS.value] = sum(last_analysis_stats.values())
            # Format dates for pandas
            for date_col in ("first_submission_date", "last_submission_date"):
                if date_col in vt_df.columns:
                    vt_df[date_col.replace("_date", "")] = pd.to_datetime(
                        vt_df[date_col], unit="s", utc=True
                    )
        else:
            vt_df = pd.DataFrame()

        # Inject ID and Type columns
        vt_df[ColumnNames.ID.value] = [vt_object.id]
        vt_df[ColumnNames.TYPE.value] = [vt_object.type]
        return vt_df.set_index([ColumnNames.ID.value])

    def __init__(self, vt_key: Optional[str] = None):
        """
        Create a new instance of VTLookupV3 class.

        Parameters
        ----------
        vt_key: str, optional
            VirusTotal API key, if not supplied, this is read from
            user configuration.

        """
        if not vt_key:
            prov_settings = get_provider_settings("TIProviders")
            vt_settings = prov_settings.get("VirusTotal")
            if vt_settings:
                self._vt_key = vt_settings.args.get("AuthKey")
        else:
            self._vt_key = vt_key
        self._vt_client = vt.Client(apikey=vt_key)

    async def _lookup_ioc_async(self, observable: str, vt_type: str) -> pd.DataFrame:
        """
        Look up and single IoC observable.

        Parameters
        ----------
        observable: str
            The observable value
        vt_type: str
            The VT entity type

        Returns
        -------
            Attributes Pandas DataFrame with the properties of the entity

        Raises
        ------
        KeyError
            Unknown vt_type

        """
        if VTEntityType(vt_type) not in self._SUPPORTED_VT_TYPES:
            raise KeyError(
                f"Property type {vt_type} not supported",
                "Valid types are",
                ", ".join(x.value for x in VTEntityType.__members__.values()),
            )

        endpoint_name = self._get_endpoint_name(vt_type)
        try:
            response = self._vt_client.get_object(f"/{endpoint_name}/{observable}")
            return self._parse_vt_object(response)
        except vt.APIError as err:
            raise MsticpyVTNoDataError(
                "An error occurred requesting data from VirusTotal"
            ) from err

    def lookup_ioc(self, observable: str, vt_type: str) -> pd.DataFrame:
        """
        Look up and single IoC observable.

        Parameters
        ----------
        observable: str
            The observable value
        vt_type: str
            The VT entity type

        Returns
        -------
            Attributes Pandas DataFrame with the properties of the entity

        Raises
        ------
        KeyError
            Unknown vt_type

        """
        try:
            return _make_sync(self._lookup_ioc_async(observable, vt_type))
        finally:
            self._vt_client.close()

    async def _lookup_iocs_async(
        self,
        observables_df: pd.DataFrame,
        observable_column: str = ColumnNames.TARGET.value,
        observable_type_column: str = ColumnNames.TARGET_TYPE.value,
    ):
        """
        Look up and multiple IoC observables.

        Parameters
        ----------
        observables_df: pd.DataFrame
            A Pandas DataFrame, where each row is an observable
        observable_column:
            ID column of each observable
        observable_type_column:
            Type column of each observable

        Returns
        -------
            Future Attributes Pandas DataFrame with the properties of the entities

        Raises
        ------
        KeyError
            Column not found in observables_df

        """
        _observables_df = observables_df.reset_index()

        for column in [observable_column, observable_type_column]:
            if column not in _observables_df.columns:
                raise KeyError(f"Column {column} not found in observables_df")

        observables_list = _observables_df[observable_column]
        types_list = _observables_df[observable_type_column]
        dfs_futures = []
        for observable, observable_type in zip(observables_list, types_list):
            try:
                ioc_df_future = self._lookup_ioc_async(observable, observable_type)
                dfs_futures.append(ioc_df_future)
            except KeyError:
                print(
                    "ERROR\t It was not possible to obtain results for",
                    f"{observable_type} {observable}",
                )
        dfs = await asyncio.gather(*dfs_futures)
        return pd.concat(dfs) if dfs else pd.DataFrame()

    def lookup_iocs(
        self,
        observables_df: pd.DataFrame,
        observable_column: str = ColumnNames.TARGET.value,
        observable_type_column: str = ColumnNames.TARGET_TYPE.value,
    ):
        """
        Look up and multiple IoC observables.

        Parameters
        ----------
        observables_df: pd.DataFrame
            A Pandas DataFrame, where each row is an observable
        observable_column:
            ID column of each observable
        observable_type_column:
            Type column of each observable

        Returns
        -------
            Attributes Pandas DataFrame with the properties of the entities

        """
        try:
            return _make_sync(
                self._lookup_iocs_async(
                    observables_df, observable_column, observable_type_column
                )
            )
        finally:
            self._vt_client.close()

    async def _lookup_ioc_relationships_async(
        self, observable: str, vt_type: str, relationship: str, limit: int = None
    ):
        """
        Look up and single IoC observable relationships.

        Parameters
        ----------
        observable: str
            The observable value
        vt_type: str
            The VT entity type
        relationship: str
            Desired relationship
        limit: int
            Relations limit

        Returns
        -------
            Future Relationship Pandas DataFrame with the relationships of the entity

        Raises
        ------
        KeyError
            Unknown vt_type

        """
        if VTEntityType(vt_type) not in self._SUPPORTED_VT_TYPES:
            raise KeyError(f"Property type {vt_type} not supported")

        endpoint_name = self._get_endpoint_name(vt_type)
        response: vt.object.Object

        if limit is None:
            try:
                response = self._vt_client.get_object(
                    f"/{endpoint_name}/{observable}?relationship_counters=true"
                )
                relationships = response.relationships
                limit = (
                    relationships[relationship]["meta"]["count"]
                    if relationship in relationships
                    else 0
                )
            except KeyError:
                print(
                    f"ERROR: Could not obtain relationship limit for {vt_type} {observable}"
                )
                return pd.DataFrame()

        if limit == 0 or limit is None:
            return pd.DataFrame()

        try:
            # print(f"Obtaining {limit} relationships for {vt_type} {observable}")
            response = self._vt_client.iterator(
                f"/{endpoint_name}/{observable}/relationships/{relationship}",
                batch_size=40,
                limit=limit,
            )
            vt_objects = [self._parse_vt_object(r) for r in response]
            result_df = pd.concat(vt_objects) if vt_objects else pd.DataFrame()

            if vt_objects:
                # Inject source and target columns
                result_df[ColumnNames.SOURCE.value] = observable
                result_df[ColumnNames.SOURCE_TYPE.value] = VTEntityType(vt_type).value
                result_df[ColumnNames.RELATIONSHIP_TYPE.value] = relationship
                result_df.reset_index(inplace=True)
                result_df.rename(
                    columns={
                        ColumnNames.ID.value: ColumnNames.TARGET.value,
                        ColumnNames.TYPE.value: ColumnNames.TARGET_TYPE.value,
                    },
                    inplace=True,
                )
                result_df.set_index(
                    [ColumnNames.SOURCE.value, ColumnNames.TARGET.value], inplace=True
                )
        except vt.APIError as err:
            raise MsticpyVTNoDataError(
                "An error occurred requesting data from VirusTotal"
            ) from err

        return result_df

    def lookup_ioc_relationships(
        self, observable: str, vt_type: str, relationship: str, limit: int = None
    ) -> pd.DataFrame:
        """
        Look up and single IoC observable relationships.

        Parameters
        ----------
        observable: str
            The observable value
        vt_type: str
            The VT entity type
        relationship: str
            Desired relationship
        limit: int
            Relations limit

        Returns
        -------
            Relationship Pandas DataFrame with the relationships of the entity

        """
        try:
            return _make_sync(
                self._lookup_ioc_relationships_async(
                    observable, vt_type, relationship, limit
                )
            )
        finally:
            self._vt_client.close()

    async def _lookup_iocs_relationships_async(
        self,
        observables_df: pd.DataFrame,
        relationship: str,
        observable_column: str = ColumnNames.TARGET.value,
        observable_type_column: str = ColumnNames.TARGET_TYPE.value,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Look up and single IoC observable relationships.

        Parameters
        ----------
        observables_df: pd.DataFrame
            A Pandas DataFrame, where each row is an observable
        relationship: str
            Desired relationship
        observable_column:
            ID column of each observable
        observable_type_column:
            Type column of each observable.
        limit: int
            Relations limit

        Returns
        -------
            Future Relationship Pandas DataFrame with the relationships of each observable.

        Raises
        ------
        KeyError
            Column not found in observables_df

        """
        _observables_df = observables_df.reset_index()

        for column in [observable_column, observable_type_column]:
            if column not in _observables_df.columns:
                raise KeyError(f"Column {column} not found in observables df")

        observables_list = _observables_df[observable_column]
        types_list = _observables_df[observable_type_column]
        dfs_futures = []

        for observable, observable_type in zip(observables_list, types_list):
            try:
                result_df_future = self._lookup_ioc_relationships_async(
                    observable, observable_type, relationship, limit
                )
                dfs_futures.append(result_df_future)
            except KeyError:
                print(
                    "ERROR:\t It was not possible to get the data for",
                    f"{observable_type} {observable}",
                )
        dfs = await asyncio.gather(*dfs_futures)
        return pd.concat(dfs) if len(dfs) > 0 else pd.DataFrame()

    def lookup_iocs_relationships(
        self,
        observables_df: pd.DataFrame,
        relationship: str,
        observable_column: str = ColumnNames.TARGET.value,
        observable_type_column: str = ColumnNames.TARGET_TYPE.value,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Look up and single IoC observable relationships.

        Parameters
        ----------
        observables_df: pd.DataFrame
            A Pandas DataFrame, where each row is an observable
        relationship: str
            Desired relationship
        observable_column:
            ID column of each observable
        observable_type_column:
            Type column of each observable.
        limit: int
            Relations limit

        Returns
        -------
            Relationship Pandas DataFrame with the relationships of each observable.

        """
        try:
            return _make_sync(
                self._lookup_iocs_relationships_async(
                    observables_df,
                    relationship,
                    observable_column,
                    observable_type_column,
                    limit,
                )
            )

        finally:
            self._vt_client.close()

    def create_vt_graph(
        self, relationship_dfs: List[pd.DataFrame], name: str, private: bool
    ) -> str:
        """
        Create a VirusTotal Graph with a set of Relationship DataFrames.

        Parameters
        ----------
        relationship_dfs:
            List of Relationship DataFrames
        name:
            New graph name
        private
            Indicates if the Graph is private or not.

        Returns
        -------
            Graph ID

        Raises
        ------
            ValueError when private is not indicated.
            ValueError when there are no relationship DataFrames
            MsticpyVTGraphSaveGraphError when Graph can not be saved

        """
        if not relationship_dfs:
            raise ValueError("There are no relationship DataFrames")

        if not isinstance(private, bool):
            raise ValueError("Please indicate if Graph is private or not")

        concatenated_df = pd.concat(relationship_dfs).reset_index()

        # Create nodes DF, with source and target
        sources_df = (
            concatenated_df.groupby(ColumnNames.SOURCE.value)[
                ColumnNames.SOURCE_TYPE.value
            ]
            .first()
            .reset_index()
            .rename(
                columns={
                    ColumnNames.SOURCE.value: ColumnNames.ID.value,
                    ColumnNames.SOURCE_TYPE.value: ColumnNames.TYPE.value,
                }
            )
        )

        target_df = (
            concatenated_df.groupby(ColumnNames.TARGET.value)[
                ColumnNames.TARGET_TYPE.value
            ]
            .first()
            .reset_index()
            .rename(
                columns={
                    ColumnNames.TARGET.value: ColumnNames.ID.value,
                    ColumnNames.TARGET_TYPE.value: ColumnNames.TYPE.value,
                }
            )
        )

        nodes_df = pd.concat([sources_df, target_df])

        graph = VTGraph(self._vt_key, name=name, private=private)

        nodes = [
            {
                "node_id": row[ColumnNames.ID.value],
                "node_type": row[ColumnNames.TYPE.value],
            }
            for _, row in nodes_df.iterrows()
        ]

        graph.add_nodes(nodes)

        for _, row in concatenated_df.iterrows():
            graph.add_link(
                source_node=row[ColumnNames.SOURCE.value],
                target_node=row[ColumnNames.TARGET.value],
                connection_type=row[ColumnNames.RELATIONSHIP_TYPE.value],
            )
        try:
            graph.save_graph()
        except vt_graph_errs.SaveGraphError as graph_err:
            raise MsticpyVTGraphSaveGraphError(
                "Could not save Graph. %s" % ""
                if not private
                else "Please check you have Private Graph premium feature enabled in"
                "your subscription. It is possible to create public Graphs"
                "with 'private=False' input argument"
            ) from graph_err

        return graph.graph_id

    @staticmethod
    def render_vt_graph(graph_id: str, width: int = 800, height: int = 600):
        """
        Display a VTGraph in a Jupyter Notebook.

        Parameters
        ----------
        graph_id:
            Graph ID
        width
            Graph width.
        height
            Graph height

        """
        display(
            HTML(
                f"""
              <iframe
                src="https://www.virustotal.com/graph/embed/{graph_id}"
                width="{width}"
                height="{height}">
              </iframe>

            """
            )
        )

    def get_object(self, vt_id: str, vt_type: str) -> pd.DataFrame:
        """
        Return the full VT object as a DataFrame.

        Parameters
        ----------
        vt_id : str
            The ID of the object
        vt_type : str
            The type of object to query.

        Returns
        -------
        pd.DataFrame
            Single column DataFrame with attribute names as
            index and values as data column.

        Raises
        ------
        KeyError
            Unrecognized VT Type
        MsticpyVTNoDataError
            Error requesting data from VT.

        """
        if VTEntityType(vt_type) not in self._SUPPORTED_VT_TYPES:
            raise KeyError(
                f"Property type {vt_type} not supported",
                "Valid types are",
                ", ".join(x.value for x in VTEntityType.__members__.values()),
            )

        endpoint_name = self._get_endpoint_name(vt_type)
        try:
            response: vt.object.Object = self._vt_client.get_object(
                f"/{endpoint_name}/{vt_id}"
            )
            return _ts_to_pydate(
                pd.DataFrame(data=response.to_dict()).drop(columns=["id", "type"])
            )
        except vt.APIError as err:
            raise MsticpyVTNoDataError(
                "An error occurred requesting data from VirusTotal"
            ) from err
        finally:
            self._vt_client.close()


def _ts_to_pydate(data):
    """Replace Unix timestamps in VT data with Py/pandas Timestamp."""
    for date_col in (col for col in data.columns if col.endswith("_date")):
        data[date_col] = pd.to_datetime(data[date_col], unit="s", utc=True)
    return data
