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
from .entity_enums import RegistryHive

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class RegistryKey(Entity):
    """
    RegistryKey Entity class.

    Attributes
    ----------
    Hive : RegistryHive
        RegistryKey Hive
    Key : str
        RegistryKey Key

    """

    ID_PROPERTIES = ["Hive", "Key"]

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
        self.Hive: Optional[RegistryHive] = None
        self.Key: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.Hive}\\{self.Key}"

    _entity_schema = {
        # Hive (type System.Nullable`1
        # [Microsoft.Azure.Security.Detection.AlertContracts.V3.Entities.RegistryHive])
        "Hive": "RegistryHive",
        # Key (type System.String)
        "Key": None,
    }
