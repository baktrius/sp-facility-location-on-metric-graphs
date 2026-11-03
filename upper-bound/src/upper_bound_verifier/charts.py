"""Exact gluing of locally conforming attribution meshes on graph products."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import product, zip_longest
from types import MappingProxyType
from typing import NoReturn

from .conformity import RootConformity, check_local_conformity
from .failures import Failure, FailureKind, VerificationError
from .graph import Graph, VertexPoint, parse_agent_count, point_in_chart
from .reader import (
    AttributionKey,
    AttributionSimplex,
    ProfileVertex,
    RootBlock,
    SourceLocation,
    attribution_root_keys,
)


@dataclass(frozen=True)
class ProductFace:
    """A fixed vertex or a whole fixed edge (array index) in each coordinate."""

    coordinates: tuple[VertexPoint | int, ...]

    @property
    def codimension(self) -> int:
        return sum(isinstance(x, VertexPoint) for x in self.coordinates)

    def to_data(self) -> list[dict[str, object]]:
        return [
            {"vertex": x.vertex} if isinstance(x, VertexPoint) else {"edge": x}
            for x in self.coordinates
        ]


@dataclass(frozen=True)
class FaceConformity:
    """All actual incident roots and their common maximal restricted ID sets."""

    roots: tuple[AttributionKey, ...]
    maximal_simplices: frozenset[frozenset[str]]


@dataclass(frozen=True)
class ChartConformity:
    """A global geometric attribution complex; no lottery admissibility claim."""

    roots: Mapping[AttributionKey, RootConformity]
    faces: Mapping[ProductFace, FaceConformity]


def check_chart_conformity(
    graph: Graph,
    agents: int,
    roots: Iterable[RootBlock],
    attribution_vertices: Mapping[str, ProfileVertex],
) -> ChartConformity:
    """Check complete decoded attribution input, local meshes and all seams.

    Root records must occur in the reader's canonical order. Recheck global
    profile injectivity, including unused vertices, and recompute S08/S09 for
    every root; no caller-asserted local validation is trusted. Wire syntax
    remains the BundleReader boundary. Weights are deliberately not checked.
    """
    agents = parse_agent_count(agents)

    def reject(
        code: str,
        message: str,
        location: SourceLocation | AttributionKey | None = None,
    ) -> NoReturn:
        raise VerificationError(
            Failure(
                FailureKind.INVALID_CERTIFICATE,
                code,
                message,
                None
                if location is None
                else location.to_dict()
                if isinstance(location, SourceLocation)
                else {"root": location.to_data()},
            )
        )

    profiles = set()
    # Membership performs the reviewed canonical point/reference checks even
    # if this arbitrary first chart does not contain the point.
    for identifier, vertex in attribution_vertices.items():
        if not isinstance(identifier, str) or not identifier or vertex.id != identifier:
            reject(
                "chart_vertex_id",
                "Global mapping keys must equal nonempty vertex IDs",
                vertex.location,
            )
        if type(vertex.point) is not tuple or len(vertex.point) != agents:
            reject(
                "chart_profile_dimension",
                "Global profiles must have exactly n coordinates",
                vertex.location,
            )
        for point in vertex.point:
            try:
                point_in_chart(graph, point, 0)
            except VerificationError as error:
                raise VerificationError(
                    replace(
                        error.failure,
                        kind=FailureKind.INVALID_CERTIFICATE
                        if error.failure.code in {"reference_vertex", "reference_index"}
                        else error.failure.kind,
                        location=vertex.location.to_dict(),
                    )
                ) from error
        if vertex.point in profiles:
            reject(
                "chart_duplicate_profile",
                "Global profiles must have one canonical ID",
                vertex.location,
            )
        profiles.add(vertex.point)

    checked = {}
    cell_ids = set()
    for expected, root in zip_longest(attribution_root_keys(graph, agents), roots):
        if root is None:
            reject(
                "chart_root_sequence", f"Missing attribution root {expected}", expected
            )
        loc = replace(root.location, root=root.key)
        if (
            not isinstance(root.key, AttributionKey)
            or type(root.key.edges) is not tuple
            or any(type(edge) is not int for edge in root.key.edges)
            or root.key != expected
        ):
            reject(
                "chart_root_sequence",
                "Attribution roots must match the complete canonical sequence",
                loc,
            )
        if root.vertices:
            reject(
                "chart_local_vertices",
                "Attribution roots use only the global vertex table",
                loc,
            )
        for cell in root.simplices:
            cell_loc = replace(cell.location, root=root.key, cell=cell.id)
            if not isinstance(cell, AttributionSimplex):
                reject(
                    "chart_simplex_kind",
                    "Attribution roots require attribution simplices",
                    cell_loc,
                )
            if not isinstance(cell.id, str) or not cell.id or cell.id in cell_ids:
                reject(
                    "chart_simplex_id",
                    "Attribution simplex IDs must be globally distinct",
                    cell_loc,
                )
            cell_ids.add(cell.id)
        checked[root.key] = check_local_conformity(graph, root, attribution_vertices)

    incidence = {
        vertex: tuple(i for i, edge in enumerate(graph.edges) if vertex in edge)
        for vertex in graph.vertices
    }
    coordinates = (*map(VertexPoint, graph.vertices), *range(len(graph.edges)))
    faces = {}
    # Explicitly enumerate every positive codimension, including leaf faces.
    for choices in product(coordinates, repeat=agents):
        face = ProductFace(choices)
        if face.codimension == 0:
            continue
        incident = tuple(
            AttributionKey(edges)
            for edges in product(
                *(
                    incidence[x.vertex] if isinstance(x, VertexPoint) else (x,)
                    for x in choices
                )
            )
        )
        common = None
        for key in incident:
            root = checked[key].coverage.root
            subsets = set()
            for cell in root.simplices:
                subset = frozenset(
                    identifier
                    for identifier in cell.vertices
                    if all(
                        point == coordinate
                        if isinstance(coordinate, VertexPoint)
                        else point_in_chart(graph, point, coordinate)
                        for point, coordinate in zip(
                            attribution_vertices[identifier].point, choices, strict=True
                        )
                    )
                )
                if subset:
                    subsets.add(subset)
            # Every restricted simplex contributes all its faces. Maximal sets
            # therefore specify the entire complex; discard contained subsets.
            maximal = frozenset(s for s in subsets if not any(s < t for t in subsets))
            if common is None:
                common = maximal
            elif maximal != common:
                reject(
                    "chart_face_mismatch",
                    f"Incident roots {incident[0].to_data()} and {key.to_data()} induce different complexes on face {face.to_data()}",
                    replace(root.location, root=key),
                )
        assert common is not None  # Connected graph: every vertex has an edge.
        faces[face] = FaceConformity(incident, common)
    return ChartConformity(MappingProxyType(checked), MappingProxyType(faces))
