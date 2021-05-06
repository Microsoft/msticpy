# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pivot helper functions ."""
from collections import abc
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union
import warnings

import attr
import pandas as pd

from .._version import VERSION
from . import entities

__version__ = VERSION
__author__ = "Ian Hellen"


_DF_SRC_COL_PARAM_NAMES = [
    "column",
    "input_column",
    "input_col",
    "src_column",
    "src_col",
]


@attr.s(auto_attribs=True)
class PivotRegistration:
    """
    Pivot registration for function.

    Notes
    -----
    src_module : str
        The src_module to import
    src_class : str, optional
        class to import and instantiate that contains the function/method
        (not needed if the target function is a pure Python function)
    src_func_name: Callable
        The function to wrap.
    func_new_name: str, optional
        Rename the function to this, defaults to `src_func_name`
    input_type : str
        The input data type that the function is expecting.
        One of 'dataframe', 'iterable', 'value'
    can_iterate: bool, optional
        True if the function supports being called multiple times
        (for iterable input). Default is True
    entity_map: Dict[str, str]
        dict of entities supported (keys) and attribute to use from
        entity as input to the function
    func_df_param_name: str
        The name of the parameter that `func` takes the input value
        e.g. func(ip=my_address) => 'ip' == func_df_col_param_name.
        In the case of a DataFrame, this is usually 'data'
    func_df_col_param_name: str
        The name that the target function uses to identify the
        column to use for input in the input DataFrame.
    func_out_column_name: str, optional
        The name of the column in the output DF to use as a key to join
        to the input. If None, use `func_df_col_param_name`
    func_static_params: Optional[Dict[str, Any]]
        static parameters (kwargs) that are always passed
        to the target function
    func_input_value_arg: Optional[str]
        The name of kwarg passed to the function that contain
        the input value. If function supports DF input, `func_df_col_param_name`
        will be used and this is not needed.
    src_config_path : Optional[str]
        The source path that the configuration was read from, default None.
    src_config_entry : Optional[str]
        The entry name in the configuration file, default None.
    entity_container_name : Optional[str]
        The name of the container in the entity that will hold
        this pivot function.
    return_raw_output : bool
        Return raw output from the wrapped function, do not
        try to format into a DataFrame. Default is False.
    create_shortcut : bool
        If True, create a shortcut function directly on the entity.

    """

    input_type: str
    entity_map: Dict[str, str]
    func_df_param_name: Optional[str] = None
    func_out_column_name: Optional[str] = None
    func_df_col_param_name: Optional[str] = None
    func_new_name: Optional[str] = None
    src_module: Optional[str] = None
    src_class: Optional[str] = None
    src_func_name: Optional[str] = None
    can_iterate: bool = True
    func_static_params: Optional[Dict[str, Any]] = None
    func_input_value_arg: Optional[str] = None
    src_config_path: Optional[str] = None
    src_config_entry: Optional[str] = None
    entity_container_name: Optional[str] = None
    return_raw_output: bool = False
    create_shortcut: bool = False

    def attr_for_entity(self, entity: Union[entities.Entity, str]) -> Optional[str]:
        """
        Return the attribute to use for the specified entity.

        Parameters
        ----------
        entity : Union[entities.Entity, str]
            Entity instance or name

        Returns
        -------
        Optional[str]
            Attribute name to use.

        """
        if isinstance(entity, entities.Entity):
            ent_name = entity.__class__.__name__
        else:
            ent_name = entity
        return self.entity_map.get(ent_name)


