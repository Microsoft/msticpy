# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Process Entity class."""
from datetime import datetime
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .account import Account
from .entity_enums import ElevationToken
from .file import File
from .host import Host
from .host_logon_session import HostLogonSession

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name, too-many-instance-attributes


@export
class Process(Entity):
    """
    Process Entity class.

    Attributes
    ----------
    ProcessId : str
        Process ProcessId
    CommandLine : str
        Process CommandLine
    ElevationToken : str
        Process ElevationToken
    CreationTimeUtc : datetime
        Process CreationTimeUtc
    ImageFile : File
        Process ImageFile
    Account : Account
        Process Account
    ParentProcess : Process
        Process ParentProcess
    Host : Host
        Process Host
    LogonSession : HostLogonSession
        Process LogonSession

    """

    ID_PROPERTIES = ["ProcessId", "ImageFile", "CreationTimeUtc", "CommandLine"]

    def __init__(
        self,
        src_entity: Mapping[str, Any] = None,
        src_event: Mapping[str, Any] = None,
        role="new",
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
        role : str, optional
            'new' or 'parent' - only relevant if the entity
            is being constructed from an event.
            (the default is 'new')

        Other Parameters
        ----------------
        kwargs : Dict[str, Any]
            Supply the entity properties as a set of
            kw arguments.

        """
        self.ProcessId: Optional[str] = None
        self.CommandLine: Optional[str] = None
        self.ElevationToken: Optional[ElevationToken] = None
        self.CreationTimeUtc: datetime = datetime.min
        self.ImageFile: Optional[File] = None
        self.Account: Optional[Account] = None
        self.ParentProcess: Optional[Process] = None
        self.Host: Optional[Host] = None
        self.LogonSession: Optional[HostLogonSession] = None
        super().__init__(src_entity=src_entity, **kwargs)

        # pylint: disable=locally-disabled, line-too-long
        if src_event is not None:
            self._create_from_event(src_event, role)

    def _create_from_event(self, src_event, role):
        if role == "new":
            self.ProcessId = (
                src_event["NewProcessId"] if "NewProcessId" in src_event else None
            )
            self.CommandLine = (
                src_event["CommandLine"] if "CommandLine" in src_event else None
            )
            if "TimeCreatedUtc" in src_event:
                self.CreationTimeUtc = src_event["TimeCreatedUtc"]
            elif "TimeGenerated" in src_event:
                self.CreationTimeUtc = src_event["TimeGenerated"]
            self.ProcessId = (
                src_event["NewProcessId"] if "NewProcessId" in src_event else None
            )
            self.ImageFile = File(src_event=src_event, role="new")
            self.Account = Account(src_event=src_event, role="subject")

            if "ParentProcessName" in src_event or "ProcessName" in src_event:
                parent = Process(src_event=src_event, role="parent")
                self.ParentProcess = parent

            # Linux properties
            self.success = src_event["success"] if "success" in src_event else None
            self.audit_user = (
                src_event["audit_user"] if "audit_user" in src_event else None
            )
            self.auid = src_event["auid"] if "auid" in src_event else None
            self.group = src_event["group"] if "group" in src_event else None
            self.gid = src_event["gid"] if "gid" in src_event else None
            self.effective_user = (
                src_event["effective_user"] if "effective_user" in src_event else None
            )
            self.euid = src_event["euid"] if "euid" in src_event else None
            self.effective_group = (
                src_event["effective_group"] if "effective_group" in src_event else None
            )
            self.egid = (
                src_event["effective_group"] if "effective_group" in src_event else None
            )
            self.cwd = src_event["cwd"] if "cwd" in src_event else None
            self.name = src_event["cwd"] if "cwd" in src_event else None
        else:
            self.ProcessId = (
                src_event["ProcessId"] if "ProcessId" in src_event else None
            )
            self.ImageFile = File(src_event=src_event, role="parent")

    @property
    def ProcessName(self) -> Optional[str]:  # noqa: N802
        """Return the name of the process file."""
        file = self["ImageFile"]
        return file.Name if file else None

    @property
    def ProcessFilePath(self) -> Optional[str]:  # noqa: N802
        """Return the name of the process file path."""
        file = self["ImageFile"]
        return file.FullPath if file else None

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        if self.ProcessFilePath:
            return f"{self.ProcessFilePath}: {self.CommandLine}"
        return self.__class__.__name__

    _entity_schema = {
        # ProcessId (type System.String)
        "ProcessId": None,
        # CommandLine (type System.String)
        "CommandLine": None,
        # ElevationToken (type System.Nullable`1
        # [Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.ElevationToken])
        "ElevationToken": None,
        # CreationTimeUtc (type System.Nullable`1[System.DateTime])
        "CreationTimeUtc": None,
        # ImageFile (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.File)
        "ImageFile": "File",
        # Account (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.Account)
        "Account": "Account",
        # ParentProcess (type Microsoft.Azure.Security.Detection.AlertContracts
        # .V3.Entities.Process)
        "ParentProcess": "Process",
        # Host (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.Host)
        "Host": "Host",
        # Host (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.HostLogonSession)
        "LogonSession": "HostLogonSession",
    }
