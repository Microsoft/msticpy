# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""
Module for TILookup classes.

Input can be a single IoC observable or a pandas DataFrame containing
multiple observables. Processing may require a an API key and
processing performance may be limited to a specific number of
requests per minute for the account type that you have.

"""
import abc
from abc import ABC
import collections
import math  # noqa
import pprint
import re
from collections import Counter, namedtuple
from enum import Enum
from functools import lru_cache, singledispatch, total_ordering
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import quote_plus

import attr
import pandas as pd
from urllib3.exceptions import LocationParseError
from urllib3.util import parse_url

from ..._version import VERSION
from ...common.utility import export
from ..iocextract import IoCExtract, IoCType

__version__ = VERSION
__author__ = "Ian Hellen"


SanitizedObservable = namedtuple("SanitizedObservable", ["observable", "status"])


# pylint: disable=too-few-public-methods
@total_ordering
class TISeverity(Enum):
    """Threat intelligence report severity."""

    # pylint: disable=invalid-name
    unknown = -1
    information = 0
    warning = 1
    high = 2

    # pylint: enable=invalid-name

    @classmethod
    def parse(cls, value) -> "TISeverity":
        """
        Parse string or numeric value to TISeverity.

        Parameters
        ----------
        value : Any
            TISeverity, str or int

        Returns
        -------
        TISeverity
            TISeverity instance.

        """
        if isinstance(value, TISeverity):
            return value
        if isinstance(value, str) and value.lower() in cls.__members__:
            return cls[value.lower()]
        if isinstance(value, int) and value in [
            v.value for v in cls.__members__.values()
        ]:
            return cls(value)
        return TISeverity.unknown

    # pylint: disable=comparison-with-callable
    def __eq__(self, other) -> bool:
        """
        Return True if severities are equal.

        Parameters
        ----------
        other : Any
            TISeverity to compare to.
            Can be a numeric value or name of TISeverity value.

        Returns
        -------
        bool
            If severities are equal

        """
        other_sev = TISeverity.parse(other)
        return self.value == other_sev.value

    def __gt__(self, other) -> bool:
        """
        Return True self is greater than other.

        Parameters
        ----------
        other : Any
            TISeverity to compare to.
            Can be a numeric value or name of TISeverity value.

        Returns
        -------
        bool
            If severities are equal

        """
        other_sev = TISeverity.parse(other)
        return self.value > other_sev.value


# pylint: enable=comparison-with-callable
# pylint: disable=too-many-instance-attributes
@attr.s(auto_attribs=True)
class LookupResult:
    """Lookup result for IoCs."""

    ioc: str
    ioc_type: str
    safe_ioc: str = ""
    query_subtype: Optional[str] = None
    provider: Optional[str] = None
    result: bool = False
    severity: int = attr.ib(default=0)
    details: Any = None
    raw_result: Optional[Union[str, dict]] = None
    reference: Optional[str] = None
    status: int = 0

    @severity.validator
    def _check_severity(self, attribute, value):
        del attribute
        if isinstance(value, TISeverity):
            self.severity = value.name
            return
        self.severity = TISeverity.parse(value).name

    @property
    def summary(self):
        """Print a summary of the Lookup Result."""
        p_pr = pprint.PrettyPrinter(indent=4)
        print("ioc:", self.ioc, "(", self.ioc_type, ")")
        print("result:", self.result)
        # print("severity:", self.severity)
        p_pr.pprint(self.details)
        print("reference: ", self.reference)

    @property
    def raw_result_fmtd(self):
        """Print raw results of the Lookup Result."""
        p_pr = pprint.PrettyPrinter(indent=4)
        p_pr.pprint(self.raw_result)

    @property
    def severity_name(self) -> str:
        """
        Return text description of severity score.

        Returns
        -------
        str
            Severity description.

        """
        try:
            return TISeverity(self.severity).name
        except ValueError:
            return TISeverity.unknown.name

    def set_severity(self, value: Any):
        """
        Set the severity from enum, int or string.

        Parameters
        ----------
        value : Any
            The severity value to set

        """
        self._check_severity(None, value)

    @classmethod
    def column_map(cls):
        """Return a dictionary that maps fields to DF Names."""
        col_mapping = {}
        for name in attr.fields_dict(cls):
            out_name = "".join([part.capitalize() for part in name.split("_")])
            col_mapping[name] = out_name
        return col_mapping


# pylint: enable=too-many-instance-attributes


# pylint: disable=too-few-public-methods
class TILookupStatus(Enum):
    """Threat intelligence lookup status."""

    ok = 0
    not_supported = 1
    bad_format = 2
    query_failed = 3
    other = 10


# pylint: enable=too-few-public-methods


_IOC_EXTRACT = IoCExtract()


@export
class TIProvider(ABC):
    """Abstract base class for Threat Intel providers."""

    _IOC_QUERIES: Dict[str, Any] = {}

    # pylint: disable=unused-argument
    def __init__(self, **kwargs):
        """Initialize the provider."""
        self._supported_types: Set[IoCType] = set()
        self.description: Optional[str] = None

        self._supported_types = {
            IoCType.parse(ioc_type.split("-")[0]) for ioc_type in self._IOC_QUERIES
        }
        if IoCType.unknown in self._supported_types:
            self._supported_types.remove(IoCType.unknown)

        self.require_url_encoding = False

    # pylint: disable=duplicate-code
    @abc.abstractmethod
    def lookup_ioc(
        self, ioc: str, ioc_type: str = None, query_type: str = None, **kwargs
    ) -> LookupResult:
        """
        Lookup a single IoC observable.

        Parameters
        ----------
        ioc : str
            IoC Observable value
        ioc_type : str, optional
            IoC Type, by default None (type will be inferred)
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the IoC type
            will be returned.

        Returns
        -------
        LookupResult
            The returned results.

        """

    def lookup_iocs(
        self,
        data: Union[pd.DataFrame, Dict[str, str], Iterable[str]],
        obs_col: str = None,
        ioc_type_col: str = None,
        query_type: str = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Lookup collection of IoC observables.

        Parameters
        ----------
        data : Union[pd.DataFrame, Dict[str, str], Iterable[str]]
            Data input in one of three formats:
            1. Pandas dataframe (you must supply the column name in
            `obs_col` parameter)
            2. Dict of observable, IoCType
            3. Iterable of observables - IoCTypes will be inferred
        obs_col : str, optional
            DataFrame column to use for observables, by default None
        ioc_type_col : str, optional
            DataFrame column to use for IoCTypes, by default None
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the IoC type
            will be returned.

        Returns
        -------
        pd.DataFrame
            DataFrame of results.

        """
        results = []
        for observable, ioc_type in generate_items(data, obs_col, ioc_type_col):
            if not observable:
                continue
            item_result = self.lookup_ioc(
                ioc=observable, ioc_type=ioc_type, query_type=query_type
            )
            results.append(pd.Series(attr.asdict(item_result)))

        return pd.DataFrame(data=results).rename(columns=LookupResult.column_map())

    @abc.abstractmethod
    def parse_results(self, response: LookupResult) -> Tuple[bool, TISeverity, Any]:
        """
        Return the details of the response.

        Parameters
        ----------
        response : LookupResult
            The returned data response

        Returns
        -------
        Tuple[bool, TISeverity, Any]
            bool = positive or negative hit
            TISeverity = enumeration of severity
            Object with match details

        """

    @property
    def supported_types(self) -> List[str]:
        """
        Return list of supported IoC types for this provider.

        Returns
        -------
        List[str]
            List of supported type names

        """
        return [ioc.name for ioc in self._supported_types]

    @property
    def ioc_query_defs(self) -> Dict[str, Any]:
        """
        Return current dictionary of IoC query/request definitions.

        Returns
        -------
        Dict[str, Any]
            IoC query/requist definitions keyed by IoCType

        """
        return self._IOC_QUERIES

    @classmethod
    def is_known_type(cls, ioc_type: str) -> bool:
        """
        Return True if this a known IoC Type.

        Parameters
        ----------
        ioc_type : str
            IoCType string to test

        Returns
        -------
        bool
            True if known type.

        """
        return ioc_type in IoCType.__members__ and ioc_type != "unknown"

    @classmethod
    def usage(cls):
        """Print usage of provider."""
        print(f"{cls.__doc__} Supported query types:")
        for ioc_key in sorted(cls._IOC_QUERIES):
            ioc_key_elems = ioc_key.split("-", maxsplit=1)
            if len(ioc_key_elems) == 1:
                print(f"\tioc_type={ioc_key_elems[0]}")
            if len(ioc_key_elems) == 2:
                print(
                    f"\tioc_type={ioc_key_elems[0]}, ioc_query_type={ioc_key_elems[1]}"
                )

    def is_supported_type(self, ioc_type: Union[str, IoCType]) -> bool:
        """
        Return True if the passed type is supported.

        Parameters
        ----------
        ioc_type : Union[str, IoCType]
            IoC type name or instance

        Returns
        -------
        bool
            True if supported.

        """
        if isinstance(ioc_type, str):
            ioc_type = IoCType.parse(ioc_type)
        return ioc_type.name in self.supported_types

    @staticmethod
    @lru_cache(maxsize=1024)
    def resolve_ioc_type(observable: str) -> str:
        """
        Return IoCType determined by IoCExtract.

        Parameters
        ----------
        observable : str
            IoC observable string

        Returns
        -------
        str
            IoC Type (or unknown if type could not be determined)

        """
        return _IOC_EXTRACT.get_ioc_type(observable)

    def _check_ioc_type(
        self, ioc: str, ioc_type: str = None, query_subtype: str = None
    ) -> LookupResult:
        """
        Check IoC Type and cleans up observable.

        Parameters
        ----------
        ioc : str
            IoC observable
        ioc_type : str, optional
            IoC type, by default None
        query_subtype : str, optional
            Query sub-type, if any, by default None

        Returns
        -------
        LookupResult
            Lookup result with resolved ioc_type and pre-processed
            observable.
            LookupResult.status is none-zero on failure.

        """
        result = LookupResult(
            ioc=ioc,
            safe_ioc=ioc,
            ioc_type=ioc_type or self.resolve_ioc_type(ioc),
            query_subtype=query_subtype,
            result=False,
            details="",
            raw_result=None,
            reference=None,
        )

        if not self.is_supported_type(result.ioc_type):
            result.details = f"IoC type {result.ioc_type} not supported."
            result.status = TILookupStatus.not_supported.value
            return result

        clean_ioc = preprocess_observable(
            ioc, result.ioc_type, self.require_url_encoding
        )

        result.safe_ioc = clean_ioc.observable

        if clean_ioc.status != "ok":
            result.details = clean_ioc.status
            result.status = TILookupStatus.bad_format.value

        return result


