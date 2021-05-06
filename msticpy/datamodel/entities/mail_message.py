# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""MailMessage Entity class."""
from typing import Any, List, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name, too-many-instance-attributes


@export
class MailMessage(Entity):
    """
    MailMessage Entity class.

    Attributes
    ----------
    Recipient : str
        Recipient of the Mail message
    Files : List[Entity]
        Files of the Mail message
    Urls : List[str]
        Urls of the Mail message
    Threats : List[str]
        Threats of the Mail message
    Sender : str
        Sender of the Mail message
    P1Sender : str
        P1Sender of the Mail message
    P1SenderDisplayName : str
        P1SenderDisplayName of the Mail message
    P1SenderDomain : str
        P1SenderDomain of the Mail message
    SenderIP : str
        SenderIP of the Mail message
    P2Sender : str
        P2Sender of the Mail message
    P2SenderDisplayName : str
        P2SenderDisplayName of the Mail message
    P2SenderDomain : str
        P2SenderDomain of the Mail message
    ReceivedDate : datetime
        ReceivedDate of the Mail message
    NetworkMessageId : str
        NetworkMessageId of the Mail message
    InternetMessageId : str
        InternetMessageId of the Mail message
    Subject : str
        Subject of the Mail message
    BodyFingerprintBin1 : str
        BodyFingerprintBin1 of the Mail message
    BodyFingerprintBin2 : str
        BodyFingerprintBin2 of the Mail message
    BodyFingerprintBin3 : str
        BodyFingerprintBin3 of the Mail message
    BodyFingerprintBin4 : str
        BodyFingerprintBin4 of the Mail message
    BodyFingerprintBin5 : str
        BodyFingerprintBin5 of the Mail message
    AntispamDirection : str
        AntispamDirection of the Mail message
    DeliveryAction : str
        DeliveryAction of the Mail message
    DeliveryLocation : str
        DeliveryLocation of the Mail message
    Language : str
        Language of the Mail message
    ThreatDetectionMethods : str
        ThreatDetectionMethods of the Mail message

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
        self.Recipient: Optional[str] = None
        self.Files: List[Entity] = []
        self.Urls: List[str] = []
        self.Threats: List[str] = []
        self.Sender: Optional[str] = None
        self.P1Sender: Optional[str] = None
        self.P1SenderDisplayName: Optional[str] = None
        self.P1SenderDomain: Optional[str] = None
        self.SenderIP: Optional[str] = None
        self.P2Sender: Optional[str] = None
        self.P2SenderDisplayName: Optional[str] = None
        self.P2SenderDomain: Optional[str] = None
        self.ReceivedDate: Any = None
        self.NetworkMessageId: Optional[str] = None
        self.InternetMessageId: Optional[str] = None
        self.Subject: Optional[str] = None
        self.BodyFingerprintBin1: Optional[str] = None
        self.BodyFingerprintBin2: Optional[str] = None
        self.BodyFingerprintBin3: Optional[str] = None
        self.BodyFingerprintBin4: Optional[str] = None
        self.BodyFingerprintBin5: Optional[str] = None
        self.AntispamDirection: Optional[str] = None
        self.DeliveryAction: Optional[str] = None
        self.DeliveryLocation: Optional[str] = None
        self.Language: Optional[str] = None
        self.ThreatDetectionMethods: Optional[str] = None

        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self):
        """Return Entity Description."""
        return self.NetworkMessageId or self.__class__.__name__

    _entity_schema = {
        "Recipient": None,
        "Files": (list, "File"),
        "Urls": None,
        "Threats": None,
        "Sender": None,
        "P1Sender": None,
        "P1SenderDisplayName": None,
        "P1SenderDomain": None,
        "SenderIP": None,
        "P2Sender": None,
        "P2SenderDisplayName": None,
        "P2SenderDomain": None,
        "ReceivedDate": None,
        "NetworkMessageId": None,
        "InternetMessageId": None,
        "Subject": None,
        "BodyFingerprintBin1": None,
        "BodyFingerprintBin2": None,
        "BodyFingerprintBin3": None,
        "BodyFingerprintBin4": None,
        "BodyFingerprintBin5": None,
        "AntispamDirection": None,
        "DeliveryAction": None,
        "DeliveryLocation": None,
        "Language": None,
        "ThreatDetectionMethods": None,
    }
