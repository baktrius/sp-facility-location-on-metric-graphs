"""Exact candidate approximation inequalities; component results are not bounds.

Lottery arguments must be successful check_lottery_admissibility results.
Checked roots/cells must come from check_comparison_root for that SAME lottery
or its ComparisonStreams. Manually constructing evidence is not validation.
"""

from dataclasses import replace

from flint import fmpq

from . import affine
from .comparison import (
    CheckedComparisonCell,
    CheckedComparisonRoot,
    check_comparison_root,
)
from .distance import AffineExpression
from .exact import format_rational
from .failures import Failure, FailureKind, VerificationError
from .graph import (
    VertexPoint,
    evaluate_selector,
    point_distance,
    point_from_chart,
    point_to_data,
)
from .lottery import AdmissibleLottery
from .reader import ApproximationKey, AttributionKey, ReportCandidate, RootBlock
from .residual import cost_difference
from .simplex import Verified


def _alpha(value: object) -> fmpq:
    if type(value) is not int and not isinstance(value, fmpq):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_alpha_type",
                "Need an exact integer or FLINT rational factor",
            )
        )
    value = fmpq(value)
    if value < 1:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_alpha_range",
                "Approximation factor must be at least one",
            )
        )
    return value


def approximation_residual(
    cell: CheckedComparisonCell, alpha: object
) -> affine.Quadratic:
    """Form alpha*candidate social cost minus expected mechanism social cost.

    Precondition: cell is an APX cell returned by the comparison checker.
    n|F| distances are agent-major/selector-minor, then n candidate distances.
    All weights and terms remain present, including zero-weight selectors.
    """
    alpha = _alpha(alpha)
    if not isinstance(cell, CheckedComparisonCell) or cell.deviated_weights is not None:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_cell_type",
                "Need a checked approximation cell",
            )
        )
    n = cell.geometry.ambient_dimension
    count = len(cell.truthful_weights)
    if n < 2 or count == 0 or len(cell.distances) != n * count + n:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_cell_shape",
                "Inconsistent checked approximation factor counts",
            )
        )
    factor = AffineExpression((fmpq(0),) * n, alpha)
    return cost_difference(
        (factor,) * n,
        cell.distances[n * count :],
        cell.truthful_weights * n,
        cell.distances[: n * count],
    )


def _checked_key(
    lottery: AdmissibleLottery, root: CheckedComparisonRoot
) -> ApproximationKey:
    if not isinstance(lottery, AdmissibleLottery) or not isinstance(
        root, CheckedComparisonRoot
    ):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_checked_type",
                "Need admissible lottery and checked comparison root",
            )
        )
    key = root.coverage.root.key
    if not isinstance(key, ApproximationKey):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_root_type",
                "Need an approximation root",
                replace(root.coverage.root.location, root=key).to_dict(),
            )
        )
    return key


def _original_weights(
    lottery: AdmissibleLottery,
    key: ApproximationKey,
    region_id: str,
    point: tuple[fmpq, ...],
) -> tuple[fmpq, ...]:
    """Replay original rows at the profile, without the pulled affine formulas."""
    region = lottery.geometry.roots[AttributionKey(key.edges)].coverage.simplices[
        region_id
    ]
    barycentric = region.barycentric(point)
    if (
        barycentric is None
        or any(b < 0 for b in barycentric)
        or sum(barycentric, fmpq(0)) != 1
    ):
        raise RuntimeError(
            "Approximation replay profile is outside its original region"
        )
    rows = lottery.regions[region_id].weights
    weights = tuple(
        sum((b * row[j] for b, row in zip(barycentric, rows, strict=True)), fmpq(0))
        for j in range(len(lottery.selectors))
    )
    if any(w < 0 for w in weights) or sum(weights, fmpq(0)) != 1:
        raise RuntimeError(
            "Approximation replay did not produce a probability distribution"
        )
    return weights