def create_pivot_func(
    target_func: Callable[[Any], Any],
    pivot_reg: PivotRegistration,
) -> Callable[..., pd.DataFrame]:
    """
    Create function wrapper for pivot function.

    Parameters
    ----------
    target_func: Callable
        The target function to wrap.
    pivot_reg : PivotRegistration
        The pivot function registration object.

    Returns
    -------
    Callable[[Any], pd.DataFrame]
        The original `target_func` wrapped in pre-processing
        and post-processing code.

    """

    @wraps(target_func)
    def pivot_lookup(*args, **kwargs) -> pd.DataFrame:
        """
        Lookup Pivot function from Entity or parameter values.

        Parameters
        ----------
        data: Union[str, List[str], pd.DataFrame]
            Not used if querying the entity value itself

        Returns
        -------
        pd.DataFrame
            DataFrame of Pivot function results.

        """
        # remove and save the join kw, if specified (so it doesn't interfere
        # with other operations and doesn't get sent to the function)
        join_type, left_on, right_on, j_ignore_case = get_join_params(kwargs)

        input_value = _get_input_value(*args, pivot_reg=pivot_reg, parent_kwargs=kwargs)
        _check_valid_settings_for_input(input_value, pivot_reg)

        # If the input_value is not a DF convert it into one and return the DF,
        # the column with the input value(s) plus the param dict that we're going
        # to send to the function. This is going to look like:
        # {"data": input_df, "src_column": input_column}
        input_df, input_column, param_dict = _create_input_df(
            input_value, pivot_reg, parent_kwargs=kwargs
        )

        # Add any static parameters for the function to our params dict
        param_dict.update(pivot_reg.func_static_params or {})

        # Call the target function and collect the results
        if pivot_reg.input_type == "value":
            if not pivot_reg.can_iterate and len(input_df) > 1:
                raise TypeError(
                    "The function does not support multiple input values.",
                    "Try again with a single row/value as input.",
                    "E.g. func(data=df.iloc[N], column=...)",
                )
            result_df = _iterate_func(
                target_func, input_df, input_column, pivot_reg, **kwargs
            )
        else:
            result_df = target_func(**param_dict, **kwargs)  # type: ignore
        merge_key = pivot_reg.func_out_column_name or input_column

        # If requested to join to input
        # and this function is returning a DataFrame
        if join_type and not pivot_reg.return_raw_output:
            left_on = left_on or input_column
            right_on = right_on or merge_key
            return join_result(
                input_df=input_df,
                result_df=result_df,
                how=join_type,
                left_on=left_on,
                right_on=right_on,
                ignore_case=j_ignore_case,
            ).drop(columns="src_row_index", errors="ignore")
        return result_df

    setattr(
        pivot_lookup,
        "pivot_properties",
        attr.asdict(pivot_reg, filter=(lambda _, val: val is not None)),
    )
    return pivot_lookup


def get_join_params(
    func_kwargs: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[str], bool]:
    """
    Get join parameters from kwargs.

    Parameters
    ----------
    func_kwargs : Dict[str, Any]
        Keyword arguments from caller

    Returns
    -------
    Tuple[str, str, str, bool]
        join_type, left_on, right_on, join_ignore_case

    """
    # remove and save the join kw, if specified (so it doesn't interfere
    # with other operations and doesn't get sent to the function)
    join_type = func_kwargs.pop("join", None)
    join_ignore_case = func_kwargs.pop("join_ignore_case", None)
    if not join_type:
        return None, None, None, False
    left_on = func_kwargs.pop("left_on", None)
    right_on = func_kwargs.pop("right_on", None)
    if left_on and not right_on:
        warnings.warn(
            "If you are specifying explicit join keys "
            "you must specify 'right_on' parameter with the "
            + "name of the output column to join on. "
            + "Results will joined on index."
        )
    if not left_on:
        col_keys = list(func_kwargs.keys() - {"start", "end", "data"})
        if len(col_keys) == 1:
            # Only one input param so assume this is the src/left
            # join key
            left_on = func_kwargs.get(col_keys[0])

    if right_on and not left_on:
        warnings.warn(
            "Could not infer 'left' join column from source data. "
            + "Please specify 'left_on' parameter with the "
            + "name of the source column to join on. "
            + "Results will joined on index."
        )
    return join_type, left_on, right_on, join_ignore_case


