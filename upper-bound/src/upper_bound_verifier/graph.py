"""Validated unit metric graphs, canonical points and labeled selectors.

Wire parsers accept decoded JSON data. JSON token and duplicate-key checks
belong to the certificate reader. No asserted metric data is accepted.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import NoReturn, cast

from flint import fmpq

from .exact import format_rational, parse_rational
from .failures import Failure, FailureKind, VerificationError


def _reject(code: str, message: str) -> NoReturn:
    raise VerificationError(Failure(FailureKind.REFUSED, code, message))


def _label(value: object) -> str:
    if type(value) is not str:
        _reject("schema_label", "Expected a string vertex label")
    return value


def _index(value: object, size: int) -> int:
    if type(value) is not int:
        _reject("schema_index", "Expected a JSON integer index")
    if not 0 <= value < size:
        _reject("reference_index", "Index is outside the declared range")
    return value


def _object(
    value: object, required: set[str], optional: set[str] | frozenset[str] = frozenset()
) -> dict[str, object]:
    if type(value) is not dict or not required <= value.keys():
        _reject("schema_fields", "Expected an object with all required fields")
    if value.keys() - required - optional:
        _reject("schema_fields", "Unknown object field")
    return cast(dict[str, object], value)


@dataclass(frozen=True)
class Graph:
    """Immutable ordered graph with distances recomputed from unit edges."""

    vertices: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    vertex_distances: tuple[tuple[int, ...], ...] = field(init=False)

    def __post_init__(self) -> None:
        if type(self.vertices) is not tuple or len(self.vertices) < 2:
            _reject("graph_vertices", "Need at least two distinct vertices")
        for vertex in self.vertices:
            _label(vertex)
        if len(set(self.vertices)) != len(self.vertices):
            _reject("graph_vertices", "Duplicate vertex label")
        if type(self.edges) is not tuple:
            _reject("graph_edges", "Expected immutable edge pairs")
        adjacency: dict[str, list[str]] = {v: [] for v in self.vertices}
        seen: set[frozenset[str]] = set()
        for edge in self.edges:
            if type(edge) is not tuple or len(edge) != 2:
                _reject("graph_edges", "Each edge needs exactly two endpoints")
            left, right = (_label(v) for v in edge)
            if left not in adjacency or right not in adjacency:
                _reject("graph_endpoint", "Edge endpoint is not a declared vertex")
            if left == right:
                _reject("graph_loop", "Self-loops are forbidden")
            key = frozenset(edge)
            if key in seen:
                _reject("graph_duplicate_edge", "Repeated undirected edge")
            seen.add(key)
            adjacency[left].append(right)
            adjacency[right].append(left)
        colors = {self.vertices[0]: 0}
        queue = deque(colors)
        while queue:
            vertex = queue.popleft()
            for neighbor in adjacency[vertex]:
                if neighbor not in colors:
                    colors[neighbor] = 1 - colors[vertex]
                    queue.append(neighbor)
                elif colors[neighbor] == colors[vertex]:
                    _reject("graph_bipartite", "Graph is not bipartite")
        if len(colors) != len(self.vertices):
            _reject("graph_connected", "Graph is not connected")
        rows = []
        for start in self.vertices:
            distances = {start: 0}
            queue = deque([start])
            while queue:
                vertex = queue.popleft()
                for neighbor in adjacency[vertex]:
                    if neighbor not in distances:
                        distances[neighbor] = distances[vertex] + 1
                        queue.append(neighbor)
            rows.append(tuple(distances[v] for v in self.vertices))
        object.__setattr__(self, "vertex_distances", tuple(rows))

    def vertex_distance(self, left: str, right: str) -> int:
        """Exact unweighted shortest-path distance between declared vertices."""
        left, right = _label(left), _label(right)
        if left not in self.vertices or right not in self.vertices:
            _reject("reference_vertex", "Unknown vertex label")
        return self.vertex_distances[self.vertices.index(left)][
            self.vertices.index(right)
        ]

    def degree(self, vertex: str) -> int:
        """Degree of a declared vertex, independent of edge orientation."""
        vertex = _label(vertex)
        if vertex not in self.vertices:
            _reject("reference_vertex", "Unknown vertex label")
        return sum(vertex in edge for edge in self.edges)


def parse_graph(value: object) -> Graph:
    """Parse SCHEMA's connected simple bipartite unit-edge graph."""
    data = _object(value, {"vertices", "edges"}, {"symmetries"})
    if "symmetries" in data:
        if type(data["symmetries"]) is not list:
            _reject("schema_symmetries", "Symmetries must be a JSON array")
        if data["symmetries"]:
            _reject("unsupported_symmetries", "Nonempty symmetries are unsupported")
    if type(data["vertices"]) is not list or type(data["edges"]) is not list:
        _reject("schema_graph", "Vertices and edges must be JSON arrays")
    edges = []
    for edge in data["edges"]:
        if type(edge) is not list or len(edge) != 2:
            _reject("schema_edge", "Each edge must be a two-element JSON array")
        edges.append((_label(edge[0]), _label(edge[1])))
    return Graph(tuple(_label(v) for v in data["vertices"]), tuple(edges))


