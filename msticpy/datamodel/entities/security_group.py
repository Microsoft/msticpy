# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""SecurityGroup Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class SecurityGroup(Entity):
    """
    SecurityGroup Entity class.

    Attributes
    ----------
    DistinguishedName : str
        SecurityGroup DistinguishedName
    SID : str
        SecurityGroup SID
    ObjectGuid : str
        SecurityGroup ObjectGuid

    """

    ID_PROPERTIES = ["DistinguishedName", "SID", "ObjectGuid"]

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
        self.DistinguishedName: Optional[str] = None
        self.SID: Optional[str] = None
        self.ObjectGuid: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self):
        """Return Entity Description."""
        return self.DistinguishedName or self.__class__.__name__

    _entity_schema = {
        # DistinguishedName (type System.String)
        "DistinguishedName": None,
        # SID (type System.String)
        "SID": None,
        # ObjectGuid (type System.String)
        "ObjectGuid": None,
    }