def join_result(
    input_df: pd.DataFrame,
    result_df: pd.DataFrame,
    how: str,
    left_on: str,
    right_on: str,
    ignore_case: bool,
) -> pd.DataFrame:
    """
    Join input and result DFs, optionally ignoring case.

    Parameters
    ----------
    input_df : pd.DataFrame
        Input DF
    result_df : pd.DataFrame
        Result DF
    how : str
        Join type - "inner", "left", "right", "outer"
    left_on : str
        Column from `input_df` to use as join key
    right_on : str
        Column from `result_df` to use as join key
    ignore_case : bool
        If True and input_df column is a string

    Returns
    -------
    pd.DataFrame
        The merged DataFrame

    """
    if not ignore_case or input_df[left_on].dtype.name not in (
        "string",
        "object",
    ):
        # Not requested case-insensitive join OR input column is
        # not a string/object
        return input_df.merge(
            result_df,
            left_on=left_on,
            right_on=right_on,
            how=how,
            suffixes=("_src", "_res"),
        )

    # We need to join case-insensitive
    left_on = f"{left_on}_lc"
    input_df[left_on] = input_df[left_on].str.casefold()
    right_on = f"{right_on}_lc"
    result_df[right_on] = result_df[right_on].astype("string").str.casefold()
    return input_df.merge(
        result_df,
        left_on=left_on,
        right_on=right_on,
        how=how,
        suffixes=("_src", "_res"),
    ).drop(columns=[left_on, right_on])


def _get_entity_attr_or_self(obj, attrib):
    """Return entity attribute or obj if not an entity."""
    if isinstance(obj, entities.Entity):
        return getattr(obj, attrib)
    return obj


def _get_input_value(
    *args, pivot_reg: PivotRegistration, parent_kwargs: Dict[str, Any]
) -> Any:
    """Extract input value from args or kwargs."""
    if args:
        input_value = args[0]
    else:
        # Search possible input arg names
        poss_args = [
            arg
            for arg in [
                pivot_reg.func_df_param_name,
                pivot_reg.func_input_value_arg,
                "value",
                "data",
                "input",
            ]
            if arg
        ]
        for arg_name in poss_args:
            input_value = parent_kwargs.pop(arg_name, None)
            if input_value is not None:
                break
        else:
            raise AttributeError(
                "Required keyword argument not found.",
                f"One of {', '.join(poss_args)} required.",
            )
    if isinstance(input_value, entities.Entity):
        src_entity_attrib = pivot_reg.attr_for_entity(input_value)
        input_value = _get_entity_attr_or_self(input_value, src_entity_attrib)
    return input_value


def _check_valid_settings_for_input(input_value: Any, pivot_reg: PivotRegistration):
    """Check input against settings in `pivot_reg`."""
    # Must have one of these specified
    if not (pivot_reg.func_df_col_param_name or pivot_reg.func_input_value_arg):
        raise ValueError(
            "A value for one of 'func_df_col_param_name' ",
            "or 'func_input_value_arg' must be given",
        )
    # If the function accepts only value type and cannot iterate. Make sure
    # that the input_value is a simple value
    if pivot_reg.input_type == "value":
        if not pivot_reg.func_input_value_arg:
            raise ValueError("No value for pivot func input argument was given")
        if not pivot_reg.can_iterate and (
            isinstance(input_value, pd.DataFrame)
            or (
                # pylint: disable=isinstance-second-argument-not-valid-type
                isinstance(input_value, pd.DataFrame)
                and not isinstance(input_value, str)
                # pylint: enable=isinstance-second-argument-not-valid-type
            )
        ):
            raise ValueError(
                f"This function does not accept inputs of {type(input_value)}"
            )


def _arg_to_dframe(arg_val, col_name: str = "param_value"):
    """
    Convert a scalar or Iterable value to a DataFrame.

    Parameters
    ----------
    arg_val: Any
        The value to be converted
    col_name: Optional[str]
        The name to assign to the DataFrame column

    Returns
    -------
    pd.DataFrame
        The resulting DataFrame

    Notes
    -----
    If `arg_val` is already a DataFrame it is returned as is.

    """
    if isinstance(arg_val, pd.DataFrame):
        return arg_val
    if isinstance(arg_val, str) or not isinstance(arg_val, abc.Iterable):
        return pd.DataFrame([arg_val], columns=[col_name])
    return pd.DataFrame(arg_val, columns=[col_name])


