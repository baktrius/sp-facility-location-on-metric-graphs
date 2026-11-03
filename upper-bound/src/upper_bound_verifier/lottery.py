"""Regional probability and whole-face lottery admissibility (SPEC S11)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import combinations
from types import MappingProxyType

from flint import fmpq

from .charts import ChartConformity, check_chart_conformity
from .failures import Failure, FailureKind, VerificationError
from .graph import Graph, GraphPoint, Selector, VertexPoint, evaluate_selector
from .reader import AttributionSimplex, ProfileVertex, RootBlock


@dataclass(frozen=True)
class AdmissibleLottery:
    """Validated S08-S11 data for later comparisons, without an SP/APX claim.

    Evidence is produced by check_lottery_admissibility; constructing this
    record directly does not perform validation.
    """

    graph: Graph
    agents: int
    selectors: tuple[Selector, ...]
    geometry: ChartConformity
    regions: Mapping[str, AttributionSimplex]
    vertices: Mapping[str, ProfileVertex]


def check_lottery_admissibility(
    graph: Graph,
    agents: int,
    selectors: tuple[Selector, ...],
    roots: Iterable[RootBlock],
    attribution_vertices: Mapping[str, ProfileVertex],
) -> AdmissibleLottery:
    """Recompute global conformity, then validate all regional lottery data."""
    vertices = MappingProxyType(dict(attribution_vertices))
    geometry = check_chart_conformity(graph, agents, roots, vertices)
    if type(selectors) is not tuple or not selectors:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "schema_selectors",
                "Expected a nonempty immutable decoded selector family",
            )
        )
    profile = (VertexPoint(graph.vertices[0]),) * agents
    seen = set()
    for selector in selectors:
        try:
            evaluate_selector(graph, selector, profile)
        except VerificationError as error:
            raise VerificationError(
                replace(
                    error.failure,
                    kind=FailureKind.INVALID_CERTIFICATE
                    if error.failure.code in {"reference_vertex", "reference_index"}
                    else error.failure.kind,
                )
            ) from error
        if selector in seen:
            raise VerificationError(
                Failure(
                    FailureKind.REFUSED,
                    "schema_duplicate_selector",
                    "Duplicate canonical selector",
                )
            )
        seen.add(selector)
    regions = {}
    locations = {}
    for key, checked in geometry.roots.items():
        for cell in checked.coverage.root.simplices:
            assert isinstance(cell, AttributionSimplex)
            location = replace(cell.location, root=key, cell=cell.id).to_dict()
            if (
                type(cell.weights) is not tuple
                or len(cell.weights) != len(cell.vertices)
                or any(
                    type(row) is not tuple or len(row) != len(selectors)
                    for row in cell.weights
                )
            ):
                raise VerificationError(
                    Failure(
                        FailureKind.INVALID_CERTIFICATE,
                        "probability_shape",
                        "Need one regional row per vertex and column per selector",
                        location,
                    )
                )
            if any(
                not isinstance(weight, fmpq) for row in cell.weights for weight in row
            ):
                raise VerificationError(
                    Failure(
                        FailureKind.REFUSED,
                        "probability_exact_type",
                        "Decoded regional weights must be FLINT rationals",
                        location,
                    )
                )
            for row in cell.weights:
                if any(weight < 0 for weight in row):
                    raise VerificationError(
                        Failure(
                            FailureKind.INVALID_CERTIFICATE,
                            "probability_negative",
                            "Regional selector weights must be nonnegative",
                            location,
                        )
                    )
                if sum(row, fmpq(0)) != 1:
                    raise VerificationError(
                        Failure(
                            FailureKind.INVALID_CERTIFICATE,
                            "probability_normalization",
                            "Regional selector weights must sum to one",
                            location,
                        )
                    )
            regions[cell.id] = cell
            locations[cell.id] = location
    # G3/G4 make the common global IDs precisely the shared simplex face.
    # Keep a SINGLE partition for its entire vertex tuple, including singletons.
    for first, second in combinations(regions.values(), 2):
        face = tuple(sorted(set(first.vertices) & set(second.vertices)))
        if not face:
            continue
        groups: dict[tuple[GraphPoint, ...], list[int]] = {}
        for column, selector in enumerate(selectors):
            outputs = tuple(
                evaluate_selector(graph, selector, vertices[v].point) for v in face
            )
            groups.setdefault(outputs, []).append(column)
        first_rows = dict(zip(first.vertices, first.weights, strict=True))
        second_rows = dict(zip(second.vertices, second.weights, strict=True))
        for columns in groups.values():
            for vertex in face:
                left = sum((first_rows[vertex][j] for j in columns), fmpq(0))
                right = sum((second_rows[vertex][j] for j in columns), fmpq(0))
                if left != right:
                    raise VerificationError(
                        Failure(
                            FailureKind.INVALID_CERTIFICATE,
                            "lottery_consistency",
                            f"Regions {first.id} and {second.id} disagree on face {face}, selector columns {columns}, vertex {vertex}",
                            locations[second.id],
                        )
                    )
    return AdmissibleLottery(
        graph, agents, selectors, geometry, MappingProxyType(regions), vertices
    )
