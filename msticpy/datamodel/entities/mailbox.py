# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Mailbox Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class Mailbox(Entity):
    """
    Mailbox Entity class.

    Attributes
    ----------
    MailboxPrimaryAddress : str
        PrimaryAddress of the Mailbox
    DisplayName : str
        DisplayName of the Mailbox
    Upn : str
        Upn of the Mailbox
    ExternalDirectoryObjectId : str
        ExternalDirectoryObjectId of the Mailbox
    RiskLevel : str
        RiskLevel of the Mailbox

    """

    ID_PROPERTIES = ["MailboxPrimaryAddress"]

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
        self.MailboxPrimaryAddress: Optional[str] = None
        self.DisplayName: Optional[str] = None
        self.Upn: Optional[str] = None
        self.ExternalDirectoryObjectId: Optional[str] = None
        self.RiskLevel: Optional[str] = None

        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self):
        """Return Entity Description."""
        return self.MailboxPrimaryAddress or self.__class__.__name__

    _entity_schema = {
        "MailboxPrimaryAddress": None,
        "DisplayName": None,
        "Upn": None,
        "ExternalDirectoryObjectId": None,
        "RiskLevel": None,
    }