def _create_input_df(input_value, pivot_reg, parent_kwargs):
    """Create input_df and params from input."""
    # If input_value type is not already a dataframe, convert it.
    # If the DF column param is specified, use that or fall back
    # to using the function input value arg.
    input_column = pivot_reg.func_df_col_param_name or pivot_reg.func_input_value_arg
    # If input_value is already a DF, this call just returns the original DF
    input_df = _arg_to_dframe(input_value, input_column)  # type: ignore

    if isinstance(input_value, pd.DataFrame):
        # If the original input_value is a DataFrame
        # try to find the column name specification in kwargs
        for col_param in (
            pivot_reg.func_df_col_param_name,
            pivot_reg.func_input_value_arg,
            *_DF_SRC_COL_PARAM_NAMES,
        ):
            if col_param in parent_kwargs and parent_kwargs[col_param] in input_df:
                input_column = parent_kwargs.pop(col_param)
                break
        else:
            raise KeyError(
                f"'{input_column}' is not in the input dataframe",
                "Please specify the column when calling the function."
                "You can use one of the parameter names for this:",
                _DF_SRC_COL_PARAM_NAMES,
            )
    # we want to get rid of data=xyz parameters from kwargs, since we're adding them
    # below
    parent_kwargs.pop("data", None)
    parent_kwargs.pop(pivot_reg.func_df_param_name, None)

    if input_column not in input_df:
        raise KeyError(f"'{input_column}' is not in the input dataframe")
    if input_column:
        param_dict = {
            pivot_reg.func_df_param_name: input_df,
            pivot_reg.func_df_col_param_name: input_column,
        }
    else:
        # If no column was specified, the user will have to specify
        # this in the call to the method - we just add the DF parameter
        param_dict = {pivot_reg.func_df_param_name: input_df}
    return input_df, input_column, param_dict


def _iterate_func(target_func, input_df, input_column, pivot_reg, **kwargs):
    """Call `target_func` function with values of each row in `input_df`."""
    results = []
    # Add any static parameters to all_rows_kwargs
    all_rows_kwargs = kwargs.copy()
    all_rows_kwargs.update((pivot_reg.func_static_params or {}))
    res_key_col_name = pivot_reg.func_out_column_name or pivot_reg.func_input_value_arg

    for row_index, row in enumerate(input_df[[input_column]].itertuples(index=False)):
        # Get rid of any conflicting arguments from kwargs
        func_kwargs = all_rows_kwargs.copy()
        func_kwargs.pop(pivot_reg.func_input_value_arg, None)
        # Create a param dictionary with the value parameter for this row
        param_dict = {pivot_reg.func_input_value_arg: row[0]}
        # run the function
        result = target_func(**param_dict, **all_rows_kwargs)

        # Process the output, if it is a DataFrame
        if not pivot_reg.return_raw_output and not isinstance(result, pd.DataFrame):
            col_value = next(iter(row._asdict().values()))
            if isinstance(result, dict):
                # if result is a dict - make that into a row.
                result = pd.DataFrame(pd.Series(result)).T
                result[res_key_col_name] = col_value
            else:
                # just make the result into a string and use that as a single col
                result = pd.DataFrame(
                    [[col_value, str(result)]], columns=[res_key_col_name, "result"]
                )
            result["src_row_index"] = row_index
        results.append(result)
    if pivot_reg.return_raw_output:
        if len(results) == 1:
            return results[0]
        return results
    return pd.concat(results, ignore_index=True)


# _PARENT_SELF = "parent_self"


# def query_cont_member_wrap(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
#     """
#     Wrap a func to work as instance method in a QueryContainer.

#     Parameters
#     ----------
#     func : Callable[[Any], Any]
#         Function to wrap as method

#     Returns
#     -------
#     Callable[[Any], Any]
#         Wrapped function

#     Notes
#     -----
#     This is designed to be used inside a `QueryContainer`. The wrapped
#     function checks to see if its arg[0] is a QueryContainer - meaning
#     it has been called as an instance function of that class.
#     If so, and the parent class has a _parent_self attribute, it will
#     replace the original arg[0] (the self of QueryContainer) with
#     the self of the containing class (_parent_self).
#     It relies containing class setting `_parent_self` as an attribute
#     in any QueryContainer attributes that it has. The msticpy Entity
#     class does this.

#     If these conditions don't apply it simply passed through the call
#     to the original function.

#     See Also
#     --------
#     QueryContainer
#     Entity

#     """

#     @wraps(func)
#     def _wrapped_member(*args, **kwargs):
#         if (
#             args
#             and args[0].__class__.__name__ == "QueryContainer"
#             and hasattr(args[0], _PARENT_SELF)
#         ):
#             parent_self = getattr(args[0], _PARENT_SELF)
#             return func(parent_self, *args[1:], **kwargs)
#         return func(*args, **kwargs)

#     return _wrapped_member
