# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Host Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .entity_enums import OSFamily

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class Host(Entity):
    """
    Host Entity class.

    Attributes
    ----------
    DnsDomain : str
        Host DnsDomain
    NTDomain : str
        Host NTDomain
    HostName : str
        Host HostName
    NetBiosName : str
        Host NetBiosName
    AzureID : str
        Host AzureID
    OMSAgentID : str
        Host OMSAgentID
    OSFamily : str
        Host OSFamily
    OSVersion : str
        Host OSVersion
    IsDomainJoined : bool
        Host IsDomainJoined

    """

    ID_PROPERTIES = ["fqdn", "AzureID", "OMSAgentID"]

    def __init__(
        self,
        src_entity: Mapping[str, Any] = None,
        src_event: Mapping[str, Any] = None,
        **kwargs,
    ):
        """
        Create a new instance of the entity type.

        Parameters
        ----------
        src_entity : Mapping[str, Any], optional
            Create entity from existing entity or
            other mapping object that implements entity properties.
            (the default is None)
        src_event : Mapping[str, Any], optional
            Create entity from event properties
            (the default is None)

        Other Parameters
        ----------------
        kwargs : Dict[str, Any]
            Supply the entity properties as a set of
            kw arguments.

        """
        self.DnsDomain: Optional[str] = None
        self.NTDomain: Optional[str] = None
        self.HostName: Optional[str] = None
        self.NetBiosName: Optional[str] = None
        self.AzureID: Optional[str] = None
        self.OMSAgentID: Optional[str] = None
        self.OSFamily: OSFamily = OSFamily.Windows
        self.OSVersion: Optional[str] = None
        self.IsDomainJoined: bool = False

        super().__init__(src_entity=src_entity, **kwargs)
        self._computer = None
        if src_event is not None:
            self._create_from_event(src_event)

    @property
    def computer(self) -> Optional[str]:
        """Return computer from source event."""
        return self._computer if self._computer is not None else self.fqdn

    @property
    def fqdn(self) -> Optional[str]:
        """Construct FQDN from host + dns."""
        if self.DnsDomain:
            return f"{self.HostName}.{self.DnsDomain}"
        return self.HostName

    @property
    def FullName(self) -> Optional[str]:  # noqa: N802
        """Return the full name of the host - either FQDN or Netbiosname."""
        if self.DnsDomain:
            return f"{self.HostName or self.NetBiosName}.{self.DnsDomain}"
        if self.NTDomain:
            return f"{self.HostName or self.NetBiosName}.{self.NTDomain}"
        return self.HostName or self.NetBiosName

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.fqdn} ({self.OSFamily})"

    def _create_from_event(self, src_event):
        self._computer = src_event["Computer"]
        if "." in src_event["Computer"]:
            self.HostName = src_event["Computer"].split(".", 1)[0]
            self.DnsDomain = src_event["Computer"].split(".", 1)[1]
        else:
            self.HostName = src_event["Computer"]
        self.NetBiosName = self.HostName

    _entity_schema = {
        # DnsDomain (type System.String)
        "DnsDomain": None,
        # NTDomain (type System.String)
        "NTDomain": None,
        # HostName (type System.String)
        "HostName": None,
        # NetBiosName (type System.String)
        "NetBiosName": None,
        # AzureID (type System.String)
        "AzureID": None,
        # OMSAgentID (type System.String)
        "OMSAgentID": None,
        # OSFamily (type System.Nullable`1
        # [Microsoft.Azure.Security.Detection.AlertContracts.V3.Entities.OSFamily])
        "OSFamily": "OSFamily",
        # IsDomainJoined (type System.Nullable`1[System.Boolean])
        "IsDomainJoined": None,
    }