@dataclass(frozen=True)
class VertexPoint:
    vertex: str

    def __post_init__(self) -> None:
        _label(self.vertex)


@dataclass(frozen=True)
class EdgePoint:
    edge: int
    coordinate: fmpq

    def __post_init__(self) -> None:
        if type(self.edge) is not int or self.edge < 0:
            _reject("schema_index", "Expected a nonnegative integer edge index")
        if not isinstance(self.coordinate, fmpq) or not 0 < self.coordinate < 1:
            _reject(
                "schema_point", "Edge points require a strict interior FLINT rational"
            )


type GraphPoint = VertexPoint | EdgePoint


def _check_point(graph: Graph, point: GraphPoint) -> None:
    if isinstance(point, VertexPoint):
        if point.vertex not in graph.vertices:
            _reject("reference_vertex", "Unknown vertex label")
    elif isinstance(point, EdgePoint):
        _index(point.edge, len(graph.edges))
    else:
        _reject("schema_point", "Expected a canonical graph point")


def parse_point(graph: Graph, value: object) -> GraphPoint:
    """Parse canonical wire form; edge coordinates 0 and 1 are rejected."""
    if type(value) is dict and "vertex" in value:
        data = _object(value, {"vertex"})
        point = VertexPoint(_label(data["vertex"]))
    else:
        data = _object(value, {"edge", "coordinate"})
        point = EdgePoint(
            _index(data["edge"], len(graph.edges)), parse_rational(data["coordinate"])
        )
    _check_point(graph, point)
    return point


def point_to_data(point: GraphPoint) -> dict[str, object]:
    """Encode an internal canonical point with normalized rational strings."""
    if isinstance(point, VertexPoint):
        return {"vertex": point.vertex}
    if isinstance(point, EdgePoint):
        return {"edge": point.edge, "coordinate": format_rational(point.coordinate)}
    _reject("schema_point", "Expected a canonical graph point")


def point_from_chart(graph: Graph, edge: int, coordinate: int | fmpq) -> GraphPoint:
    """Convert an internal closed-chart coordinate to canonical identity."""
    edge = _index(edge, len(graph.edges))
    if type(coordinate) is int:
        coordinate = fmpq(coordinate)
    if not isinstance(coordinate, fmpq) or not 0 <= coordinate <= 1:
        _reject("schema_coordinate", "Expected an exact coordinate in [0,1]")
    # All incident charts identify an endpoint by its single graph label.
    if coordinate == 0 or coordinate == 1:
        return VertexPoint(graph.edges[edge][int(coordinate)])
    return EdgePoint(edge, coordinate)


def point_in_chart(graph: Graph, point: GraphPoint, edge: int) -> bool:
    """Whether a canonical point lies in this closed edge chart."""
    _check_point(graph, point)
    edge = _index(edge, len(graph.edges))
    if isinstance(point, VertexPoint):
        return point.vertex in graph.edges[edge]
    return point.edge == edge


def chart_coordinate(graph: Graph, point: GraphPoint, edge: int) -> fmpq:
    """Return the exact coordinate, refusing points outside this chart."""
    if not point_in_chart(graph, point, edge):
        _reject("graph_chart", "Point does not belong to the declared edge chart")
    if isinstance(point, VertexPoint):
        return fmpq(graph.edges[edge].index(point.vertex))
    return point.coordinate


