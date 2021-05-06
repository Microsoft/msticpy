# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""IoTDevice Entity class."""
from typing import Any, Mapping, Optional

from ..._version import VERSION
from ...common.utility import export
from .entity import Entity

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=invalid-name, too-many-instance-attributes


@export
class IoTDevice(Entity):
    """
    IoTDevice Entity class.

    Attributes
    ----------
    IoTHub : str
        IoTHub of the IoT device
    DeviceId : str
        DeviceId of the IoT device
    DeviceName : str
        DeviceName of the IoT device
    IoTSecurityAgentId : str
        IoTSecurityAgentId of the IoT device
    DeviceType : str
        DeviceType of the IoT device
    Source : str
        Source of the IoT device
    SourceRef : str
        SourceRef of the IoT device
    Manufacturer : str
        Manufacturer of the IoT device
    Model : str
        Model of the IoT device
    OperatingSystem : str
        OperatingSystem of the IoT device
    IpAddress : str
        IpAddress of the IoT device
    MacAddress : str
        MacAddress of the IoT device
    Protocols : str
        Protocols of the IoT device
    SerialNumber : str
        SerialNumber of the IoT device

    """

    ID_PROPERTIES = ["IoTHub", "DeviceId"]

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
        self.IoTHub: Optional[str] = None
        self.DeviceId: Optional[str] = None
        self.DeviceName: Optional[str] = None
        self.IoTSecurityAgentId: Optional[str] = None
        self.DeviceType: Optional[str] = None
        self.Source: Optional[str] = None
        self.SourceRef: Optional[str] = None
        self.Manufacturer: Optional[str] = None
        self.Model: Optional[str] = None
        self.OperatingSystem: Optional[str] = None
        self.IpAddress: Optional[str] = None
        self.MacAddress: Optional[str] = None
        self.Protocols: Optional[str] = None
        self.SerialNumber: Optional[str] = None

        super().__init__(src_entity=src_entity, **kwargs)

    @property
    def description_str(self):
        """Return Entity Description."""
        return self.DeviceName or self.__class__.__name__

    _entity_schema = {
        "IoTHub": None,
        "DeviceId": None,
        "DeviceName": None,
        "IoTSecurityAgentId": None,
        "DeviceType": None,
        "Source": None,
        "SourceRef": None,
        "Manufacturer": None,
        "Model": None,
        "OperatingSystem": None,
        "IpAddress": "IpAddress",
        "MacAddress": None,
        "Protocols": None,
        "SerialNumber": None,
    }
