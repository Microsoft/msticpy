# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Module for common display functions."""
from datetime import datetime
from typing import Any, Union, Set, Dict, Tuple, List

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
from pandas.errors import OutOfBoundsDatetime
from bokeh.io import output_notebook, show
from bokeh.models.annotations import LegendItem
from bokeh.models import (
    ColumnDataSource,
    DatetimeTickFormatter,
    HoverTool,
    Label,
    Legend,
    RangeTool,
    Title,
)

# pylint: disable=too-many-lines
# pylint: disable=no-name-in-module
from bokeh.palettes import viridis

# pylint: enable=no-name-in-module
from bokeh.plotting import figure, reset_output
from bokeh.layouts import column

from .._version import VERSION
from ..common.utility import export, check_kwargs

__version__ = VERSION
__author__ = "Ian Hellen"


# Constants
_WRAP = 50
_WRAP_CMDL = "WrapCmdl"
_DEFAULT_KWARGS = [
    "color",
    "data",
    "group_by",
    "height",
    "legend",
    "range_tool",
    "ref_event",
    "ref_time",
    "source_columns",
    "time_column",
    "title",
    "width",
    "yaxis",
]

_TL_KWARGS = [
    "alert",
    "overlay_color",
    "overlay_data",
    "ref_time",
    "ygrid",
    "xgrid",
    "hide",
]


@export
def display_timeline(
    data: Union[pd.DataFrame, dict],
    time_column: str = "TimeGenerated",
    source_columns: list = None,
    **kwargs,
) -> figure:
    """
    Display a timeline of events.

    Parameters
    ----------
    data : Union[dict, pd.DataFrame]
        Either
        dict of data sets to plot on the timeline with the following structure::

            Key (str) - Name of data set to be displayed in legend
            Value (Dict[str, Any]) - containing:
                data (pd.DataFrame) - Data to plot
                time_column (str, optional) - Name of the timestamp column
                source_columns (list[str], optional) - source columns to use
                    in tooltips
                color (str, optional) - color of datapoints for this data
            If any of the last values are omitted, they default to the values
            supplied as parameters to the function (see below)

        Or
        DataFrame as a single data set or grouped into individual
        plot series using the `group_by` parameter
    time_column : str, optional
        Name of the timestamp column
        (the default is 'TimeGenerated')
    source_columns : list, optional
        List of default source columns to use in tooltips
        (the default is None)

    Other Parameters
    ----------------
    title : str, optional
        Title to display (the default is None)
    alert : SecurityAlert, optional
        Add a reference line/label using the alert time (the default is None)
    ref_event : Any, optional
        Add a reference line/label using the alert time (the default is None)
    ref_time : datetime, optional
        Add a reference line/label using `ref_time` (the default is None)
    group_by : str
        (where `data` is a DataFrame)
        The column to group timelines on
    legend: str, optional
        "left", "right", "inline" or "none"[data]
        (the default is to show a legend when plotting multiple series
        and not to show one when plotting a single series)
    yaxis : bool, optional
        Whether to show the yaxis and labels (default is False)
    ygrid : bool, optional
        Whether to show the yaxis grid (default is False)
    xgrid : bool, optional
        Whether to show the xaxis grid (default is True)
    range_tool : bool, optional
        Show the the range slider tool (default is True)
    height : int, optional
        The height of the plot figure
        (the default is auto-calculated height)
    width : int, optional
        The width of the plot figure (the default is 900)
    color : str
        Default series color (default is "navy")
    overlay_color : str
        Overlay series color (default is "green")

    Returns
    -------
    figure
        The bokeh plot figure.

    """
    # Get args
    check_kwargs(kwargs, _DEFAULT_KWARGS + _TL_KWARGS)
    overlay_data: pd.DataFrame = kwargs.pop("overlay_data", None)
    overlay_columns: list = kwargs.pop("overlay_columns", source_columns)
    color: str = kwargs.get("color", "navy")  # don't remove this from kwargs
    overlay_color: str = kwargs.pop("overlay_color", "green")

    kwargs_sub = kwargs.copy()
    kwargs_sub["time_column"] = time_column
    kwargs_sub["source_columns"] = source_columns
    kwargs_sub["ref_time"], kwargs_sub["ref_label"] = _get_ref_event_time(**kwargs)

    if isinstance(data, pd.DataFrame):
        if overlay_data is not None:
            aggr_data = {
                "Primary": {
                    "data": data,
                    "time_column": time_column,
                    "source_columns": source_columns,
                    "color": color,
                },
                "Secondary": {
                    "data": overlay_data,
                    "time_column": time_column,
                    "source_columns": overlay_columns,
                    "color": overlay_color,
                },
            }
            return _display_timeline_dict(data=aggr_data, **kwargs_sub)

        # Create a dictionary from a grouped or simple series
        series_dict = _create_dict_from_grouping(
            data=data,
            source_columns=source_columns,
            time_column=time_column,
            group_by=kwargs.get("group_by", None),
            color=kwargs.get("color", "navy"),
        )
        return _display_timeline_dict(data=series_dict, **kwargs_sub)

    if isinstance(data, dict):
        return _display_timeline_dict(data, **kwargs_sub)
    return None


