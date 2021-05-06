# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Module for timeseries analysis functions."""
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from .._version import VERSION
from ..common.exceptions import MsticpyException, MsticpyImportExtraError
from ..common.timespan import TimeSpan
from ..common.utility import check_kwargs, export

try:
    from scipy import stats
    from statsmodels.tsa.seasonal import STL
except ImportError as imp_err:
    raise MsticpyImportExtraError(
        "Cannot use this feature without scipy and statsmodel installed",
        title="Error importing package",
        extra="ml",
    ) from imp_err

__version__ = VERSION
__author__ = "Ashwin Patil"


# Constants
_DEFAULT_KWARGS = ["seasonal", "period", "score_threshold"]


@export
def ts_anomalies_stl(data: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    Return anomalies in Timeseries using STL.

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame as a time series data set retrived from data connector or
        external data source. Dataframe must have 2 columns with time column
        set as index and other numeric value.

    Other Parameters
    ----------------
    seasonal : int, optional
        Seasonality period of the input data required for STL.
        Must be an odd integer, and should normally be >= 7 (default).
    period: int, optional
        Periodicity of the the input data. by default 24 (Hourly).
    score_threshold : float, optional
        standard deviation threshold value calculated using Z-score used to
        flag anomalies, by default 3

    Returns
    -------
    pd.DataFrame
        Returns a dataframe with additional columns by decomposing time series data
        into residual, trend, seasonal, weights, baseline, score and anomalies.
        The anomalies column will have 0, 1,-1 values based on score_threshold set.

    Notes
    -----
    The decomposition method is STL - Seasonal-Trend Decomposition using LOESS

    """
    check_kwargs(kwargs, _DEFAULT_KWARGS)
    seasonal: int = kwargs.get("seasonal", 7)
    period: int = kwargs.get("period", 24)
    score_threshold: float = kwargs.get("score_threshold", 3.0)

    if not isinstance(data, pd.DataFrame):
        raise MsticpyException("input data should be a pandas dataframe")

    # STL method does Season-Trend decomposition using LOESS.
    # Accepts timeseries dataframe
    stl = STL(data, seasonal=seasonal, period=period)
    # Fitting the data - Estimate season, trend and residuals components.
    res = stl.fit()
    result = data.copy()
    # Create dataframe columns from decomposition results
    result["residual"] = res.resid
    result["trend"] = res.trend
    result["seasonal"] = res.seasonal
    result["weights"] = res.weights
    # Baseline is generally seasonal + trend
    result["baseline"] = result["seasonal"] + result["trend"]
    # Type cast and replace na values with 0
    result = result.fillna(0).astype("int64")
    # Calculate zscore based on residual column
    # this column does not contain seasonal/trend components
    result["score"] = stats.zscore(result["residual"])
    # create spikes(1) and dips(-1) based on threshold and seasonal columns
    result.loc[
        (result["score"] > score_threshold) & (result["seasonal"] > 0), "anomalies"
    ] = 1
    result.loc[
        (result["score"] > score_threshold) & (result["seasonal"] < 0), "anomalies"
    ] = -1
    result.loc[(result["score"] < score_threshold), "anomalies"] = 0
    # Datatype casting
    result["anomalies"] = result["anomalies"].astype("int64")
    result = result.reset_index()
    return result


timeseries_anomalies_stl = ts_anomalies_stl


def extract_anomaly_periods(
    data: pd.DataFrame,
    time_column: str = "TimeGenerated",
    period: str = "1H",
    pos_only: bool = True,
) -> Dict[datetime, datetime]:
    """
    Merge adjacent anomaly periods.

    Parameters
    ----------
    data : pd.DataFrame
        The data to process
    time_column : str, optional
        The name of the time column
    period : str, optional
        pandas-compatible time period designator,
        by default "1H"
    pos_only : bool, optional
        If True only extract positive anomaly periods,
        else extract both positive and negative.
        By default, True

    Returns
    -------
    Dict[datetime, datetime] :
        start_period, end_period

    """
    # Resample data based on period - period is the granularity that
    # we want to merge 2 adject samples on.
    anom_filter = [1] if pos_only else [1, -1]
    resampled = (
        data[(data["anomalies"].isin(anom_filter))]
        .sort_values(time_column)
        .set_index(time_column)
        .resample(period)
    )

    end_period = None
    start_period = None
    periods = {}

    # iterate through the resampled data
    for time, group in resampled:
        if group.empty:
            continue
        if not end_period:
            # If we're not already in an anomaly period
            # create start/end for a new one
            start_period = time - pd.Timedelta(period)
            end_period = time + pd.Timedelta(period)
            periods[start_period] = end_period
        elif (time - end_period) <= pd.Timedelta(
            period
        ) * 2 and start_period is not None:
            # if the current time is less than 2x the period away
            # from our current end_period time, update the end_time
            periods[start_period] = time + pd.Timedelta(period)
        else:
            # otherwise start a new period
            start_period = time - pd.Timedelta(period)
            periods[start_period] = time + pd.Timedelta(period)
        end_period = time
    return periods


def find_anomaly_periods(
    data: pd.DataFrame,
    time_column: str = "TimeGenerated",
    period: str = "1H",
    pos_only: bool = True,
) -> List[TimeSpan]:
    """
    Merge adjacent anomaly periods.

    Parameters
    ----------
    data : pd.DataFrame
        The data to process
    time_column : str, optional
        The name of the time column
    period : str, optional
        pandas-compatible time period designator,
        by default "1H"
    pos_only : bool, optional
        If True only extract positive anomaly periods,
        else extract both positive and negative.
        By default, True

    Returns
    -------
    List[TimeSpan] :
        TimeSpan(start, end)

    """
    return [
        TimeSpan(start=key, end=val)
        for key, val in extract_anomaly_periods(
            data=data, time_column=time_column, period=period, pos_only=pos_only
        ).items()
    ]


def create_time_period_kqlfilter(periods: Dict[datetime, datetime]) -> str:
    """
    Create KQL time filter expression from time periods dict.

    Parameters
    ----------
    periods : Dict[datetime, datetime]
        Dict of start, end periods

    Returns
    -------
    str
        KQL filter clause

    """
    time_column = "TimeGenerated"
    time_brackets = [
        f"{time_column} between (datetime({start}) .. datetime({end}))"
        for start, end in periods.items()
    ]

    return f"| where {' or '.join(time_brackets)}"


def set_new_anomaly_threshold(
    data: pd.DataFrame, threshold: int, threshold_low: Optional[int] = None
) -> pd.DataFrame:
    """
    Return DataFrame with anomalies calculated based on new threshold.

    Parameters
    ----------
    data : pd.DataFrame
        Input DataFrame
    threshold : int
        Threshold above (beyond) which values will be marked as
        anomalies. Used as positive and negative threshold
        unless `threshold_low` is specified.
    threshold_low : Optional[int], optional
        The threshhold below which values will be reported
        as anomalies, by default None.

    Returns
    -------
    pd.DataFrame
        Output DataFrame with recalculated anomalies.

    """
    threshold_low = threshold_low or threshold
    new_df = data.assign(newanomalies=0)
    new_df.loc[new_df["score"] >= threshold, "newanomalies"] = 1
    new_df.loc[new_df["score"] <= -threshold_low, "newanomalies"] = -1
    return new_df.drop(columns=["anomalies"]).rename(
        columns={"newanomalies": "anomalies"}
    )
