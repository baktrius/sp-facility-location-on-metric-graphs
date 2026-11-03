"""Ordinary SP on real checked lotteries, with independent exact cost oracles."""

from dataclasses import replace
from typing import Any, cast

import pytest
from flint import fmpq
from test_charts import meshes
from test_comparison import affine_lottery, comparison_cube

from upper_bound_verifier.affine import evaluate
from upper_bound_verifier.comparison import check_comparison_root
from upper_bound_verifier.distance import AffineExpression
from upper_bound_verifier.failures import Failure, FailureKind, VerificationError
from upper_bound_verifier.graph import (
    ConstantSelector,
    EdgePoint,
    Graph,
    PeakSelector,
    VertexPoint,
    chart_coordinate,
    evaluate_selector,
    parse_point,
    point_distance,
)
from upper_bound_verifier.lottery import AdmissibleLottery, check_lottery_admissibility
from upper_bound_verifier.reader import ComparisonSimplex, SourceLocation, SPKey
from upper_bound_verifier.simplex import Verified


def lottery_fixture(agents=2, weight=None, constant=None):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph, agents)
    roots = tuple(
        replace(
            root,
            simplices=tuple(
                replace(
                    cell,
                    weights=tuple(
                        (fmpq(1), fmpq(0), fmpq(0))
                        if weight is None
                        else weight(vertices[v].point)
                        for v in cell.vertices
                    ),
                )
                for cell in root.simplices
            ),
        )
        for root in roots
    )
    return check_lottery_admissibility(
        graph,
        agents,
        (
            PeakSelector(0),
            PeakSelector(agents - 1),
            ConstantSelector(constant or VertexPoint("a")),
        ),
        roots,
        vertices,
    )


def test_dictatorship_certifies_every_cell_of_representative_sp_roots():
    from upper_bound_verifier.sp import check_sp_root

    lottery = lottery_fixture()
    for agent in (0, 1):
        root = comparison_cube(lottery.graph, SPKey(agent, (0, 0, 0)), lottery)
        assert isinstance(check_sp_root(lottery, root), Verified)


def test_report_dependent_admissible_lottery_returns_actual_profitable_deviation():
    from upper_bound_verifier.sp import check_sp_root

    # M reports peak0 with probability x0 and peak1 with probability 1-x0.
    # At x=(1/4,1), z=1/2 costs 1/2 rather than 9/16, difference -1/16.
    def weight(profile):
        x = fmpq(profile[0] == VertexPoint("b"))
        return x, 1 - x, fmpq(0)

    lottery = lottery_fixture(weight=weight)
    root = comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    result = check_sp_root(lottery, root)
    assert isinstance(result, Failure)
    assert result.kind is FailureKind.COUNTEREXAMPLE
    assert result.code == "sp_violation"
    assert result.witness is not None
    assert fmpq(result.witness["difference"]) < 0
    checked = check_comparison_root(lottery, root)
    assert result.location is not None
    cell = checked.cells[cast(str, result.location["cell"])]
    from upper_bound_verifier.sp import sp_residual

    q = sp_residual(cell)
    matrix = cell.geometry.vertices
    # All vertices are nonnegative; the actual violation requires an interior
    # point of a simplex face, detected by the complete quadratic kernel.
    assert all(
        evaluate(q, tuple(matrix[i, j] for i in range(3))) >= 0 for j in range(4)
    )
    replay_witness(lottery, checked, result)


