# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
r"""
eventcluster module.

This module is intended to be used to summarize large numbers of events
into clusters of different patterns. High volume repeating events can
often make it difficult to see unique and interesting items.

The module contains functions to generate clusterable features from
string data. For example, an administration command that does some
maintenance on thousands of servers with a commandline such as:
``install-update -hostname {host.fqdn} -tmp:/tmp/{GUID}/rollback``\  can
be collapsed into a single cluster pattern by ignoring the character
values in the string and using delimiters or tokens to group the values.

This is an unsupervised learning module implemented using SciKit Learn
DBScan.

Contains:
dbcluster_events: generic clustering method using DBSCAN designed to summarize
process events and other similar data by grouping on common features.

add_process_features: derives numerical features from text features such as
commandline and process path.

"""
from binascii import crc32
from functools import lru_cache
from math import log10, floor
import re
from typing import List, Any, Tuple, Union

import numpy as np
import pandas as pd

from ..common.exceptions import MsticpyImportExtraError
from ..common.utility import export
from .._version import VERSION

try:
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import Normalizer
    import matplotlib.pyplot as plt
    from matplotlib import cm
except ImportError as imp_err:
    raise MsticpyImportExtraError(
        "Cannot use this feature without Sklearn and matplotlib installed",
        title="Error importing Scikit Learn and matplotlib",
        extra="ml",
    ) from imp_err

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=too-many-arguments, too-many-locals
@export
def dbcluster_events(
    data: Any,
    cluster_columns: List[Any] = None,
    verbose: bool = False,
    normalize: bool = True,
    time_column: str = "TimeCreatedUtc",
    max_cluster_distance: float = 0.01,
    min_cluster_samples: int = 2,
    **kwargs,
) -> Tuple[pd.DataFrame, DBSCAN, np.ndarray]:
    """
    Cluster data set according to cluster_columns features.

    Parameters
    ----------
    data : Any
        Input data as a pandas DataFrame or numpy array
    cluster_columns : List[Any], optional
        List of columns to use for features
        - for DataFrame this is a list of column names
        - for numpy array this is a list of column indexes
    verbose : bool, optional
        Print additional information about clustering results (the default is False)
    normalize : bool, optional
        Normalize the input data (should probably always be True)
    time_column : str, optional
        If there is a time column the output data will be ordered by this
        (the default is 'TimeCreatedUtc')
    max_cluster_distance : float, optional
        DBSCAN eps (max cluster member distance) (the default is 0.01)
    min_cluster_samples : int, optional
        DBSCAN min_samples (the minimum cluster size) (the default is 2)

    Other Parameters
    ----------------
    kwargs: Other arguments are passed to DBSCAN constructor

    Returns
    -------
    Tuple[pd.DataFrame, DBSCAN, np.ndarray]
        Output dataframe with clustered rows
        DBSCAN model
        Normalized data set

    """
    allowed_types = [np.ndarray, pd.DataFrame]

    x_input = None
    if isinstance(data, pd.DataFrame):
        if cluster_columns is None:
            x_input = data.values
        else:
            x_input = data[cluster_columns].values
    elif isinstance(data, np.ndarray):
        x_input = data if cluster_columns is None else data[:, cluster_columns].values
    if x_input is None:
        mssg = "Input data not in expected format.\n{} is not one of allowed types {}"
        type_list = ", ".join(str(t) for t in allowed_types)
        mssg = mssg.format(str(type(data)), type_list)
        raise ValueError(mssg)

    # Create DBSCAN cluster object
    db_cluster = DBSCAN(
        eps=max_cluster_distance, min_samples=min_cluster_samples, **kwargs
    )

    # Normalize the data (most clustering algorithms don't do well with
    # unnormalized data)
    x_norm = Normalizer().fit_transform(x_input) if normalize else x_input
    # fit the data set
    db_cluster.fit(x_norm)
    labels = db_cluster.labels_
    cluster_set, counts = np.unique(labels, return_counts=True)
    if verbose:
        print(
            "Clustering for set size ",
            len(x_norm),
            " - ",
            len(cluster_set),
            " clusters",
        )
        print("Individual cluster sizes: ", ", ".join(str(c) for c in counts))

    clustered_events = _merge_clustered_items(
        cluster_set, labels, data, time_column, counts
    )

    if verbose:
        print("Cluster output rows: ", len(clustered_events))

    return clustered_events, db_cluster, x_norm


