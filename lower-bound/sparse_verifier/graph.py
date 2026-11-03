"""The embedded graph, read and validated from its own document.

Invariant: a `Graph` is connected, simple, bipartite and unit-edged, with its
vertices in document order. Edges have no weights because the document has
nowhere to put one, and the graph declares no symmetries because a declaration
is refused before it is read here. A document that is not shaped like a graph
raises `MalformedError`; one that is shaped like a graph outside the problem raises
`GraphInvalidError`, naming the fault.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from sparse_verifier.errors import MalformedError

VERTICES = "vertices"
EDGES = "edges"
SYMMETRIES = "symmetries"
_KEYS = frozenset({VERTICES, EDGES, SYMMETRIES})
_MIN_VERTICES = 2
_EDGE_ARITY = 2


class GraphInvalidError(ValueError):
    """The document is a graph, but not a connected simple bipartite one."""


@dataclass(frozen=True)
class Graph:
    """A validated explicit graph.

    Attributes:
        labels (tuple[str, ...]): The vertex labels, whose order numbers them.
        edges (tuple[tuple[int, int], ...]): The edges as index pairs.

    """

    labels: tuple[str, ...]
    edges: tuple[tuple[int, int], ...]


def read_graph(document: object) -> Graph:
    """Validate a decoded graph document.

    Args:
        document (object): The `graph` of a certificate's identity.

    Returns:
        Graph: The validated graph.

    Raises:
        MalformedError: If the document is not shaped like a graph.
        GraphInvalidError: If it is a graph outside the problem.

    """
    if not isinstance(document, dict):
        msg = "the graph is not a JSON object"
        raise MalformedError(msg)
    for key in (VERTICES, EDGES):
        if key not in document:
            msg = f"the graph has no {key!r} key"
            raise MalformedError(msg)
    extra = sorted(set(document) - _KEYS)
    if extra:
        msg = f"the graph has an unexpected key {extra[0]!r}"
        raise GraphInvalidError(msg)
    labels = _labels(document[VERTICES])
    edges = _edges(document[EDGES], labels)
    _check_connected_and_bipartite(len(labels), edges)
    return Graph(labels, edges)


def _labels(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        msg = "the graph's vertices are not a list of string labels"
        raise MalformedError(msg)
    if len(set(value)) != len(value):
        msg = "the graph repeats a vertex label"
        raise GraphInvalidError(msg)
    if len(value) < _MIN_VERTICES:
        msg = f"the graph needs at least {_MIN_VERTICES} vertices, got {len(value)}"
        raise GraphInvalidError(msg)
    return tuple(value)


def _edges(value: object, labels: tuple[str, ...]) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        msg = "the graph's edges are not a list"
        raise MalformedError(msg)
    index = {label: i for i, label in enumerate(labels)}
    seen: set[frozenset[int]] = set()
    edges: list[tuple[int, int]] = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != _EDGE_ARITY
            or not all(isinstance(end, str) for end in item)
        ):
            msg = f"edge {item!r} is not a pair of labels"
            raise MalformedError(msg)
        for end in item:
            if end not in index:
                msg = f"edge {item!r} names an unknown vertex {end!r}"
                raise GraphInvalidError(msg)
        u, v = index[item[0]], index[item[1]]
        if u == v:
            msg = f"edge {item!r} is a self-loop"
            raise GraphInvalidError(msg)
        if frozenset((u, v)) in seen:
            msg = f"edge {item!r} repeats an earlier edge"
            raise GraphInvalidError(msg)
        seen.add(frozenset((u, v)))
        edges.append((u, v))
    return tuple(edges)


def _check_connected_and_bipartite(
    count: int, edges: tuple[tuple[int, int], ...]
) -> None:
    neighbours: list[list[int]] = [[] for _ in range(count)]
    for u, v in edges:
        neighbours[u].append(v)
        neighbours[v].append(u)
    hops: list[int | None] = [None] * count
    hops[0] = 0
    queue = deque([0])
    while queue:
        u = queue.popleft()
        for v in neighbours[u]:
            if hops[v] is None:
                hops[v] = (hops[u] or 0) + 1
                queue.append(v)
    if any(hop is None for hop in hops):
        msg = "the graph is disconnected"
        raise GraphInvalidError(msg)
    for u, v in edges:
        if hops[u] == hops[v]:
            msg = "the graph is not bipartite: an edge closes an odd cycle"
            raise GraphInvalidError(msg)
