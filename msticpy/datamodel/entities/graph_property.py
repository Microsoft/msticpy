# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Entity graph property."""
from typing import Union

from ..._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"

# flake8: noqa: F821
# "Entity" cannot be imported due to circular reference


# Future - will replace entity graph creation with property factory
def graph_property(
    name: str, prop_type: Union[type, str], edge_name: str = None
) -> property:
    """Property factory for graph_property."""
    storage_name = f"_{name}"
    edge_attrs = {"name": edge_name or name}
    prop_doc = f"Get, set or delete {name} property."
    if not isinstance(prop_type, type) or not prop_type == "self":
        raise TypeError(
            f"{prop_type} is not resolvable.",
            "'prop_type' must be a type of Entity or the string 'self'",
        )

    def prop_getter(self: "Entity") -> "Entity":  # type: ignore
        """Return property value."""
        return getattr(self, storage_name, None)

    def prop_setter(self: "Entity", value: "Entity"):  # type: ignore
        """Set property value and add graph edge."""
        nonlocal prop_type
        if prop_type == "self":
            prop_type = self.__class__
        if not isinstance(prop_type, type) or not isinstance(value, prop_type):
            raise TypeError(
                f"Cannot assign {type(value)} to property {name}.",
                f"Property must be of type {prop_type}",
            )
        if hasattr(self, storage_name):
            delattr(self, storage_name)
            for edge in self.edges:
                if edge.attrs.get("name") == name:
                    self.edges.remove(edge)
                    break

        setattr(self, storage_name, value)
        self.add_edge(target=value, edge_attrs=edge_attrs)

    def prop_del(self):
        """Property deleter."""
        if not hasattr(self, storage_name):
            return
        for edge in self.edges:
            if edge.attrs.get("name") == name:
                self.edges.remove(edge)
                break
        delattr(self, storage_name)

    return property(prop_getter, prop_setter, prop_del, prop_doc)