def _merge_clustered_items(
    cluster_set: np.array,
    labels: np.array,
    data: Union[pd.DataFrame, np.array],
    time_column: str,
    counts: np.array,
) -> pd.DataFrame:
    """
    Merge outliers and core clusters into single DataFrame.

    Parameters
    ----------
    cluster_set : np.array
        The set of clusters
    labels : np.array
        The cluster labels
    data : Union[pd.DataFrame, np.array]
        The source data
    time_column : str
        Name of the Time column
    counts : np.array
        The counts of members in each cluster

    Returns
    -------
    pd.DataFrame
        Merged dataframe

    """
    tz_aware = data.iloc[0][time_column].tz
    ts_type = "datetime64[ns, UTC]" if tz_aware is not None else "datetime64[ns]"

    cluster_list = []
    # Iterate through clusters, adding exemplar to output frame
    # pylint: disable=consider-using-enumerate
    # we need to know the index of the item within the loop
    for idx in range(len(cluster_set)):
        cluster_id = cluster_set[idx]
        class_members = labels == cluster_id
        if isinstance(data, pd.DataFrame):
            time_ordered = data[class_members].sort_values(time_column, ascending=True)
            first_event_time = time_ordered[0:][time_column].iat[0]
            last_event_time = time_ordered[-1:][time_column].iat[0]
        else:
            first_event_time = None
            last_event_time = None

        if cluster_id == -1:
            # 'Noise' events are individual items that could not be assigned
            # to a cluster and so are unique
            cluster_list.append(
                data[class_members]
                .assign(
                    Clustered=False,
                    ClusterId=cluster_id,
                    ClusterSize=1,
                    TimeGenerated=first_event_time,
                    FirstEventTime=first_event_time,
                    LastEventTime=last_event_time,
                )
                .astype(
                    dtype={
                        "TimeGenerated": ts_type,
                        "FirstEventTime": ts_type,
                        "LastEventTime": ts_type,
                    }
                )
            )
        else:
            # Otherwise, just choose the first example of the cluster set
            cluster_list.append(
                data[class_members]
                .assign(
                    Clustered=True,
                    ClusterId=cluster_id,
                    ClusterSize=counts[idx],
                    TimeGenerated=first_event_time,
                    FirstEventTime=first_event_time,
                    LastEventTime=last_event_time,
                )[0:1]
                .astype(
                    dtype={
                        "TimeGenerated": ts_type,
                        "FirstEventTime": ts_type,
                        "LastEventTime": ts_type,
                    }
                )
            )
    # pylint: enable=consider-using-enumerate
    return pd.concat(cluster_list)


@export
def add_process_features(
    input_frame: pd.DataFrame, path_separator: str = None, force: bool = False
) -> pd.DataFrame:
    r"""
    Add numerical features based on patterns of command line and process name.

    Parameters
    ----------
    input_frame : pd.DataFrame
        The input dataframe
    path_separator : str, optional
        Path separator. If not supplied, try to determine
        from 'NewProcessName' column of first 10 rows
        (the default is None)
    force : bool, optional
        Forces re-calculation of feature columns even if they
        already exist (the default is False)

    Returns
    -------
    pd.DataFrame
        Copy of the dataframe with the additional numeric features

    Notes
    -----
    Features added:

    - processNameLen: length of process file name (inc path)
    - processNameTokens: the number of elements in the path
    - processName: the process file name (minus path)
    - commandlineTokens: number of space-separated tokens in the command line
    - commandlineLen: length of the command line
    - commandlineLogLen: log10 length of commandline
    - isSystemSession: 1 if session Id is 0x3e7 for Windows or -1 for Linux
    - commandlineTokensFull: counts number of token separators in commandline
      [\\s\-\\/\.,"\'\|&:;%$()]
    - pathScore: sum of ord() value of characters in path
    - pathLogScore: log10 of pathScore
    - commandlineScore: sum of ord() value of characters in commandline
    - commandlineLogScore: log10 of commandlineScore

    """
    output_df = input_frame.copy()

    # Set any NaN values to empty string
    if "NewProcessName" in output_df and "CommandLine" in output_df:
        output_df[["NewProcessName", "CommandLine"]] = output_df[
            ["NewProcessName", "CommandLine"]
        ].fillna(value="")

    # try to determine the path separator
    if path_separator is None:
        sample_df = output_df.head(10)
        lx_path = len(sample_df[sample_df["NewProcessName"].str.contains("/")])
        path_separator = "/" if lx_path else "\\"
    # Create features from process name and command line
    if "NewProcessName" in output_df:
        _add_processname_features(output_df, force, path_separator)

    if "CommandLine" in output_df:
        _add_commandline_features(output_df, force)

    if "SubjectLogonId" in output_df and ("isSystemSession" not in output_df or force):
        output_df["isSystemSession"] = output_df["SubjectLogonId"].isin(["0x3e7", "-1"])

    return output_df