def check_approximation_cell(
    lottery: AdmissibleLottery, root: CheckedComparisonRoot, cell_id: str, alpha: object
) -> Verified | Failure:
    """Certify one cell or return an independently replayed negative inequality.

    Precondition: root was checked for this same successful admissibility result.
    The candidate need not minimize social cost for a genuine counterexample.
    """
    key = _checked_key(lottery, root)
    alpha = _alpha(alpha)
    if type(cell_id) is not str or cell_id not in root.cells:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "approximation_cell_reference",
                "Need a cell in the checked root",
                replace(root.coverage.root.location, root=key).to_dict(),
            )
        )
    cell = root.cells[cell_id]
    location = replace(cell.record.location, root=key, cell=cell_id).to_dict()
    location.update(candidate=key.candidate.to_data(), comparison="approximation")
    try:
        quadratic = approximation_residual(cell, alpha)
        result = affine.check_nonnegative(quadratic, cell.geometry.vertices)
        if isinstance(result, Verified):
            return result
        point = result.witness
        if (
            cell.geometry.barycentric(point) != result.barycentric
            or any(b < 0 for b in result.barycentric)
            or sum(result.barycentric, fmpq(0)) != 1
        ):
            raise RuntimeError("Approximation replay witness is outside its cell")
        profile = tuple(
            point_from_chart(lottery.graph, e, x)
            for e, x in zip(key.edges, point, strict=True)
        )
        candidate = (
            profile[key.candidate.agent]
            if isinstance(key.candidate, ReportCandidate)
            else VertexPoint(key.candidate.vertex)
        )
        weights = _original_weights(lottery, key, cell.record.truthful, point)
        outputs = tuple(
            evaluate_selector(lottery.graph, selector, profile)
            for selector in lottery.selectors
        )
        mechanism_cost = sum(
            (
                w * point_distance(lottery.graph, report, output)
                for report in profile
                for w, output in zip(weights, outputs, strict=True)
            ),
            fmpq(0),
        )
        candidate_cost = sum(
            (point_distance(lottery.graph, report, candidate) for report in profile),
            fmpq(0),
        )
        difference = alpha * candidate_cost - mechanism_cost
        if (
            difference != result.value
            or difference != affine.evaluate(quadratic, point)
            or difference >= 0
        ):
            raise RuntimeError(
                "Approximation residual disagrees with original graph-lottery replay"
            )
        return Failure(
            FailureKind.COUNTEREXAMPLE,
            "approximation_violation",
            "Expected social cost exceeds alpha times candidate social cost",
            location,
            {
                "profile": [point_to_data(p) for p in profile],
                "candidate": key.candidate.to_data(),
                "candidate_point": point_to_data(candidate),
                "barycentric": [format_rational(b) for b in result.barycentric],
                "alpha": format_rational(alpha),
                "difference": format_rational(difference),
                "candidate_cost": format_rational(candidate_cost),
                "mechanism_cost": format_rational(mechanism_cost),
            },
        )
    except VerificationError as error:
        raise VerificationError(
            replace(error.failure, location=error.failure.location or location)
        ) from error
    except (RuntimeError, KeyError, ValueError, IndexError, AssertionError) as error:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "internal_error_approximation_replay",
                "Inconsistent checked approximation evidence or witness replay",
                location,
            )
        ) from error


def check_checked_approximation_root(
    lottery: AdmissibleLottery, root: CheckedComparisonRoot, alpha: object
) -> Verified | Failure:
    """Check every cell of one root already validated for the same lottery.

    Complete root enumeration/EOF and SP remain the later composition's duties.
    """
    _checked_key(lottery, root)
    alpha = _alpha(alpha)
    for cell_id in root.cells:
        result = check_approximation_cell(lottery, root, cell_id, alpha)
        if isinstance(result, Failure):
            return result
    return Verified()


def check_approximation_root(
    lottery: AdmissibleLottery, root: RootBlock, alpha: object
) -> Verified | Failure:
    """Validate a decoded root completely before interpreting its residuals.

    The lottery must be the successful global S08-S11 check result. This
    checks one candidate/root only, not a complete approximation guarantee.
    """
    return check_checked_approximation_root(
        lottery, check_comparison_root(lottery, root), alpha
    )