_TL_VALUE_KWARGS = ["kind", "y", "x"]


# pylint: disable=invalid-name, too-many-locals, too-many-statements, too-many-branches
@export  # noqa: C901, MC0001
def display_timeline_values(
    data: pd.DataFrame,
    y: str,
    time_column: str = "TimeGenerated",
    source_columns: list = None,
    **kwargs,
) -> figure:
    """
    Display a timeline of events.

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame as a single data set or grouped into individual
        plot series using the `group_by` parameter
    time_column : str, optional
        Name of the timestamp column
        (the default is 'TimeGenerated')
    y : str
        The column name holding the value to plot vertically
    source_columns : list, optional
        List of default source columns to use in tooltips
        (the default is None)

    Other Parameters
    ----------------
    x : str, optional
        alias of `time_column`
    title : str, optional
        Title to display (the default is None)
    ref_event : Any, optional
        Add a reference line/label using the alert time (the default is None)
    ref_time : datetime, optional
        Add a reference line/label using `ref_time` (the default is None)
    group_by : str
        (where `data` is a DataFrame)
        The column to group timelines on
    legend: str, optional
        "left", "right", "inline" or "none"
        (the default is to show a legend when plotting multiple series
        and not to show one when plotting a single series)
    yaxis : bool, optional
        Whether to show the yaxis and labels
    range_tool : bool, optional
        Show the the range slider tool (default is True)
    height : int, optional
        The height of the plot figure
        (the default is auto-calculated height)
    width : int, optional
        The width of the plot figure (the default is 900)
    color : str
        Default series color (default is "navy"). This is overridden by
        automatic color assignments if plotting a grouped chart
    kind : Union[str, List[str]]
        one or more glyph types to plot., optional
        Supported types are "circle", "line" and "vbar" (default is "vbar")

    Returns
    -------
    figure
        The bokeh plot figure.

    """
    check_kwargs(kwargs, _DEFAULT_KWARGS + _TL_VALUE_KWARGS)

    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        print("No data to plot.")
        return figure()

    reset_output()
    output_notebook()
    height: int = kwargs.pop("height", None)
    width: int = kwargs.pop("width", 900)
    title: str = kwargs.pop("title", None)
    time_column = kwargs.get("x", time_column)
    group_by: str = kwargs.get("group_by", None)
    show_yaxis: bool = kwargs.pop("yaxis", True)
    show_range: bool = kwargs.pop("range_tool", True)
    color: str = kwargs.get("color", "navy")
    legend_pos: str = kwargs.pop("legend", None)
    kind: Any = kwargs.pop("kind", ["vbar"])
    plot_kinds = kind if isinstance(kind, list) else [kind]
    hide: bool = kwargs.pop("hide", False)

    ref_time, ref_label = _get_ref_event_time(**kwargs)

    if source_columns is None:
        source_columns = [y]
    if y not in source_columns:
        source_columns.append(y)
    graph_df, group_count_df, tool_tip_columns, series_count = _create_data_grouping(
        data, source_columns, time_column, group_by, color
    )

    tooltips, formatters = _create_tool_tips(data, tool_tip_columns)
    hover = HoverTool(tooltips=tooltips, formatters=formatters)

    # Create the Plot figure
    title = title if title else "Timeline"
    min_time = graph_df[time_column].min()
    max_time = graph_df[time_column].max()
    start_range = min_time - ((max_time - min_time) * 0.1)
    end_range = max_time + ((max_time - min_time) * 0.1)
    height = height if height else _calc_auto_plot_height(series_count)

    plot = figure(
        x_range=(start_range, end_range),
        min_border_left=50,
        plot_height=height,
        plot_width=width,
        x_axis_label="Event Time",
        x_axis_type="datetime",
        x_minor_ticks=10,
        y_axis_label=y,
        tools=[hover, "xwheel_zoom", "box_zoom", "reset", "save", "xpan"],
        toolbar_location="above",
        title=title,
    )
    plot.yaxis.visible = show_yaxis
    plot.ygrid.minor_grid_line_color = "navy"
    plot.ygrid.minor_grid_line_alpha = 0.1
    plot.ygrid.grid_line_color = "navy"
    plot.ygrid.grid_line_alpha = 0.3
    plot.xgrid.minor_grid_line_color = "navy"
    plot.xgrid.minor_grid_line_alpha = 0.1
    plot.xgrid.grid_line_color = "navy"
    plot.xgrid.grid_line_alpha = 0.3

    # set the tick datetime formatter
    plot.xaxis[0].formatter = _get_tick_formatter()

    # plot groups individually so that we can create an interactive legend
    if group_by:
        legend_items = []
        for _, group_id in group_count_df[group_by].items():
            first_group_item = graph_df[graph_df[group_by] == group_id].iloc[0]
            legend_label = str(first_group_item[group_by])
            inline_legend = str(group_id)
            group_color = first_group_item["color"]
            row_source = ColumnDataSource(graph_df[graph_df[group_by] == group_id])
            p_series = []
            # create default plot args
            plot_args: Dict[str, Any] = dict(
                x=time_column, alpha=0.7, source=row_source
            )
            if legend_pos != "none":
                plot_args["legend_label"] = str(inline_legend)

            if "vbar" in plot_kinds:
                p_series.append(plot.vbar(top=y, width=4, color="color", **plot_args))
            if "circle" in plot_kinds:
                p_series.append(plot.circle(y=y, size=4, color="color", **plot_args))
            if "line" in plot_kinds:
                p_series.append(
                    plot.line(y=y, line_width=2, line_color=group_color, **plot_args)
                )
            if not inline_legend:
                legend_items.append((legend_label, p_series))

        if legend_pos == "inline":
            # Position the inline legend
            plot.legend.location = "top_left"
            plot.legend.click_policy = "hide"
        elif legend_pos in ["left", "right"]:
            # Create the legend box outside of the plot area
            ext_legend = Legend(
                items=legend_items,
                location="center",
                click_policy="hide",
                label_text_font_size="8pt",
            )
            plot.add_layout(ext_legend, legend_pos)
    else:
        plot_args = dict(
            x=time_column, color=color, alpha=0.7, source=ColumnDataSource(graph_df)
        )
        if "vbar" in plot_kinds:
            plot.vbar(top=y, width=4, **plot_args)
        if "circle" in plot_kinds:
            plot.circle(y=y, size=4, **plot_args)
        if "line" in plot_kinds:
            plot.line(y=y, line_width=2, **plot_args)

    # if we have a reference, plot the time as a line
    if ref_time is not None:
        _add_ref_line(plot, ref_time, ref_label, data[y].max())

    if show_range:
        rng_select = _create_range_tool(
            data=graph_df,
            min_time=min_time,
            max_time=max_time,
            plot_range=plot.x_range,
            width=width,
            height=height,
            time_column=time_column,
        )
        plot_layout = column(plot, rng_select)
    else:
        plot_layout = plot

    if not hide:
        show(plot_layout)
    return plot_layout


