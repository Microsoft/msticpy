# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""RegistryValue Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .registry_key import RegistryKey


__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class RegistryValue(Entity):
    """
    RegistryValue Entity class.

    Attributes
    ----------
    Key : str
        RegistryValue Key
    Name : str
        RegistryValue Name
    Value : str
        RegistryValue Value
    ValueType : str
        RegistryValue ValueType

    """

    ID_PROPERTIES = ["Key", "Name", "Value"]

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
        self.Key: Optional[RegistryKey] = None
        self.Name: Optional[str] = None
        self.Value: Optional[str] = None
        self.ValueType: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.Name}[{self.ValueType}]:{repr(self.Value)}"

    _entity_schema = {
        # Key (type Microsoft.Azure.Security.Detection
        # .AlertContracts.V3.Entities.RegistryKey)
        "Key": "RegistryKey",
        # Name (type System.String)
        "Name": None,
        # Value (type System.String)
        "Value": None,
        # ValueType (type System.Nullable`1[Microsoft.Win32.RegistryValueKind])
        "ValueType": None,
    }
