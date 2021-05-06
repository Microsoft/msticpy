# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Module for pre-defined widget layouts."""
import asyncio
import json
import os
import random
from abc import ABC
from datetime import datetime, timedelta
from enum import IntEnum
from json import JSONDecodeError
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union, Iterable
from weakref import WeakValueDictionary

import ipywidgets as widgets
import pandas as pd
from deprecated.sphinx import deprecated
from IPython.display import HTML, display
from ipywidgets import Layout

from .._version import VERSION
from ..common.utility import export, check_kwargs
from ..common.timespan import TimeSpan

__version__ = VERSION
__author__ = "Ian Hellen"


# pylint: disable=too-many-lines, invalid-name
class TimeUnit(IntEnum):
    """Time unit enumeration and value."""

    second = 1
    minute = 60
    hour = 60 * 60
    day = 60 * 60 * 24
    week = 7 * 60 * 60 * 24


# pylint: enable=invalid-name


def _parse_time_unit(unit_str: str) -> TimeUnit:
    """Return the TimeUnit enum matching the input string."""
    if unit_str.casefold().startswith("m"):
        return TimeUnit.minute
    if unit_str.casefold().startswith("h"):
        return TimeUnit.hour
    if unit_str.casefold().startswith("s"):
        return TimeUnit.second
    if unit_str.casefold().startswith("d"):
        return TimeUnit.day
    if unit_str.casefold().startswith("w"):
        return TimeUnit.week
    return TimeUnit.minute


_WIDGET_REG: WeakValueDictionary = WeakValueDictionary()


# pylint: disable=too-few-public-methods
class RegisteredWidget(ABC):
    """
    Register widget in the widget registry.

    Registered widgets will store their values in the register.
    Each widget has an ID that that is derived from one or more of the
    initialization parameters. If an instance of the same widget class is
    created with the same parameters, its previous value will be repopulated
    from the registry.
    This is especially useful in notebooks where people accidently re-run
    the same cell after entering values.
    """

    def __init__(
        self,
        id_vals: Optional[List[Any]] = None,
        val_attrs: Optional[List[str]] = None,
        nb_params: Optional[Dict[str, str]] = None,
        ns: Dict[str, Any] = globals(),
        register: bool = True,
        **kwargs,
    ):
        """
        Initialize a registered widget.

        Parameters
        ----------
        id_vals : Optional[List[Any]], optional
            The list of parameter values to use to identify this widget instance,
            by default None
        val_attrs : Optional[List[str]], optional
            The names of the attributes to persist in the registry
            and recall, by default ["value"]
        nb_params : Optional[Dict[str, str]], optional
            A dictionary of attribute names and global variables. If the variable
            exists in the global namespace it will be used to populate the
            corresponding widget attribute. This is only done if the widget
            attribute currently has no value (i.e. restoring a value from
            the registry takes priority over this),
            by default None
        ns : Dict[str, Any], optional
            Namespace to look for global variables, by default None
        register : bool
            Do not register the widget or retrieve values from previously-
            registered instance.

        """
        del kwargs  # allow to be called with kwargs that are ignored
        # Try to retrieve previous values based on ID of this control
        if register and id_vals:
            id_list = [self.__class__.__name__, *[str(val) for val in id_vals]]
            self._id = hash("".join(id_list))

            if not val_attrs:
                val_attrs = ["value"]
            if self._id in _WIDGET_REG:
                for attr in val_attrs:
                    if hasattr(_WIDGET_REG[self._id], attr):
                        setattr(self, attr, getattr(_WIDGET_REG[self._id], attr))
            # register the current instance as the last instance
            _WIDGET_REG[self._id] = self

        # if there are any notebook params relevant to this control
        if nb_params and ns:
            for attr, nb_param in nb_params.items():
                # if this doesn't have a value set explicitly or
                # one that was recovered from the widget registry
                # set it from the nb_param value
                if nb_param in ns and not getattr(self, attr, None):
                    setattr(self, attr, ns[nb_param])


# pylint: enable=too-few-public-methods