# slightly stricter than normal URL regex to exclude '() from host string
_HTTP_STRICT_REGEX = r"""
    (?P<protocol>(https?|ftp|telnet|ldap|file)://)
    (?P<userinfo>([a-z0-9-._~!$&*+,;=:]|%[0-9A-F]{2})*@)?
    (?P<host>([a-z0-9-._~!$&\*+,;=]|%[0-9A-F]{2})*)
    (:(?P<port>\d*))?
    (/(?P<path>([^?\#| ]|%[0-9A-F]{2})*))?
    (\?(?P<query>([a-z0-9-._~!$&'()*+,;=:/?@]|%[0-9A-F]{2})*))?
    (\#(?P<fragment>([a-z0-9-._~!$&'()*+,;=:/?@]|%[0-9A-F]{2})*))?\b"""

_HTTP_STRICT_RGXC = re.compile(_HTTP_STRICT_REGEX, re.I | re.X | re.M)


# pylint: disable=too-many-return-statements, too-many-branches
def preprocess_observable(
    observable, ioc_type, require_url_encoding: bool = False
) -> SanitizedObservable:
    """
    Preprocesses and checks validity of observable against declared IoC type.

        :param observable: the value of the IoC
        :param ioc_type: the IoC type
    """
    observable = observable.strip()
    try:
        validated = _IOC_EXTRACT.validate(observable, ioc_type)
    except KeyError:
        validated = False
    if not validated:
        return SanitizedObservable(
            None, "Observable does not match expected pattern for " + ioc_type
        )
    if ioc_type == "url":
        return _preprocess_url(observable, require_url_encoding)
    if ioc_type == "ipv4":
        return _preprocess_ip(observable, version=4)
    if ioc_type == "ipv6":
        return _preprocess_ip(observable, version=6)
    if ioc_type in ["dns", "hostname"]:
        return _preprocess_dns(observable)
    if ioc_type in ["md5_hash", "sha1_hash", "sha256_hash", "file_hash"]:
        return _preprocess_hash(observable)
    return SanitizedObservable(observable, "ok")