# pylint: enable=invalid-name,too-many-locals, too-many-statements, too-many-branches


# pylint: disable=too-many-locals, too-many-statements, too-many-branches
def _display_timeline_dict(data: dict, **kwargs) -> figure:  # noqa: C901, MC0001
    """
    Display a timeline of events.

    Parameters
    ----------
    data : dict
        Data points to plot on the timeline.
            Need to contain:
                Key - Name of data type to be displayed in legend
                Value - dict of data containing:
                    data : pd.DataFrame
                        Data to plot
                    time_column : str
                        Name of the timestamp column
                    source_columns : list
                        List of source columns to use in tooltips
                    color: str
                        Color of datapoints for this data
    Other Parameters
    ----------------
    ref_time : datetime, optional
        Input reference line to display (the default is None)
    title : str, optional
        Title to display (the default is None)
    time_column : str, optional
        Name of the timestamp column
        (the default is 'TimeGenerated')
    legend: str, optional
        Where to position the legend
        None, left, right or inline (default is None)
    yaxis : bool, optional
        Whether to show the yaxis and labels
    range_tool : bool, optional
        Show the the range slider tool (default is True)
    source_columns : list, optional
        List of default source columns to use in tooltips
        (the default is None)
    height : int, optional
        The height of the plot figure
        (the default is auto-calculated height)
    width : int, optional
        The width of the plot figure (the default is 900)

    Returns
    -------
    figure
        The bokeh plot figure.

    """
    reset_output()
    output_notebook()

    height: int = kwargs.pop("height", None)
    width: int = kwargs.pop("width", 900)
    ref_time: Any = kwargs.pop("ref_time", None)
    ref_label: str = kwargs.pop("ref_label", None)
    title: str = kwargs.pop("title", None)
    legend_pos: str = kwargs.pop("legend", None)
    show_yaxis: bool = kwargs.pop("yaxis", False)
    show_range: bool = kwargs.pop("range_tool", True)
    xgrid: bool = kwargs.pop("xgrid", True)
    ygrid: bool = kwargs.pop("ygrid", False)
    hide: bool = kwargs.pop("hide", False)

    tool_tip_columns, min_time, max_time = _unpack_data_series_dict(data, **kwargs)
    series_count = len(data)

    tooltips, formatters = _create_tool_tips(data, tool_tip_columns)
    hover = HoverTool(tooltips=tooltips, formatters=formatters)

    title = f"Timeline: {title}" if title else "Event Timeline"
    try:
        start_range = min_time - ((max_time - min_time) * 0.1)
        end_range = max_time + ((max_time - min_time) * 0.1)
    except OutOfBoundsDatetime:
        min_time = min_time.to_pydatetime()
        max_time = max_time.to_pydatetime()
        start_range = min_time - ((max_time - min_time) * 0.1)
        end_range = max_time + ((max_time - min_time) * 0.1)
    height = height if height else _calc_auto_plot_height(len(data))
    y_range = ((-1 / series_count), series_count - 1 + (1 / series_count))
    plot = figure(
        x_range=(start_range, end_range),
        y_range=y_range,
        min_border_left=50,
        plot_height=height,
        plot_width=width,
        x_axis_label="Event Time",
        x_axis_type="datetime",
        x_minor_ticks=10,
        tools=[hover, "xwheel_zoom", "box_zoom", "reset", "save", "xpan"],
        title=title,
    )
    plot.yaxis.visible = show_yaxis
    if show_yaxis:
        if data:
            y_labels = {ser_def["y_index"]: str(lbl) for lbl, ser_def in data.items()}
            plot.yaxis.major_label_overrides = y_labels
    if ygrid:
        plot.ygrid.minor_grid_line_color = "navy"
        plot.ygrid.minor_grid_line_alpha = 0.1
        plot.ygrid.grid_line_color = "navy"
        plot.ygrid.grid_line_alpha = 0.3
    else:
        plot.ygrid.grid_line_color = None
    if xgrid:
        plot.xgrid.minor_grid_line_color = "navy"
        plot.xgrid.minor_grid_line_alpha = 0.3
    else:
        plot.xgrid.grid_line_color = None

    # Create plot bar to act as as range selector
    rng_select = _create_range_tool(
        data=data,
        min_time=min_time,
        max_time=max_time,
        plot_range=plot.x_range,
        width=width,
        height=height,
    )

    # set the tick datetime formatter
    plot.xaxis[0].formatter = _get_tick_formatter()

    if series_count > 1 and not legend_pos:
        legend_pos = "left"

    # plot groups individually so that we can create an interactive legend
    # if legend_pos is "inline", we add add the normal legend inside the plot
    # if legend_pos is "left" or "right", we add the legend to the side
    legend_items = []
    for ser_name, series_def in data.items():
        if legend_pos == "inline":
            p_series = plot.diamond(
                x=series_def["time_column"],
                y="y_index",
                color=series_def["color"],
                alpha=0.5,
                size=10,
                source=series_def["source"],
                legend_label=str(ser_name),
            )
        else:
            p_series = plot.diamond(
                x=series_def["time_column"],
                y="y_index",
                color=series_def["color"],
                alpha=0.5,
                size=10,
                source=series_def["source"],
            )
        if legend_pos in ["left", "right"]:
            legend_items.append(
                LegendItem(
                    label=str(ser_name),
                    renderers=[p_series],
                )
            )

    if legend_pos == "inline":
        # Position the inline legend
        plot.legend.location = "center_left"
        plot.legend.click_policy = "hide"
    elif legend_pos in ["left", "right"]:
        # Create the legend box outside of the plot area
        ext_legend = Legend(
            items=legend_items[::-1],  # the legend is in the wrong order otherwise
            location="center",
            click_policy="hide",
            label_text_font_size="8pt",
        )
        plot.add_layout(ext_legend, legend_pos)

    if ref_time is not None:
        _add_ref_line(plot, ref_time, ref_label, len(data))

    if show_range:
        plot_layout = column(plot, rng_select)
    else:
        plot_layout = plot

    if not hide:
        show(plot_layout)

    return plot_layout


