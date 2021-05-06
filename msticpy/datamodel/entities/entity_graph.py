# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""Entity Graph classes."""
from typing import Any, Dict, Set, Optional

from ..._version import VERSION

__version__ = VERSION
__author__ = "Ian Hellen"


class Node:
    """Entity node."""

    def __init__(self):
        """Initialize the node."""
        self.edges: Set["Edge"] = set()

    def add_edge(self, target: "Node", edge_attrs: Optional[Dict[str, Any]] = None):
        """
        Add an edge between self and target.

        Parameters
        ----------
        target : Node
            Target node.
        edge_attrs : Optional[Dict[str, Any]], optional
            Attributes to assign to new edge, by default None

        """
        edge = Edge(self, target, edge_attrs) if edge_attrs else Edge(self, target)
        if not self.has_edge(target):
            self.edges.add(edge)
        if not target.has_edge(self):
            target.edges.add(edge)

    def has_edge(self, other):
        """Return True if node has an edge with `other`."""
        return any(edge for edge in self.edges if other in (edge.target, edge.source))


class Edge:
    """Entity edge class."""

    def __init__(self, source: Node, target: Node, attrs: Dict[str, Any] = None):
        """
        Create a new edge between `source` and `target`.

        Parameters
        ----------
        source : Node
            Source node.
        target : Node
            Target node.
        attrs : Dict[str, Any], optional
            Dictionary of name/value edge attributes, by default None

        """
        self.source: Node = source
        self.target: Node = target

        self.attrs: Dict[str, Any] = attrs or {}

    def add_attr(self, name: str, value: Any):
        """Add an edge attribute."""
        self.attrs[name] = value

    def __str__(self):
        """Return string representation of edge."""
        return self.attrs.get("name", "unnamed-edge")

    def __repr__(self):
        """Return full repr of edge."""
        other_attrs = [
            f"{name}='{val}'" for name, val in self.attrs.items() if name != "name"
        ]
        if not other_attrs:
            return f"Edge(name={str(self)}"
        return f"Edge(name={str(self)}, {', '.join(other_attrs)}"