def replay_witness(lottery, checked, failure):
    """Replay graph lotteries independently from source vertex rows."""
    witness = failure.witness
    assert witness is not None and failure.location is not None
    profile = tuple(parse_point(lottery.graph, p) for p in witness["profile"])
    deviation = parse_point(lottery.graph, witness["deviation"])
    agent = witness["agent"]
    altered = tuple(deviation if j == agent else p for j, p in enumerate(profile))
    cell = checked.cells[failure.location["cell"]]
    key = checked.coverage.root.key
    barycentric = tuple(fmpq(b) for b in witness["barycentric"])
    assert all(b >= 0 for b in barycentric) and sum(barycentric) == 1
    coordinates = tuple(
        sum(
            (cell.geometry.vertices[i, j] * b for j, b in enumerate(barycentric)),
            fmpq(0),
        )
        for i in range(lottery.agents + 1)
    )
    assert (
        tuple(
            chart_coordinate(lottery.graph, p, e)
            for e, p in zip(key.edges, (*profile, deviation), strict=True)
        )
        == coordinates
    )

    def direct(reports, region_id):
        record = lottery.regions[region_id]
        # Resolve the original geometry by region ID, independently of SP axes.
        region = next(
            r.coverage.simplices[region_id]
            for r in lottery.geometry.roots.values()
            if region_id in r.coverage.simplices
        )
        source_key = next(
            k
            for k, r in lottery.geometry.roots.items()
            if region_id in r.coverage.simplices
        )
        point = tuple(
            chart_coordinate(lottery.graph, p, e)
            for e, p in zip(source_key.edges, reports, strict=True)
        )
        b = region.barycentric(point)
        assert b is not None and all(x >= 0 for x in b)
        weights = tuple(
            sum((x * row[j] for x, row in zip(b, record.weights, strict=True)), fmpq(0))
            for j in range(len(lottery.selectors))
        )
        assert sum(weights) == 1 and all(w >= 0 for w in weights)
        return sum(
            (
                w
                * point_distance(
                    lottery.graph,
                    profile[agent],
                    evaluate_selector(lottery.graph, selector, reports),
                )
                for w, selector in zip(weights, lottery.selectors, strict=True)
            ),
            fmpq(0),
        )

    truthful = direct(profile, cell.record.truthful)
    deviated = direct(altered, cell.record.deviated)
    assert truthful == fmpq(witness["truthful_cost"])
    assert deviated == fmpq(witness["deviated_cost"])
    assert deviated - truthful == fmpq(witness["difference"]) < 0
    assert failure.location["agent"] == agent == key.agent
    assert failure.location["comparison"] == "sp"


def report_lottery():
    def weight(profile):
        x = fmpq(profile[0] == VertexPoint("b"))
        return x, 1 - x, fmpq(0)

    return lottery_fixture(weight=weight)


def test_both_costs_use_true_agent_location_when_z_would_reverse_the_sign():
    from upper_bound_verifier.sp import sp_residual

    lottery = report_lottery()
    checked = check_comparison_root(
        lottery, comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    )
    samples = ((fmpq(1, 2), fmpq(1), fmpq(1)), (fmpq(1, 4), fmpq(1), fmpq(1, 2)))
    for point, expected in zip(samples, (fmpq(1, 4), fmpq(-1, 16)), strict=True):
        cells = [c for c in checked.cells.values() if c.geometry.contains(point)]
        assert cells
        assert all(evaluate(sp_residual(c), point) == expected for c in cells)
    # Wrong deviated evaluation at z gives 0 - 1/4 = -1/4 for the first
    # point. Correct true-location evaluation gives 1/2 - 1/4 = +1/4.
    assert samples[0][0] != samples[0][2]


def test_assembled_costs_match_independent_hand_formula_on_closed_cell_points():
    from upper_bound_verifier.sp import sp_residual

    lottery = report_lottery()
    checked = check_comparison_root(
        lottery, comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    )
    for cell in checked.cells.values():
        matrix = cell.geometry.vertices
        points = [tuple(matrix[i, j] for i in range(3)) for j in range(4)]
        points.append(
            tuple(sum((matrix[i, j] for j in range(4)), fmpq(0)) / 4 for i in range(3))
        )
        for x0, x1, z in points:
            truthful = (1 - x0) * abs(x1 - x0)
            deviated = z * abs(z - x0) + (1 - z) * abs(x1 - x0)
            assert evaluate(sp_residual(cell), (x0, x1, z)) == deviated - truthful


def test_counterexample_retains_cell_source_line_actual_root_and_json_shape():
    import json

    from upper_bound_verifier.sp import check_sp_root

    lottery = report_lottery()
    root = comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    stale = SPKey(1, (0, 0, 0))
    root = replace(
        root,
        simplices=tuple(
            replace(c, location=SourceLocation("sp.jsonl", 271, stale, c.id))
            for c in root.simplices
        ),
    )
    failure = check_sp_root(lottery, root)
    assert isinstance(failure, Failure)
    assert failure.location is not None
    assert failure.location["line"] == 271
    assert failure.location["root"] == root.key.to_data()
    assert json.loads(json.dumps(failure.to_dict()))["kind"] == "counterexample"
    assert failure.witness is not None
    difference = failure.witness["difference"]
    assert isinstance(difference, str) and str(fmpq(difference)) == difference


