# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Dns Entity class."""
from typing import Any, List, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .ip_address import IpAddress

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class Dns(Entity):
    """
    DNS Resolve Entity class.

    Attributes
    ----------
    DomainName : str
        DnsResolve DomainName
    IpAdresses : List[str]
        DnsResolve IpAdresses
    DnsServerIp : IPAddress
        DnsResolve DnsServerIp
    HostIpAddress : IPAddress
        DnsResolve HostIpAddress

    """

    ID_PROPERTIES = ["DomainName"]

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
        self.DomainName: Optional[str] = None
        self.IpAdresses: List[IpAddress] = []
        self.DnsServerIp: Optional[IpAddress] = None
        self.HostIpAddress: Optional[IpAddress] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.DomainName}: IPs: {repr(self.IpAdresses)}"

    _entity_schema = {
        # DomainName (type System.String)
        "DomainName": None,
        # IpAdresses (type System.Collections.Generic.List`1
        # [Microsoft.Azure.Security.Detection.AlertContracts.V3.Entities.IP])
        "IpAdresses": (List, "IpAddress"),
        # DnsServerIp (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.IP)
        "DnsServerIp": "IpAddress",
        # HostIpAddress (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.IP)
        "HostIpAddress": "IpAddress",
    }