# pylint: enable=too-many-locals, too-many-statements, too-many-branches


# pylint: disable=too-many-locals
def _unpack_data_series_dict(data, **kwargs):
    time_column: str = kwargs.pop("time_column", "TimeGenerated")
    source_columns: list = kwargs.pop("source_columns", None)

    if not source_columns:
        source_columns = ["NewProcessName", "EventID", "CommandLine"]
    def_source_columns = set(source_columns) if source_columns else set()

    # Process the input dictionary
    # Take each item that is passed and fill in blanks and add a y_index
    tool_tip_columns: Set[str] = set()
    min_time = None
    max_time = None
    y_index = 0

    # Create a color map in case colors have not been specified
    # (Shift the Viridis palatte so we lose the top, harder-to-see colors)
    series_count = len(data)
    colors, palette_size = _get_color_palette(series_count)

    for ser_name, series_def in data.items():
        data_columns: Set[str] = set()
        series_data = series_def["data"]

        if (
            series_data is None
            or not isinstance(series_data, pd.DataFrame)
            or series_data.empty
        ):
            print(f"No data to plot for series {ser_name}.")
            continue

        # if the series has source columns, use those
        src_cols = series_def.get("source_columns", def_source_columns)
        data_columns.update(src_cols or def_source_columns)

        time_col = series_def.get("time_column", None)
        if not time_col:
            time_col = time_column
            series_def["time_column"] = time_col
        data_columns.update([time_col])
        # add the data columns to the tool tip column set
        tool_tip_columns.update(data_columns)

        # Create the Column data source to plot
        graph_df = series_data[list(data_columns)].copy()
        graph_df["y_index"] = y_index
        series_def["y_index"] = y_index
        ser_color = series_def.get("color", None)
        if not ser_color:
            ser_color = colors[y_index % palette_size]
            series_def["color"] = ser_color
        # Wrap tooltip lines longer than 50 chars
        _wrap_df_columns(graph_df, 50)
        series_def["source"] = ColumnDataSource(graph_df)
        y_index += 1

        # calculate min/max time from this set
        if min_time is None:
            min_time = series_data[time_col].min()
            max_time = series_data[time_col].max()
        else:
            min_time = min(min_time, series_data[time_col].min())
            max_time = max(max_time, series_data[time_col].max())

    return tool_tip_columns, min_time, max_time


