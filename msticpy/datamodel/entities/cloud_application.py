# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""CloudApplication Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class CloudApplication(Entity):
    """
    CloudApplication Entity class.

    Attributes
    ----------
    Name : str
        CloudApplication Name
    AppId : str
        The AppId of the cloud application
    InstanceName : str
        The instance name of the application

    """

    ID_PROPERTIES = ["Name"]

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
        self.Name: Optional[str] = None
        self.AppId: Optional[str] = None
        self.InstanceName: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return self.Name or self.__class__.__name__

    _entity_schema = {
        # Name (type System.String)
        "Name": None,
        "AppId": None,
        "InstanceName": None,
    }
