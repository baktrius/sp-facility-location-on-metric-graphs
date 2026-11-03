"""Complete comparison streams and checked regional formulas (SPEC S12-S13).

The lottery argument MUST come from successful check_lottery_admissibility.
Constructing its evidence record manually is not validation. No certificate
field can assert this precondition. These checks return neither residual signs
nor a complete verifier acceptance; future composition must consume both
streams through EOF and check every residual on every returned cell.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal

from flint import fmpq

from .coverage import RootCoverage, check_root_coverage
from .distance import (
    AffineExpression,
    DistanceTerm,
    check_distance_terms,
    constant_expression,
    root_expressions,
    selector_expression,
)
from .failures import Failure, FailureKind, VerificationError
from .geometry import Simplex, intrinsic_coordinates
from .graph import VertexPoint
from .lottery import AdmissibleLottery
from .reader import (
    ApproximationKey,
    AttributionKey,
    ComparisonSimplex,
    ReportCandidate,
    RootBlock,
    SPKey,
    VertexCandidate,
    approximation_root_keys,
    sp_root_keys,
)

type ComparisonKey = SPKey | ApproximationKey


def _next_root(iterator: Iterator[RootBlock]) -> RootBlock | None:
    """Distinguish real exhaustion from any supplied value, including None."""
    try:
        root = next(iterator)
    except StopIteration:
        return None
    if not isinstance(root, RootBlock):
        raise _error(
            "comparison_root_type", "Expected a decoded root block", malformed=True
        )
    return root


def _error(code: str, message: str, *, malformed: bool = False) -> VerificationError:
    return VerificationError(
        Failure(
            FailureKind.REFUSED if malformed else FailureKind.INVALID_CERTIFICATE,
            code,
            message,
        )
    )


def _key(lottery: AdmissibleLottery, key: object) -> ComparisonKey:
    if not isinstance(lottery, AdmissibleLottery):
        raise _error(
            "comparison_lottery_type",
            "Need checked admissible lottery data",
            malformed=True,
        )
    if not isinstance(key, (SPKey, ApproximationKey)):
        raise _error(
            "comparison_root_type", "Need an SP or approximation key", malformed=True
        )
    n = lottery.agents
    if type(key.edges) is not tuple or len(key.edges) != n + isinstance(key, SPKey):
        raise _error(
            "comparison_root_shape", "Wrong immutable root dimension", malformed=True
        )
    if any(type(e) is not int for e in key.edges):
        raise _error(
            "comparison_root_index_type",
            "Edge indices must be integers",
            malformed=True,
        )
    if any(not 0 <= e < len(lottery.graph.edges) for e in key.edges):
        raise _error("reference_index", "Unknown comparison root edge")
    if isinstance(key, SPKey):
        agent = key.agent
    elif isinstance(key.candidate, ReportCandidate):
        agent = key.candidate.agent
    elif isinstance(key.candidate, VertexCandidate):
        if type(key.candidate.vertex) is not str:
            raise _error(
                "comparison_candidate_type",
                "Vertex label must be a string",
                malformed=True,
            )
        if key.candidate.vertex not in lottery.graph.vertices:
            raise _error("reference_vertex", "Unknown candidate vertex")
        if lottery.graph.degree(key.candidate.vertex) < 3:
            raise _error(
                "reference_candidate",
                "Vertex candidate must have degree at least three",
            )
        return key
    else:
        raise _error(
            "comparison_candidate_type",
            "Need a report or vertex candidate",
            malformed=True,
        )
    # Dataclass equality would otherwise let False alias agent/index zero.
    if type(agent) is not int:
        raise _error(
            "comparison_agent_type", "Agent index must be an integer", malformed=True
        )
    if not 0 <= agent < n:
        raise _error("reference_index", "Unknown comparison agent")
    return key


def _root_key(lottery: AdmissibleLottery, root: RootBlock) -> ComparisonKey:
    try:
        return _key(lottery, root.key)
    except VerificationError as error:
        raise VerificationError(
            replace(
                error.failure, location=replace(root.location, root=root.key).to_dict()
            )
        ) from error


def comparison_distance_terms(
    lottery: AdmissibleLottery, key: ComparisonKey
) -> tuple[DistanceTerm, ...]:
    """Generate canonical ordered operands independently of branches and weights."""
    key = _key(lottery, key)
    graph, n = lottery.graph, lottery.agents
    coordinates = root_expressions(graph, key.edges)
    reports = coordinates[:n]
    outputs = tuple(selector_expression(graph, f, reports) for f in lottery.selectors)
    if isinstance(key, SPKey):
        deviated = tuple(
            coordinates[n] if j == key.agent else reports[j] for j in range(n)
        )
        altered = tuple(
            selector_expression(graph, f, deviated) for f in lottery.selectors
        )
        # The true x_i is the left operand in BOTH groups. Only peak_i changes.
        return tuple(
            DistanceTerm(reports[key.agent], out) for out in (*outputs, *altered)
        )
    candidate = (
        reports[key.candidate.agent]
        if isinstance(key.candidate, ReportCandidate)
        else constant_expression(graph, VertexPoint(key.candidate.vertex), n)
    )
    return (
        *(DistanceTerm(report, out) for report in reports for out in outputs),
        *(DistanceTerm(report, candidate) for report in reports),
    )


@dataclass(frozen=True)
class CheckedComparisonCell:
    """Formulas valid throughout this covered closed cell, without sign claims.

    Weight and distance tuple orders are selector/SCHEMA orders. SP distances
    split after |F|; APX candidate distances begin after n|F|. record retains
    original IDs, branches and source provenance for subsequent witnesses.
    """

    record: ComparisonSimplex
    geometry: Simplex
    truthful_weights: tuple[AffineExpression, ...]
    deviated_weights: tuple[AffineExpression, ...] | None
    terms: tuple[DistanceTerm, ...]
    distances: tuple[AffineExpression, ...]


@dataclass(frozen=True)
class CheckedComparisonRoot:
    coverage: RootCoverage
    cells: Mapping[str, CheckedComparisonCell]


def _region_weights(
    lottery: AdmissibleLottery,
    cell: Simplex,
    edges: tuple[int, ...],
    axes: tuple[int, ...],
    region_id: str,
) -> tuple[AffineExpression, ...]:
    expected = AttributionKey(tuple(edges[j] for j in axes))
    # Resolve inside the EXPECTED root, not just the globally valid ID namespace.
    root = lottery.geometry.roots[expected].coverage
    if region_id not in root.simplices:
        raise _error(
            "region_root", "Attribution reference is outside its expected edge root"
        )
    region = root.simplices[region_id]
    matrix = cell.vertices
    for j in range(matrix.ncols()):
        if not region.contains(tuple(matrix[i, j] for i in axes)):
            raise _error(
                "region_containment",
                "A projected cell vertex is outside the attribution simplex",
            )
    rows = lottery.regions[region_id].weights
    weights = []
    for column in range(len(lottery.selectors)):
        # Original geometry columns and regional rows have the original vertex
        # order. Refinement only composes that interpolant with a projection.
        coefficients, constant = region.interpolate(
            tuple(row[column] for row in rows)
        ).coefficients()
        pulled = [fmpq(0)] * cell.ambient_dimension
        for coefficient, axis in zip(coefficients, axes, strict=True):
            pulled[axis] += coefficient
        weights.append(AffineExpression(tuple(pulled), constant))
    return tuple(weights)


def check_comparison_root(
    lottery: AdmissibleLottery, root: RootBlock
) -> CheckedComparisonRoot:
    """Validate one auxiliary root; completeness requires ComparisonStreams.

    Precondition: lottery is the successful S08-S11 checker result. This
    function performs S08 for the auxiliary cover, then S12/S13 for every cell.
    Auxiliary facet conformity is deliberately not required.
    """
    if not isinstance(root, RootBlock):
        raise _error(
            "comparison_root_type", "Expected a decoded root block", malformed=True
        )
    key = _root_key(lottery, root)
    location = replace(root.location, root=key).to_dict()
    try:
        seen_ids, seen_points = set(), set()
        for vertex in root.vertices:
            location = replace(vertex.location, root=key).to_dict()
            intrinsic_coordinates(lottery.graph, key.edges, vertex.point)
            if vertex.id in seen_ids or vertex.point in seen_points:
                raise _error(
                    "reference_duplicate_vertex",
                    "Duplicate local vertex ID or canonical point",
                )
            seen_ids.add(vertex.id)
            seen_points.add(vertex.point)
        location = replace(root.location, root=key).to_dict()
        coverage = check_root_coverage(lottery.graph, root)
        terms = comparison_distance_terms(lottery, key)
        cells = {}
        axes = tuple(range(lottery.agents))
        for record in root.simplices:
            location = replace(record.location, root=key, cell=record.id).to_dict()
            if not isinstance(record, ComparisonSimplex):
                raise _error(
                    "comparison_simplex_type",
                    "Need an auxiliary simplex record",
                    malformed=True,
                )
            if (
                isinstance(key, SPKey)
                and (type(record.deviated) is not str or not record.deviated)
            ) or (isinstance(key, ApproximationKey) and record.deviated is not None):
                raise _error(
                    "region_reference",
                    "Wrong deviated-reference shape for comparison type",
                )
            geometry = coverage.simplices[record.id]
            truthful = _region_weights(
                lottery, geometry, key.edges, axes, record.truthful
            )
            deviated = None
            if isinstance(key, SPKey):
                assert record.deviated is not None
                replacement = tuple(
                    lottery.agents if j == key.agent else j for j in axes
                )
                deviated = _region_weights(
                    lottery, geometry, key.edges, replacement, record.deviated
                )
            distances = check_distance_terms(
                lottery.graph, geometry, terms, record.branches, location=location
            )
            cells[record.id] = CheckedComparisonCell(
                record, geometry, truthful, deviated, terms, distances
            )
        return CheckedComparisonRoot(coverage, MappingProxyType(cells))
    except VerificationError as error:
        raise VerificationError(
            replace(error.failure, location=error.failure.location or location)
        ) from error


class ComparisonStreams:
    """Check roots one at a time; set completion only after actual exhaustion.

    Both one-shot iterators must reach StopIteration. Merely obtaining the
    last root, closing, failing or abandoning either leaves streams_exhausted
    false. This flag proves comparisons were prepared, never residual signs.
    When wrapping BundleReader iterators, its EOF/trailing-record checks run
    before the corresponding completion flag is set here.
    """

    def __init__(self, lottery: AdmissibleLottery):
        if not isinstance(lottery, AdmissibleLottery):
            raise _error(
                "comparison_lottery_type",
                "Need checked admissible lottery data",
                malformed=True,
            )
        self.lottery = lottery
        self._started: set[str] = set()
        self._finished: set[str] = set()

    def _iterate(
        self, stream: Literal["sp", "approximation"], roots: Iterable[RootBlock]
    ) -> Iterator[CheckedComparisonRoot]:
        if stream in self._started:
            raise ValueError(f"{stream} is a one-shot comparison stream")
        self._started.add(stream)
        return self._consume(stream, roots)

    def _consume(
        self, stream: Literal["sp", "approximation"], roots: Iterable[RootBlock]
    ) -> Iterator[CheckedComparisonRoot]:
        expected = (
            sp_root_keys(self.lottery.graph, self.lottery.agents)
            if stream == "sp"
            else approximation_root_keys(self.lottery.graph, self.lottery.agents)
        )
        iterator = iter(roots)
        for required in expected:
            root = _next_root(iterator)
            if root is None:
                raise VerificationError(
                    Failure(
                        FailureKind.INVALID_CERTIFICATE,
                        "reference_root_sequence",
                        "Comparison stream ended before every required root",
                        {"file": stream + ".jsonl", "root": required.to_data()},
                    )
                )
            _root_key(self.lottery, root)
            if root.key != required:
                raise VerificationError(
                    Failure(
                        FailureKind.INVALID_CERTIFICATE,
                        "reference_root_sequence",
                        "Comparison root does not match the next required root",
                        replace(root.location, root=root.key).to_dict(),
                    )
                )
            yield check_comparison_root(self.lottery, root)
        extra = _next_root(iterator)
        if extra is not None:
            raise VerificationError(
                Failure(
                    FailureKind.INVALID_CERTIFICATE,
                    "reference_root_sequence",
                    "Extra comparison root after required sequence",
                    replace(extra.location, root=extra.key).to_dict(),
                )
            )
        self._finished.add(stream)

    def iter_sp_roots(
        self, roots: Iterable[RootBlock]
    ) -> Iterator[CheckedComparisonRoot]:
        return self._iterate("sp", roots)

    def iter_approximation_roots(
        self, roots: Iterable[RootBlock]
    ) -> Iterator[CheckedComparisonRoot]:
        return self._iterate("approximation", roots)

    @property
    def streams_exhausted(self) -> bool:
        return self._finished == {"sp", "approximation"}
