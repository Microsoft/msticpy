# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Entity sub-package."""
import difflib

from .account import Account
from .alert import Alert
from .azure_resource import AzureResource
from .cloud_application import CloudApplication
from .dns import Dns
from .entity import Entity
from .entity_enums import (  # noqa: F401
    Algorithm,
    ElevationToken,
    OSFamily,
    RegistryHive,
)
from .file import File
from .file_hash import FileHash
from .geo_location import GeoLocation
from .host import Host
from .host_logon_session import HostLogonSession
from .iot_device import IoTDevice
from .ip_address import IpAddress
from .mailbox import Mailbox
from .mail_cluster import MailCluster
from .mail_message import MailMessage
from .malware import Malware
from .network_connection import NetworkConnection
from .process import Process
from .registry_key import RegistryKey
from .registry_value import RegistryValue
from .security_group import SecurityGroup
from .submission_mail import SubmissionMail
from .threat_intelligence import Threatintelligence
from .unknown_entity import UnknownEntity
from .url import Url

# Dictionary to map text names of types to the class.
Entity.ENTITY_NAME_MAP.update(
    {
        "account": Account,
        "azureresource": AzureResource,
        "host": Host,
        "process": Process,
        "file": File,
        "cloudapplication": CloudApplication,
        "dnsresolve": Dns,
        "ipaddress": IpAddress,
        "iotdevice": IoTDevice,
        "ip": IpAddress,
        "networkconnection": NetworkConnection,
        "mailbox": Mailbox,
        "mail-message": MailMessage,
        "mail-cluster": MailCluster,
        "malware": Malware,
        "registry-key": RegistryKey,
        "registrykey": RegistryKey,
        "registry-value": RegistryValue,
        "registryvalue": RegistryValue,
        "host-logon-session": HostLogonSession,
        "hostlogonsession": HostLogonSession,
        "filehash": FileHash,
        "security-group": SecurityGroup,
        "securitygroup": SecurityGroup,
        "SubmissionMail": SubmissionMail,
        "alerts": Alert,
        "alert": Alert,
        "threatintelligence": Threatintelligence,
        "url": Url,
        "unknown": UnknownEntity,
        "geolocation": GeoLocation,
    }
)


def find_entity(entity):
    """Find entity name."""
    entity_cf = entity.casefold()
    entity_classes = {
        cls.__name__.casefold(): cls for cls in Entity.ENTITY_NAME_MAP.values()
    }
    if entity_cf in Entity.ENTITY_NAME_MAP.keys():
        print(f"Match found '{Entity.ENTITY_NAME_MAP[entity].__name__}'")
        return Entity.ENTITY_NAME_MAP[entity]
    if entity_cf in entity_classes:
        print(f"Match found '{entity_classes[entity_cf].__name__}'")
        return entity_classes[entity_cf]
    # Try to find the closest matches
    closest = difflib.get_close_matches(entity, entity_classes.keys(), cutoff=0.4)
    mssg = [f"No exact match found for '{entity}'. "]
    if len(closest) == 1:
        mssg.append(f"Closest match is '{entity_classes[closest[0]].__name__}'")
    elif closest:
        match_list = [f"'{entity_classes[mtch].__name__}'" for mtch in closest]
        mssg.append(f"Closest matches are {', '.join(match_list)}")
    else:
        mssg.extend(
            [
                "No close match found. Entities available:",
                *(cls.__name__ for cls in entity_classes.values()),
            ]
        )
    print("\n".join(mssg))
    return None
