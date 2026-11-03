"""Internally derived affine metric branches on closed simplices (SPEC S13)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from flint import fmpq

from .failures import Failure, FailureKind, VerificationError
from .geometry import Simplex
from .graph import ConstantSelector, EdgePoint, Graph, PeakSelector, VertexPoint


def _error(code: str, message: str, *, malformed: bool = False) -> VerificationError:
    kind = FailureKind.REFUSED if malformed else FailureKind.INVALID_CERTIFICATE
    return VerificationError(Failure(kind, code, message))


def _scalar(value: object) -> fmpq:
    if type(value) is int:
        return fmpq(value)
    if isinstance(value, fmpq):
        return value
    raise _error(
        "distance_expression_scalar",
        "Expected an integer or FLINT rational",
        malformed=True,
    )


@dataclass(frozen=True, init=False)
class AffineExpression:
    """An exact ambient affine function; constructors copy and normalize inputs.

    These are internal expressions, not certificate-supplied polynomials.
    """

    coefficients: tuple[fmpq, ...]
    constant: fmpq

    def __init__(self, coefficients: object, constant: object) -> None:
        if not isinstance(coefficients, (list, tuple)):
            raise _error(
                "distance_expression_shape",
                "Expected a coefficient sequence",
                malformed=True,
            )
        object.__setattr__(
            self, "coefficients", tuple(_scalar(x) for x in coefficients)
        )
        object.__setattr__(self, "constant", _scalar(constant))

    def evaluate(self, point: object) -> fmpq:
        if not isinstance(point, (list, tuple)) or len(point) != len(self.coefficients):
            raise _error(
                "distance_expression_dimension",
                "Point dimension mismatch",
                malformed=True,
            )
        return self.constant + sum(
            (a * _scalar(x) for a, x in zip(self.coefficients, point, strict=True)),
            fmpq(0),
        )


@dataclass(frozen=True, init=False)
class EdgeExpression:
    """A closed root-edge chart, retained even when its coordinate is an endpoint."""

    edge: int
    coordinate: AffineExpression

    def __init__(self, edge: object, coordinate: object) -> None:
        if type(edge) is not int or edge < 0:
            raise _error(
                "distance_expression_edge",
                "Expected a nonnegative edge index",
                malformed=True,
            )
        if not isinstance(coordinate, AffineExpression):
            raise _error(
                "distance_expression_type",
                "Expected an affine coordinate",
                malformed=True,
            )

        object.__setattr__(self, "edge", edge)
        object.__setattr__(self, "coordinate", coordinate)


def _combine(
    left: AffineExpression, right: AffineExpression, sign: int = 1, constant: int = 0
) -> AffineExpression:
    return AffineExpression(
        tuple(
            a + sign * b
            for a, b in zip(left.coefficients, right.coefficients, strict=True)
        ),
        left.constant + sign * right.constant + constant,
    )


def _offset(point: EdgeExpression, endpoint: int) -> AffineExpression:
    if endpoint == 0:
        return point.coordinate
    return AffineExpression(
        tuple(-a for a in point.coordinate.coefficients), 1 - point.coordinate.constant
    )


type PointExpression = VertexPoint | EdgeExpression


def _validate_expression(graph: Graph, cell: Simplex, point: object) -> PointExpression:
    if isinstance(point, VertexPoint):
        if point.vertex not in graph.vertices:
            raise _error("reference_vertex", "Unknown constant vertex")
        return point
    if not isinstance(point, EdgeExpression):
        raise _error(
            "distance_expression_type",
            "Expected a vertex constant or edge expression",
            malformed=True,
        )
    if point.edge >= len(graph.edges):
        raise _error("reference_index", "Unknown expression edge")
    if len(point.coordinate.coefficients) != cell.ambient_dimension:
        raise _error(
            "distance_expression_dimension",
            "Affine coordinate dimension differs from the cell",
            malformed=True,
        )
    vertices = cell.vertices
    for j in range(vertices.ncols()):
        coordinates = tuple(vertices[i, j] for i in range(vertices.nrows()))
        if not 0 <= point.coordinate.evaluate(coordinates) <= 1:
            raise _error(
                "distance_expression_domain",
                "Affine coordinate leaves its closed edge at a cell vertex",
            )
    return point


def check_distance_branch(
    graph: object, cell: object, left: object, right: object, branch: object
) -> AffineExpression:
    """Derive and check the supplied metric branch on every cell vertex.

    Inputs are internally generated affine coordinates, never wire coefficients.
    Embedded simplices are supported; comparisons enforce their own root dimensions.
    """
    if not isinstance(graph, Graph) or not isinstance(cell, Simplex):
        raise _error(
            "distance_input_type",
            "Expected a validated graph and simplex",
            malformed=True,
        )
    left = _validate_expression(graph, cell, left)
    right = _validate_expression(graph, cell, right)
    same_edge = (
        isinstance(left, EdgeExpression)
        and isinstance(right, EdgeExpression)
        and left.edge == right.edge
    )
    if isinstance(left, VertexPoint) and isinstance(right, VertexPoint):
        routes = (
            AffineExpression(
                (fmpq(0),) * cell.ambient_dimension,
                fmpq(graph.vertex_distance(left.vertex, right.vertex)),
            ),
        )
    elif isinstance(left, EdgeExpression) and isinstance(right, EdgeExpression):
        if same_edge:
            routes = (
                _combine(left.coordinate, right.coordinate, -1),
                _combine(right.coordinate, left.coordinate, -1),
            )
        else:
            # First bit refers to the left argument; listed edge orientation is retained.
            routes = tuple(
                _combine(
                    _offset(left, a),
                    _offset(right, b),
                    constant=graph.vertex_distance(
                        graph.edges[left.edge][a], graph.edges[right.edge][b]
                    ),
                )
                for a in (0, 1)
                for b in (0, 1)
            )
    else:
        vertex, edge = (left, right) if isinstance(left, VertexPoint) else (right, left)
        assert isinstance(vertex, VertexPoint) and isinstance(edge, EdgeExpression)
        routes = tuple(
            _combine(
                _offset(edge, a),
                AffineExpression(
                    (fmpq(0),) * cell.ambient_dimension,
                    fmpq(
                        graph.vertex_distance(vertex.vertex, graph.edges[edge.edge][a])
                    ),
                ),
            )
            for a in (0, 1)
        )
    if type(branch) is not int:
        raise _error(
            "distance_branch_type", "Expected an integer branch number", malformed=True
        )
    if not 0 <= branch < len(routes):
        raise _error(
            "distance_branch", "Branch number is outside this distance type's range"
        )
    result = routes[branch]
    vertices = cell.vertices
    for j in range(vertices.ncols()):
        point = tuple(vertices[i, j] for i in range(vertices.nrows()))
        value = result.evaluate(point)
        # Same-edge distance is absolute value, never a minimum of signed routes.
        if (same_edge and value < 0) or (
            not same_edge and any(value > route.evaluate(point) for route in routes)
        ):
            raise _error(
                "distance_branch", "Branch fails a metric inequality at a cell vertex"
            )
    return result


def _dimension(value: object) -> int:
    if type(value) is not int or value < 0:
        raise _error(
            "distance_expression_dimension",
            "Expected a nonnegative ambient dimension",
            malformed=True,
        )
    return value


def _edge(graph: object, edge: object) -> int:
    if not isinstance(graph, Graph):
        raise _error(
            "distance_input_type", "Expected a validated graph", malformed=True
        )
    if type(edge) is not int:
        raise _error(
            "distance_expression_edge", "Expected an integer edge index", malformed=True
        )
    if not 0 <= edge < len(graph.edges):
        raise _error("reference_index", "Unknown expression edge")
    return edge


def coordinate_expression(dimension: object, coordinate: object) -> AffineExpression:
    """Construct the coordinate projection used by a report in its root chart."""
    dimension = _dimension(dimension)
    if type(coordinate) is not int:
        raise _error(
            "distance_expression_index",
            "Expected an integer coordinate index",
            malformed=True,
        )
    if not 0 <= coordinate < dimension:
        raise _error(
            "reference_index", "Coordinate index outside the ambient dimension"
        )
    return AffineExpression(
        tuple(fmpq(int(i == coordinate)) for i in range(dimension)), fmpq(0)
    )


def root_expressions(graph: object, edges: object) -> tuple[EdgeExpression, ...]:
    """Construct each variable report from an ordered root; preserve endpoint charts."""
    if type(edges) is not tuple or not edges:
        raise _error(
            "distance_root_shape",
            "Expected a nonempty immutable edge root",
            malformed=True,
        )
    return tuple(
        EdgeExpression(_edge(graph, edge), coordinate_expression(len(edges), i))
        for i, edge in enumerate(edges)
    )


def constant_expression(
    graph: object, point: object, dimension: object
) -> PointExpression:
    """Keep canonical vertices fixed, and interior constants in their edge chart."""
    dimension = _dimension(dimension)
    if not isinstance(graph, Graph):
        raise _error(
            "distance_input_type", "Expected a validated graph", malformed=True
        )
    if isinstance(point, VertexPoint):
        if point.vertex not in graph.vertices:
            raise _error("reference_vertex", "Unknown constant vertex")
        return point
    if isinstance(point, EdgePoint):
        return EdgeExpression(
            _edge(graph, point.edge),
            AffineExpression((fmpq(0),) * dimension, point.coordinate),
        )
    raise _error(
        "distance_expression_type",
        "Expected a canonical graph constant",
        malformed=True,
    )


def selector_expression(
    graph: object, selector: object, reports: object
) -> PointExpression:
    """Evaluate a selector on internally generated, possibly substituted reports.

    reports is in labeled agent order; each coordinate still lives in the original
    comparison's ambient space. No weights are inspected or selectors omitted.
    """
    if (
        type(reports) is not tuple
        or len(reports) < 2
        or any(not isinstance(p, EdgeExpression) for p in reports)
    ):
        raise _error(
            "distance_reports_shape",
            "Expected at least two immutable report expressions",
            malformed=True,
        )
    reports = cast(tuple[EdgeExpression, ...], reports)
    dimension = len(reports[0].coordinate.coefficients)
    for report in reports:
        _edge(graph, report.edge)
        if len(report.coordinate.coefficients) != dimension:
            raise _error(
                "distance_expression_dimension",
                "Report expressions have different ambient dimensions",
                malformed=True,
            )
    if isinstance(selector, PeakSelector):
        if selector.agent >= len(reports):
            raise _error("reference_index", "Unknown selector agent")
        return reports[selector.agent]
    if isinstance(selector, ConstantSelector):
        return constant_expression(graph, selector.point, dimension)
    raise _error(
        "distance_selector_type", "Expected a peak or constant selector", malformed=True
    )


@dataclass(frozen=True, init=False)
class DistanceTerm:
    """One ordered distance with no weight or supplied polynomial attached."""

    left: PointExpression
    right: PointExpression

    def __init__(self, left: object, right: object) -> None:
        if any(not isinstance(p, (VertexPoint, EdgeExpression)) for p in (left, right)):
            raise _error(
                "distance_expression_type",
                "Expected internally generated point expressions",
                malformed=True,
            )

        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)


def check_distance_terms(
    graph: object,
    cell: object,
    terms: object,
    branches: object,
    *,
    location: Mapping[str, object] | None = None,
) -> tuple[AffineExpression, ...]:
    """Check every ordered term with exactly one supplied branch, without filtering.

    The comparison layer generates the SP/APX order and supplies source context.
    This checker has no weights and cannot drop a zero-weight column.
    """
    _term_index = None
    try:
        if not isinstance(graph, Graph) or not isinstance(cell, Simplex):
            raise _error(
                "distance_input_type",
                "Expected a validated graph and simplex",
                malformed=True,
            )
        if (
            type(terms) is not tuple
            or any(not isinstance(term, DistanceTerm) for term in terms)
            or type(branches) is not tuple
        ):
            raise _error(
                "distance_terms_shape",
                "Expected immutable terms and branch numbers",
                malformed=True,
            )
        terms = cast(tuple[DistanceTerm, ...], terms)
        if len(branches) != len(terms):
            raise _error(
                "distance_branch_count",
                "Need exactly one branch per generated distance term",
            )
        result = []
        for _term_index, (term, branch) in enumerate(zip(terms, branches, strict=True)):
            result.append(
                check_distance_branch(graph, cell, term.left, term.right, branch)
            )
        return tuple(result)
    except VerificationError as error:
        context = dict(location) if location is not None else {}
        if _term_index is not None:
            context["term"] = _term_index
        failure = error.failure
        raise VerificationError(
            Failure(
                failure.kind, failure.code, failure.message, location=context or None
            )
        ) from error
