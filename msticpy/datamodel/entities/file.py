# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""File Entity class."""
from typing import Any, List, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .entity_enums import Algorithm, OSFamily
from .file_hash import FileHash
from .host import Host

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name, too-many-instance-attributes


@export
class File(Entity):
    """
    File Entity class.

    Attributes
    ----------
    FullPath : str
        File FullPath
    Directory : str
        File Directory
    Name : str
        File Name
    Md5 : str
        File Md5
    Host : str
        File Host
    Sha1 : str
        File Sha1
    Sha256 : str
        File Sha256
    Sha256Ac : str
        File Sha256Ac
    FileHashes : List[FileHash]
        File FileHashes

    """

    ID_PROPERTIES = ["FullPath", "Sha1", "Sha256", "Sha256ac", "Md5"]

    def __init__(
        self,
        src_entity: Mapping[str, Any] = None,
        src_event: Mapping[str, Any] = None,
        role: str = "new",
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
        self.FullPath: Optional[str] = None
        self.Directory: Optional[str] = None
        self.Name: Optional[str] = None
        self.Md5: Optional[str] = None
        self.Host: Optional[Host] = None
        self.Sha1: Optional[str] = None
        self.Sha256: Optional[str] = None
        self.Sha256Ac: Optional[str] = None
        self.FileHashes: List[FileHash] = []
        self.PathSeparator: Optional[str] = "\\"
        self.OSFamily = OSFamily.Windows
        super().__init__(src_entity=src_entity, **kwargs)
        if src_event is not None:
            self._create_from_event(src_event, role)

        if not self.FullPath:
            file_name = self.Name
            directory = self.Directory or ""
            sep = self.path_separator if directory else ""
            self.FullPath = f"{directory}{sep}{file_name}"

    @property
    def path_separator(self):
        """Return the path separator used by the file."""
        if (
            self.Directory and "/" in self.Directory
        ) or self.OSFamily != OSFamily.Windows:
            return "/"
        return "\\"

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return self.FullPath or self.__class__.__name__

    def _create_from_event(self, src_event, role):
        if role == "new" and "NewProcessName" in src_event:
            self._add_paths(src_event["NewProcessName"])
        elif role == "parent" and "ParentProcessName" in src_event:
            self._add_paths(src_event["ParentProcessName"])

    _entity_schema = {
        # FullPath (type System.String)
        "FullPath": None,
        # Directory (type System.String)
        "Directory": None,
        # Name (type System.String)
        "Name": None,
        # Md5 (type System.String)
        "Md5": None,
        # Host (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.Host)
        "Host": "Host",
        # Sha1 (type System.String)
        "Sha1": None,
        # Sha256 (type System.String)
        "Sha256": None,
        # Sha256Ac (type System.String)
        "Sha256Ac": None,
        "FileHashes": (list, "FileHash"),
    }

    def _add_paths(self, full_path):
        if "/" in full_path:
            self.PathSeparator = "/"
            self.OSFamily = OSFamily.Linux
        else:
            self.PathSeparator = "\\"
            self.OSFamily = OSFamily.Windows

        self.FullPath = full_path
        self.Name = full_path.split(self.PathSeparator)[-1]
        self.Directory = full_path.split(self.PathSeparator)[:-1]

    @property
    def file_hash(self) -> Optional[str]:
        """
        Return the first defined file hash.

        Returns
        -------
        Optional[str]
            Returns first-defined file hash in order of
            SHA256, SHA1, MD5, SHA256AC (authenticode)

        """
        if self.FileHashes:
            alg_order = {
                Algorithm.SHA256: 0,
                Algorithm.SHA1: 1,
                Algorithm.MD5: 2,
                Algorithm.SHA256AC: 3,
            }

            return next(
                iter(
                    sorted(
                        self.FileHashes,
                        key=lambda f_hash: alg_order.get(f_hash.Algorithm, 10),
                    )
                )
            ).Value

        return self.Sha256 or self.Sha1 or self.Md5 or self.Sha256Ac
