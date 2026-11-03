"""Exact ordinary-SP residuals; these component checks are not bound acceptance.

Lottery arguments must come from successful check_lottery_admissibility.
Checked roots/cells must come from check_comparison_root for that SAME lottery
or its ComparisonStreams. Manually constructing evidence records is not a
validation path. check_sp_root validates a decoded auxiliary root itself.
"""

from dataclasses import replace

from flint import fmpq

from . import affine
from .comparison import (
    CheckedComparisonCell,
    CheckedComparisonRoot,
    check_comparison_root,
)
from .exact import format_rational
from .failures import Failure, FailureKind, VerificationError
from .graph import evaluate_selector, point_distance, point_from_chart, point_to_data
from .lottery import AdmissibleLottery
from .reader import AttributionKey, RootBlock, SPKey
from .residual import cost_difference
from .simplex import Verified


def sp_residual(cell: CheckedComparisonCell) -> affine.Quadratic:
    """Assemble deviated cost minus truthful cost from a validated SP cell.

    Precondition: cell is an SP cell returned by the comparison checker.
    Both ordered distance groups are evaluated at the same true x_i.
    """
    if not isinstance(cell, CheckedComparisonCell) or cell.deviated_weights is None:
        raise VerificationError(
            Failure(FailureKind.REFUSED, "sp_cell_type", "Need a checked SP cell")
        )
    count = len(cell.truthful_weights)
    if len(cell.distances) != 2 * count or len(cell.deviated_weights) != count:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "sp_cell_shape",
                "Inconsistent checked SP factor counts",
            )
        )
    return cost_difference(
        cell.deviated_weights,
        cell.distances[count:],
        cell.truthful_weights,
        cell.distances[:count],
    )


def _checked_key(lottery: AdmissibleLottery, root: CheckedComparisonRoot) -> SPKey:
    if not isinstance(lottery, AdmissibleLottery) or not isinstance(
        root, CheckedComparisonRoot
    ):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "sp_checked_type",
                "Need admissible lottery and checked comparison root",
            )
        )
    key = root.coverage.root.key
    if not isinstance(key, SPKey):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "sp_root_type",
                "Need an SP root",
                replace(root.coverage.root.location, root=key).to_dict(),
            )
        )
    return key


def _original_weights(
    lottery: AdmissibleLottery,
    key: SPKey,
    region_id: str,
    point: tuple[fmpq, ...],
    axes: tuple[int, ...],
) -> tuple[fmpq, ...]:
    """Replay only original vertex rows and barycentrics, not pulled formulas."""
    expected = AttributionKey(tuple(key.edges[j] for j in axes))
    region = lottery.geometry.roots[expected].coverage.simplices[region_id]
    barycentric = region.barycentric(tuple(point[j] for j in axes))
    if (
        barycentric is None
        or any(x < 0 for x in barycentric)
        or sum(barycentric, fmpq(0)) != 1
    ):
        raise RuntimeError("SP replay projection is outside its original region")
    record = lottery.regions[region_id]
    weights = tuple(
        sum(
            (b * row[j] for b, row in zip(barycentric, record.weights, strict=True)),
            fmpq(0),
        )
        for j in range(len(lottery.selectors))
    )
    if any(w < 0 for w in weights) or sum(weights, fmpq(0)) != 1:
        raise RuntimeError("SP replay did not produce a probability distribution")
    return weights


def check_sp_cell(
    lottery: AdmissibleLottery,
    root: CheckedComparisonRoot,
    cell_id: str,
) -> Verified | Failure:
    """Certify one validated cell or return an independently replayed SP failure.

    Precondition: root was checked for this same successful admissibility result.
    The result says nothing about unchecked cells, other roots or approximation.
    """
    key = _checked_key(lottery, root)
    if type(cell_id) is not str or cell_id not in root.cells:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "sp_cell_reference",
                "Need a cell in the checked root",
                replace(root.coverage.root.location, root=key).to_dict(),
            )
        )
    cell = root.cells[cell_id]
    location = replace(cell.record.location, root=key, cell=cell_id).to_dict()
    location.update(agent=key.agent, comparison="sp")
    try:
        quadratic = sp_residual(cell)
        result = affine.check_nonnegative(quadratic, cell.geometry.vertices)
        if isinstance(result, Verified):
            return result
        point = result.witness
        barycentric = cell.geometry.barycentric(point)
        if (
            barycentric != result.barycentric
            or any(b < 0 for b in result.barycentric)
            or sum(result.barycentric, fmpq(0)) != 1
        ):
            raise RuntimeError("SP replay witness is outside its cell")
        n = lottery.agents
        graph_points = tuple(
            point_from_chart(lottery.graph, e, x)
            for e, x in zip(key.edges, point, strict=True)
        )
        profile, deviation = graph_points[:n], graph_points[n]
        altered = tuple(
            deviation if j == key.agent else p for j, p in enumerate(profile)
        )
        true_point = profile[key.agent]
        assert cell.record.deviated is not None
        truthful_weights = _original_weights(
            lottery, key, cell.record.truthful, point, tuple(range(n))
        )
        deviated_weights = _original_weights(
            lottery,
            key,
            cell.record.deviated,
            point,
            tuple(n if j == key.agent else j for j in range(n)),
        )

        def cost(reports, weights):
            return sum(
                (
                    w
                    * point_distance(
                        lottery.graph,
                        true_point,
                        evaluate_selector(lottery.graph, selector, reports),
                    )
                    for w, selector in zip(weights, lottery.selectors, strict=True)
                ),
                fmpq(0),
            )

        truthful_cost = cost(profile, truthful_weights)
        deviated_cost = cost(altered, deviated_weights)
        difference = deviated_cost - truthful_cost
        if (
            difference != result.value
            or difference != affine.evaluate(quadratic, point)
            or difference >= 0
        ):
            raise RuntimeError(
                "SP residual disagrees with original graph-lottery replay"
            )
        return Failure(
            FailureKind.COUNTEREXAMPLE,
            "sp_violation",
            "A deviation strictly decreases expected distance to the true location",
            location,
            {
                "agent": key.agent,
                "profile": [point_to_data(p) for p in profile],
                "deviation": point_to_data(deviation),
                "barycentric": [format_rational(b) for b in result.barycentric],
                "difference": format_rational(difference),
                "truthful_cost": format_rational(truthful_cost),
                "deviated_cost": format_rational(deviated_cost),
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
                "internal_error_sp_replay",
                "Inconsistent checked SP evidence or witness replay",
                location,
            )
        ) from error


def check_checked_sp_root(
    lottery: AdmissibleLottery, root: CheckedComparisonRoot
) -> Verified | Failure:
    """Check all cells of one SP root already validated for the same lottery.

    Use with ComparisonStreams.iter_sp_roots for independently ordered complete
    streams. Completion/EOF and approximation remain the composition's duties.
    """
    _checked_key(lottery, root)
    for cell_id in root.cells:
        result = check_sp_cell(lottery, root, cell_id)
        if isinstance(result, Failure):
            return result
    return Verified()


def check_sp_root(lottery: AdmissibleLottery, root: RootBlock) -> Verified | Failure:
    """Validate a decoded SP root, then certify its cells; no complete bound.

    The lottery must be the successful full S08-S11 check result. Invalid
    branches/regions anywhere in this root fail before interpreting a residual.
    A valid root and global attribution suffice for a genuine counterexample
    even if further comparison roots have not yet been read.
    """
    return check_checked_sp_root(lottery, check_comparison_root(lottery, root))
