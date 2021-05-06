# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Entity enumerations."""
from enum import Enum
from typing import Dict, Type

from ..._version import VERSION
from ...common.utility import export

__version__ = VERSION
__author__ = "Ian Hellen"


ENTITY_ENUMS: Dict[str, Type] = {}


# pylint: disable=invalid-name
@export
class Algorithm(Enum):
    """FileHash Algorithm Enumeration."""

    Unknown = 0
    MD5 = 1
    SHA1 = 2
    SHA256 = 3
    SHA256AC = 4


@export
class ElevationToken(Enum):
    """ElevationToken enumeration."""

    Default = 0
    Full = 1
    Limited = 2


@export
class OSFamily(Enum):
    """OSFamily enumeration."""

    Linux = 0
    Windows = 1


@export
class RegistryHive(Enum):
    """RegistryHive enumeration."""

    # <summary>HKEY_LOCAL_MACHINE</summary>
    HKEY_LOCAL_MACHINE = 0
    # <summary>HKEY_CLASSES_ROOT</summary>
    HKEY_CLASSES_ROOT = 1
    # <summary>HKEY_CURRENT_CONFIG</summary>
    HKEY_CURRENT_CONFIG = 2
    # <summary>HKEY_USERS</summary>
    HKEY_USERS = 3
    # <summary>HKEY_CURRENT_USER_LOCAL_SETTINGS</summary>
    HKEY_CURRENT_USER_LOCAL_SETTINGS = 4
    # <summary>HKEY_PERFORMANCE_DATA</summary>
    HKEY_PERFORMANCE_DATA = 5
    # <summary>HKEY_PERFORMANCE_NLSTEXT</summary>
    HKEY_PERFORMANCE_NLSTEXT = 6
    # <summary>HKEY_PERFORMANCE_TEXT</summary>
    HKEY_PERFORMANCE_TEXT = 7
    # <summary>HKEY_A</summary>
    HKEY_A = 8
    # <summary>HKEY_CURRENT_USER</summary>
    HKEY_CURRENT_USER = 9


ENTITY_ENUMS = {
    Algorithm.__name__: Algorithm,
    ElevationToken.__name__: ElevationToken,
    OSFamily.__name__: OSFamily,
    RegistryHive.__name__: RegistryHive,
}
