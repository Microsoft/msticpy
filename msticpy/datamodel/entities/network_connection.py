# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""NetworkConnection Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .ip_address import IpAddress

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class NetworkConnection(Entity):
    """
    NetworkConnection Entity class.

    Attributes
    ----------
    SourceAddress : IPAddress
        NetworkConnection SourceAddress
    SourcePort : int
        NetworkConnection SourcePort
    DestinationAddress : IPAddress
        NetworkConnection DestinationAddress
    DestinationPort : int
        NetworkConnection DestinationPort
    Protocol : str
        NetworkConnection Protocol


    """

    ID_PROPERTIES = [
        "SourceAddress",
        "SourcePort",
        "DestinationAddress",
        "DestinationPort",
    ]

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
        self.SourceAddress: Optional[IpAddress] = None
        self.SourcePort: Optional[int] = None
        self.DestinationAddress: Optional[IpAddress] = None
        self.DestinationPort: Optional[int] = None
        self.Protocol: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return "{}:{} [{}]-> {}:{}".format(
            self.SourceAddress,
            self.SourcePort,
            self.Protocol,
            self.DestinationAddress,
            self.DestinationPort,
        )

    _entity_schema = {
        # SourceAddress (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.IP)
        "SourceAddress": "IpAddress",
        # SourcePort (type System.Nullable`1[System.Int32])
        "SourcePort": None,
        # DestinationAddress (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.IP)
        "DestinationAddress": "IpAddress",
        # DestinationPort (type System.Nullable`1[System.Int32])
        "DestinationPort": None,
        # Protocol (type System.Nullable`1[System.Net.Sockets.ProtocolType])
        "Protocol": None,
    }