def _add_processname_features(
    output_df: pd.DataFrame, force: bool, path_separator: str
):
    """
    Add process name default features.

    Parameters
    ----------
    output_df : pd.DataFrame
        The dataframe to add features to
    force : bool
        If True overwrite existing feature columns
    path_separator : str
        Path separator for OS

    """
    if "processName" not in output_df or force:
        output_df["processName"] = output_df.apply(
            lambda x: x.NewProcessName.split(path_separator)[-1], axis=1
        )
    if "pathScore" not in output_df or force:
        output_df["pathScore"] = output_df.apply(
            lambda x: char_ord_score(x.NewProcessName), axis=1
        )
    if "pathLogScore" not in output_df or force:
        output_df["pathLogScore"] = output_df.apply(
            lambda x: log10(x.pathScore) if x.pathScore else 0, axis=1
        )
    if "pathHash" not in output_df or force:
        output_df["pathHash"] = output_df.apply(
            lambda x: crc32_hash(x.NewProcessName), axis=1
        )


def _add_commandline_features(output_df: pd.DataFrame, force: bool):
    """
    Add commandline default features.

    Parameters
    ----------
    output_df : pd.DataFrame
        The dataframe to add features to
    force : bool
        If True overwrite existing feature columns

    """
    if "commandlineLen" not in output_df or force:
        output_df["commandlineLen"] = output_df.apply(
            lambda x: len(x.CommandLine), axis=1
        )
    if "commandlineLogLen" not in output_df or force:
        output_df["commandlineLogLen"] = output_df.apply(
            lambda x: log10(x.commandlineLen) if x.commandlineLen else 0, axis=1
        )
    if "commandlineTokensFull" not in output_df or force:
        output_df["commandlineTokensFull"] = output_df[["CommandLine"]].apply(
            lambda x: delim_count(x.CommandLine), axis=1
        )

    if "commandlineScore" not in output_df or force:
        output_df["commandlineScore"] = output_df.apply(
            lambda x: char_ord_score(x.CommandLine), axis=1
        )
    if "commandlineTokensHash" not in output_df or force:
        output_df["commandlineTokensHash"] = output_df.apply(
            lambda x: delim_hash(x.CommandLine), axis=1
        )


@export
@lru_cache(maxsize=1024)
def delim_count(value: str, delim_list: str = r'[\s\-\\/\.,"\'|&:;%$()]') -> int:
    r"""
    Count the delimiters in input column.

    Parameters
    ----------
    value : str
        Data to process
    delim_list : str, optional
        delimiters to use. (the default is r'[\\s\\\\-\\\\\\\\/\.,"\\\\'|&:;%$()]')

    Returns
    -------
    int
        Count of delimiters in the string.

    """
    return len(re.findall(delim_list, value))


@export
@lru_cache(maxsize=1024)
def delim_hash(value: str, delim_list: str = r'[\s\-\\/\.,"\'|&:;%$()]') -> int:
    r"""
    Return a hash (CRC32) of the delimiters from input column.

    Parameters
    ----------
    value : str
        Data to process
    delim_list : str, optional
        delimiters to use. (the default is r'[\\s\\\\-\\\\\\\\/\.,"\\\\'|&:;%$()]')

    Returns
    -------
    int
        Hash of delimiter set in the string.

    """
    return crc32(bytes("".join(re.findall(delim_list, value)), "utf-8"))