def refined_root(lottery, agent, cut):
    """Real small grid with constant-distance kinks and all coordinate orders."""
    n = lottery.agents
    roots, vertices, _ = meshes(lottery.graph, n + 1, cuts=lambda key, axis: (cut,))
    raw = roots[0]
    key = SPKey(agent, (0,) * (n + 1))
    loc = SourceLocation("sp.jsonl", 123, key)
    records = []
    for record in raw.simplices:
        points = tuple(
            tuple(chart_coordinate(lottery.graph, p, 0) for p in vertices[v].point)
            for v in record.vertices
        )
        centroid = tuple(
            sum((p[j] for p in points), fmpq(0)) / len(points) for j in range(n + 1)
        )
        truth = centroid[:n]
        altered = tuple(centroid[n] if j == agent else truth[j] for j in range(n))

        def region(profile):
            return next(
                name
                for r in lottery.geometry.roots.values()
                for name, geometry in r.coverage.simplices.items()
                if geometry.contains(profile)
            )

        branches = []
        for deviated in (False, True):
            for selector in lottery.selectors:
                if isinstance(selector, PeakSelector):
                    axis = n if deviated and selector.agent == agent else selector.agent
                    gaps = tuple(p[agent] - p[axis] for p in points)
                else:
                    constant = chart_coordinate(lottery.graph, selector.point, 0)
                    gaps = tuple(p[agent] - constant for p in points)
                assert all(x >= 0 for x in gaps) or all(x <= 0 for x in gaps)
                branches.append(0 if all(x >= 0 for x in gaps) else 1)
        records.append(
            ComparisonSimplex(
                record.id,
                record.vertices,
                region(truth),
                region(altered),
                tuple(branches),
                replace(loc, cell=record.id),
            )
        )
    return replace(
        raw,
        key=key,
        vertices=tuple(replace(v, location=loc) for v in vertices.values()),
        simplices=tuple(records),
        location=loc,
    )


def test_three_agents_agent_two_with_positive_mass_on_rational_interior_constant():
    from upper_bound_verifier.sp import check_sp_cell, sp_residual

    def weight(profile):
        x = fmpq(profile[2] == VertexPoint("b"))
        return 1 - x, fmpq(0), x

    lottery = lottery_fixture(3, weight, EdgePoint(0, fmpq(1, 3)))
    checked = check_comparison_root(lottery, refined_root(lottery, 2, fmpq(1, 3)))
    point = (fmpq(1), fmpq(0), fmpq(1, 3), fmpq(1))
    cell = next(c for c in checked.cells.values() if c.geometry.contains(point))
    # Truthful weights (2/3,0,1/3): cost (2/3)*(2/3)=4/9.
    # Deviated weight on the constant is one; its distance to true x2 is zero.
    assert cell.truthful_weights[2].evaluate(point) == fmpq(1, 3)
    assert cell.deviated_weights is not None
    assert cell.deviated_weights[2].evaluate(point) == 1
    assert evaluate(sp_residual(cell), point) == fmpq(-4, 9)
    result = check_sp_cell(lottery, checked, cell.record.id)
    assert isinstance(result, Failure) and result.kind is FailureKind.COUNTEREXAMPLE
    replay_witness(lottery, checked, result)


def test_symmetric_product_coefficients_match_hand_expansion_and_direct_costs():
    from upper_bound_verifier.residual import cost_difference

    # (2x-y+1/3)(x+3y-2/5) - (-x+2)(4y+1/7)
    q = cost_difference(
        (AffineExpression((2, -1), fmpq(1, 3)),),
        (AffineExpression((1, 3), fmpq(-2, 5)),),
        (AffineExpression((-1, 0), 2),),
        (AffineExpression((0, 4), fmpq(1, 7)),),
    )
    assert q.H[0, 0] == 2 and q.H[1, 1] == -3
    assert q.H[0, 1] == q.H[1, 0] == fmpq(9, 2)
    assert q.g == (fmpq(-34, 105), fmpq(-33, 5))
    assert q.c == fmpq(-44, 105)
    for x, y in ((fmpq(0), fmpq(0)), (fmpq(2, 7), fmpq(-3, 5)), (fmpq(1), fmpq(1))):
        direct = (2 * x - y + fmpq(1, 3)) * (x + 3 * y - fmpq(2, 5)) - (-x + 2) * (
            4 * y + fmpq(1, 7)
        )
        assert evaluate(q, (x, y)) == direct


@pytest.mark.parametrize("agent", [0, 1, 2])
def test_three_agent_dictatorship_certifies_checked_stream_root(agent):
    from upper_bound_verifier.sp import check_checked_sp_root

    lottery = lottery_fixture(3)
    root = comparison_cube(lottery.graph, SPKey(agent, (0, 0, 0, 0)), lottery)
    assert isinstance(
        check_checked_sp_root(lottery, check_comparison_root(lottery, root)), Verified
    )


