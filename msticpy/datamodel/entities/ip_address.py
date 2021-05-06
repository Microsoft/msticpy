# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""IpAddress Entity class."""
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any, List, Mapping, Optional, Union

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .geo_location import GeoLocation
from .threat_intelligence import Threatintelligence

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class IpAddress(Entity):
    """
    IPAddress Entity class.

    Attributes
    ----------
    Address : str
        IpAddress Address
    Location : GeoLocation
        IpAddress Location
    ThreatIntelligence : List[Threatintelligence]
        IpAddress ThreatIntelligence

    """

    ID_PROPERTIES = ["Address"]

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
        self.Address: str = ""
        self.Location: Optional[GeoLocation] = None
        self.ThreatIntelligence: List[Threatintelligence] = []
        super().__init__(src_entity=src_entity, **kwargs)

        if src_event is not None and "IpAddress" in src_event:
            self.Address = src_event["IpAddress"]

    @property
    def ip_address(self) -> Union[IPv4Address, IPv6Address, None]:
        """Return a python IP address object from the entity property."""
        try:
            return ip_address(self.Address)
        except ValueError:
            return None

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return self.Address

    _entity_schema = {
        # Address (type System.String)
        "Address": None,
        # Location (type Microsoft.Azure.Security.Detection.AlertContracts
        # .V3.ContextObjects.GeoLocation)
        "Location": "GeoLocation",
        # ThreatIntelligence (type System.Collections.Generic.List`1
        # [Microsoft.Azure.Security.Detection.AlertContracts.V3
        # .ContextObjects.ThreatIntelligence])
        "ThreatIntelligence": (list, "Threatintelligence"),
    }


# Alias for IpAddress
Ip = IpAddress
