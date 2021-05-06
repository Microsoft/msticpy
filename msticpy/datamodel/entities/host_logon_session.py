# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""HostLogonSession Entity class."""
from datetime import datetime
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .account import Account
from .host import Host

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class HostLogonSession(Entity):
    """
    HostLogonSession Entity class.

    Attributes
    ----------
    Account : Account
        HostLogonSession Account
    StartTimeUtc : datetime
        HostLogonSession StartTimeUtc
    EndTimeUtc : datetime
        HostLogonSession EndTimeUtc
    Host : Host
        HostLogonSession Host
    SessionId : str
        HostLogonSession SessionId

    """

    ID_PROPERTIES = ["Account", "Host", "SessionId"]

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
        self.Account: Optional[Account] = None
        self.StartTimeUtc: datetime = datetime.min
        self.EndTimeUtc: datetime = datetime.min
        self.Host: Optional[Host] = None
        self.SessionId: str = ""
        super().__init__(src_entity=src_entity, **kwargs)

        if src_event is not None:
            if "TimeCreatedUtc" in src_event:
                self.StartTimeUtc = src_event["TimeCreatedUtc"]
            elif "TimeGenerated" in src_event:
                self.StartTimeUtc = src_event["TimeGenerated"]
            self.EndTimeUtc = self.StartTimeUtc
            self.SessionId = (
                src_event["TargetLogonId"] if "TargetLogonId" in src_event else None
            )

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        if self.Host:
            return f"{self.Host.HostName}: session: {self.SessionId}"
        return self.__class__.__name__

    _entity_schema = {
        # Account
        "Account": "Account",
        # StartTimeUtc (type System.Nullable`1[System.DateTime])
        "StartTimeUtc": None,
        # EndTimeUtc (type System.Nullable`1[System.DateTime])
        "EndTimeUtc": None,
        # Host
        "Host": "Host",
        # SessionId (type System.String)
        "SessionId": None,
    }