@export
@lru_cache(maxsize=1024)
def char_ord_score(value: str, scale: int = 1) -> int:
    """
    Return sum of ord values of characters in string.

    Parameters
    ----------
    value : str
        Data to process
    scale : int, optional
        reduce the scale of the feature (reducing the
        influence of variations this feature on the clustering
        algorithm (the default is 1)

    Returns
    -------
    int
        [description]

    Notes
    -----
    This function sums the ordinal value of each character in the
    input string. Two strings with minor differences will result in
    a similar score. However, for strings with highly variable content
    (e.g. command lines or http requests containing GUIDs) this may result
    in too much variance to be useful when you are trying to detect
    similar patterns. You can use the scale parameter to reduce the
    influence of features using this function on clustering and anomaly
    algorithms.

    """
    return floor(sum(ord(x) for x in value) / scale)


@export
@lru_cache(maxsize=1024)
def token_count(value: str, delimiter: str = " ") -> int:
    """
    Return count of delimiter-separated tokens pd.Series column.

    Parameters
    ----------
    value : str
        Data to process
    delimiter : str, optional
        Delimiter used to split the column string.
        (the default is ' ')

    Returns
    -------
    int
        count of tokens

    """
    return len(value.split(delimiter))


def _string_score(input_str):
    """Sum the ord(c) for characters in a string."""
    return sum(ord(x) for x in input_str)


@export
@lru_cache(maxsize=1024)
def crc32_hash(value: str) -> int:
    """
    Return the CRC32 hash of the input column.

    Parameters
    ----------
    value : str
        Data to process

    Returns
    -------
    int
        CRC32 hash

    """
    return crc32(bytes(value.encode("utf-8")))


@export
def delim_count_df(
    data: pd.DataFrame, column: str, delim_list: str = r'[\s\-\\/\.,"\'|&:;%$()]'
) -> pd.Series:
    r"""
    Count the delimiters in input column.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame to process
    column : str
        The name of the column to process
    delim_list : str, optional
        delimiters to use. (the default is r\'[\\s\\\\-\\\\\\\\/\.,"\\\\'|&:;%$()]\')

    Returns
    -------
    pd.Series
        Count of delimiters in the string in `column`.

    """
    return data[column].str.count(delim_list)


@export
def char_ord_score_df(data: pd.DataFrame, column: str, scale: int = 1) -> pd.Series:
    """
    Return sum of ord values of characters in string.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame to process
    column : str
        Column name to process
    scale : int, optional
        reduce the scale of the feature (reducing the
        influence of variations this feature on the clustering
        algorithm (the default is 1)

    Returns
    -------
    pd.Series
        The sum of the ordinal values of the characters
        in `column`.

    Notes
    -----
    This function sums the ordinal value of each character in the
    input string. Two strings with minor differences will result in
    a similar score. However, for strings with highly variable content
    (e.g. command lines or http requests containing GUIDs) this may result
    in too much variance to be useful when you are trying to detect
    similar patterns. You can use the scale parameter to reduce the
    influence of features using this function on clustering and anomaly
    algorithms.

    """
    return data.apply(lambda x: sum(ord(char) for char in x[column]) / scale, axis=1)


@export
def token_count_df(data: pd.DataFrame, column: str, delimiter: str = " ") -> pd.Series:
    """
    Return count of delimiter-separated tokens pd.Series column.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame to process
    column : str
        Column name to process
    delimiter : str, optional
        Delimiter used to split the column string.
        (the default is ' ')

    Returns
    -------
    pd.Series
        count of tokens in strings in `column`

    """
    return data.apply(lambda x: len(x[column].split(delimiter)), axis=1)


@export
def crc32_hash_df(data: pd.DataFrame, column: str) -> pd.Series:
    """
    Return the CRC32 hash of the input column.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame to process
    column : str
        Column name to process

    Returns
    -------
    pd.Series
        CRC32 hash of input column

    """
    return data.apply(lambda x: crc32(bytes(x[column].encode("utf-8"))), axis=1)