def test_cross_edge_deviation_certifies_the_actual_graph_metric():
    from upper_bound_verifier.sp import check_sp_root

    graph = Graph(("a", "b", "c"), (("a", "b"), ("c", "b")))
    lottery = affine_lottery(graph)
    root = comparison_cube(graph, SPKey(1, (0, 0, 1)), lottery)
    root = replace(
        root,
        simplices=tuple(
            replace(c, branches=(*c.branches[:4], 3, c.branches[5]))
            for c in root.simplices
        ),
    )
    # Deviated own-peak distance is (1-x1)+(1-z); all other terms stay fixed.
    assert isinstance(check_sp_root(lottery, root), Verified)


@pytest.mark.parametrize("attack", ["branch", "region", "containment", "coverage"])
def test_bad_raw_root_is_never_a_counterexample_even_after_a_profitable_cell(attack):
    from upper_bound_verifier.sp import check_sp_root

    lottery = report_lottery()
    root = comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    *rest, last = root.simplices
    if attack == "branch":
        # Final zero-weight constant term still needs a correct metric branch.
        last = replace(last, branches=(*last.branches[:-1], 1))
    elif attack == "region":
        last = replace(last, truthful="missing")
    elif attack == "containment":
        other = next(r for r in lottery.regions if r != last.truthful)
        last = replace(last, truthful=other)
    else:
        rest = rest[:-1]
    root = replace(root, simplices=(*rest, last))
    with pytest.raises(VerificationError) as caught:
        check_sp_root(lottery, root)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code != "sp_violation"


def test_invalid_global_attribution_fails_before_any_sp_counterexample():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = tuple(
        replace(
            r,
            simplices=tuple(
                replace(c, weights=((fmpq(0),) * 3,) * 3) for c in r.simplices
            ),
        )
        for r in roots
    )
    with pytest.raises(VerificationError) as caught:
        lottery = check_lottery_admissibility(
            graph,
            2,
            (PeakSelector(0), PeakSelector(1), ConstantSelector(VertexPoint("a"))),
            roots,
            vertices,
        )
        from upper_bound_verifier.sp import check_sp_root

        check_sp_root(lottery, comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery))
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "probability_normalization"


def test_inconsistent_negative_formula_fails_closed_at_original_lottery_replay():
    from upper_bound_verifier.sp import check_sp_cell

    lottery = lottery_fixture()
    root = check_comparison_root(
        lottery, comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    )
    cell_id, cell = next(iter(root.cells.items()))
    # Deliberately corrupt an internally checked formula after a genuine check.
    # This is an inconsistency probe, never a certificate validation shortcut.
    cell = replace(
        cell, distances=(AffineExpression((0, 0, 0), 100), *cell.distances[1:])
    )
    corrupted = replace(root, cells={**root.cells, cell_id: cell})
    with pytest.raises(VerificationError) as caught:
        check_sp_cell(lottery, corrupted, cell_id)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "internal_error_sp_replay"
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["cell"] == cell_id


@pytest.mark.parametrize(
    "attack", ["empty", "mismatched_count", "wrong_dimension", "inexact_factor"]
)
def test_cost_algebra_refuses_inconsistent_or_inexact_factors(attack):
    from upper_bound_verifier.residual import cost_difference

    factor = AffineExpression((1,), 0)
    groups: list[Any] = [(factor,)] * 4
    groups[0] = {
        "empty": (),
        "mismatched_count": (factor, factor),
        "wrong_dimension": (AffineExpression((1, 0), 0),),
        "inexact_factor": (0.5,),
    }[attack]
    with pytest.raises(VerificationError) as caught:
        cost_difference(*groups)
    assert caught.value.failure.kind is FailureKind.REFUSED


def test_sp_interfaces_refuse_apx_and_non_evidence_inputs():
    from upper_bound_verifier.reader import ApproximationKey, ReportCandidate
    from upper_bound_verifier.sp import check_sp_cell, check_sp_root, sp_residual

    lottery = lottery_fixture()
    root = comparison_cube(
        lottery.graph, ApproximationKey(ReportCandidate(0), (0, 0)), lottery
    )
    with pytest.raises(VerificationError) as caught:
        check_sp_root(lottery, root)
    assert caught.value.failure.code == "sp_root_type"
    assert (
        caught.value.failure.location == replace(root.location, root=root.key).to_dict()
    )
    checked = check_comparison_root(lottery, root)
    with pytest.raises(VerificationError):
        sp_residual(next(iter(checked.cells.values())))
    with pytest.raises(VerificationError):
        check_sp_cell(lottery, checked, "missing")
    with pytest.raises(VerificationError):
        check_sp_root(cast(AdmissibleLottery, None), root)