# Would complicate code with too many branches
# pylint: disable=too-many-return-statements
def _preprocess_url(
    url: str, require_url_encoding: bool = False
) -> SanitizedObservable:
    """
    Check that URL can be parsed.

    Parameters
    ----------
    url : str
        The URL to check
    require_url_encoding : bool
        Set to True if url's require encoding before passing to provider

    Returns
    -------
    SanitizedObservable
        Pre-processed result

    """
    clean_url, scheme, host = get_schema_and_host(url, require_url_encoding)

    if scheme is None or host is None:
        return SanitizedObservable(None, f"Could not obtain scheme or host from {url}")
    # get rid of some obvious false positives (localhost, local hostnames)
    try:
        addr = ip_address(host)
        if addr.is_private:
            return SanitizedObservable(None, "Host part of URL is a private IP address")
        if addr.is_loopback:
            return SanitizedObservable(
                None, "Host part of URL is a loopback IP address"
            )
    except ValueError:
        pass

    if "." not in host:
        return SanitizedObservable(None, "Host is unqualified domain name")

    if scheme.lower() in ["file"]:
        return SanitizedObservable(None, f"{scheme} URL scheme is not supported")

    return SanitizedObservable(clean_url, "ok")


def get_schema_and_host(
    url: str, require_url_encoding: bool = False
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return URL scheme and host and cleaned URL.

    Parameters
    ----------
    url : str
        Input URL
    require_url_encoding : bool
        Set to True if url needs encoding. Defualt is False.

    Returns
    -------
    Tuple[Optional[str], Optional[str], Optional[str]
        Tuple of URL, scheme, host

    """
    clean_url = None
    scheme = None
    host = None
    try:
        scheme, _, host, _, _, _, _ = parse_url(url)
        clean_url = url
    except LocationParseError:
        # Try to clean URL and re-check
        cleaned_url = _clean_url(url)
        if cleaned_url is not None:
            try:
                scheme, _, host, _, _, _, _ = parse_url(cleaned_url)
                clean_url = cleaned_url
            except LocationParseError:
                pass
    if require_url_encoding and clean_url:
        clean_url = quote_plus(clean_url)
    return clean_url, scheme, host


def _clean_url(url: str) -> Optional[str]:
    """
    Clean URL to remove query params and fragments and any trailing stuff.

    Parameters
    ----------
    url : str
        the URL to check

    Returns
    -------
    Optional[str]
        Cleaned URL or None if the input was not a valid URL

    """
    # Try to clean URL and re-check
    match_url = _HTTP_STRICT_RGXC.search(url)
    if (
        not match_url
        or match_url.groupdict()["protocol"] is None
        or match_url.groupdict()["host"] is None
    ):
        return None

    # build the URL dropping the query string and fragments
    clean_url = match_url.groupdict()["protocol"]
    if match_url.groupdict()["userinfo"]:
        clean_url += match_url.groupdict()["userinfo"]
    clean_url += match_url.groupdict()["host"]
    if match_url.groupdict()["port"]:
        clean_url += ":" + match_url.groupdict()["port"]
    if match_url.groupdict()["path"]:
        clean_url += "/" + match_url.groupdict()["path"]

    return clean_url


# Would complicate code with too many branches
# pylint: disable=too-many-return-statements
def _preprocess_ip(ipaddress: str, version=4):
    """Ensure Ip address is a valid public IPv4 address."""
    try:
        addr = ip_address(ipaddress)
    except ValueError:
        return SanitizedObservable(None, "IP address is invalid format")

    if version == 4 and not isinstance(addr, IPv4Address):
        return SanitizedObservable(None, "Not an IPv4 address")
    if version == 6 and not isinstance(addr, IPv6Address):
        return SanitizedObservable(None, "Not an IPv6 address")
    if addr.is_global:
        return SanitizedObservable(ipaddress, "ok")

    return SanitizedObservable(None, "IP address is not global")


def _preprocess_dns(domain: str) -> SanitizedObservable:
    """Ensure DNS is a valid-looking domain."""
    if "." not in domain:
        return SanitizedObservable(None, "Domain is unqualified domain name")
    try:
        addr = ip_address(domain)
        del addr
        return SanitizedObservable(None, "Domain is an IP address")
    except ValueError:
        pass

    return SanitizedObservable(domain, "ok")


def _preprocess_hash(hash_str: str) -> SanitizedObservable:
    """Ensure Hash has minimum entropy (rather than a string of 'x')."""
    str_entropy = entropy(hash_str)
    if str_entropy < 3.0:
        return SanitizedObservable(None, "String has too low an entropy to be a hash")
    return SanitizedObservable(hash_str, "ok")


def entropy(input_str: str) -> float:
    """Compute entropy of input string."""
    str_len = float(len(input_str))
    return -sum(
        map(
            lambda a: (a / str_len) * math.log2(a / str_len),
            Counter(input_str).values(),
        )
    )


@singledispatch
def generate_items(
    data: Any, obs_col: Optional[str] = None, ioc_type_col: Optional[str] = None
) -> Iterable[Tuple[Optional[str], Optional[str]]]:
    """
    Generate item pairs from different input types.

    Parameters
    ----------
    data : Any
        DataFrame, dictionary or iterable
    obs_col : Optional[str]
        If `data` is a DataFrame, the column containing the observable value.
    ioc_type_col : Optional[str]
        If `data` is a DataFrame, the column containing the observable type.

    Returns
    -------
    Iterable[Tuple[Optional[str], Optional[str]]]] - a tuple of Observable/Type.

    """
    del obs_col, ioc_type_col

    if isinstance(data, collections.abc.Iterable):
        for item in data:
            yield item, TIProvider.resolve_ioc_type(item)
    else:
        yield None, None


@generate_items.register(pd.DataFrame)
def _(data: pd.DataFrame, obs_col: str, ioc_type_col: Optional[str] = None):
    for _, row in data.iterrows():
        if ioc_type_col is None:
            yield row[obs_col], TIProvider.resolve_ioc_type(row[obs_col])
        else:
            yield row[obs_col], row[ioc_type_col]


@generate_items.register(dict)  # type: ignore
def _(data: dict, obs_col: Optional[str] = None, ioc_type_col: Optional[str] = None):
    for obs, ioc_type in data.items():
        if not ioc_type:
            ioc_type = TIProvider.resolve_ioc_type(obs)
        yield obs, ioc_type
