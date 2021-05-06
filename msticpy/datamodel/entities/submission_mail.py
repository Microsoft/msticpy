# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Submission mail Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name


@export
class SubmissionMail(Entity):
    """
    SubmissionMail Entity class.

    Attributes
    ----------
    SubmissionId : str
        SubmissionId of the submission mail
    SubmissionDate : datetime
        SubmissionDate of the submission mail
    Submitter : str
        Submitter email of the submission mail
    NetworkMessageId : str
        NetworkMessageId of the submission mail
    Timestamp : datetime
        The Time stamp when the message is received
    Recipient : str
        Recipient of the submission mail
    Sender : str
        Sender of the submission mail
    SenderIp : str
        SenderIp of the submission mail
    Subject : str
        Subject of the submission mail
    ReportType : str
        ReportType of the submission mail

    """

    ID_PROPERTIES = ["NetworkMessageId", "Recipient"]

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
        self.SubmissionId: Optional[str] = None
        self.SubmissionDate: Any = None
        self.Submitter: Optional[str] = None
        self.NetworkMessageId: Optional[str] = None
        self.Timestamp: Any = None
        self.Recipient: Optional[str] = None
        self.Sender: Optional[str] = None
        self.SenderIp: Optional[str] = None
        self.Subject: Optional[str] = None
        self.ReportType: Optional[str] = None

        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self):
        """Return Entity Description."""
        return self.SubmissionId or self.__class__.__name__

    _entity_schema = {
        "SubmissionId": None,
        "SubmissionDate": None,
        "Submitter": None,
        "NetworkMessageId": None,
        "Timestamp": None,
        "Recipient": None,
        "Sender": None,
        "SenderIp": None,
        "Subject": None,
        "ReportType": None,
    }
