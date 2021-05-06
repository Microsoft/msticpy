# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Pandas DataFrame accessor for Pivot functions."""
import re
import json
from json import JSONDecodeError
from datetime import datetime
from numbers import Number
import warnings
from typing import Callable, Dict, Iterable, Set, Union

import numpy as np
import pandas as pd
from IPython import get_ipython
from IPython.display import HTML, display

from .._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


def _verbose_out(data, func, st_time, verbose=False, debug=False, **kwargs):
    """Output verbose or debug info."""
    end_time = datetime.now()

    if verbose or debug:
        print(f"{len(data)} rows returned from function {func.__name__}")
    if debug:
        print(f"Columns in result from function {func.__name__}:")
        print(data.columns)
        print(f"Execution time: {end_time - st_time}")
        print(f"Parameters: {kwargs}")


@pd.api.extensions.register_dataframe_accessor("mp_pivot")
class PivotAccessor:
    """Pandas api extension for Pivot functions."""

    def __init__(self, pandas_obj):
        """Instantiate pivot extension class."""
        self._df = pandas_obj
        self._ip = get_ipython()

    def run(self, func: Callable[..., pd.DataFrame], **kwargs) -> pd.DataFrame:
        """
        Run a pivot function on the current DataFrame.

        Parameters
        ----------
        func : Callable[..., pd.DataFrame]
            Pivot function to run
        kwargs:
            Keyword arguments to pass to `func`.
            A column specification (e.g. column="src_col_name")
            is usually the minimum needed.
            For data queries the `column` keyword must be the
            name of the the query parameter (e.g. host_name = "src_col_name")

        Returns
        -------
        pd.DataFrame
            The output DataFrame from the function.

        Notes
        -----
        You can pass the `join` keyword argument to most
        pivot functions. Values for join are "inner", "left", "right"
        or "outer".

        """
        st_time = datetime.now()
        verbose = kwargs.pop("verbose", False)
        debug = kwargs.pop("debug", False)
        result = self._df.pipe((func, "data"), **kwargs)
        if verbose or debug:
            _verbose_out(
                data=result,
                func=func,
                st_time=st_time,
                verbose=verbose,
                debug=debug,
                **kwargs,
            )
        return result

    def display(
        self,
        title: str = None,
        cols: Iterable[str] = None,
        query: str = None,
        head: int = None,
    ) -> pd.DataFrame:
        """
        Display the DataFrame in the middle of a pipeline.

        Parameters
        ----------
        title : str, optional
            Title to display for the DataFrame, by default None
        cols : Iterable[str], optional
            List of columns to display, by default None
        query : str, optional
            Query to filter the displayed data, by default None
            This should be a string executable by the DataFrame.query
            function
        head : int, optional
            Limit the displayed output to `head` rows, by default None

        Returns
        -------
        pd.DataFrame
            Passed through input DataFrame.

        """
        if title:
            display(HTML(f"<h3>{title}</h3>"))
        disp_df = self._df
        if cols:
            disp_df = disp_df[cols]
        if query:
            disp_df = disp_df.query(query)  # , parser='python', engine='python')
        if head:
            disp_df = disp_df.head(head)
        display(disp_df)
        return self._df

    def tee(self, var_name: str, clobber: bool = False) -> pd.DataFrame:
        """
        Save current dataframe to `var_name` in the IPython user namespace.

        Parameters
        ----------
        var_name : str
            The name of the DF variable to create.
        clobber : bool, optional
            Whether to overwrite an existing variable of the same name,
            by default False

        Returns
        -------
        pd.DataFrame
            Passed through input DataFrame.

        Notes
        -----
        This function only works in an IPython/Jupyter notebook environment.
        It will attempt to create a variable in the user local namespace
        that references the current state of the DataFrame in the pipeline.

        By default it will not overwrite an existing variable of the same
        name (specify `clobber=True` to overwrite)

        """
        if self._ip and var_name:
            if var_name in self._ip.ns_table["user_local"] and not clobber:
                warnings.warn(f"Did not overwrite existing {var_name} in namespace")
            else:
                self._ip.ns_table["user_local"][var_name] = self._df
        return self._df

    def tee_exec(self, df_func: str, *args, **kwargs) -> pd.DataFrame:
        """
        Run a dataframe method on the dataframe without changing it.

        Parameters
        ----------
        df_func : str
            The name of the function to execute. Accessor methods
            must be of the form "accessor.method".
        args : tuple
            Positional arguments to be passed to the function
        kwargs : dict
            Keyword arguments to be passed to the function.

        Returns
        -------
        pd.DataFrame
            Passed through input DataFrame.

        Notes
        -----
        This function runs the DataFrame method or accessor function.
        It does not alter the DataFrame (unless the function does
        any kind of in-place modification). The function is run and
        the original input DataFrame is returned.

        """
        acc_name = func_name = func = None
        if "." in df_func:
            acc_name, func_name = df_func.split(".")
            accessor = getattr(self._df, acc_name, None)
            if accessor:
                func = getattr(accessor, func_name, None)
        else:
            func = getattr(self._df, df_func, None)
        if func:
            # run the function with any additional args
            func(*args, **kwargs)
        return self._df

    def filter_cols(
        self,
        cols: Union[str, Iterable[str]],
        match_case: bool = False,
        sort_cols: bool = False,
    ) -> pd.DataFrame:
        """
        Filter output columns matching names in `cols` expression(s).

        Parameters
        ----------
        cols : Union[str, Iterable[str]]
            Either a string or a list of strings with filter expressions.
            These can be exact matches for column names, wildcard patterns
            ("*" matches multiple chars and "?" matches a single char),
            or regular expressions.
        match_case: bool, optional
            Use case-sensitive matching, by default False
        sort_cols : bool, optional
            Alphabetically sort column names, by default False

        Returns
        -------
        pd.DataFrame
            The input DataFrame with only columns that match the
            filtering expressions.

        """
        curr_cols = self._df.columns
        filt_cols: Set[str] = set()
        if isinstance(cols, str):
            filt_cols.update(_name_match(curr_cols, cols, match_case))
        elif isinstance(cols, list):
            for col_filter in cols:
                filt_cols.update(_name_match(curr_cols, col_filter, match_case))
        if not filt_cols:
            raise ValueError("Column filter expression(s) did not match any columns")

        if sort_cols:
            out_cols = sorted(filt_cols)
        else:
            # keep the existing order
            out_cols = [col for col in curr_cols if col in filt_cols]
        return self._df[out_cols]

    def filter(
        self,
        expr: Union[str, Number],
        match_case: bool = False,
        numeric_col: bool = False,
    ) -> pd.DataFrame:
        """
        Filter all columns of DataFrame, return rows with any matches.

        Parameters
        ----------
        expr : Union[str, Number]
            String or regular expression to match or a (partial) number.
            If `expr` is a string it is matched against any string or object
            columns using pandas `str.contains(..regex=True)`
            If `expr` is a number or if `numeric_col` is True, `expr`
            is converted to a string and matched as a substring of any numeric
            columns.
        match_case : bool, optional
            The match is not case-sensitive by default. Set to True to force
            case-sensitive matches.
        numeric_col : bool, optional
            If `expr` is a numeric string or number this will force a match against
            only numeric columns, by default False

        Returns
        -------
        pd.DataFrame
            The filtered dataframe

        Raises
        ------
        TypeError
            If `expr` is neither a string or number.

        """
        if isinstance(expr, str) and not numeric_col:
            text_cols = self._df.select_dtypes(include=[object, "string"])
            return self._df[
                text_cols.apply(
                    lambda col: col.str.contains(
                        expr, regex=True, case=match_case, na=False
                    )
                ).any(axis=1)
            ]
        if isinstance(expr, Number) or numeric_col:
            num_cols = self._df.select_dtypes(include="number")
            str_expr = str(expr)
            return self._df[
                num_cols.apply(
                    lambda col: col.astype("string").str.contains(str_expr, regex=True)
                ).any(axis=1)
            ]
        raise TypeError("expr '{expr}' must be a string or numeric type.")

    def sort(
        self, cols: Union[str, Iterable[str], Dict[str, str]], ascending: bool = None
    ) -> pd.DataFrame:
        """
        Sort output by column expression.

        Parameters
        ----------
        cols : Union[str, Iterable[str], Dict[str, str]]
            If this is a string, then this should be a column name expression. A column name
            expression is either a column name, a case-insenstive column name or a
            regular expression to match one or more column names.
            Each column name expression can be of
            the format `col_name_expr:desc` to sort descending (`col_name_expr:asc` is the default).
            The col_name can also be a regular expression or partial column name.
            If this is a list, then each element should be a column name expression
            with an optional ':asc' or ':desc' suffix.
            If this is a dict, then the keys should be column name expressions and the
            values bools indication 'ascending' (True) or 'descending' (False) sort.
        ascending : [type], optional
            Overrides any ordering specified for individual columns and sorts
            'ascending' if True or 'descending' if False. If not supplied and no
            column-specific ordering is supplied it sorts ascending.

        Returns
        -------
        pd.DataFrame
            The sorted DataFrame

        Raises
        ------
        ValueError
            One or more column expressions matched no column name in the input.

        """
        if isinstance(cols, dict):
            col_dict = cols
        else:
            if isinstance(cols, str):
                col_list = [col.strip() for col in cols.split(",")]
            else:
                col_list = list(cols)
            col_dict = {
                col.split(":")[0].strip(): not col.casefold().endswith(":desc")
                for col in col_list
            }

        sort_cols = {}
        # create case-insensitive mapping for DF cols
        df_cols = {col.casefold(): col for col in self._df.columns}
        for col in col_dict:
            # Use case-matched name, if available
            if col in self._df.columns:
                sort_cols[col] = col_dict[col]
                continue
            # Look for case-insensitive match
            df_col = df_cols.get(col.casefold())
            if df_col:
                sort_cols[col] = col_dict[col]
                continue
            # look for regex matches for col name
            df_match_cols = [
                df_cols[s_col]
                for s_col in df_cols
                if re.match(col, s_col, re.IGNORECASE)
            ]
            # we might get multiple matches
            if df_match_cols:
                sort_cols.update({df_col: col_dict[col] for df_col in df_match_cols})
                continue
            raise ValueError(
                f"'{col}' column in sort list did not match any columns in input data."
            )
        # create the ascending parameter
        asc_param = ascending if ascending is not None else list(sort_cols.values())
        return self._df.sort_values(list(sort_cols.keys()), ascending=asc_param)

    def list_to_rows(self, cols: Union[str, Iterable[str]]) -> pd.DataFrame:
        """
        Expand a list column to individual rows.

        Parameters
        ----------
        cols : Union[str, Iterable[str]]
            The columns to be expanded.

        Returns
        -------
        pd.DataFrame
            The expanded DataFrame

        """
        orig_cols = self._df.columns
        data = self._df
        if isinstance(cols, str):
            cols = [cols]
        for col in cols:
            item_col = f"{col}_list_item$$"
            ren_col = {item_col: col}
            data = (
                pd.DataFrame(data[col].to_list(), index=data.index)
                .replace([None], np.nan)  # convert any Nones to NaN
                .merge(data, right_index=True, left_index=True)
                .melt(id_vars=orig_cols, value_name=item_col)
                .dropna(subset=[item_col])  # get rid of rows with NaNs in this col
                .drop([col, "variable"], axis=1)
                .rename(columns=ren_col)
            )
        return data

    def parse_json(self, cols: Union[str, Iterable[str]]) -> pd.DataFrame:
        """
        Convert JSON string columns to Python types.

        Parameters
        ----------
        cols : Union[str, Iterable[str]]
            Column or interable of columns to process

        Returns
        -------
        pd.DataFrame
            Processed dataframe

        """
        if isinstance(cols, str):
            cols = [cols]
        data = self._df
        for col in cols:
            col_parsed = f"{col}_parsed"
            data[col_parsed] = data[col].apply(_json_safe_conv)
            data = data.drop([col], axis=1).rename(columns={col_parsed: col})
        return data


def _name_match(cur_cols: Iterable[str], col_filter, match_case):
    col_filter = re.sub(r"[^.]\*", ".*", col_filter)
    col_filter = re.sub(r"[^.]\?", ".?", col_filter)
    regex_opts = [re.IGNORECASE] if not match_case else []
    return {col for col in cur_cols if re.match(col_filter, col, *regex_opts)}


def _json_safe_conv(val):
    if val:
        try:
            return json.loads(val)
        except (TypeError, JSONDecodeError):
            pass
    return val
