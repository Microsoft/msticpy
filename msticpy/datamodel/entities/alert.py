# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Alert Entity class."""
from datetime import datetime
from typing import Any, List, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class Alert(Entity):
    """
    Alert Entity class.

    Attributes
    ----------
    DisplayName : str
        Alert DisplayName
    CompromisedEntity : str
        Alert CompromisedEntity
    Count : int
        Alert Count
    StartTimeUtc : datetime
        Alert StartTimeUtc
    EndTimeUtc : datetime
        Alert EndTimeUtc
    Severity : str
        Alert Severity
    SystemAlertIds : List[str]
        Alert SystemAlertIds
    AlertType : str
        Alert AlertType
    VendorName : str
        Alert VendorName
    ProviderName : str
        Alert ProviderName

    """

    ID_PROPERTIES = ["SystemAlertIds"]

    def __init__(self, src_entity: Mapping[str, Any] = None, **kwargs):
        """
        Create a new instance of the entity type.

        Parameters
        ----------
        src_entity : Mapping[str, Any], optional
            Create entity from existing entity or
            other mapping object that implements entity properties.
            (the default is None)

        Other Parameters
        ----------------
        kwargs : Dict[str, Any]
            Supply the entity properties as a set of
            kw arguments.

        """
        self.DisplayName: Optional[str] = None
        self.CompromisedEntity: Optional[str] = None
        self.Count: Any = None
        self.StartTimeUtc: datetime = datetime.min
        self.EndTimeUtc: datetime = datetime.min
        self.Severity: Any = None
        self.SystemAlertIds: List[str] = []
        self.AlertType: Optional[str] = None
        self.VendorName: Optional[str] = None
        self.ProviderName: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)
        if src_entity is not None:
            if "AlertDisplayName" in src_entity:
                self.DisplayName = src_entity["AlertDisplayName"]
            if "SystemAlertId" in src_entity:
                self.SystemAlertIds.append(src_entity["SystemAlertId"])
            self._add_additional_data(src_entity)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.DisplayName} ({self.StartTimeUtc}) {self.CompromisedEntity}"

    def _add_additional_data(self, src_entity: Mapping[str, Any]):
        """Populate additional alert properties."""
        entity_props = set(self.__dict__.keys()) | {"AlertDisplayName", "SystemAlertId"}
        if isinstance(src_entity, dict):
            prop_list = src_entity.items()
        elif type(src_entity).__name__ == "SecurityAlert":
            prop_list = src_entity.properties.items()  # type: ignore
        # pylint: disable=all
        elif isinstance(src_entity, Mapping):
            prop_list = src_entity.iteritems()  # type: ignore
        # pylint: enable=all
        else:
            return

        for prop_name, prop in prop_list:
            if prop_name not in entity_props:
                self.AdditionalData[prop_name] = prop

    _entity_schema = {
        # DisplayName (type System.String)
        "DisplayName": None,
        # CompromisedEntity (type System.String)
        "CompromisedEntity": None,
        # Count (type System.Nullable`1[System.Int32])
        "Count": None,
        # StartTimeUtc (type System.Nullable`1[System.DateTime])
        "StartTimeUtc": None,
        # EndTimeUtc (type System.Nullable`1[System.DateTime])
        "EndTimeUtc": None,
        # Severity (type System.Nullable`1
        # [Microsoft.Azure.Security.Detection.AlertContracts.V3.Severity])
        "Severity": None,
        # SystemAlertIds (type System.Collections.Generic.List`1[System.String])
        "SystemAlertIds": None,
        # AlertType (type System.String)
        "AlertType": None,
        # VendorName (type System.String)
        "VendorName": None,
        # ProviderName (type System.String)
        "ProviderName": None,
    }
