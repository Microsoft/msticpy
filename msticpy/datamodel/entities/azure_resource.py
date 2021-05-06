# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""AzureResource Entity class."""
from itertools import islice
import re
from typing import Any, Dict, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"

# pylint: disable=invalid-name


@export
class AzureResource(Entity):
    """
    AzureResource Entity class.

    Attributes
    ----------
    ResourceId : str
        AzureResource ResourceId
    ResourceIdParts : Dict[str, str]
        AzureResource ResourceIdParts

    """

    ID_PROPERTIES = ["ResourceId"]

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
        self.ResourceId: Optional[str] = None
        self.ResourceIdParts: Dict[str, str] = {}
        self.Url: Optional[str] = None
        super().__init__(src_entity=src_entity, **kwargs)
        if self.ResourceId and not self.ResourceIdParts:
            self._extract_resource_parts()

    @property
    def description_str(self) -> str:
        """Return Entity Description."""
        return self.ResourceId or self.__class__.__name__

    @property
    def SubscriptionId(self):  # noqa
        """Return the subscription Id or None."""
        return self.ResourceIdParts.get("subscriptions")

    @property
    def ResourceGroup(self):  # noqa
        """Return the ResourceGroup name or None."""
        return self.ResourceIdParts.get("resourceGroups")

    @property
    def Provider(self):  # noqa
        """Return the Provider name or None."""
        return self.ResourceIdParts.get("providers")

    _entity_schema = {
        # ResourceId (type System.String)
        "ResourceId": None,
        # ResourceIdParts (type System.Collections.Generic.IReadOnlyDictionary`2
        # [System.String,System.String])
        "ResourceIdParts": None,
    }

    def _extract_resource_parts(self):
        res_match = re.search("/resource/(?P<res_path>.+)", self.ResourceId)
        if not res_match:
            return
        res_elems = res_match.groupdict().get("res_path", "").split("/")
        keys = islice(res_elems, 0, len(res_elems), 2)
        vals = islice(res_elems, 1, len(res_elems), 2)
        self.ResourceIdParts = dict(zip(keys, vals))
