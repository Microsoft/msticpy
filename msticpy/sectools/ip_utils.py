# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

"""

Contains a series of functions required to manipulate and enrich IP Address data to assist investigations.

Designed to support any data source containing IP address entity.

"""
import ipaddress as ip

from .._version import VERSION
from ..nbtools.entityschema import GeoLocation, Host, IpAddress
from ..nbtools.utility import export
from .geoip import GeoLiteLookup

__version__ = VERSION
__author__ = "Ashwin Patil"

IPLOCATION = GeoLiteLookup()


class Error(Exception):
    """Base class for other exceptions."""


class DataError(Error):
    """Raised when thereis a data input error."""


def convert_to_ip_entities(ip_str: str) -> Tuple[IpAddress]:
    """
    Take in an IP Address string and converts it to an IP Entitity.

    Parameters
    ----------
    ip_str : str
        The string of the IP Address

    Returns
    -------
    Tuple
        The populated IP entities including address and geo-location

    """
    ip_entities = []
    if ip_str:
        if "," in ip_str:
            addrs = ip_str.split(",")
        elif " " in ip_str:
            addrs = ip_str.split(" ")
        else:
            addrs = [ip_str]

        for addr in addrs:
            ip_entity = IpAddress()
            ip_entity.Address = addr.strip()
            try:
                IPLOCATION.lookup_ip(ip_entity=ip_entity)
            except DataError:
                pass
            ip_entities.append(ip_entity)
    return ip_entities


@export
def get_ip_type(ip_str: str) -> str:
    """ function to validate given value is an IP address and deteremine IPType category (e.g. Private/Public/Multicast)"""
    try:
        ip.ip_address(ip_str)
        if ip.ip_address(ip_str).is_private:
            return "Private"
        elif ip.ip_address(ip_str).is_multicast:
            return "Multicast"
        elif ip.ip_address(ip_str).is_unspecified:
            return "Unspecified"
        elif ip.ip_address(ip_str).is_reserved:
            return "Reserved"
        elif ip.ip_address(ip_str).is_loopback:
            return "Loopback"
        elif ip.ip_address(ip_str).is_global:
            return "Public"
        elif ip.ip_address(ip_str).is_link_local:
            return "Link Local"
    except ValueError:
        print(f"{ip_str} does not appear to be an IPv4 or IPv6 address")


@export
def create_ip_record(
    heartbeat_df: pd.DataFrame, az_net_df: pd.DataFrame = None
) -> IpAddress:
    """
    Generate ip_entity record for provided IP value.

    Parameters
    ----------
    heartbeat_df : pd.DataFrame
        A dataframe of heartbeat data for the host
    az_net_df : pd.DataFrame
        Option dataframe of Azure network data for the host

    Returns
    -------
    IP
        Details of the IP data collected

    """
    ip_entity = IpAddress(src_event=heartbeat_df.iloc[0])

    # Produce ip_entity record using available dataframes
    ip_hb = heartbeat_df.iloc[0]
    ip_entity.Address = ip_hb["ComputerIP"]
    ip_entity.hostname = ip_hb["Computer"]
    ip_entity.SourceComputerId = ip_hb["SourceComputerId"]
    ip_entity.OSType = ip_hb["OSType"]
    ip_entity.OSName = ip_hb["OSName"]
    ip_entity.OSVMajorersion = ip_hb["OSMajorVersion"]
    ip_entity.OSVMinorVersion = ip_hb["OSMinorVersion"]
    ip_entity.ComputerEnvironment = ip_hb["ComputerEnvironment"]
    ip_entity.OmsSolutions = [sol.strip() for sol in ip_hb["Solutions"].split(",")]
    ip_entity.VMUUID = ip_hb["VMUUID"]
    ip_entity.SubscriptionId = ip_hb["SubscriptionId"]
    geoloc_entity = GeoLocation()
    geoloc_entity.CountryName = ip_hb["RemoteIPCountry"]
    geoloc_entity.Longitude = ip_hb["RemoteIPLongitude"]
    geoloc_entity.Latitude = ip_hb["RemoteIPLatitude"]
    ip_entity.Location = geoloc_entity
    ip_entity.IPAddress = ip_entity

    # If Azure network data present add this to host record
    if az_net_df is not None and not az_net_df.empty:
        if len(az_net_df) == 1:
            priv_addr_str = az_net_df["PrivateIPAddresses"].loc[0]
            ip_entity["private_ips"] = convert_to_ip_entities(priv_addr_str)
            pub_addr_str = az_net_df["PublicIPAddresses"].loc[0]
            ip_entity["public_ips"] = convert_to_ip_entities(pub_addr_str)
        else:
            if "private_ips" not in ip_entity:
                ip_entity["private_ips"] = []
            if "public_ips" not in ip_entity:
                ip_entity["public_ips"] = []

    return ip_entity