# pylint: enable=too-many-locals


def _create_data_grouping(data, source_columns, time_column, group_by, color):
    if not source_columns:
        data_columns = set(["NewProcessName", "EventID", "CommandLine"])
    else:
        data_columns = set(source_columns)
    # If the time column not explicity specified in source_columns, add it
    data_columns.add(time_column)
    tool_tip_columns = data_columns.copy()
    # create group frame so that we can color each group separately
    if group_by:
        group_count_df = (
            data[[group_by, time_column]]
            .groupby(group_by)
            .count()
            .reset_index()
            .rename(columns={time_column: "count"})
        )
        group_count_df["y_index"] = group_count_df.index

        # Shift the Viridis palatte so we lose the top, harder-to-see colors
        series_count = len(group_count_df)
        colors, palette_size = _get_color_palette(series_count)
        group_count_df["color"] = group_count_df.apply(
            lambda x: colors[x.y_index % palette_size], axis=1
        )
        # re-join with the original data
        data_columns.update([group_by, "y_index", "color"])
        clean_data = data.drop(columns=["y_index", "color"], errors="ignore")
        graph_df = clean_data.merge(group_count_df, on=group_by)[list(data_columns)]
    else:
        graph_df = data[list(data_columns)].copy()
        graph_df["color"] = color
        graph_df["y_index"] = 1
        series_count = 1
        group_count_df = None
    return graph_df, group_count_df, tool_tip_columns, series_count


