# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Intake kql driver."""
import re

# from collections import ChainMap
from datetime import datetime, timedelta
from numbers import Number
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

from dateutil.relativedelta import relativedelta
from dateutil.parser import parse, ParserError  # type: ignore

from ..common.utility import collapse_dicts
from .._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


def _value_or_default(src_dict: Dict, prop_name: str, default: Dict):
    """Return value from dict or emtpy dict."""
    src_value = src_dict.get(prop_name)
    return src_value if src_value is not None else default


RD_UNIT_MAP = {
    "y": "years",
    "mon": "months",
    "w": "weeks",
    "d": "days",
    "h": "hours",
    "m": "minutes",
    "s": "seconds",
}


# pylint: disable=too-many-instance-attributes
class QuerySource:
    """
    Query definition class for templated queries.

    Attributes
    ----------
    name: str
        The query name
    metadata: Dict[str, Any]
        The consolidated metadata for the query
    params: dict[str, Any]
        The dictionary of parameter definitions for the query.
    query_store: QueryStore
        The query store object that the query belongs to

    """

    def __init__(
        self,
        name: str,
        source: Dict[str, Any],
        defaults: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        """
        Initialize query source definition.

        Parameters
        ----------
        name : str
            The query name
        source : dict
            The data source definition settings
        defaults : dict
            The default settings (if source-specific setting
            not supplied)
        metadata : dict
            The global metadata from the source file.

        Notes
        -----
        A data source can belong to multiple families (e.g. a query
        that joins data from several sources)

        """
        self.name = name
        self._source: Dict[str, Any] = source or {}
        self.defaults: Dict[str, Any] = defaults or {}
        self._global_metadata: Dict[str, Any] = dict(metadata) if metadata else {}
        self.query_store: Optional["QueryStore"] = None  # type: ignore  # noqa: F821

        # consolidate source metadata - source-specifc
        # overrides global
        # add an empty dict in case neither has defined params
        # self.metadata = ChainMap(
        #     _value_or_default(self._source, "metadata", {}),
        #     _value_or_default(self.defaults, "metadata", {}),
        #     self._global_metadata,
        # )
        self.metadata = collapse_dicts(
            self._global_metadata,
            self.defaults.get("metadata", {}),
            self._source.get("metadata", {}),
        )
        # make ChainMap for parameters from with source
        # higher priority than default
        # add an empty dict in case neither has defined params
        # self.params = ChainMap(
        #     _value_or_default(self._source, "parameters", {}),
        #     _value_or_default(self.defaults, "parameters", {}),
        #     # self._source.get("parameters", {}),
        #     # self.defaults.get("parameters", {}),
        # )
        self.params = collapse_dicts(
            self.defaults.get("parameters", {}),
            self._source.get("parameters", {}),
        )

        self._query: str = self["args.query"]
        self._replace_query_macros()

    def __getitem__(self, key: str):
        """
        Getitem override - allows access to properties via dotted notation.

        Parameters
        ----------
        key : str
            The hiearchical path to the property (e.g. `source.description`)

        """
        path_elems = key.split(".")
        cur_node = self._source
        for elem in path_elems:
            cur_node = cur_node.get(elem, None)
            if cur_node is None:
                raise KeyError(f"{elem} value of {key} is not a valid path")
        return cur_node

    @property
    def description(self) -> str:
        """
        Return description of the query.

        Returns
        -------
        str
            Query description.

        """
        try:
            return self["description"]
        except KeyError:
            return "no description"

    @property
    def query(self) -> str:
        """
        Return the query template.

        Returns
        -------
        str
            The template query.

        """
        return self._query

    @property
    def default_params(self) -> Dict[str, dict]:
        """
        Return the set of parameters with default values.

        Returns
        -------
        Iterable[dict]
            List of parameters

        """
        return {
            p_key: p_props
            for p_key, p_props in self.params.items()
            if "default" in p_props
        }

    @property
    def required_params(self) -> Dict[str, dict]:
        """
        Return the set of parameters with no default values.

        Returns
        -------
        Iterable[dict]
            List of parameters

        """
        return {
            p_key: p_props
            for p_key, p_props in self.params.items()
            if "default" not in p_props
        }

    @property
    def data_families(self) -> List[str]:
        """
        Return the list of data families used by the query.

        Returns
        -------
        List[str]
            The list of data families. A data family is
            usually equivalent to a table or entity set.

        """
        return self.metadata["data_families"]

    def create_query(self, formatters: Dict[str, Callable] = None, **kwargs) -> str:
        """
        Return query with values from kwargs and defaults substituted.

        Parameters
        ----------
        formatters : Dict[str, Callable]
            Dictionary of custom parameter formatters indexed
            by data type
        kwargs: Mapping[str, Any]
            Set of parameter name, value pairs used to
            populate the template query.

        Returns
        -------
        str
            The populated query

        Raises
        ------
        ValueError
            If one or more parameters with no default values
            are not supplied.

        Notes
        -----
        Parameters supplied as arguments will override any
        parameter defaults (see `default_params` property).

        """
        param_dict = {
            name: value.get("default", None) for name, value in self.params.items()
        }

        param_dict.update(self.resolve_param_aliases(kwargs))
        missing_params = {
            name: value for name, value in param_dict.items() if value is None
        }
        if missing_params:
            raise ValueError(
                "These required parameters were not set: ", f"{missing_params.keys()}"
            )

        # Handle formatting for datetimes and cases where a format
        # template has been supplied
        for p_name, settings in self.params.items():
            # These types may require custom extraction
            if settings["type"] == "datetime":
                param_dict[p_name] = self._convert_datetime(param_dict[p_name])
            if settings["type"] == "list":
                param_dict[p_name] = self._parse_param_list(param_dict[p_name])

            # The parameter may need custom formatting
            fmt_template = settings.get("format", None)
            if fmt_template:
                # custom formatting template in the query definition
                param_dict[p_name] = fmt_template.format(param_dict[p_name])
            elif settings["type"] == "datetime" and isinstance(
                param_dict[p_name], datetime
            ):
                if formatters and "datetime" in formatters:
                    param_dict[p_name] = formatters["datetime"](param_dict[p_name])
                else:
                    param_dict[p_name] = self._format_datetime_default(
                        param_dict[p_name]
                    )
            elif settings["type"] == "list":
                if formatters and "list" in formatters:
                    param_dict[p_name] = formatters["list"](param_dict[p_name])
                else:
                    param_dict[p_name] = self._format_list_default(param_dict[p_name])

        return self._query.format(**param_dict)

    def _convert_datetime(self, param_value: Any) -> datetime:
        if isinstance(param_value, datetime):
            return param_value
        if isinstance(param_value, Number):
            # datetime specified as a number - we
            # interpret this as an offset from utcnow
            return datetime.utcnow() + timedelta(  # type: ignore
                param_value  # type: ignore
            )
        try:
            # If this is a simple integer we want to catch it before sending
            # it to dateutil parser since this does the wrong thing with it.
            int(param_value)
            return self._calc_timeoffset(str(param_value))
        except ValueError:
            pass
        try:
            # Try to parse datetime with dateutil parser
            return parse(param_value)
        except ParserError:
            # If none of these, assume a time delta
            return self._calc_timeoffset(str(param_value))

    def resolve_param_aliases(self, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Try to resolve any parameters in `param_dict` that are aliases."""
        out_dict = {}
        for param, value in param_dict.items():
            if param in self.params:
                out_dict[param] = value
            else:
                aliased_param = self._get_aliased_param(param)
                if aliased_param:
                    out_dict[aliased_param] = value
                else:
                    out_dict[param] = value
        return out_dict

    def _get_aliased_param(self, alias: str) -> Optional[str]:
        """Return first parameter with a matching alias."""
        aliased_params = {
            p_name: p_prop
            for p_name, p_prop in self.params.items()
            if "aliases" in p_prop
        }
        for param, props in aliased_params.items():
            if alias in props["aliases"]:
                return param
        return None

    @classmethod
    def _calc_timeoffset(cls, time_offset: str) -> datetime:
        """Calculate date from offset specification."""
        delta = time_offset.split("@")[0]
        rounding = None
        if "@" in time_offset:
            rounding = time_offset.split("@")[1].casefold()

        # Calculate the raw offset
        t_delta = cls._parse_timedelta(delta)
        result_date = datetime.utcnow() + t_delta

        # If rounding to a specified unit (e.g. -3d@d)
        if rounding:
            # extract the date components into a list
            rounded_dt = list(result_date.timetuple())[:6]
            # round up if timedelta is positive or down if negative
            round_down = time_offset.strip().startswith("-")
            round_item = None
            datetime_units = list(RD_UNIT_MAP.keys())
            datetime_units.remove("w")
            for dt_part, period in enumerate(datetime_units):
                if round_item:
                    rounded_dt[dt_part] = 0
                if rounding.startswith(period):
                    # once we match the period, set all subsequent values
                    # to zero
                    round_item = period
            result_date = datetime(*rounded_dt)  # type: ignore
            if not round_down:
                # Use dateutil relativedelta to add one to whatever rounding
                # unit was specified
                units = RD_UNIT_MAP.get(round_item or "d", "days")
                # expand dict to args for relativedelta
                result_date = result_date + relativedelta(
                    **({units: +1})  # type: ignore
                )
        return result_date

    @staticmethod
    def _parse_timedelta(time_range: str = "0") -> timedelta:
        """Parse time period string and return equivalent timedelta."""
        tr_regex = r"(?P<sign>[+\-]?)\s*(?P<value>[\d]+)\s*(?P<unit>([ywdhms]?|mon))"
        m_time = re.match(tr_regex, time_range, re.IGNORECASE)

        if not m_time or "value" not in m_time.groupdict():
            return timedelta(0)
        tm_val = int(m_time.groupdict()["sign"] + m_time.groupdict()["value"])
        tm_unit = (
            m_time.groupdict()["unit"].lower() if m_time.groupdict()["unit"] else "d"
        )
        # Use relative delta to build the timedelta based on the units
        # in the time range expression
        unit_param = RD_UNIT_MAP.get(tm_unit, "days")
        # expand dict to args for relativedelta
        return relativedelta(**({unit_param: tm_val}))  # type: ignore

    @staticmethod
    def _parse_param_list(param_value: Union[str, List]) -> List[Any]:
        """Parse list, comma-delim str or str."""
        if isinstance(param_value, list):
            return param_value
        if isinstance(param_value, str) and "," in param_value:
            return [item.strip() for item in param_value.split(",")]
        return [param_value]

    @staticmethod
    def _format_datetime_default(date_time: datetime) -> str:
        return date_time.isoformat(sep="T") + "Z"

    @staticmethod
    def _format_list_default(item_list: List[Any]) -> str:
        """Return formatted list parameter."""
        fmt_list = []
        for item in item_list:
            if isinstance(item, str):
                fmt_list.append(f"'{item}'")
            else:
                fmt_list.append(f"{item}")
        return ",".join(fmt_list)

    def help(self):
        """Print help for query."""
        print("Query: ", self.name)
        if self.query_store is not None:
            print("Data source: ", self.query_store.environment)
        print(self.create_doc_string())
        print("Query:")
        print(self.query)

    def create_doc_string(self) -> str:
        """
        Return a doc string for the query.

        Returns
        -------
        str
            New-line delimited docstring dynamically
            created from query definition properties.

        """
        param_block = ["Parameters", "----------"]
        for p_name, p_props in sorted(self.params.items()):
            if "default" in p_props:
                optional = " (optional)"
                def_value = p_props["default"]
                if isinstance(def_value, str) and len(def_value) > 50:
                    def_value = def_value[:50] + "..."
            else:
                optional = ""
                def_value = None
            param_block.append(f'{p_name}: {p_props.get("type", "Any")}{optional}')
            param_block.append(f'    {p_props.get("description", "no description")}')
            if def_value:
                param_block.append(f"    (default value is: {def_value})")
            if "aliases" in p_props:
                alias_list = ", ".join(f"'{alias}'" for alias in p_props["aliases"])
                param_block.append(f"    Aliases: {alias_list}")
        doc_string = [f"{self.description}", ""]
        return "\n".join(doc_string + param_block)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the source to ensure that all required properties are present.

        Returns
        -------
        bool
            True if validation is successful.

        """
        req_source_items = {"args"}
        # match items surrounded by single {} but not double
        param_pattern = r"(?!{{){([^}]+)}(?!})"

        valid_failures = []

        # Need req_source_items AND query item to be present
        source_props = self._source.keys() | self.defaults.keys()
        if not req_source_items.issubset(source_props):
            msg = (
                f"Source {self.name} does not have all required "
                + f"elements: {req_source_items - source_props}"
            )
            valid_failures.append(msg)
        if not self._query:
            msg = (
                f'Source {self.name} does not have "query" property '
                + "in args element."
            )
            valid_failures.append(msg)

        # Now get the query and the parameter definitions from the source and
        # check that every parameter specified in the query has a corresponding
        # 'parameter definition in either the source or the defaults.
        source_params = self.params.keys()
        q_params = set(re.findall(param_pattern, self._query))

        missing_params = q_params - source_params
        if missing_params:
            msg = (
                f"Source {self.name} has parameters that are defined in "
                + "the query but not included in either defaults or "
                + "query-specific parameters element(s)\n"
                + f"Missing parameters are {missing_params}"
            )
            valid_failures.append(msg)

        missing_types = {
            p_name for p_name, p_props in self.params.items() if "type" not in p_props
        }
        if missing_types:
            msg = (
                f"Source {self.name} has parameters that are defined in "
                + 'the query but do not have a valid "type" property\n'
                + f"Parameters with missing types are {missing_types}"
            )
            valid_failures.append(msg)
        return (not valid_failures, valid_failures)

    def _replace_query_macros(self):
        """Replace any macro strings in the query with substitutions."""
        replace_keys = re.findall(r"\$\<([^>]+)\>\$?", self._query)
        if not replace_keys:
            return
        replace_values = {}
        if "query_macros" in self._source:
            replace_values = {
                name: properties.get("value", "")
                for name, properties in self["query_macros"].items()
            }
        for key in replace_keys:
            if key in replace_keys:
                replacement = replace_values.get(key, "")
                self._query = self._query.replace(f"$<{key}>$", replacement)
        self._query = re.sub("\n{2,}", "\n", self._query)
