"""Exact simplex geometry in vertex-column coordinates (SPEC S07)."""

from dataclasses import dataclass, field
from math import factorial

from flint import fmpq, fmpq_mat

from .failures import Failure, FailureKind, VerificationError
from .graph import Graph, chart_coordinate


def _error(code: str, message: str, *, malformed: bool = False) -> VerificationError:
    kind = FailureKind.REFUSED if malformed else FailureKind.INVALID_CERTIFICATE
    return VerificationError(Failure(kind, code, message))


def _vector(value: object, dimension: int) -> tuple[fmpq, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != dimension:
        raise _error(
            "simplex_vector_shape", "Exact vector dimension mismatch", malformed=True
        )
    result = []
    for coordinate in value:
        if type(coordinate) is int:
            result.append(fmpq(coordinate))
        elif isinstance(coordinate, fmpq):
            result.append(coordinate)
        else:
            raise _error(
                "simplex_scalar_type",
                "Expected an integer or FLINT rational",
                malformed=True,
            )
    return tuple(result)


@dataclass(frozen=True, init=False)
class Simplex:
    """An affinely independent rational simplex; input columns are copied."""

    _columns: tuple[tuple[fmpq, ...], ...] = field(repr=False)
    ambient_dimension: int
    dimension: int

    def __init__(self, vertices: object) -> None:
        if not isinstance(vertices, fmpq_mat):
            raise _error(
                "simplex_vertices_type", "Expected an fmpq_mat", malformed=True
            )
        if vertices.ncols() < 1:
            raise _error("simplex_vertices_shape", "Need at least one vertex column")
        augmented = fmpq_mat(vertices.nrows() + 1, vertices.ncols())
        for j in range(vertices.ncols()):
            for i in range(vertices.nrows()):
                augmented[i, j] = vertices[i, j]
            augmented[vertices.nrows(), j] = 1
        if augmented.rank() != vertices.ncols():
            raise _error("simplex_affine_dependence", "Vertices are affinely dependent")
        object.__setattr__(self, "ambient_dimension", vertices.nrows())
        object.__setattr__(self, "dimension", vertices.ncols() - 1)
        object.__setattr__(
            self,
            "_columns",
            tuple(
                tuple(vertices[i, j] for i in range(vertices.nrows()))
                for j in range(vertices.ncols())
            ),
        )

    @property
    def vertices(self) -> fmpq_mat:
        result = fmpq_mat(self.ambient_dimension, self.dimension + 1)
        for j, column in enumerate(self._columns):
            for i, value in enumerate(column):
                result[i, j] = value
        return result

    def volume(self) -> fmpq:
        """Lebesgue volume in full ambient coordinates, including dimension zero."""
        if self.dimension != self.ambient_dimension:
            raise _error(
                "unsupported_embedded_volume",
                "Determinant volume requires a full-dimensional coordinate simplex",
                malformed=True,
            )
        edges = fmpq_mat(self.dimension, self.dimension)
        for j in range(self.dimension):
            for i in range(self.dimension):
                edges[i, j] = self._columns[j + 1][i] - self._columns[0][i]
        return abs(edges.det()) / factorial(self.dimension)

    def barycentric(self, point: object) -> tuple[fmpq, ...] | None:
        """Unique sum-one coordinates, or None if outside the affine hull.

        Coordinates may be negative. All ambient equations participate in the
        exact solve; a successful projection alone does not establish hull membership.
        """
        point = _vector(point, self.ambient_dimension)
        count = self.dimension + 1
        system = fmpq_mat(self.ambient_dimension + 1, count + 1)
        for j, column in enumerate(self._columns):
            for i, value in enumerate(column):
                system[i, j] = value
            system[self.ambient_dimension, j] = 1
        for i, value in enumerate(point):
            system[i, count] = value
        system[self.ambient_dimension, count] = 1
        reduced, rank = system.rref()
        # The vertex columns have full rank. A further pivot is inconsistency.
        if rank != count:
            return None
        return tuple(reduced[i, count] for i in range(count))

    def contains(self, point: object) -> bool:
        """Membership in the closed simplex, including all faces."""
        barycentric = self.barycentric(point)
        return barycentric is not None and all(x >= 0 for x in barycentric)

    def interpolate(self, values: object) -> AffineInterpolant:
        """Unique affine function on this hull matching the vertex values."""
        return AffineInterpolant(self, _vector(values, self.dimension + 1))

    def facets(self) -> tuple[Facet, ...]:
        """Nonempty codimension-one faces, in opposite-vertex order."""
        if self.dimension == 0:
            return ()
        return tuple(Facet(self, opposite) for opposite in range(self.dimension + 1))


@dataclass(frozen=True)
class AffineInterpolant:
    """An affine function restricted to a simplex's affine hull.

    Embedded hulls do not determine a unique ambient extension. Coefficients
    are exposed only when the hull is the whole ambient coordinate space.
    """

    simplex: Simplex
    values: tuple[fmpq, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.simplex, Simplex):
            raise _error("simplex_type", "Expected a Simplex", malformed=True)
        object.__setattr__(
            self, "values", _vector(self.values, self.simplex.dimension + 1)
        )

    def evaluate(self, point: object) -> fmpq:
        barycentric = self.simplex.barycentric(point)
        if barycentric is None:
            raise _error(
                "simplex_affine_hull", "Point lies outside interpolant's affine hull"
            )
        return sum(
            (a * b for a, b in zip(self.values, barycentric, strict=True)), fmpq(0)
        )

    def coefficients(self) -> tuple[tuple[fmpq, ...], fmpq]:
        """Return (linear coefficients, constant) for a full-dimensional hull."""
        if self.simplex.dimension != self.simplex.ambient_dimension:
            raise _error(
                "unsupported_ambient_extension",
                "Embedded interpolation has no unique ambient extension",
                malformed=True,
            )
        count = self.simplex.dimension + 1
        system = fmpq_mat(count, count)
        for j, column in enumerate(self.simplex._columns):
            for i, value in enumerate(column):
                system[j, i] = value
            system[j, count - 1] = 1
        rhs = fmpq_mat(count, 1)
        for j, value in enumerate(self.values):
            rhs[j, 0] = value
        solution = system.solve(rhs)
        return tuple(solution[i, 0] for i in range(count - 1)), solution[count - 1, 0]


@dataclass(frozen=True)
class Facet:
    """A facet with inward support equal to its opposite barycentric coordinate."""

    simplex: Simplex
    opposite: int

    def __post_init__(self) -> None:
        if not isinstance(self.simplex, Simplex):
            raise _error("simplex_type", "Expected a Simplex", malformed=True)
        if type(self.opposite) is not int:
            raise _error(
                "simplex_index_type", "Expected an integer index", malformed=True
            )
        if (
            self.simplex.dimension == 0
            or not 0 <= self.opposite <= self.simplex.dimension
        ):
            raise _error("simplex_facet_index", "No such nonempty facet")

    @property
    def vertex_indices(self) -> tuple[int, ...]:
        return tuple(j for j in range(self.simplex.dimension + 1) if j != self.opposite)

    def _support(self) -> AffineInterpolant:
        return self.simplex.interpolate(
            tuple(int(j == self.opposite) for j in range(self.simplex.dimension + 1))
        )

    def side(self, point: object) -> fmpq:
        """Signed exact support on the affine hull, positive inward."""
        return self._support().evaluate(point)

    def hyperplane(self) -> tuple[tuple[fmpq, ...], fmpq]:
        """Return normal, offset for h(x)=normal dot x-offset (full dimension)."""
        normal, constant = self._support().coefficients()
        return normal, -constant


def cube_simplex(vertices: object) -> Simplex:
    """Validate a full-dimensional simplex contained in its closed unit cube."""
    result = Simplex(vertices)
    if result.dimension != result.ambient_dimension:
        raise _error(
            "simplex_full_dimension", "Mechanism simplex must fill the root dimension"
        )
    if any(not 0 <= x <= 1 for column in result._columns for x in column):
        raise _error("simplex_out_of_box", "Simplex vertex lies outside the root cube")
    return result


def intrinsic_coordinates(
    graph: object, edges: object, point: object
) -> tuple[fmpq, ...]:
    """Convert a graph-product point in a checked ordered edge root.

    This boundary has no dependency on reader records or certificate files.
    Well-formed unresolved references and chart failures are certificate errors.
    """
    if not isinstance(graph, Graph):
        raise _error("simplex_graph_type", "Expected a validated Graph", malformed=True)
    if not isinstance(edges, (list, tuple)) or not edges:
        raise _error(
            "simplex_root_shape",
            "Expected a nonempty ordered edge tuple",
            malformed=True,
        )
    if not isinstance(point, (list, tuple)) or len(point) != len(edges):
        raise _error(
            "simplex_point_shape", "Point must match the root dimension", malformed=True
        )
    result = []
    for edge, coordinate in zip(edges, point, strict=True):
        try:
            result.append(chart_coordinate(graph, coordinate, edge))
        except VerificationError as error:
            code = error.failure.code
            if code == "graph_chart":
                raise _error(
                    "simplex_root_chart", "Vertex does not belong to the root chart"
                ) from error
            if code in {"reference_vertex", "reference_index"}:
                raise _error(code, error.failure.message) from error
            raise
    return tuple(result)


def simplex_in_root(graph: object, edges: object, points: object) -> Simplex:
    """Convert and validate one full-dimensional graph-root mechanism simplex."""
    if not isinstance(points, (list, tuple)) or not points:
        raise _error(
            "simplex_points_shape",
            "Expected a nonempty vertex sequence",
            malformed=True,
        )
    columns = tuple(intrinsic_coordinates(graph, edges, point) for point in points)
    dimension = len(columns[0])
    if len(columns) != dimension + 1:
        raise _error("simplex_full_dimension", "Need root dimension plus one vertices")
    vertices = fmpq_mat(dimension, len(columns))
    for j, column in enumerate(columns):
        for i, value in enumerate(column):
            vertices[i, j] = value
    return cube_simplex(vertices)