# pylint: enable=too-many-arguments


def _create_dict_from_grouping(data, source_columns, time_column, group_by, color):
    if not source_columns:
        data_columns = set()
        if all(
            col in data.columns for col in ["NewProcessName", "EventID", "CommandLine"]
        ):
            data_columns = set(["NewProcessName", "EventID", "CommandLine"])
    else:
        data_columns = set(source_columns)
    # If the time column not explicitly specified in source_columns, add it
    data_columns.add(time_column)

    series_dict: Dict[str, Dict] = {}
    # create group frame so that we can color each group separately
    if group_by:
        data_columns.add(group_by)
        grouped_data = data[list(data_columns)].groupby(group_by)

        series_count = len(grouped_data)
        colors, palette_size = _get_color_palette(series_count)
        for color_index, (group_name, group_df) in enumerate(grouped_data):
            series_dict[str(group_name)] = dict(
                data=group_df,
                time_column=time_column,
                source_columns=source_columns,
                color=colors[color_index % palette_size],
            )
    else:
        group_df = data[list(data_columns)].copy()
        series_dict["unnamed series"] = dict(
            data=group_df,
            time_column=time_column,
            source_columns=source_columns,
            color=color,
        )

    return series_dict


def _get_ref_event_time(**kwargs) -> Tuple[datetime, str]:
    """Extract the reference time from kwargs."""
    ref_alert = kwargs.get("alert", None)
    if ref_alert is not None:
        ref_event = ref_alert
        ref_label = "Alert time"
    else:
        ref_event = kwargs.get("ref_event", None)
        ref_label = "Event time"

    if ref_event is not None:
        ref_time = getattr(ref_event, "StartTimeUtc", None)
        if not ref_time:
            ref_time = getattr(ref_event, "TimeGenerated", None)
    else:
        ref_time = kwargs.get("ref_time", None)
        ref_label = "Ref time"
    return ref_time, kwargs.get("ref_label", ref_label)


def _get_datetime_tooltip(col: str, dataset: pd.DataFrame):
    """Return tooltip and formatter entries for column."""
    if " " in col:
        disp_col = col.replace(" ", "_")
        tt_col = f"{{{col}}}"
    else:
        disp_col = tt_col = col
    if col in dataset and is_datetime64_any_dtype(dataset[col]):
        col_tooltip = f"@{tt_col}{{%F %T.%3N}}"
        col_fmt: Dict[Any, Any] = {f"@{tt_col}": "datetime"}
    else:
        col_tooltip = f"@{tt_col}"
        col_fmt = {}
    return disp_col, col_tooltip, col_fmt


def _create_tool_tips(
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame]], columns: List[str]
) -> Tuple[List[Tuple[str, str]], Dict[str, str]]:
    """Create formatting for tool tip columns."""
    formatters: Dict[str, str] = {}
    # if this is a dict we need to unpack each dataframe and process
    # the tooltip columns for all of the data sets.
    if isinstance(data, dict):
        tool_tip_dict = {}
        for data_set in data.values():
            data_df = data_set.get("data", {})
            for col in columns:
                disp_col, col_tooltip, col_fmt = _get_datetime_tooltip(col, data_df)
                tool_tip_dict[disp_col] = col_tooltip
                formatters.update(col_fmt)
        return list(tool_tip_dict.items()), formatters

    # If just a dataframe we just process the columns against this
    tool_tip_items = []
    for col in columns:
        disp_col, col_tooltip, col_fmt = _get_datetime_tooltip(col, data)
        tool_tip_items.append((disp_col, col_tooltip))
        formatters.update(col_fmt)

    return tool_tip_items, formatters


