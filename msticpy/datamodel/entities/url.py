# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Url Entity class."""
from typing import Any, Dict, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from ...sectools.domain_utils import url_components
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class Url(Entity):
    """
    URL Entity.

    Attributes
    ----------
    Url : str
        The URL

    """

    ID_PROPERTIES = ["Url"]

    def __init__(self, src_entity: Mapping[str, Any] = None, **kwargs):
        """
        Create a new instance of the entity type.

            :param src_entity: instantiate entity using properties of src entity
            :param kwargs: key-value pair representation of entity
        """
        self.Url: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return self.Url or super().description_str

    def __getitem__(self, key: str):
        """Allow property get using dictionary key syntax."""
        if self.Url:
            val = url_components(self.Url).get(key)
            if val:
                return val
        return super().__getitem__(key)

    def __getattr__(self, name: str):
        """Return the value of the named property 'name'."""
        if self.Url:
            val = url_components(self.Url).get(name)
            if val:
                return val
        return super().__getattr__(name)

    _entity_schema: Dict[str, Any] = {
        # Url (type System.String)
        "Url": None,
    }
