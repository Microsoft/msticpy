# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Timespan class."""
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, Union

import pandas as pd
from dateutil.parser import ParserError  # type: ignore

from .._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


class TimeSpan:
    """Timespan parameter for notebook modules."""

    # pylint: enable=too-many-branches
    def __init__(
        self,
        timespan: Optional[Union["TimeSpan", Tuple[Any, Any], Any]] = None,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        period: Optional[Union[timedelta, str]] = None,
    ):
        """
        Initialize Timespan.

        Parameters
        ----------
        timespan : Union(TimeSpan, Tuple(Any, Any), Any), optional
            A TimeSpan object
            or a tuple of datetimes or datetime strings,
            or an object that has either `start` and `end` or `start` and
            `period` date_time-like attributes.
            By default None
        start : Optional[Union[datetime, str]], optional
            datetime of the start of the time period, by default None
        end : Optional[Union[datetime, str]], optional
            datetime of the end of the time period, by default utcnow
        period : Optional[Union[timedelta, str]], optional
            duration of the period, by default None

        Raises
        ------
        ValueError
            If neither `start` nor `period` are specified.

        """
        start, end, period = self._process_args(timespan, start, end, period)

        if not start and not period:
            raise ValueError(
                "start, period",
                "At least one of 'start' or 'period' must be specified.",
            )

        self._period = None
        if period:
            self._period = self._parse_timedelta(period)

        self._end = self._parse_time(end, "end")
        self._start = self._parse_time(start, "start")
        if self._start and self._period:
            self._end = self._start + self._period
        if self._end is None:
            self._end = datetime.utcnow()
        if self._start is None and self._period:
            self._start = self._end - self._period

    def __eq__(self, value):
        """Return True if the timespans are equal."""
        if not isinstance(value, TimeSpan):
            return False
        return self.start == value.start and self.end == value.end

    def __hash__(self):
        """Return the hash of the timespan."""
        return hash((self.start, self.end))

    def __repr__(self):
        """Return repr string."""
        return (
            f"{self.__class__.__name__}"
            f"(start={self.start}, end={self.end}, period={self.period})"
        )

    @property
    def start(self) -> datetime:
        """
        Return the start of the timeperiod.

        Returns
        -------
        datetime
            Start datetime.

        """
        return self._start

    @property
    def end(self) -> datetime:
        """
        Return the end of the timeperiod.

        Returns
        -------
        datetime
            End datetime.

        """
        return self._end

    @property
    def period(self) -> timedelta:
        """
        Return the period of the timeperiod.

        Returns
        -------
        timedelta
            Period timedelta.

        """
        if not self._period:
            self._period = self.end - self.start
        return self._period

    @staticmethod
    def _process_args(timespan, start, end, period):
        if timespan:
            if isinstance(timespan, TimeSpan):
                start = timespan.start
                end = timespan.end
                period = timespan.period
            elif isinstance(timespan, tuple):
                start = timespan[0]
                end = timespan[1]
        if not start and hasattr(timespan, "start"):
            start = getattr(timespan, "start", None)
        if not end and hasattr(timespan, "end"):
            end = getattr(timespan, "end", None)
        if not period and hasattr(timespan, "period"):
            period = getattr(timespan, "period", None)
        return start, end, period

    @staticmethod
    def _parse_time(time_val, prop_name):
        if time_val is None:
            return None
        if isinstance(time_val, datetime):
            return time_val
        try:
            if isinstance(time_val, str):
                return pd.to_datetime(time_val, infer_datetime_format=True)
        except (ValueError, ParserError):
            pass
        raise ValueError(f"'{prop_name}' must be a datetime or a datetime string.")

    @staticmethod
    def _parse_timedelta(time_val):
        if time_val is None:
            return None
        if isinstance(time_val, timedelta):
            return time_val
        try:
            if isinstance(time_val, str):
                return pd.Timedelta(time_val).to_pytimedelta()
        except (ValueError, ParserError):
            pass
        raise ValueError(
            "'period' must be a pandas-compatible time period string",
            " or Python timedelta.",
        )
