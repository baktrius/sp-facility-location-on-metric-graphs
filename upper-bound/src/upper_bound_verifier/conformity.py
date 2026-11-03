"""Exact facet pairing for attribution meshes inside one covered root cube."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NoReturn

from .coverage import RootCoverage, check_root_coverage
from .failures import Failure, FailureKind, VerificationError
from .graph import Graph
from .reader import AttributionKey, ProfileVertex, RootBlock


@dataclass(frozen=True)
class FacetIncidence:
    """Original cell and its opposite vertex index (in reader vertex order)."""

    cell: str
    opposite: int


@dataclass(frozen=True)
class RootConformity:
    """One covered geometric triangulation; no cross-root or lottery checks."""

    coverage: RootCoverage
    facets: Mapping[tuple[str, ...], tuple[FacetIncidence, ...]]
    boundary_facets: frozenset[tuple[str, ...]]


def check_local_conformity(
    graph: Graph, root: RootBlock, attribution_vertices: Mapping[str, ProfileVertex]
) -> RootConformity:
    """Check S08 then S09 on decoded attribution records and global vertices.

    Comparison meshes use check_root_coverage alone. This public boundary
    recomputes coverage rather than accepting caller-asserted coverage evidence.
    """
    if not isinstance(root.key, AttributionKey):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "conformity_root_kind",
                "Local conformity applies only to attribution roots",
                replace(root.location, root=root.key).to_dict(),
            )
        )
    coverage = check_root_coverage(graph, root, attribution_vertices)
    records = {cell.id: cell for cell in root.simplices}
    incidences: dict[tuple[str, ...], list[FacetIncidence]] = {}
    for cell in root.simplices:
        for facet in coverage.simplices[cell.id].facets():
            key = tuple(sorted(cell.vertices[j] for j in facet.vertex_indices))
            incidences.setdefault(key, []).append(
                FacetIncidence(cell.id, facet.opposite)
            )

    def reject(code: str, message: str, incidence: FacetIncidence) -> NoReturn:
        location = replace(
            records[incidence.cell].location, root=root.key, cell=incidence.cell
        )
        raise VerificationError(
            Failure(FailureKind.INVALID_CERTIFICATE, code, message, location.to_dict())
        )

    boundary = set()
    for key, partners in incidences.items():
        first = partners[0]
        shape = coverage.simplices[first.cell]
        facet = shape.facets()[first.opposite]
        matrix = shape.vertices
        # All facet vertices, on ONE actual cube hyperplane. Vertices merely
        # lying somewhere on the cube boundary do not make a boundary facet.
        on_boundary = any(
            all(matrix[axis, j] == value for j in facet.vertex_indices)
            for axis in range(shape.dimension)
            for value in (0, 1)
        )
        if on_boundary:
            if len(partners) != 1:
                reject(
                    "conformity_boundary_incidence",
                    "Cube-boundary facet requires exactly one incidence",
                    first,
                )
            boundary.add(key)
            continue
        if len(partners) != 2:
            reject(
                "conformity_internal_incidence",
                "Internal facet requires exactly two incidences",
                first,
            )
        second = partners[1]
        other = coverage.simplices[second.cell]
        other_facet = other.facets()[second.opposite]
        other_matrix = other.vertices
        # Global IDs resolve from one table, so equality of the ID sets already
        # gives identical vertices. Check the actual coordinate sets as well.
        points = {
            tuple(matrix[i, j] for i in range(shape.dimension))
            for j in facet.vertex_indices
        }
        other_points = {
            tuple(other_matrix[i, j] for i in range(other.dimension))
            for j in other_facet.vertex_indices
        }
        if points != other_points:
            reject(
                "conformity_facet_geometry",
                "Paired facets must have identical geometry",
                first,
            )
        opposite = tuple(
            other_matrix[i, second.opposite] for i in range(other.dimension)
        )
        # Facet.side is its own opposite barycentric coordinate: positive in
        # the first cell. Its partner must therefore have strictly negative side.
        if facet.side(opposite) >= 0:
            reject(
                "conformity_opposite_side",
                "Partner opposite vertices must lie on opposite sides",
                first,
            )
    return RootConformity(
        coverage,
        MappingProxyType({key: tuple(value) for key, value in incidences.items()}),
        frozenset(boundary),
    )
