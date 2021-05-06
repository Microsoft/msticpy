# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""FileHash Entity class."""
from typing import Any, Mapping

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity
from .entity_enums import Algorithm

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class FileHash(Entity):
    """
    File Hash class.

    Attributes
    ----------
    Algorithm : Algorithm
        FileHash Algorithm
    Value : str
        FileHash Value

    """

    ID_PROPERTIES = ["Value"]

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
        self.Algorithm: Algorithm = Algorithm.Unknown
        self.Value: str = ""
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return f"{self.Algorithm}: {self.Value}"

    _entity_schema = {
        # The hash algorithm (type System.String)
        "Algorithm": "Algorithm",
        # Value (type System.String)
        "Value": None,
    }