def point_distance(graph: Graph, left: GraphPoint, right: GraphPoint) -> fmpq:
    """Evaluate the continuous graph metric directly, without polynomials."""
    _check_point(graph, left)
    _check_point(graph, right)
    if isinstance(left, VertexPoint) and isinstance(right, VertexPoint):
        return fmpq(graph.vertex_distance(left.vertex, right.vertex))
    if isinstance(left, EdgePoint) and isinstance(right, EdgePoint):
        if left.edge == right.edge:
            # Unit edges guarantee that no detour beats the direct segment.
            return abs(left.coordinate - right.coordinate)
        left_endpoints, right_endpoints = (
            graph.edges[left.edge],
            graph.edges[right.edge],
        )
        left_offsets = (left.coordinate, 1 - left.coordinate)
        right_offsets = (right.coordinate, 1 - right.coordinate)
        return min(
            left_offsets[a]
            + graph.vertex_distance(left_endpoints[a], right_endpoints[b])
            + right_offsets[b]
            for a in (0, 1)
            for b in (0, 1)
        )
    if isinstance(left, EdgePoint):
        left, right = right, left
    assert isinstance(left, VertexPoint) and isinstance(right, EdgePoint)
    first, second = graph.edges[right.edge]
    return min(
        graph.vertex_distance(left.vertex, first) + right.coordinate,
        graph.vertex_distance(left.vertex, second) + 1 - right.coordinate,
    )


def parse_agent_count(value: object) -> int:
    """Validate a JSON integer count for at least two labeled agents."""
    if type(value) is not int or value < 2:
        _reject("schema_agents", "Agent count must be a JSON integer at least two")
    return value


@dataclass(frozen=True)
class PeakSelector:
    agent: int

    def __post_init__(self) -> None:
        if type(self.agent) is not int or self.agent < 0:
            _reject("schema_index", "Expected a nonnegative integer agent index")


@dataclass(frozen=True)
class ConstantSelector:
    point: GraphPoint

    def __post_init__(self) -> None:
        if not isinstance(self.point, (VertexPoint, EdgePoint)):
            _reject("schema_point", "Constant requires a canonical graph point")


type Selector = PeakSelector | ConstantSelector


def parse_selectors(graph: Graph, value: object, agents: int) -> tuple[Selector, ...]:
    """Validate a nonempty ordered family with distinct canonical descriptions."""
    agents = parse_agent_count(agents)
    if type(value) is not list or not value:
        _reject("schema_selectors", "Expected a nonempty JSON selector array")
    selectors: list[Selector] = []
    for item in value:
        item = _object(item, {"kind"}, {"agent", "point"})
        if item["kind"] == "peak":
            data = _object(item, {"kind", "agent"})
            selector = PeakSelector(_index(data["agent"], agents))
        elif item["kind"] == "constant":
            data = _object(item, {"kind", "point"})
            selector = ConstantSelector(parse_point(graph, data["point"]))
        else:
            _reject("schema_selector", "Unknown selector kind")
        if selector in selectors:
            _reject("schema_duplicate_selector", "Duplicate canonical selector")
        selectors.append(selector)
    return tuple(selectors)


def parse_profile(graph: Graph, value: object, agents: int) -> tuple[GraphPoint, ...]:
    """Parse exactly n graph points, retaining the labeled agent order."""
    agents = parse_agent_count(agents)
    if type(value) is not list or len(value) != agents:
        _reject("schema_profile", "Expected a JSON point array of length n")
    return tuple(parse_point(graph, point) for point in value)


def evaluate_selector(
    graph: Graph, selector: Selector, profile: tuple[GraphPoint, ...]
) -> GraphPoint:
    """Evaluate a peak or constant on a labeled profile using this graph."""
    if type(profile) is not tuple:
        _reject("schema_profile", "Expected an immutable labeled profile")
    parse_agent_count(len(profile))
    for point in profile:
        _check_point(graph, point)
    if isinstance(selector, PeakSelector):
        return profile[_index(selector.agent, len(profile))]
    if isinstance(selector, ConstantSelector):
        _check_point(graph, selector.point)
        return selector.point
    _reject("schema_selector", "Expected a peak or constant selector")