# pylint: disable=too-many-arguments, too-many-statements
@export  # noqa: C901, MC0001
def plot_cluster(
    db_cluster: DBSCAN,
    data: pd.DataFrame,
    x_predict: np.ndarray,
    plot_label: str = None,
    plot_features: Tuple[int, int] = (0, 1),
    verbose: bool = False,
    cut_off: int = 3,
    xlabel: str = None,
    ylabel: str = None,
):
    """
    Plot clustered data as scatter chart.

    Parameters
    ----------
    db_cluster : DBSCAN
        DBScan Cluster (from SkLearn DBSCAN).
    data : pd.DataFrame
        Dataframe containing original data.
    x_predict : np.ndarray
        The DBSCAN predict numpy array
    plot_label : str, optional
         If set the column to use to label data points
         (the default is None)
    plot_features :  Tuple[int, int], optional
        Which two features in x_predict to plot (the default is (0, 1))
    verbose : bool, optional
        Verbose execution with some extra info
        (the default is False)
    cut_off : int, optional
        The cluster size below which items are considered outliers
        (the default is 3)
    xlabel : str, optional
        x-axis label (the default is None)
    ylabel : str, optional
        y-axis label (the default is None)

    """
    max_idx = x_predict.shape[1] - 1
    if plot_features[0] >= x_predict.shape[1]:
        raise ValueError(
            "plot_features[0] index must be a value from 0 to {}.".format(max_idx)
        )
    if plot_features[1] >= x_predict.shape[1]:
        raise ValueError(
            "plot_features[1] index must be a value from 0 to {}.".format(max_idx)
        )
    if plot_features[0] == plot_features[1]:
        mssg = "plot_features indexes must be 2 different values in range 0 to"
        raise ValueError(mssg + f" {max_idx}.")

    labels = db_cluster.labels_
    core_samples_mask = np.zeros_like(labels, dtype=bool)

    # pylint: disable=unsupported-assignment-operation
    # (assignment of numpy array is valid)
    core_samples_mask[db_cluster.core_sample_indices_] = True
    unique_labels = set(labels)

    # pylint: disable=no-member
    # Spectral color map does exist
    colors = [cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]
    # Number of clusters in labels, ignoring noise if present.
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise_ = list(labels).count(-1)
    _, counts = np.unique(labels, return_counts=True)

    if verbose:
        print("Estimated number of clusters: %d" % n_clusters_)
        print("Estimated number of noise points: %d" % n_noise_)
        # print("Silhouette Coefficient: %0.3f"
        #       % metrics.silhouette_score(x_predict, labels))

    if (
        not isinstance(data, pd.DataFrame)
        or plot_label is not None
        and plot_label not in data
    ):
        plot_label = None
    p_label = None
    for cluster_id, color in zip(unique_labels, colors):
        if cluster_id == -1:
            # Black used for noise.
            color = [0, 0, 0, 1]
        class_member_mask = labels == cluster_id

        cluster_size = counts[cluster_id]
        marker_size = cluster_size
        marker = "o"
        font_size = "small"
        alpha = 0.4

        if cluster_size < cut_off:
            marker = "+"
            marker_size = 10
            font_size = "large"
            alpha = 1.0
        xy_pos = x_predict[class_member_mask & core_samples_mask]
        plt.plot(
            xy_pos[:, plot_features[0]],
            xy_pos[:, plot_features[1]],
            marker,
            markerfacecolor=tuple(color),
            markersize=marker_size,
        )

        if plot_label:
            first_row = data[class_member_mask].iloc[0]
            if not first_row.empty and plot_label in first_row:
                p_label = first_row[plot_label]
                try:
                    plt.annotate(
                        p_label,
                        xy=(xy_pos[0, plot_features[0]], xy_pos[0, plot_features[1]]),
                        fontsize=font_size,
                        alpha=alpha,
                    )
                except IndexError:
                    pass

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title("Estimated number of clusters: %d" % n_clusters_)
    plt.show()
    return plt