def _get_color_palette(series_count):
    palette_size = min(256, series_count + int(series_count / 5))
    return viridis(palette_size), palette_size


def _plot_dict_series(data, plot, legend_pos):
    """Plot series from dict."""
    # If legend_pos is outside the graph we need to create the legend
    # seperately.
    # We plot groups individually so that we can create an interactive legend.
    legend_items = []
    for ser_name, series_def in data.items():
        if legend_pos == "inline":
            p_series = plot.diamond(
                x=series_def["time_column"],
                y="y_index",
                color=series_def["color"],
                alpha=0.5,
                size=10,
                source=series_def["source"],
                legend_label=str(ser_name),
            )
        else:
            p_series = plot.diamond(
                x=series_def["time_column"],
                y="y_index",
                color=series_def["color"],
                alpha=0.5,
                size=10,
                source=series_def["source"],
            )
        if legend_pos in ["left", "right"]:
            legend_items.append((ser_name, [p_series]))

    if legend_pos == "inline":
        # Position the inline legend
        plot.legend.location = "top_left"
        plot.legend.click_policy = "hide"
    elif legend_pos in ["left", "right"]:
        # Create the legend box outside of the plot area
        ext_legend = Legend(
            items=legend_items,
            location="center",
            click_policy="hide",
            label_text_font_size="8pt",
        )
        plot.add_layout(ext_legend, legend_pos)


def _wrap_df_columns(data: pd.DataFrame, wrap_len: int = 50):
    """Wrap any string columns."""
    if not data.empty:
        for col in data.columns:
            if isinstance(data[col].iloc[0], str):
                data[col] = data[col].str.wrap(wrap_len)


def _get_tick_formatter() -> DatetimeTickFormatter:
    """Return tick formatting for different zoom levels."""
    # '%H:%M:%S.%3Nms
    tick_format = DatetimeTickFormatter()
    tick_format.days = ["%m-%d %H:%M"]
    tick_format.hours = ["%H:%M:%S"]
    tick_format.minutes = ["%H:%M:%S"]
    tick_format.seconds = ["%H:%M:%S"]
    tick_format.milliseconds = ["%H:%M:%S.%3N"]
    return tick_format


def _calc_auto_plot_height(group_count):
    """Dynamic calculation of plot height."""
    ht_per_row = 40
    if group_count > 15:
        ht_per_row = 25
    return max(ht_per_row * group_count, 300)


# pylint: disable=too-many-arguments, invalid-name, too-many-locals
def _create_range_tool(
    data,
    min_time,
    max_time,
    plot_range,
    width,
    height,
    time_column: str = None,
    y: str = "y_index",
):
    """Create plot bar to act as as range selector."""
    ext_min = min_time - ((max_time - min_time) * 0.15)
    ext_max = max_time + ((max_time - min_time) * 0.15)
    plot_height = max(120, int(height * 0.20))
    rng_select = figure(
        x_range=(ext_min, ext_max),
        title="Range Selector",
        plot_height=plot_height,
        plot_width=width,
        x_axis_type="datetime",
        y_axis_type=None,
        tools="",
        toolbar_location=None,
    )
    help_str = (
        "Drag the middle or edges of the selection box to change "
        + "the range in the main chart"
    )
    rng_select.add_layout(
        Title(text=help_str, align="right", text_font_size="10px"), "below"
    )
    rng_select.xaxis[0].formatter = _get_tick_formatter()
    if isinstance(data, dict):
        for _, series_def in data.items():
            rng_select.circle(
                x=series_def["time_column"],
                y=y,
                color=series_def["color"],
                source=series_def["source"],
            )
    elif isinstance(data, pd.DataFrame):
        rng_select.circle(
            x=time_column, y=y, color="blue", source=ColumnDataSource(data)
        )

    range_tool = RangeTool(x_range=plot_range)
    range_tool.overlay.fill_color = "navy"
    range_tool.overlay.fill_alpha = 0.2
    rng_select.ygrid.grid_line_color = None
    rng_select.add_tools(range_tool)
    rng_select.toolbar.active_multi = range_tool
    return rng_select


