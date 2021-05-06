# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Reads pivot registration config files."""
import importlib
from typing import Any, Callable, Dict, Type
import warnings

import yaml

from .._version import VERSION
from ..common.exceptions import MsticpyUserConfigError
from ..data.query_container import QueryContainer
from . import entities
from .pivot_register import PivotRegistration, create_pivot_func

__version__ = VERSION
__author__ = "Ian Hellen"


def register_pivots(
    file_path: str,
    namespace: Dict[str, Any] = None,
    container: str = "other",
    force_container: bool = False,
    **kwargs,
):
    """
    Register pivot functions from configuration file.

    Parameters
    ----------
    file_path : str
        Path to config yaml file
    namespace : Dict[str, Any], optional
        Namespace to search for existing instances of classes, by default None
    container : str, optional
        Container name to use for entity pivot functions, by default "other"
    force_container : bool, optional
        Force `container` value to be used even if entity definitions have
        specific setting for a container name, by default False

    Raises
    ------
    ValueError
        An entity specified in the config file is not recognized.

    """
    for piv_reg in _read_reg_file(file_path):
        if "debug" in kwargs:
            print(piv_reg)

        func = None
        if not piv_reg.src_module:
            raise ValueError(
                f"{piv_reg.src_config_entry} had no 'src_module' value in",
                piv_reg.src_config_path,
            )

        # try to import the module and retrieve the function
        src_module = importlib.import_module(piv_reg.src_module)
        if piv_reg.src_class:
            # if we need to get this from a class/object we need
            # to find or create one.
            func = _get_func_from_class(src_module, namespace, piv_reg)
            if not func:
                continue
        else:
            # not a class, just get the function from the module
            func = getattr(src_module, piv_reg.src_func_name, None)

        if not func:
            raise ValueError(
                f"Could not find function {piv_reg.src_func_name}",
                piv_reg.src_config_entry,
                piv_reg.src_config_path,
            )
        # create the pivot function and add to each entity
        if force_container:
            q_container = container
        else:
            q_container = piv_reg.entity_container_name or container
        _add_func_to_entities(func, piv_reg, q_container, **kwargs)


def add_unbound_pivot_function(
    func: Callable[[Any], Any],
    pivot_reg: PivotRegistration = None,
    container: str = "other",
    **kwargs,
):
    """
    Add a pivot function to entities.

    Parameters
    ----------
    func : Callable[[Any], Any]
        The function to add
    pivot_reg : PivotRegistration, optional
        Pivot registration object, by default None
    container : str, optional
        The name of the container into which the function
        should be added, by default "other"

    Other Parameters
    ----------------
    kwargs
        If `pivot_reg` is not supplied you can specify required
        pivot registration parameters via keyword arguments. You must
        specify `input_type` (str) and `entity_map` (dict of entity_name,
        entity_attribute pairs)

    See Also
    --------
    PivotRegistration

    """
    if pivot_reg is None:
        pivot_reg = PivotRegistration(**kwargs)
    _add_func_to_entities(func, piv_reg=pivot_reg, container=container, **kwargs)


def _read_reg_file(file_path: str):
    """Read the yaml file and return generator of PivotRegistrations."""
    with open(file_path) as f_handle:
        # use safe_load instead load
        pivot_regs = yaml.safe_load(f_handle)

    for entry_name, settings in pivot_regs.get("pivot_providers").items():
        try:
            yield PivotRegistration(
                src_config_path=file_path, src_config_entry=entry_name, **settings
            )
        except TypeError as err:
            raise MsticpyUserConfigError(
                "One or more missing fields found in pivot defintion.",
                f"Source file: {file_path}",
                title=f"Error importing pivot definition {entry_name}",
            ) from err


def _add_func_to_entities(func, piv_reg, container, **kwargs):
    """Create the pivot function and add to entities."""
    pivot_func = create_pivot_func(func, piv_reg)

    for entity_name in piv_reg.entity_map:
        entity = getattr(entities, entity_name, None)
        if not entity:
            raise ValueError(f"Unrecognized entity {entity_name}")
        query_container = getattr(entity, container, None)
        if not query_container:
            query_container = QueryContainer()
            setattr(entity, container, query_container)
        func_name = piv_reg.func_new_name or piv_reg.src_func_name
        setattr(query_container, func_name, pivot_func)

        if piv_reg.create_shortcut:
            setattr(entity, func_name, pivot_func)

        if "debug" in kwargs:
            print(
                entity_name,
                [func for func in dir(entity.other) if not func.startswith("_")],
            )


def _get_func_from_class(src_module, namespace, piv_reg):
    """Return function from class instance - created or found in namespace."""
    # If this is a class instance method, we need to have
    # an instance of the class
    src_class = getattr(src_module, piv_reg.src_class)
    src_obj = None
    # If a namespace was passed, look for an already-created
    # object of this type
    if namespace:
        src_obj = _last_instance_of_type(src_class, namespace)
    if not src_obj:
        try:
            src_obj = src_class()
        except Exception as err:  # pylint: disable=broad-except
            warnings.warn(
                f"Could not create instance of class {src_class.__name__}. "
                + f"Exception was {err}"
            )
            return None
    # get the function from the object
    return getattr(src_obj, piv_reg.src_func_name, None)


def _last_instance_of_type(var_type: Type, namespace: Dict[str, Any]):
    """Return the most recently created instance of type in namespace."""
    matches = [var for _, var in namespace.items() if isinstance(var, var_type)]
    if matches:
        return matches[-1]
    return None