@export
class Lookback:
    """Time lookback slider."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        default: Optional[int] = None,
        label: str = "Select time ({units}) to look back",
        origin_time: datetime = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        units: str = "hour",
        auto_display: bool = False,
    ):
        """
        Create an instance of the lookback slider widget.

        Parameters
        ----------
        default : int, optional
            The default 'lookback' time (the default is 4)
        label : str, optional
            The description to display
            (the default is 'Select time ({units}) to look back')
        origin_time : datetime, optional
            The origin time (the default is `datetime.utcnow()`)
        min_value : int, optional
            Minimum value (the default is 1)
        max_value : int, optional
            Maximum value (the default is 240)
        units : str, optional
            Time unit (the default is 'hour')
            Permissable values are 'day', 'hour', 'minute', 'second',
            'week'
            These can all be abbreviated down to initial characters
            ('d', 'm', etc.)
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        """
        # default to now
        self.origin_time = datetime.utcnow() if origin_time is None else origin_time

        self._time_unit = _parse_time_unit(units)
        if "{units}" in label:
            label = label.format(units=self._time_unit.name)
        default = _default_before_after(default, self._time_unit)
        min_value = min_value or 1
        max_value = _default_max_buffer(max_value, default, self._time_unit)

        self._lookback_wgt = widgets.IntSlider(
            value=default,
            min=min_value,
            max=max_value,
            step=1,
            description=label,
            layout=Layout(width="60%", height="50px"),
            style={"description_width": "initial"},
        )

        self.end = self.origin_time
        self._time_unit = _parse_time_unit(units)
        self.start = self.end - timedelta(
            seconds=(self._time_unit.value * self._lookback_wgt.value)
        )

        self._lookback_wgt.observe(self._time_range_change, names="value")

        if auto_display:
            self.display()

    @property
    def layout(self):
        """Return underlying widget."""
        return self._lookback_wgt

    def display(self):
        """Display the interactive widgets."""
        display(self._lookback_wgt)

    @property
    def lookback(self):
        """Return current widget lookback value."""
        return self._lookback_wgt.value

    @property
    def value(self):
        """Return current widget lookback value."""
        return self._lookback_wgt.value

    def _time_range_change(self, change):
        del change
        self.start = self.origin_time - timedelta(
            0, self._lookback_wgt.value * self._time_unit.value
        )

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


def _default_max_buffer(max_default, default, unit) -> int:
    mag_default = abs(int(default * 4))
    if max_default is not None:
        max_value = abs(max_default)
        return max(max_value, mag_default)
    if unit == TimeUnit.day:
        return max(28, mag_default)
    if unit == TimeUnit.hour:
        return max(48, mag_default)
    if unit == TimeUnit.week:
        return max(20, mag_default)
    return max(240, mag_default)


def _default_before_after(default, unit) -> int:
    if default is not None:
        return abs(default)
    if unit in (TimeUnit.day, TimeUnit.week):
        return 1
    if unit == TimeUnit.hour:
        return 6
    return 60


# pylint: disable=too-many-instance-attributes
@export
class QueryTime(RegisteredWidget):
    """
    QueryTime.

    Composite widget to capture date and time origin
    and set start and end times for queries.

    See Also
    --------
    RegisteredWidget

    """

    _ALLOWED_KWARGS = [
        "origin_time",
        "before",
        "after",
        "start",
        "end",
        "max_before",
        "max_after",
        "label",
        "description",
        "units",
        "auto_display",
        "timespan",
        "register",
    ]

    _label_style = {"description_width": "initial"}

    def __init__(
        self,
        **kwargs,
    ):
        """
        Create new instance of QueryTime.

        Parameters
        ----------
        origin_time : datetime, optional
            The origin time (the default is `datetime.utcnow()`)
        label : str, optional
            The description to display
            (the default is 'Select time ({units}) to look back')
        before : int, optional
            The default number of `units` before the `origin_time`
            (the default varies based on the unit)
        after : int, optional
            The default number of `units` after the `origin_time`
            (the default varies based on the unit)
        start : Union[datetime, str]
            Start of query time - alternative to specifying origin,
            before, after
        end : Union[datetime, str]
            End of query time - alternative to specifying origin,
            before, after
        timespan : TimeSpan
            TimeSpan of query time - alternative to specifying origin,
            before, after
        max_before : int, optional
            The largest value for `before` (the default varies based on the unit)
        max_after : int, optional
            The largest value for `after` (the default varies based on the unit)
        units : str, optional
            Time unit (the default is 'hour')
            Permissable values are 'day', 'hour', 'minute', 'second',
            'week'
            These can all be abbreviated down to initial characters
            ('d', 'm', etc.)
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        """
        check_kwargs(kwargs, self._ALLOWED_KWARGS)
        self._label = kwargs.pop(
            "description", kwargs.pop("label", "Set query time boundaries")
        )
        self._time_unit = _parse_time_unit(kwargs.get("units", "min"))

        self.before = kwargs.pop("before", None)
        self.after = kwargs.pop("after", None)
        self._query_start = self._query_end = self.origin_time = datetime.utcnow
        self._get_time_parameters(**kwargs)

        self.max_before = kwargs.pop("max_before", 0)
        self.max_after = kwargs.pop("max_after", 0)
        self._adjust_max_before_after(self.max_before, self.max_after)

        # Call superclass to register
        ids_params = [
            self.origin_time,
            self.before,
            self.after,
            self.max_before,
            self.max_after,
            self._label,
            self._time_unit,
        ]
        ids_attribs = [
            "origin_time",
            "before",
            "after",
            "_query_start",
            "_query_end",
            "_label",
        ]
        super().__init__(id_vals=ids_params, val_attrs=ids_attribs, **kwargs)

        # Create widgets
        self._w_origin_dt = widgets.DatePicker(
            description="Origin Date", disabled=False, value=self.origin_time.date()
        )
        self._w_origin_tm = widgets.Text(
            description="Time (24hr)",
            disabled=False,
            value=str(self.origin_time.time()),
        )

        range_desc = "Time Range"
        self._w_tm_range = widgets.IntRangeSlider(
            value=(-self.before, self.after),
            min=-self.max_before,
            max=self.max_after,
            step=1,
            description=range_desc,
            disabled=False,
            continuous_update=True,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            layout=Layout(width="70%"),
            style=self._label_style,
        )
        # pylint: disable=no-member
        self._w_time_unit = widgets.Dropdown(
            options=[
                unit for unit, _ in TimeUnit.__members__.items() if unit != "second"
            ],
            value=self._time_unit.name,
            layout=Layout(width="100px"),
        )
        # pylint: enable=no-member

        self._w_start_time_txt = widgets.Text(
            value=self._query_start.isoformat(sep=" "),
            description="Query start time (UTC):",
            layout=Layout(width="50%"),
            style=self._label_style,
        )
        self._w_end_time_txt = widgets.Text(
            value=self._query_end.isoformat(sep=" "),
            description="Query end time (UTC) :  ",
            layout=Layout(width="50%"),
            style=self._label_style,
        )

        # Add change event handlers
        self._w_tm_range.observe(self._time_range_change, names="value")
        self._w_origin_dt.observe(self._update_origin, names="value")
        self._w_origin_tm.observe(self._update_origin, names="value")
        self._w_time_unit.observe(self._change_time_unit, names="value")

        self.layout = self._create_layout()
        if kwargs.pop("auto_display", False):
            self.display()

    def _create_layout(self):
        return widgets.VBox(
            [
                widgets.HTML("<h4>{}</h4>".format(self._label)),
                widgets.HBox([self._w_origin_dt, self._w_origin_tm]),
                widgets.VBox(
                    [
                        widgets.HBox([self._w_tm_range, self._w_time_unit]),
                        self._w_start_time_txt,
                        self._w_end_time_txt,
                    ]
                ),
            ]
        )

    def display(self):
        """Display the interactive widgets."""
        display(self.layout)

    def _change_time_unit(self, change):
        """Reset before/after and max buffers to defaults."""
        unit = change["new"]
        self._time_unit = _parse_time_unit(unit)
        self.before = _default_before_after(default=None, unit=self._time_unit)
        self.after = _default_before_after(default=None, unit=self._time_unit)
        self._adjust_max_before_after(max_before=None, max_after=None)
        self._w_tm_range.value = (-self.before, self.after)
        self._w_tm_range.min = -self.max_before
        self._w_tm_range.max = self.max_after

    def _get_time_parameters(self, **kwargs):
        """Process different init time parameters."""
        timespan: TimeSpan = kwargs.pop("timespan", None)
        start = kwargs.pop("start", None)
        end = kwargs.pop("end", None)
        if timespan:
            self._query_end = self.origin_time = timespan.end
            self._query_start = timespan.start
        elif start and end:
            timespan = TimeSpan(start=start, end=end)
            self._query_start = timespan.start
            self._query_end = self.origin_time = timespan.end
        else:
            self.origin_time = kwargs.pop("origin_time", datetime.utcnow())
            self.before = _default_before_after(self.before, self._time_unit)
            self.after = _default_before_after(self.after, self._time_unit)
            # Calculate time offsets from origin
            self._query_start = self.origin_time - timedelta(
                0, self.before * self._time_unit.value
            )
            self._query_end = self.origin_time + timedelta(
                0, self.after * self._time_unit.value
            )
            timespan = TimeSpan(start=self._query_start, end=self._query_end)
        if "units" not in kwargs:
            self._infer_time_units()
        if self.after is None:
            self.after = 0
        if self.before is None:
            self.before = int(
                (self._query_end - self._query_start).total_seconds()
                / self._time_unit.value
            )

    def _infer_time_units(self):
        # If time units not set explicitly, set to something sensible,
        # based on start/end times
        if abs(self.timespan.period.days) > 1:
            self._time_unit = TimeUnit.day
        elif abs(self.timespan.period.total_seconds()) > 3600:
            self._time_unit = TimeUnit.hour
        else:
            self._time_unit = TimeUnit.minute

    def _adjust_max_before_after(self, max_before, max_after):
        """Adjust the max values so the are always bigger than the defaults."""
        self.max_before = _default_max_buffer(
            max_before, self.before or 1, self._time_unit
        )
        self.max_after = _default_max_buffer(
            max_after, self.after or 1, self._time_unit
        )

    def _update_origin(self, change):
        del change
        try:
            tm_value = datetime.strptime(self._w_origin_tm.value, "%H:%M:%S.%f").time()
            self.origin_time = datetime.combine(self._w_origin_dt.value, tm_value)
            self._time_range_change(change=None)
        except (ValueError, TypeError):
            # reset on error
            self._w_origin_dt.value = self.origin_time.date()
            self._w_origin_tm = self.origin_time.time()

    def _time_range_change(self, change):
        del change
        self._query_start = self.origin_time + timedelta(
            0, self._w_tm_range.value[0] * self._time_unit.value
        )
        self._query_end = self.origin_time + timedelta(
            0, self._w_tm_range.value[1] * self._time_unit.value
        )
        self._w_start_time_txt.value = self._query_start.isoformat(sep=" ")
        self._w_end_time_txt.value = self._query_end.isoformat(sep=" ")

    @property
    def start(self):
        """Query start time."""
        return self._query_start

    @property
    def end(self):
        """Query end time."""
        return self._query_end

    @property
    def units(self):
        """Time units used by control."""
        return self._time_unit.name

    @property
    def timespan(self):
        """Return the timespan as a TimeSpan object."""
        return TimeSpan(start=self.start, end=self.end)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


# pylint: disable=too-many-instance-attributes
@export
class SelectAlert:
    """
    Alert Selector.

    View list of alerts and select one for investigation.
    Optionally provide and action to call with the selected alert as a parameter
    (typically used to display the alert.)

    Attributes
    ----------
    selected_alert : SecurityAlert
        The selected alert
    alert_id : str
        The SystemAlertId of the selected alert
    alerts : List[SecurityAlert]
        The current alert list (DataFrame)
    action : Callable[..., Optional[Tuple[...]]]
        The callback action to execute on selection
        of an alert.

    """

    _ALERTID_REGEX = r"\[id:(?P<alert_id>.*)\]$"

    def __init__(
        self,
        alerts: pd.DataFrame,
        action: Callable[..., Optional[Tuple]] = None,
        columns: List[str] = None,
        auto_display: bool = False,
    ):
        """
        Create a new instance of AlertSelector.

        Parameters
        ----------
        alerts : pd.DataFrame
            DataFrame of alerts.
        action : Callable[..., Optional[Tuple]], optional
            Optional function to execute for each selected alert.
            If the function returns one or a tuple of displayable objects
            these will be displayed.
        columns : List[str], optional
            Override the default column names to use from `alerts`
            (the default is ['StartTimeUtc', 'AlertName',
            'CompromisedEntity', 'SystemAlertId'])
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        """
        self.alerts = alerts
        self.alert_action = action

        if not columns:
            columns = [
                "StartTimeUtc",
                "AlertName",
                "CompromisedEntity",
                "SystemAlertId",
            ]

        items = alerts[columns]
        items = items.sort_values("StartTimeUtc", ascending=True)
        self._select_items = items.apply(self._alert_summary, axis=1).values.tolist()

        self.selected_alert = None
        self.alert_id = None

        self._w_select_alert = widgets.Select(
            options=self._select_items,
            description="Select alert :",
            layout=Layout(width="95%", height="300px"),
            style={"description_width": "initial"},
        )

        self._w_filter_alerts = widgets.Text(
            value="",
            description="Filter alerts by title:",
            style={"description_width": "initial"},
        )

        # setup to use updatable display objects
        rand_id = random.randint(0, 999999)  # nosec
        self._output_id = f"{self.__class__.__name__}_{rand_id}"
        self._disp_elems: List[Any] = []

        # set up observer callbacks
        self._w_filter_alerts.observe(self._update_options, names="value")
        self._w_select_alert.observe(self._select_alert, names="value")
        self.layout = widgets.VBox([self._w_filter_alerts, self._w_select_alert])

        if auto_display:
            self.display()

    def display(self):
        """Display the interactive widgets."""
        display(self.layout)
        display(HTML("<hr>"))
        self._select_top_alert()

    @staticmethod
    def _alert_summary(alert_row):
        """Return summarized string of alert properties."""
        if "TI Risk" in alert_row:
            return (
                f"{alert_row.StartTimeUtc} - {alert_row.AlertName}"
                + f" - ({alert_row.CompromisedEntity}) "
                + f" - TI Risk: {alert_row['TI Risk']}"
                + f" - [id:{alert_row.SystemAlertId}]",
                alert_row.SystemAlertId,
            )

        return (
            f"{alert_row.StartTimeUtc} - {alert_row.AlertName}"
            + f" - ({alert_row.CompromisedEntity}) "
            + f" - [id:{alert_row.SystemAlertId}]",
            alert_row.SystemAlertId,
        )

    def _update_options(self, change):
        """Filter the alert list by substring."""
        if change is not None and "new" in change:
            self._w_select_alert.options = [
                alert_dtl
                for alert_dtl in self._select_items
                if change["new"].lower() in alert_dtl[0].lower()
            ]

    def _select_alert(self, selection=None):
        """Select action triggered by picking item from list."""
        if (
            selection is None
            or "new" not in selection
            or not isinstance(selection["new"], str)
        ):
            self.selected_alert = None
        else:
            self.alert_id = selection["new"]
            self.selected_alert = self._get_alert(self.alert_id)
            if self.alert_action is not None:
                self._run_action()

    def _get_alert(self, alert_id):
        """Get the alert by alert_id."""
        self.alert_id = alert_id
        selected_alerts = self.alerts[self.alerts["SystemAlertId"] == alert_id]

        if selected_alerts.shape[0] > 0:
            alert = pd.Series(selected_alerts.iloc[0])
            if isinstance(alert["ExtendedProperties"], str):
                try:
                    alert["ExtendedProperties"] = json.loads(
                        (alert["ExtendedProperties"])
                    )
                except JSONDecodeError:
                    pass
            if isinstance(alert["Entities"], str):
                try:
                    alert["Entities"] = json.loads((alert["Entities"]))
                except JSONDecodeError:
                    pass
            return alert
        return None

    def _select_top_alert(self):
        """Select the first alert by default."""
        top_alert = self.alerts.iloc[0]
        if not top_alert.empty:
            self.alert_id = top_alert.SystemAlertId
            self.selected_alert = self._get_alert(self.alert_id)
            if self.alert_action is not None:
                self._run_action()

    def _run_action(self):
        """Run any action function and display details, if any."""
        output_objs = self.alert_action(self.selected_alert)
        if output_objs is None:
            return
        if not isinstance(output_objs, (tuple, list)):
            output_objs = [output_objs]
        display_objs = bool(self._disp_elems)
        for idx, out_obj in enumerate(output_objs):
            if not display_objs:
                self._disp_elems.append(
                    display(out_obj, display_id=f"{self._output_id}_{idx}")
                )
            else:
                if idx == len(self._disp_elems):
                    break
                self._disp_elems[idx].update(out_obj)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


# pylint: disable=too-many-instance-attributes
@deprecated(
    reason="Superceded by SelectAlert. Please use that version", version="0.5.2"
)
@export
class AlertSelector(SelectAlert):
    """
    AlertSelector.

    View list of alerts and select one for investigation.
    Optionally provide and action to call with the selected alert as a parameter
    (typically used to display the alert.)

    Attributes
    ----------
    selected_alert : SecurityAlert
        The selected alert
    alert_id : str
        The SystemAlertId of the selected alert
    alerts : List[SecurityAlert]
        The current alert list (DataFrame)
    action : Callable[..., None]
        The callback action to execute on selection
        of an alert.

    """

    def __init__(
        self,
        alerts: pd.DataFrame,
        action: Callable[..., None] = None,
        columns: List[str] = None,
        auto_display: bool = False,
    ):
        """
        Create a new instance of AlertSelector.

        Parameters
        ----------
        alerts : pd.DataFrame
            DataFrame of alerts.
        action : Callable[..., None], optional
            Optional function to execute for each selected alert.
            (the default is None)
        columns : List[str], optional
            Override the default column names to use from `alerts`
            (the default is ['StartTimeUtc', 'AlertName',
            'CompromisedEntity', 'SystemAlertId'])
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        """
        self._w_output = widgets.Output(layout={"border": "1px solid black"})
        super().__init__(alerts, action, columns, auto_display)

    def display(self):
        """Display the interactive widgets."""
        self._select_top_alert()
        display(
            widgets.VBox([self._w_filter_alerts, self._w_select_alert, self._w_output])
        )

    def _run_action(self):
        self._w_output.clear_output()
        with self._w_output:
            self.alert_action(self.selected_alert)

    @property
    def query_params(self):
        """
        Query parameters derived from alert.

        Returns
        -------
            dict(str, str) -- Dictionary of parameter names

        """
        return {"provider_alert_id": self.alert_id}


@export
class GetEnvironmentKey(RegisteredWidget):
    """
    GetEnvironmentKey.

    Tries to retrieve an environment variable value. The value
    can be changed/set and optionally saved back to the system
    environment.
    """

    def __init__(
        self,
        env_var: str,
        help_str: str = None,
        prompt: str = "Enter the value: ",
        auto_display: bool = False,
        **kwargs,
    ):
        """
        Create a new instance of GetEnvironmentKey.

        Parameters
        ----------
        env_var : str
            Name of the environment variable.
        help_str : str, optional
            Help to display if the environment variable is not set. (the default is None)
        prompt : str, optional
            Prompt to display with the text box.
            (the default is "Enter the value: ")
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        """
        env_val = os.environ.get(env_var)
        self._name = env_var
        self._value = ""

        # Call superclass to register
        super().__init__(id_vals=[env_var, prompt], val_attrs=["_value"], **kwargs)

        # Use the registed widget "remembered" value but if the environment
        # variable is set override with this value.
        if env_val is not None:
            self._value = env_val

        if not self._value and help_str is not None:
            display(widgets.HTML(value=help_str))

        self._w_text = widgets.Text(
            value=self._value,
            description=prompt,
            layout=Layout(width="50%"),
            style={"description_width": "initial"},
        )

        self._w_save_button = widgets.Button(
            description="Set",
            layout=Layout(width="10%", disabled=False),
            style={"description_width": "initial"},
        )
        self._w_check_save = widgets.Checkbox(
            value=True, description="Save as environment var", disabled=False
        )
        self._w_save_button.on_click(self._on_save_button_clicked)
        self._hbox = widgets.HBox(
            [self._w_text, self._w_save_button, self._w_check_save]
        )

        if auto_display:
            self.display()

    @property
    def value(self):
        """Get the current value of the key."""
        self._value = self._w_text.value or ""
        return self._value.strip()

    @property
    def name(self):
        """Get the current name of the key."""
        return self._name

    @property
    def layout(self):
        """Return underlying widget collection."""
        return self._hbox

    def display(self):
        """Display the interactive widgets."""
        display(self._hbox)

    def _on_save_button_clicked(self, button):
        del button
        self._value = self.value
        if self._w_check_save.value:
            os.environ[self._name] = self.value

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


@export
class GetText(RegisteredWidget):
    """
    GetEnvironmentKey.

    Tries to retrieve an environment variable value. The value
    can be changed/set and optionally saved back to the system
    environment.
    """

    def __init__(
        self,
        default: str = None,
        prompt: str = "Enter the value: ",
        auto_display: bool = False,
        **kwargs,
    ):
        """
        Create a new instance of GetEnvironmentKey.

        Parameters
        ----------
        default : str
            Default value.
        prompt : str, optional
            Prompt to display with the text box.
            (the default is "Enter the value: ")
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)

        See Also
        --------
        RegisteredWidget

        """
        self._value = default

        # Call superclass to register
        super().__init__(id_vals=[default, prompt], val_attrs=["_value"], **kwargs)

        self._w_text = widgets.Text(
            value=self._value,
            description=prompt,
            layout=Layout(width="50%"),
            style={"description_width": "initial"},
        )

        self._w_text.observe(self._update_value, names="value")
        if auto_display:
            self.display()

    def _update_value(self, change):
        self._value = change.get("new", "")

    @property
    def layout(self):
        """Return underlying widget collection."""
        return self._w_text

    @property
    def value(self):
        """Get the current value of the key."""
        return self._value.strip()

    def display(self):
        """Display the interactive widgets."""
        if self._value:
            self._w_text.value = self._value
        display(self.layout)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


@export
class SelectItem:
    """
    Selection list from list or dict.

    Attributes
    ----------
    value : Any
        The selected value.
    item_action : Callable[..., Optional[Tuple]]
        Action to call for each selection.

    """

    # pylint: disable=too-many-arguments, too-few-public-methods
    def __init__(
        self,
        description: str = "Select an item",
        item_list: List[str] = None,
        action: Callable[..., Optional[Tuple]] = None,
        item_dict: Mapping[str, str] = None,
        auto_display: bool = False,
        height: str = "100px",
        width: str = "50%",
        display_filter: bool = True,
    ):
        """
        Select an item from a list or dict.

        Parameters
        ----------
        description : str, optional
            The widget label to display.
            (the default is 'Select an item')
        item_list : List[str], optional
            A `list` of items to select from (the default is None)
        item_dict : Mapping[str, str], optional
            A `dict` of items to select from. When using `item_dict`
            the keys are displayed as the selectable items and value
            corresponding to the selected key is set as the `value`
            property.
            (the default is None)
        action : Callable[..., Optional[Tuple[...]]], optional
            function to call when item selected (passed a single
            parameter - the value of the currently selected item)
            (the default is None).
            If the function returns one or a tuple of displayable objects
            these will be displayed.
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)
        height : str, optional
            Selection list height (the default is '100px')
        width : str, optional
            Selection list width (the default is '50%')
        display_filter : bool, optional
            Whether to display item filter (the default is True)

        """
        if item_list:
            self._item_list = item_list
            self._item_dict = None
            self.value = item_list[0]
        elif item_dict:
            self._item_list = list(item_dict.keys())
            self._item_dict = item_dict
            self.value = list(self._item_dict.values())[0]
        else:
            raise ValueError("One of item_list or item_dict must be supplied.")

        self._wgt_select = widgets.Select(
            options=self._item_list,
            description=description,
            layout=Layout(width=width, height=height),
            style={"description_width": "initial"},
        )
        self._display_filter = display_filter
        if display_filter:
            self._w_filter = widgets.Text(
                value="", description="Filter:", style={"description_width": "initial"}
            )

            # set up observer callbacks
            self._w_filter.observe(self._update_options, names="value")
        self._wgt_select.observe(self._select_item, names="value")

        self.item_action = action

        # setup to use updatable display objects
        rand_id = random.randint(0, 999999)  # nosec
        self._output_id = f"{self.__class__.__name__}_{rand_id}"
        self._disp_elems: List[Any] = []

        if auto_display:
            self.display()

    def _select_item(self, selection):
        if (
            selection is None
            or "new" not in selection
            or not isinstance(selection["new"], str)
        ):
            return
        value = selection["new"]
        self.value = self._item_dict.get(value, None) if self._item_dict else value
        if self.item_action is not None:
            self._run_action()

    def _update_options(self, change):
        """Filter the alert list by substring."""
        if change is not None and "new" in change:
            self._wgt_select.options = [
                i for i in self._item_list if change["new"].lower() in i.lower()
            ]

    def _run_action(self):
        """Run any action function and display details, if any."""
        output_objs = self.item_action(self.value)
        if output_objs is None:
            return
        if not isinstance(output_objs, (tuple, list)):
            output_objs = [output_objs]
        display_objs = dict(enumerate(self._disp_elems))
        for idx, out_obj in enumerate(output_objs):
            if idx not in display_objs:
                self._disp_elems.append(
                    display(out_obj, display_id=f"{self._output_id}_{idx}")
                )
            else:
                self._disp_elems[idx].update(out_obj)

    @property
    def layout(self):
        """Return underlying widget collection."""
        wgt_list = []
        if self._display_filter:
            wgt_list.append(self._w_filter)
        wgt_list.append(self._wgt_select)
        return widgets.VBox(wgt_list)

    def display(self):
        """Display the interactive widget."""
        display(self.layout)
        display(HTML("<hr>"))
        self._show_top_item()

    def _show_top_item(self):
        """Run action on the first item by default."""
        if self.item_action is not None and self.value is not None:
            self._run_action()

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


@deprecated(reason="Superceded by SelectItem. Please use that version", version="0.5.2")
@export
class SelectString(SelectItem):
    """
    Selection list from list or dict.

    Attributes
    ----------
    value : Any
        The selected value.
    item_action : Callable[..., None]
        Action to call for each selection.

    """

    # pylint: disable=too-many-arguments, too-few-public-methods
    def __init__(
        self,
        description: str = "Select an item",
        item_list: List[str] = None,
        action: Callable[..., None] = None,
        item_dict: Mapping[str, str] = None,
        auto_display: bool = False,
        height: str = "100px",
        width: str = "50%",
        display_filter: bool = True,
    ):
        """
        Select an item from a list or dict.

        Parameters
        ----------
        description : str, optional
            The widget label to display.
            (the default is 'Select an item')
        item_list : List[str], optional
            A `list` of items to select from (the default is None)
        item_dict : Mapping[str, str], optional
            A `dict` of items to select from. When using `item_dict`
            the keys are displayed as the selectable items and value
            corresponding to the selected key is set as the `value`
            property.
            (the default is None)
        action : Callable[..., None], optional
            function to call when item selected (passed a single
            parameter - the value of the currently selected item)
            (the default is None)
        auto_display : bool, optional
            Whether to display on instantiation (the default is False)
        height : str, optional
            Selection list height (the default is '100px')
        width : str, optional
            Selection list width (the default is '50%')
        display_filter : bool, optional
            Whether to display item filter (the default is True)

        """
        self._w_output = widgets.Output(layout={"border": "1px solid black"})

        super().__init__(
            description=description,
            item_list=item_list,
            item_dict=item_dict,
            action=action,
            auto_display=auto_display,
            height=height,
            width=width,
            display_filter=display_filter,
        )

    def _run_action(self):
        self._w_output.clear_output()
        with self._w_output:
            self.item_action(self.value)

    def display(self):
        """Display the interactive widget."""
        self._show_top_item()
        wgt_list = []
        if self._display_filter:
            wgt_list.append(self._w_filter)
        wgt_list.append(self._wgt_select)
        if self.item_action:
            wgt_list.append(self._w_output)
        display(widgets.VBox(wgt_list))


@export
class SelectSubset:
    """Class to select a subset from an input list."""

    def __init__(
        self,
        source_items: Union[Dict[str, str], List[Any]],
        default_selected: Union[Dict[str, str], List[Any]] = None,
        display_filter: bool = True,
        auto_display: bool = True,
    ):
        """
        Create instance of SelectSubset widget.

        Parameters
        ----------
        source_items : Union[Dict[str, str], List[Any]]
            List of source items - either a dictionary(label, value),
            a simple list or
            a list of (label, value) tuples.
        default_selected : Union[Dict[str, str], List[Any]]
            Populate the selected list with values - either
            a dictionary(label, value),
            a simple list or
            a list of (label, value) tuples.
        display_filter : bool, optional
            Whether to display item filter (the default is True)
        auto_display : bool, optional
            Whether to display on instantiation (the default is True)

        """
        if isinstance(source_items, dict):
            source_items = list(source_items.items())

        self.src_items = sorted(set(source_items))
        if isinstance(self.src_items[0], tuple):
            self._src_dict = {val: (label, val) for label, val in self.src_items}
        else:
            self._src_dict = {}

        w_layout = widgets.Layout(width="40%", height="200px")
        self._source_list = widgets.SelectMultiple(
            options=sorted(set(self.src_items)), layout=w_layout, description="Source: "
        )

        if isinstance(default_selected, dict):
            default_selected = list(default_selected.items())
        if default_selected:
            set_selected = set(default_selected)
            selected_items = sorted(set_selected.intersection(source_items))
        else:
            selected_items = []

        self._select_list = widgets.SelectMultiple(
            options=selected_items, layout=w_layout, description="Selected: "
        )

        self._display_filter = display_filter
        if display_filter:
            self._w_filter = widgets.Text(
                value="", description="Filter:", style={"description_width": "initial"}
            )

            # set up observer callbacks
            self._w_filter.observe(self._update_options, names="value")

        self._b_add_all = widgets.Button(description="Add All \u21fe")
        self._b_add = widgets.Button(description="Add \u21fe")
        self._b_del = widgets.Button(description="\u21fd Remove")
        self._b_del_all = widgets.Button(description="\u21fd Remove All")

        self._b_add.on_click(self._on_btn_add)
        self._b_del.on_click(self._on_btn_del)
        self._b_del_all.on_click(self._on_btn_del_all)
        self._b_add_all.on_click(self._on_btn_add_all)

        v_box = widgets.VBox(
            [self._b_add_all, self._b_add, self._b_del, self._b_del_all]
        )
        self.layout = widgets.HBox([self._source_list, v_box, self._select_list])
        if self._display_filter:
            self.layout = widgets.VBox([self._w_filter, self.layout])
        if auto_display:
            self.display()

    @property
    def selected_items(self) -> List[Any]:
        """
        Return a list of the selected items.

        If the input list is a list of tuples, this returns
        a list of the selected tuples.

        Returns
        -------
        List[Any]
            List of items in the selected list.

        """
        return list(self._select_list.options)

    @property
    def selected_values(self) -> List[Any]:
        """
        Return list of selected values.

        If the input list is a list of tuples, this returns
        a list of values of the items.

        Returns
        -------
        List[Any]
            List of selected item values.

        """
        if self._select_list.options and isinstance(
            self._select_list.options[0], tuple
        ):
            return [item[1] for item in self._select_list.options]
        return self.selected_items

    def _update_options(self, change):
        """Filter the alert list by substring."""
        if change is not None and "new" in change:
            self._source_list.options = sorted(
                {
                    i
                    for i in self.src_items
                    if str(change["new"]).lower() in str(i).lower()
                }
            )

    # pylint: disable=not-an-iterable
    def _on_btn_add(self, button):
        del button
        selected_set = set(self._select_list.options)
        for selected in self._source_list.value:
            if self._src_dict:
                selected_set.add(self._src_dict[selected])
            else:
                selected_set.add(selected)
        self._select_list.options = sorted(list(selected_set))

    def _on_btn_add_all(self, button):
        del button
        self._select_list.options = sorted(list(set(self._source_list.options)))

    def _on_btn_del(self, button):
        del button
        selected_set = set(self._select_list.options)
        # save the current index
        cur_index = max(self._select_list.index)
        if selected_set:
            if self._src_dict:
                # if we're working with tuples, we need to specify the tuple to remove
                for selected in self._select_list.value:
                    selected_set.remove(self._src_dict[selected])
            else:
                # else just delete the value
                for selected in self._select_list.value:
                    selected_set.remove(selected)
            self._select_list.options = sorted(list(selected_set))
        if not self._select_list.options:
            return
        # try to set the index to the next item in the list
        if cur_index < len(self._select_list.options):
            next_item = cur_index if cur_index else 0
            self._select_list.index = tuple([next_item])
        else:
            last_item = max(len(self._select_list.options) - 1, 0)
            self._select_list.index = tuple([last_item])

    # pylint: enable=not-an-iterable

    def _on_btn_del_all(self, button):
        del button
        self._select_list.options = []

    def display(self):
        """Display the control."""
        display(self.layout)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


@export
class Progress:
    """UI Progress bar."""

    def __init__(self, completed_len: int, visible: bool = True):
        """
        Instantiate new _Progress UI.

        Parameters
        ----------
        completed_len : int
            The expected value that indicates 100% done.
        visible : bool
            If True start the progress UI visible, by default True.

        """
        self._completed = 0
        self._total = completed_len
        self._progress = widgets.IntProgress(
            value=0,
            max=100,
            step=1,
            description="Progress:",
            bar_style="info",
            orientation="horizontal",
        )
        self._done_label = widgets.Label(value="0%")
        self._progress.visible = visible
        self._done_label.visible = visible
        self.layout = widgets.HBox([self._progress, self._done_label])
        self.display()

    @property
    def value(self) -> int:
        """
        Return the current progress value.

        Returns
        -------
        int
            Progess value

        """
        return self._completed

    @property
    def max(self) -> int:
        """
        Return the current progress maximum value.

        Returns
        -------
        int
            Max value

        """
        return self._total

    def update_progress(self, new_total: int = 0, delta: int = 0):
        """
        Update progress UI by increment or new total.

        Parameters
        ----------
        new_total : int, optional
            New total, by default 0
        delta : int, optional
            Increment to update current total, by default 0

        """
        if new_total:
            self._completed = new_total
        else:
            self._completed += delta
        perc_total = int(100 * self._completed / self._total)
        self._progress.value = perc_total
        self._done_label.value = f"{perc_total}%"

    def show(self):
        """Make the controls visible."""
        self._progress.visible = True
        self._done_label.visible = True

    def hide(self):
        """Hide the controls."""
        self._progress.visible = True
        self._done_label.visible = True

    def display(self):
        """Display the control."""
        display(self.layout)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()


class OptionButtons:
    """
    OptionButtons creates a sequence of buttons to choose from.

    The widget can be run in synchronous mode as a simple option
    selector or in async mode with a timeout.
    In the latter mode, after the timeout has expired the widget
    value is set to the default option button value.
    To use the async mode you must call `widget.display_async()` with
    the async keyword.

    Attributes
    ----------
    value : str
        The value of the option selected (case-normalized)

    Example
    -------
    >>> opt = OptionButtons(description="Continue something?",
    ...  buttons=["Maybe", "Yes", "Cancel"], timeout=10)
    >>> await opt.display_async()

    """

    def __init__(
        self,
        description: Optional[str] = "Select an option to continue",
        buttons: Optional[Iterable[str]] = None,
        default: Optional[str] = None,
        timeout: int = 0,
        debug: bool = False,
    ):
        """
        Initialize the OptionButton widget.

        Parameters
        ----------
        description : Optional[str], optional
            Description label displayed above the buttons,
            by default "Select an option to continue"
        buttons : Optional[Iterable[str]], optional
            A list of button values, by default None. This
            will default to ["Yes", "No", "Cancel"]
        default : Optional[str], optional
            The default value to use on timeout, by default the
            first value in the `buttons` list
        timeout : int, optional
            Timeout in seconds, by default 0
        debug : bool, optional
            Adds some debug information to an Output controle,
            by default False

        """
        if buttons is None:
            buttons = ["Yes", "No", "Cancel"]
        self._buttons = []
        for b_item in buttons:
            self._buttons.append(widgets.Button(description=b_item))
        self._desc_label = widgets.Label(value=description)
        self._timer_label = widgets.Label(layout=widgets.Layout(left="10px"))
        self.default = default or next(iter(buttons)).casefold()
        self.value: Optional[str] = None
        self.timeout = timeout

        self._completion: Any = None
        self._fut_val: Any = None
        self._debug = debug
        if self._debug:
            self._out = widgets.Output()

    @property
    def layout(self):
        """Create layout for buttons."""
        return widgets.VBox(
            [self._desc_label, widgets.HBox([*(self._buttons), self._timer_label])]
        )

    def _debug_out(self, mssg: str):
        if self._debug:
            self._out.append_stdout(mssg)

    def _create_button_callbacks(self, btns):
        """Set up buttons."""

        def getvalue(change):
            """Button on_click handler."""
            self.value = change.description.casefold()
            for btn in btns:
                btn.on_click(getvalue, remove=True)

        for btn in btns:
            btn.on_click(getvalue)

    async def _await_widget(self):
        """Awaitable coroutine for widget."""
        self._debug_out("await_widget entered\n")
        self._create_button_callbacks(self._buttons)
        self._debug_out("buttons set\n")

        done, _ = await asyncio.wait(
            [self._wait_for_button_change(), self._await_timer(self.timeout)],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=self.timeout + 5,
        )
        self._debug_out("wait returned\n")
        self._completion = done
        self._debug_out(str(done))
        return done

    async def _wait_for_button_change(self):
        """Awaitable for button selection state."""
        self._debug_out("wait_for_button_change entered\n")
        while self.value is None:
            await asyncio.sleep(0.1)
            if self._debug:
                self._debug_out("*")

    async def _await_timer(self, timeout: int = 5):
        timeout = max(timeout, 0)
        while timeout > 0:
            self._timer_label.value = f"Waiting {timeout} sec..."
            if self.value:
                self._timer_label.value = f"Option selected: '{self.value}'"
                return
            await asyncio.sleep(1)
            timeout -= 1
        self.value = self.default
        self._timer_label.value = f"Timed out. Defaulted to '{self.value}'"

    async def display_async(self, reset: bool = False):
        """
        Display widget with timeout.

        Parameters
        ----------
        reset : bool, optional
            Resets any current value to None,
            by default False

        """
        if reset:
            self.value = None
        display(self.layout)
        if self._debug:
            display(self._out)
        self._fut_val = asyncio.ensure_future(self._await_widget())
        self._debug_out("future returned\n")
        self._debug_out(str(self._fut_val) + "\n")

    def display(self):
        """Display widget in simple sync mode."""
        display(self.layout)

    def _ipython_display_(self):
        """Display in IPython."""
        self.display()