# pylint: enable=too-many-arguments


def _add_ref_line(plot, ref_time, ref_text="Ref time", series_count=1):
    """Add a reference marker line and label at `ref_time`."""
    ref_label_tm = pd.Timestamp(ref_time)
    plot.line(
        x=[ref_label_tm, ref_label_tm],
        y=[0, series_count],
        line_width=2,
        line_color="red",
        line_dash="dashed",
    )
    ref_label = Label(
        x=ref_label_tm,
        y=0,
        y_offset=10,
        x_units="data",
        y_units="data",
        text=f"< {ref_text}",
        text_font_size="8pt",
        render_mode="css",
        border_line_color="red",
        border_line_alpha=1.0,
        background_fill_color="white",
        background_fill_alpha=0.5,
    )

    plot.add_layout(ref_label)


@pd.api.extensions.register_dataframe_accessor("mp_timeline")
class TimeLineAccessor:
    """Pandas api extension for Timeline."""

    def __init__(self, pandas_obj):
        """Instantiate pandas extension class."""
        self._df = pandas_obj

    def plot(self, **kwargs) -> figure:
        """
        Display a timeline of events.

        Parameters
        ----------
        time_column : str, optional
            Name of the timestamp column
            (the default is 'TimeGenerated')
        source_columns : list, optional
            List of default source columns to use in tooltips
            (the default is None)

        Other Parameters
        ----------------
        title : str, optional
            Title to display (the default is None)
        alert : SecurityAlert, optional
            Add a reference line/label using the alert time (the default is None)
        ref_event : Any, optional
            Add a reference line/label using the alert time (the default is None)
        ref_time : datetime, optional
            Add a reference line/label using `ref_time` (the default is None)
        group_by : str
            (where `data` is a DataFrame)
            The column to group timelines on
        legend: str, optional
            "left", "right", "inline" or "none"
            (the default is to show a legend when plotting multiple series
            and not to show one when plotting a single series)
        yaxis : bool, optional
            Whether to show the yaxis and labels (default is False)
        ygrid : bool, optional
            Whether to show the yaxis grid (default is False)
        xgrid : bool, optional
            Whether to show the xaxis grid (default is True)
        range_tool : bool, optional
            Show the the range slider tool (default is True)
        height : int, optional
            The height of the plot figure
            (the default is auto-calculated height)
        width : int, optional
            The width of the plot figure (the default is 900)
        color : str
            Default series color (default is "navy")
        overlay_color : str
            Overlay series color (default is "green")

        Returns
        -------
        figure
            The bokeh plot figure.

        """
        return display_timeline(data=self._df, **kwargs)

    # pylint: disable=invalid-name
    def plot_values(self, y: str, **kwargs) -> figure:
        """
        Display a timeline of events.

        Parameters
        ----------
        time_column : str, optional
            Name of the timestamp column
            (the default is 'TimeGenerated')
        y : str
            The column name holding the value to plot vertically
        source_columns : list, optional
            List of default source columns to use in tooltips
            (the default is None)

        Other Parameters
        ----------------
        x : str, optional
            alias of `time_column`
        title : str, optional
            Title to display (the default is None)
        ref_event : Any, optional
            Add a reference line/label using the alert time (the default is None)
        ref_time : datetime, optional
            Add a reference line/label using `ref_time` (the default is None)
        group_by : str
            (where `data` is a DataFrame)
            The column to group timelines on
        legend: str, optional
            "left", "right", "inline" or "none"
            (the default is to show a legend when plotting multiple series
            and not to show one when plotting a single series)
        yaxis : bool, optional
            Whether to show the yaxis and labels
        range_tool : bool, optional
            Show the the range slider tool (default is True)
        height : int, optional
            The height of the plot figure
            (the default is auto-calculated height)
        width : int, optional
            The width of the plot figure (the default is 900)
        color : str
            Default series color (default is "navy"). This is overridden by
            automatic color assignments if plotting a grouped chart
        kind : Union[str, List[str]]
            one or more glyph types to plot., optional
            Supported types are "circle", "line" and "vbar" (default is "vbar")

        Returns
        -------
        figure
            The bokeh plot figure.

        """
        return display_timeline_values(data=self._df, y=y, **kwargs)
