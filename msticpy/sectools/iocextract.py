# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""
Module for IoCExtract class.

Uses a set of builtin regular expressions to look for Indicator of
Compromise (IoC) patterns. Input can be a single string or a pandas
dataframe with one or more columns specified as input.

The following types are built-in:

-  IPv4 and IPv6
-  URL
-  DNS domain
-  Hashes (MD5, SHA1, SHA256)
-  Windows file paths
-  Linux file paths (this is kind of noisy because a legal linux file
   path can have almost any character) You can modify or add to the
   regular expressions used at runtime.

"""

import re
from collections import defaultdict, namedtuple
from enum import Enum
from typing import Any, Dict, List, Set, Tuple, Union
from urllib.parse import unquote

import pandas as pd

from .._version import VERSION
from ..common.utility import check_kwargs, export
from .domain_utils import DomainValidator

__version__ = VERSION
__author__ = "Ian Hellen"


def _compile_regex(regex):
    return re.compile(regex, re.I | re.X | re.M)


IoCPattern = namedtuple("IoCPattern", ["ioc_type", "comp_regex", "priority", "group"])

_RESULT_COLS = ["IoCType", "Observable", "SourceIndex", "Input"]


@export
class IoCType(Enum):
    """Enumeration of IoC Types."""

    # pylint: disable=invalid-name
    unknown = "unknown"
    ipv4 = "ipv4"
    ipv6 = "ipv6"
    dns = "dns"
    url = "url"
    md5_hash = "md5_hash"
    sha1_hash = "sha1_hash"
    sha256_hash = "sha256_hash"
    file_hash = "file_hash"
    email = "email"
    windows_path = "windows_path"
    linux_path = "linux_path"
    hostname = "hostname"

    # pylint: enable=invalid-name

    @classmethod
    def parse(cls, value: str) -> "IoCType":
        """
        Return parsed IoCType of string.

        Parameters
        ----------
        value : str
            Enumeration name

        Returns
        -------
        IoCType
            IoCType matching name or unknown if no match

        """
        try:
            ioc_type = IoCType(value.lower())
        except ValueError:
            ioc_type = IoCType.unknown
        return ioc_type


# pylint: enable=invalid-name


@export
class IoCExtract:
    """
    IoC Extractor - looks for common IoC patterns in input strings.

    The extract() method takes either a string or a pandas DataFrame
    as input. When using the string option as an input extract will
    return a dictionary of results. When using a DataFrame the results
    will be returned as a new DataFrame with the following columns:
    IoCType: the mnemonic used to distinguish different IoC Types
    Observable: the actual value of the observable
    SourceIndex: the index of the row in the input DataFrame from
    which the source for the IoC observable was extracted.

    The class has a number of built-in IoC regex definitions.
    These can be retrieved using the ioc_types attribute.

    Addition IoC definitions can be added using the add_ioc_type
    method.

    Note: due to some ambiguity in the regular expression patterns
    for different types and observable may be returned assigned to
    multiple observable types. E.g. 192.168.0.1 is a also a legal file
    name in both Linux and Windows. Linux file names have a particularly
    large scope in terms of legal characters so it will be quite common
    to see other IoC observables (or parts of them) returned as a
    possible linux path.
    """

    IPV4_REGEX = r"(?P<ipaddress>(?:[0-9]{1,3}\.){3}[0-9]{1,3})"
    IPV6_REGEX = r"(?<![:.\w])(?:[A-F0-9]{0,4}:){2,7}[A-F0-9]{0,4}(?![:.\w])"
    DNS_REGEX = r"((?=[a-z0-9-]{1,63}\.)[a-z0-9]+(-[a-z0-9]+)*\.){1,126}[a-z]{2,63}"

    URL_REGEX = r"""
            (?P<protocol>(https?|ftp|telnet|ldap|file)://)
            (?P<userinfo>([a-z0-9-._~!$&\'()*+,;=:]|%[0-9A-F]{2})*@)?
            (?P<host>([a-z0-9-._~!$&\'()*+,;=]|%[0-9A-F]{2})*)
            (:(?P<port>\d*))?
            (/(?P<path>([^?\#"<>\s]|%[0-9A-F]{2})*/?))?
            (\?(?P<query>([a-z0-9-._~!$&'()*+,;=:/?@]|%[0-9A-F]{2})*))?
            (\#(?P<fragment>([a-z0-9-._~!$&'()*+,;=:/?@]|%[0-9A-F]{2})*))?"""

    WINPATH_REGEX = r"""
            (?P<root>[a-z]:|\\\\[a-z0-9_.$-]+||[.]+)
            (?P<folder>\\(?:[^\/:*?"\'<>|\r\n]+\\)*)
            (?P<file>[^\\/*?""<>|\r\n ]+)"""
    # Linux simplified - this ignores some legal linux paths avoid matching too much
    # This also matches URLs but these should be thrown out by priority
    # weighting since URL has a higher priority
    LXPATH_REGEX = r"""(?P<root>/+||[.]+)
            (?P<folder>/(?:[^\\/:*?<>|\r\n]+/)*)
            (?P<file>[^/\0<>|\r\n ]+)"""

    MD5_REGEX = r"(?:^|[^A-Fa-f0-9])(?P<hash>[A-Fa-f0-9]{32})(?:$|[^A-Fa-f0-9])"
    SHA1_REGEX = r"(?:^|[^A-Fa-f0-9])(?P<hash>[A-Fa-f0-9]{40})(?:$|[^A-Fa-f0-9])"
    SHA256_REGEX = r"(?:^|[^A-Fa-f0-9])(?P<hash>[A-Fa-f0-9]{64})(?:$|[^A-Fa-f0-9])"

    _content_regex: Dict[str, IoCPattern] = {}

    def __init__(self):
        """Initialize new instance of IoCExtract."""
        # IP Addresses
        self.add_ioc_type(IoCType.ipv4.name, self.IPV4_REGEX, 0, "ipaddress")
        self.add_ioc_type(IoCType.ipv6.name, self.IPV6_REGEX, 0)

        # Dns Domains
        # This also matches IP addresses but IPs have higher
        # priority both matching on the same substring will defer
        # to the IP regex
        self.add_ioc_type(IoCType.dns.name, self.DNS_REGEX, 1)

        # Http requests
        self.add_ioc_type(IoCType.url.name, self.URL_REGEX, 0)

        # File paths
        # Windows
        self.add_ioc_type(IoCType.windows_path.name, self.WINPATH_REGEX, 2)

        self.add_ioc_type(IoCType.linux_path.name, self.LXPATH_REGEX, 2)

        # MD5, SHA1, SHA256 hashes
        self.add_ioc_type(IoCType.md5_hash.name, self.MD5_REGEX, 1, "hash")
        self.add_ioc_type(IoCType.sha1_hash.name, self.SHA1_REGEX, 1, "hash")
        self.add_ioc_type(IoCType.sha256_hash.name, self.SHA256_REGEX, 1, "hash")

        self._dom_validator = DomainValidator()
        self._ignore_tld = False

    # Public members
    def add_ioc_type(
        self, ioc_type: str, ioc_regex: str, priority: int = 0, group: str = None
    ):
        """
        Add an IoC type and regular expression to use to the built-in set.

        Parameters
        ----------
        ioc_type : str
            A unique name for the IoC type
        ioc_regex : str
            A regular expression used to search for the type
        priority : int, optional
            Priority of the regex match vs. other ioc_patterns. 0 is
            the highest priority (the default is 0).
        group : str, optional
            The regex group to match (the default is None,
            which will match on the whole expression)

        Notes
        -----
        Pattern priorities.
            If two IocType patterns match on the same substring, the matched
            substring is assigned to the pattern/IocType with the highest
            priority. E.g. `foo.bar.com` will match types: `dns`, `windows_path`
            and `linux_path` but since `dns` has a higher priority, the expression
            is assigned to the `dns` matches.

        """
        if ioc_type is None or ioc_type.strip() is None:
            raise Exception("No value supplied for ioc_type parameter")
        if ioc_regex is None or ioc_regex.strip() is None:
            raise Exception("No value supplied for ioc_regex parameter")

        self._content_regex[ioc_type] = IoCPattern(
            ioc_type=ioc_type,
            comp_regex=_compile_regex(regex=ioc_regex),
            priority=priority,
            group=group,
        )

    @property
    def ioc_types(self) -> dict:
        """
        Return the current set of IoC types and regular expressions.

        Returns
        -------
        dict
            dict of IoC Type names and regular expressions

        """
        return self._content_regex

    # pylint: disable=too-many-locals
    def extract(
        self,
        src: str = None,
        data: pd.DataFrame = None,
        columns: List[str] = None,
        **kwargs,
    ) -> Union[Dict[str, Set[str]], pd.DataFrame]:
        """
        Extract IoCs from either a string or pandas DataFrame.

        Parameters
        ----------
        src : str, optional
            source string in which to look for IoC patterns
            (the default is None)
        data : pd.DataFrame, optional
            input DataFrame from which to read source strings
            (the default is None)
        columns : list, optional
            The list of columns to use as source strings,
            if the `data` parameter is used. (the default is None)

        Other Parameters
        ----------------
        ioc_types : list, optional
            Restrict matching to just specified types.
            (default is all types)
        include_paths : bool, optional
            Whether to include path matches (which can be noisy)
            (the default is false - excludes 'windows_path'
            and 'linux_path'). If `ioc_types` is specified
            this parameter is ignored.
        ignore_tlds : bool, optional
            If True, ignore the official Top Level Domains
            list when determining whether a domain name is
            a legal domain.

        Returns
        -------
        Any
            dict of found observables (if input is a string) or
            DataFrame of observables

        Notes
        -----
        Extract takes either a string or a pandas DataFrame as input.
        When using the string option as an input extract will
        return a dictionary of results.
        When using a DataFrame the results will be returned as a new
        DataFrame with the following columns:
        - IoCType: the mnemonic used to distinguish different IoC Types
        - Observable: the actual value of the observable
        - SourceIndex: the index of the row in the input DataFrame from
        which the source for the IoC observable was extracted.

        IoCType Pattern selection
        The default list is:  ['ipv4', 'ipv6', 'dns', 'url',
        'md5_hash', 'sha1_hash', 'sha256_hash'] plus any
        user-defined types.
        'windows_path', 'linux_path' are excluded unless `include_paths`
        is True or explicitly included in `ioc_paths`.

        """
        check_kwargs(kwargs, ["ioc_types", "include_paths", "ignore_tlds"])
        ioc_types = kwargs.get("ioc_types", None)
        include_paths = kwargs.get("include_paths", False)
        ignore_tld_current = self._ignore_tld
        self._ignore_tld = kwargs.get("ignore_tlds", False)

        if src and src.strip():
            return self._scan_for_iocs(src=src, ioc_types=ioc_types)

        if data is None:
            raise Exception("No source data was supplied to extract")

        if columns is None:
            raise Exception("No values were supplied for the columns parameter")

        ioc_types_to_use = self._get_ioc_types_to_use(ioc_types, include_paths)

        col_set = set(columns)
        if not col_set <= set(data.columns):
            missing_cols = [elem for elem in col_set if elem not in data.columns]
            raise Exception(
                "Source column(s) {} not found in supplied DataFrame".format(
                    ", ".join(missing_cols)
                )
            )

        result_rows: List[pd.Series] = []
        for idx, datarow in data.iterrows():
            result_rows.extend(
                self._search_in_row(datarow, idx, columns, ioc_types_to_use)
            )
        self._ignore_tld = ignore_tld_current
        return pd.DataFrame(data=result_rows, columns=_RESULT_COLS)

    # pylint: disable=too-many-arguments
    def _search_in_row(
        self,
        datarow: pd.Series,
        idx: Any,
        columns: List[str],
        ioc_types_to_use: List[str],
    ) -> List[pd.Series]:
        """Return results for a single input row."""
        result_rows = []
        for col in columns:
            ioc_results = self._scan_for_iocs(datarow[col], ioc_types_to_use)
            for result_type, result_set in ioc_results.items():
                if result_set:
                    for observable in result_set:
                        result_row = pd.Series(
                            data=[result_type, observable, idx, datarow[col]],
                            index=_RESULT_COLS,
                        )
                        result_rows.append(result_row)
        return result_rows

    def extract_df(
        self, data: pd.DataFrame, columns: Union[str, List[str]], **kwargs
    ) -> pd.DataFrame:
        """
        Extract IoCs from either a pandas DataFrame.

        Parameters
        ----------
        data : pd.DataFrame
            input DataFrame from which to read source strings
        columns : Union[str, list]
            A single column name as a string or a
            a list of columns to use as source strings,

        Other Parameters
        ----------------
        ioc_types : list, optional
            Restrict matching to just specified types.
            (default is all types)
        include_paths : bool, optional
            Whether to include path matches (which can be noisy)
            (the default is false - excludes 'windows_path'
            and 'linux_path'). If `ioc_types` is specified
            this parameter is ignored.
        ignore_tlds : bool, optional
            If True, ignore the official Top Level Domains
            list when determining whether a domain name is
            a legal domain.

        Returns
        -------
        pd.DataFrame
            DataFrame of observables

        Notes
        -----
        Extract takes a pandas DataFrame as input.
        The results will be returned as a new
        DataFrame with the following columns:
        - IoCType: the mnemonic used to distinguish different IoC Types
        - Observable: the actual value of the observable
        - SourceIndex: the index of the row in the input DataFrame from
        which the source for the IoC observable was extracted.

        IoCType Pattern selection
        The default list is:  ['ipv4', 'ipv6', 'dns', 'url',
        'md5_hash', 'sha1_hash', 'sha256_hash'] plus any
        user-defined types.
        'windows_path', 'linux_path' are excluded unless `include_paths`
        is True or explicitly included in `ioc_paths`.

        """
        check_kwargs(kwargs, ["ioc_types", "include_paths", "ignore_tlds"])
        ioc_types = kwargs.get("ioc_types", None)
        include_paths = kwargs.get("include_paths", False)
        ignore_tld_current = self._ignore_tld
        self._ignore_tld = kwargs.get("ignore_tlds", False)

        ioc_types_to_use = self._get_ioc_types_to_use(ioc_types, include_paths)
        if isinstance(columns, str):
            columns = [columns]
        col_set = set(columns)
        if not col_set <= set(data.columns):
            missing_cols = [elem for elem in col_set if elem not in data.columns]
            raise Exception(
                "Source column(s) {} not found in supplied DataFrame".format(
                    ", ".join(missing_cols)
                )
            )

        result_rows = []
        for idx, datarow in data.iterrows():
            result_rows.extend(
                self._search_in_row(datarow, idx, columns, ioc_types_to_use)
            )
        self._ignore_tld = ignore_tld_current
        return pd.DataFrame(data=result_rows, columns=_RESULT_COLS)

    def _get_ioc_types_to_use(
        self, ioc_types: List[str], include_paths: bool
    ) -> List[str]:
        # Use only requested IoC Type patterns
        if ioc_types:
            ioc_types_to_use = list(set(ioc_types))
        else:
            ioc_types_to_use = list(set(self._content_regex.keys()))
            # don't include linux paths unless explicitly included
            ioc_types_to_use.remove(IoCType.linux_path.name)
            if not include_paths:
                # windows path matching is less noisy
                ioc_types_to_use.remove(IoCType.windows_path.name)
        return ioc_types_to_use

    def validate(
        self, input_str: str, ioc_type: str, ignore_tlds: bool = False
    ) -> bool:
        """
        Check that `input_str` matches the regex for the specificed `ioc_type`.

        Parameters
        ----------
        input_str : str
            the string to test
        ioc_type : str
            the regex pattern to use
        ignore_tlds : bool, optional
            If True, ignore the official Top Level Domains
            list when determining whether a domain name is
            a legal domain.

        Returns
        -------
        bool
            True if match.

        """
        ignore_tld_current = self._ignore_tld
        self._ignore_tld = ignore_tlds
        if ioc_type == IoCType.file_hash.name:
            val_type = self.file_hash_type(input_str).name
        elif ioc_type == IoCType.hostname.name:
            val_type = "dns"
        else:
            val_type = ioc_type
        if val_type not in self._content_regex:
            raise KeyError(
                "Unknown type {}. Valid types are: {}".format(
                    ioc_type, list(self._content_regex.keys())
                )
            )
        rgx = self._content_regex[val_type]
        pattern_match = rgx.comp_regex.fullmatch(input_str)
        validated = True
        if val_type == "dns":
            validated = self._validate_tld(input_str)
        self._ignore_tld = ignore_tld_current
        return pattern_match and validated

    @staticmethod
    def file_hash_type(file_hash: str) -> IoCType:
        """
        Return specific IoCType based on hash length.

        Parameters
        ----------
        file_hash : str
            File hash string

        Returns
        -------
        IoCType
            Specific hash type or unknown.

        """
        hashsize_map = {
            32: IoCType.md5_hash,
            40: IoCType.sha1_hash,
            64: IoCType.sha256_hash,
        }
        hashsize = len(file_hash.strip())
        return hashsize_map.get(hashsize, IoCType.unknown)

    def get_ioc_type(self, observable: str) -> str:
        """
        Return first matching type.

        Parameters
        ----------
        observable : str
            The IoC Observable to check

        Returns
        -------
        str
            The IoC type enumeration (unknown, if no match)

        """
        results = self._scan_for_iocs(src=observable)

        if not results:
            results = self._scan_for_iocs(
                src=observable, ioc_types=[IoCType.linux_path.name]
            )
        if not results:
            return IoCType.unknown.name

        # we need to select the type that is an exact match for the whole
        # observable string (_scan_for_iocs will return matching substrings)
        for ioc_type, match_set in results.items():
            if observable in match_set:
                return ioc_type

        return IoCType.unknown.name

    # Private methods
    def _validate_tld(self, domain: str) -> bool:
        """If validate TLDS check with TLD list."""
        if self._ignore_tld:
            return True
        return self._dom_validator.validate_tld(domain)

    def _scan_for_iocs(
        self, src: str, ioc_types: List[str] = None
    ) -> Dict[str, Set[str]]:
        """Return IoCs found in the string."""
        ioc_results: Dict[str, Set] = defaultdict(set)
        iocs_found: Dict[str, Tuple[str, int]] = {}

        # pylint: disable=too-many-nested-blocks
        for (ioc_type, rgx_def) in self._content_regex.items():
            if ioc_types and ioc_type not in ioc_types:
                continue

            match_pos = 0
            for rgx_match in rgx_def.comp_regex.finditer(src, match_pos):
                if rgx_match is None:
                    break
                # If the rgx_def names a group to match on, use that
                match_str = (
                    rgx_match.groupdict()[rgx_def.group]
                    if rgx_def.group
                    else rgx_match.group()
                )

                if ioc_type == "dns" and not self._validate_tld(match_str):
                    continue

                self._add_highest_pri_match(iocs_found, match_str, rgx_def)
                if ioc_type == "url":
                    self._check_decode_url(match_str, rgx_def, match_pos, iocs_found)
                match_pos = rgx_match.end()

        for ioc, ioc_result in iocs_found.items():
            ioc_results[ioc_result[0]].add(ioc)

        return ioc_results

    def _check_decode_url(self, match_str, rgx_def, match_pos, iocs_found):
        """Get any other IoCs from decoded URL."""
        decoded_url = unquote(match_str)
        for url_match in rgx_def.comp_regex.finditer(decoded_url, match_pos):
            if url_match is not None:
                self._add_highest_pri_match(iocs_found, url_match.group(), rgx_def)
                self._add_highest_pri_match(
                    iocs_found,
                    url_match.groupdict()["host"],
                    self._content_regex["dns"],
                )

    @staticmethod
    def _add_highest_pri_match(
        iocs_found: dict, current_match: str, current_def: IoCPattern
    ):
        # if we already found a match for this item and the previous
        # ioc type is more specific then don't add this to the results
        if (
            current_match in iocs_found
            and current_def.priority >= iocs_found[current_match][1]
        ):
            return

        iocs_found[current_match] = (current_def.ioc_type, current_def.priority)


# pylint: disable=too-few-public-methods
@pd.api.extensions.register_dataframe_accessor("mp_ioc")
class IoCExtractAccessor:
    """Pandas api extension for IoC Extractor."""

    def __init__(self, pandas_obj):
        """Instantiate pandas extension class."""
        self._df = pandas_obj
        self._ioc = IoCExtract()

    def extract(self, columns, **kwargs):
        """
        Extract IoCs from either a pandas DataFrame.

        Parameters
        ----------
        columns : list
            The list of columns to use as source strings,

        Other Parameters
        ----------------
        ioc_types : list, optional
            Restrict matching to just specified types.
            (default is all types)
        include_paths : bool, optional
            Whether to include path matches (which can be noisy)
            (the default is false - excludes 'windows_path'
            and 'linux_path'). If `ioc_types` is specified
            this parameter is ignored.

        Returns
        -------
        pd.DataFrame
            DataFrame of observables

        Notes
        -----
        Extract takes a pandas DataFrame as input.
        The results will be returned as a new
        DataFrame with the following columns:
        - IoCType: the mnemonic used to distinguish different IoC Types
        - Observable: the actual value of the observable
        - SourceIndex: the index of the row in the input DataFrame from
        which the source for the IoC observable was extracted.

        IoCType Pattern selection
        The default list is:  ['ipv4', 'ipv6', 'dns', 'url',
        'md5_hash', 'sha1_hash', 'sha256_hash'] plus any
        user-defined types.
        'windows_path', 'linux_path' are excluded unless `include_paths`
        is True or explicitly included in `ioc_paths`.

        """
        return self._ioc.extract_df(data=self._df, columns=columns, **kwargs)
