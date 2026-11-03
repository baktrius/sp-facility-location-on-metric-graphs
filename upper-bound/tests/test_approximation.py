"""Approximation inequalities on actual checked graph lotteries."""

from dataclasses import replace
from typing import Any, cast

import pytest
from flint import fmpq
from test_charts import meshes
from test_comparison import comparison_cube
from test_sp import lottery_fixture

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
from upper_bound_verifier.reader import (
    ApproximationKey,
    AttributionKey,
    ComparisonSimplex,
    ReportCandidate,
    SourceLocation,
    SPKey,
    VertexCandidate,
    approximation_candidates,
)
from upper_bound_verifier.simplex import Verified


def replay(lottery, checked, failure):
    """Recover weights from original regional rows, independently of residuals."""
    witness, location = failure.witness, failure.location
    assert witness is not None and location is not None
    cell = checked.cells[location["cell"]]
    profile = tuple(parse_point(lottery.graph, p) for p in witness["profile"])
    candidate = parse_point(lottery.graph, witness["candidate_point"])
    point = tuple(
        chart_coordinate(lottery.graph, p, e)
        for e, p in zip(checked.coverage.root.key.edges, profile, strict=True)
    )
    barycentric = tuple(fmpq(b) for b in witness["barycentric"])
    assert cell.geometry.barycentric(point) == barycentric
    assert all(b >= 0 for b in barycentric) and sum(barycentric) == 1
    region = next(
        r.coverage.simplices[cell.record.truthful]
        for r in lottery.geometry.roots.values()
        if cell.record.truthful in r.coverage.simplices
    )
    b = region.barycentric(point)
    assert b is not None and all(x >= 0 for x in b) and sum(b) == 1
    weights = tuple(
        sum(
            (
                x * row[j]
                for x, row in zip(
                    b, lottery.regions[cell.record.truthful].weights, strict=True
                )
            ),
            fmpq(0),
        )
        for j in range(len(lottery.selectors))
    )
    mechanism = sum(
        (
            w
            * point_distance(
                lottery.graph, p, evaluate_selector(lottery.graph, selector, profile)
            )
            for p in profile
            for w, selector in zip(weights, lottery.selectors, strict=True)
        ),
        fmpq(0),
    )
    candidate_cost = sum(
        (point_distance(lottery.graph, p, candidate) for p in profile), fmpq(0)
    )
    assert mechanism == fmpq(witness["mechanism_cost"])
    assert candidate_cost == fmpq(witness["candidate_cost"])
    assert (
        fmpq(witness["alpha"]) * candidate_cost - mechanism
        == fmpq(witness["difference"])
        < 0
    )


def test_sp_constant_false_finite_factor_fails_at_collocated_reports():
    from upper_bound_verifier.approximation import check_approximation_root
    from upper_bound_verifier.comparison import check_comparison_root
    from upper_bound_verifier.sp import check_sp_root

    lottery = lottery_fixture(weight=lambda p: (fmpq(0), fmpq(0), fmpq(1)))
    for agent in (0, 1):
        sp = comparison_cube(lottery.graph, SPKey(agent, (0, 0, 0)), lottery)
        assert isinstance(check_sp_root(lottery, sp), Verified)
    key = ApproximationKey(ReportCandidate(1), (0, 0))
    root = comparison_cube(lottery.graph, key, lottery)
    result = check_approximation_root(lottery, root, fmpq(1000000))
    assert isinstance(result, Failure) and result.kind is FailureKind.COUNTEREXAMPLE
    assert result.code == "approximation_violation"
    assert result.witness is not None
    assert result.witness["profile"] == [{"vertex": "b"}, {"vertex": "b"}]
    assert result.witness["candidate_cost"] == "0"
    assert result.witness["mechanism_cost"] == "2"
    assert result.witness["difference"] == "-2"
    replay(lottery, check_comparison_root(lottery, root), result)


def test_two_agent_dictatorship_certifies_all_candidates_at_factor_one():
    from upper_bound_verifier.approximation import check_approximation_root

    lottery = lottery_fixture()
    for agent in (0, 1):
        key = ApproximationKey(ReportCandidate(agent), (0, 0))
        root = comparison_cube(lottery.graph, key, lottery)
        assert isinstance(check_approximation_root(lottery, root, fmpq(1)), Verified)


def graph_lottery(graph, agents=2, weight=None, constant=None):
    weight = (fmpq(1), fmpq(0), fmpq(0)) if weight is None else weight
    roots, vertices, _ = meshes(graph, agents)
    roots = tuple(
        replace(
            r,
            simplices=tuple(
                replace(
                    c,
                    weights=tuple(
                        weight if not callable(weight) else weight(vertices[v].point)
                        for v in c.vertices
                    ),
                )
                for c in r.simplices
            ),
        )
        for r in roots
    )
    return check_lottery_admissibility(
        graph,
        agents,
        (
            PeakSelector(0),
            PeakSelector(agents - 1),
            ConstantSelector(constant or VertexPoint(graph.vertices[0])),
        ),
        roots,
        vertices,
    )


def approximation_grid(lottery, key, cuts=()):
    """Genuine grid; branches chosen independently from endpoint route formulas.

    Supported examples have one branch valid on every grid-simplex vertex.
    This constructor supplies certificate records, never checked evidence.
    """
    roots, vertices, _ = meshes(
        lottery.graph, lottery.agents, cuts=lambda key, axis: cuts
    )
    raw = next(r for r in roots if r.key.edges == key.edges)
    loc = SourceLocation("approximation.jsonl", 123, key)
    graph = lottery.graph
    records = []
    for record in raw.simplices:
        profiles = tuple(vertices[v].point for v in record.vertices)
        coordinates = tuple(
            tuple(
                chart_coordinate(graph, p, e)
                for e, p in zip(key.edges, profile, strict=True)
            )
            for profile in profiles
        )

        def route(i, right, coordinates=coordinates, profiles=profiles):
            left_edge = key.edges[i]
            if isinstance(right, int):
                right_edge, y = key.edges[right], tuple(p[right] for p in coordinates)
            elif isinstance(right, EdgePoint):
                right_edge, y = right.edge, (right.coordinate,) * len(profiles)
            else:
                assert isinstance(right, VertexPoint)
                values = tuple(
                    tuple(
                        (p[i] if a == 0 else 1 - p[i])
                        + graph.vertex_distance(graph.edges[left_edge][a], right.vertex)
                        for p in coordinates
                    )
                    for a in (0, 1)
                )
                return next(
                    a
                    for a, candidate in enumerate(values)
                    if all(
                        candidate[j] == min(v[j] for v in values)
                        for j in range(len(profiles))
                    )
                )
            if left_edge == right_edge:
                gaps = tuple(p[i] - z for p, z in zip(coordinates, y, strict=True))
                assert all(x >= 0 for x in gaps) or all(x <= 0 for x in gaps)
                return 0 if all(x >= 0 for x in gaps) else 1
            values = tuple(
                tuple(
                    (p[i] if a == 0 else 1 - p[i])
                    + (z if b == 0 else 1 - z)
                    + graph.vertex_distance(
                        graph.edges[left_edge][a], graph.edges[right_edge][b]
                    )
                    for p, z in zip(coordinates, y, strict=True)
                )
                for a in (0, 1)
                for b in (0, 1)
            )
            return next(
                a
                for a, candidate in enumerate(values)
                if all(
                    candidate[j] == min(v[j] for v in values)
                    for j in range(len(profiles))
                )
            )

        branches = tuple(
            route(
                i,
                selector.agent
                if isinstance(selector, PeakSelector)
                else selector.point,
            )
            for i in range(lottery.agents)
            for selector in lottery.selectors
        )
        candidate = (
            key.candidate.agent
            if isinstance(key.candidate, ReportCandidate)
            else VertexPoint(key.candidate.vertex)
        )
        branches += tuple(route(i, candidate) for i in range(lottery.agents))
        # Grid cells refine the original monotone attribution simplices.
        centroid = tuple(
            sum((p[j] for p in coordinates), fmpq(0)) / len(profiles)
            for j in range(lottery.agents)
        )
        region = next(
            name
            for name, geometry in lottery.geometry.roots[
                AttributionKey(key.edges)
            ].coverage.simplices.items()
            if geometry.contains(centroid)
        )
        records.append(
            ComparisonSimplex(
                record.id,
                record.vertices,
                region,
                None,
                branches,
                replace(loc, cell=record.id),
            )
        )
    return replace(
        raw,
        key=key,
        vertices=tuple(
            replace(v, location=loc)
            for v in vertices.values()
            if v.id in {name for c in raw.simplices for name in c.vertices}
        ),
        simplices=tuple(records),
        location=loc,
    )


def test_three_agents_every_social_term_matches_direct_costs_with_nonzero_constant():
    from upper_bound_verifier.approximation import (
        approximation_residual,
        check_approximation_cell,
    )

    def weight(profile):
        x = fmpq(profile[2] == VertexPoint("b"))
        return (1 - x) / 3, 2 * (1 - x) / 3, x

    lottery = lottery_fixture(3, weight, EdgePoint(0, fmpq(1, 3)))
    key = ApproximationKey(ReportCandidate(1), (0, 0, 0))
    checked = check_comparison_root(
        lottery, approximation_grid(lottery, key, (fmpq(1, 3),))
    )
    alpha = fmpq(7, 3)
    negative = 0
    for cell in checked.cells.values():
        matrix = cell.geometry.vertices
        points = [tuple(matrix[i, j] for i in range(3)) for j in range(4)]
        points.append(
            tuple(sum((matrix[i, j] for j in range(4)), fmpq(0)) / 4 for i in range(3))
        )
        q = approximation_residual(cell, alpha)
        for x0, x1, x2 in points:
            weights = ((1 - x2) / 3, 2 * (1 - x2) / 3, x2)
            mechanism = sum(
                (
                    w * abs(x - output)
                    for x in (x0, x1, x2)
                    for w, output in zip(weights, (x0, x2, fmpq(1, 3)), strict=True)
                ),
                fmpq(0),
            )
            candidate = sum((abs(x - x1) for x in (x0, x1, x2)), fmpq(0))
            assert evaluate(q, (x0, x1, x2)) == alpha * candidate - mechanism
        outcome = check_approximation_cell(lottery, checked, cell.record.id, alpha)
        if isinstance(outcome, Failure):
            negative += 1
            replay(lottery, checked, outcome)
    assert negative > 0


def test_nonoptimal_candidate_still_yields_a_genuine_violation():
    from upper_bound_verifier.approximation import check_approximation_cell

    graph = Graph(("h", "a", "b", "c"), (("h", "a"), ("h", "b"), ("h", "c")))
    lottery = graph_lottery(
        graph, constant=VertexPoint("c"), weight=(fmpq(0), fmpq(0), fmpq(1))
    )
    key = ApproximationKey(VertexCandidate("h"), (0, 0))
    checked = check_comparison_root(
        lottery, approximation_grid(lottery, key, (fmpq(1, 2),))
    )
    # On this closed upper-grid simplex reports collocate away from h at its
    # first vertex. The hub costs >0 while the report itself achieves OPT=0.
    cell = next(
        c
        for c in checked.cells.values()
        if all(
            c.geometry.vertices[i, j] >= fmpq(1, 2) for i in range(2) for j in range(3)
        )
    )
    failure = check_approximation_cell(lottery, checked, cell.record.id, 1)
    assert isinstance(failure, Failure) and failure.witness is not None
    profile = tuple(
        parse_point(graph, p) for p in cast(list[object], failure.witness["profile"])
    )
    assert profile[0] == profile[1]
    assert fmpq(failure.witness["candidate_cost"]) > 0
    assert sum((point_distance(graph, p, profile[0]) for p in profile), fmpq(0)) == 0
    assert failure.witness["candidate"] == VertexCandidate("h").to_data()
    replay(lottery, checked, failure)


def test_branch_candidates_omit_degree_two_and_unreported_leaves():
    from upper_bound_verifier.approximation import check_approximation_root

    graph = Graph(
        ("h", "m", "a", "b", "c"), (("h", "m"), ("m", "a"), ("h", "b"), ("h", "c"))
    )
    assert approximation_candidates(graph, 3) == (
        ReportCandidate(0),
        ReportCandidate(1),
        ReportCandidate(2),
        VertexCandidate("h"),
    )
    lottery = graph_lottery(graph, 3)
    key = ApproximationKey(VertexCandidate("h"), (0, 0, 0))
    assert isinstance(
        check_approximation_root(lottery, approximation_grid(lottery, key), 2), Verified
    )


def test_four_cycle_collocated_interior_reports_and_returning_arc():
    from upper_bound_verifier.approximation import (
        approximation_residual,
        check_approximation_cell,
    )

    graph = Graph(
        ("a", "b", "c", "d"), (("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"))
    )
    lottery = graph_lottery(
        graph, constant=VertexPoint("c"), weight=(fmpq(0), fmpq(0), fmpq(1))
    )
    assert approximation_candidates(graph, 2) == (
        ReportCandidate(0),
        ReportCandidate(1),
    )
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    checked = check_comparison_root(lottery, approximation_grid(lottery, key))
    point = (fmpq(1, 2),) * 2
    for cell in checked.cells.values():
        assert cell.geometry.contains(point)
        assert evaluate(approximation_residual(cell, 100), point) == -3
        result = check_approximation_cell(lottery, checked, cell.record.id, 100)
        assert isinstance(result, Failure)
        replay(lottery, checked, result)
    # Removing the single report A leaves an arc of length4 returning to A.
    # Every distance is min(s,4-s); social cost is twice that distance.
    report = EdgePoint(0, fmpq(1, 2))
    assert point_distance(graph, report, report) == 0
    for edge, coordinate, expected in (
        (0, fmpq(3, 4), fmpq(1, 4)),
        (1, fmpq(1, 2), 1),
        (2, fmpq(1, 2), 2),
        (3, fmpq(1, 2), 1),
    ):
        assert point_distance(graph, report, EdgePoint(edge, coordinate)) == expected


@pytest.mark.parametrize("attack", ["branch", "region", "containment", "coverage"])
def test_bad_root_after_negative_cell_is_a_certificate_failure(attack):
    from upper_bound_verifier.approximation import check_approximation_root

    lottery = lottery_fixture(weight=lambda p: (fmpq(0), fmpq(0), fmpq(1)))
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    root = comparison_cube(lottery.graph, key, lottery)
    *rest, last = root.simplices
    if attack == "branch":
        # Peak1 has zero weight here; its distance must still be valid.
        last = replace(
            last,
            branches=(last.branches[0], 1 - last.branches[1], *last.branches[2:]),
        )
    elif attack == "region":
        last = replace(last, truthful="missing")
    elif attack == "containment":
        last = replace(
            last, truthful=next(r for r in lottery.regions if r != last.truthful)
        )
    else:
        rest = []
    with pytest.raises(VerificationError) as caught:
        check_approximation_root(lottery, replace(root, simplices=(*rest, last)), 1)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code != "approximation_violation"


def test_corrupted_negative_formula_refuses_original_lottery_disagreement():
    from upper_bound_verifier.approximation import check_approximation_cell

    lottery = lottery_fixture()
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    checked = check_comparison_root(
        lottery, comparison_cube(lottery.graph, key, lottery)
    )
    name, cell = next(iter(checked.cells.items()))
    bad = replace(cell, distances=(AffineExpression((0, 0), 100), *cell.distances[1:]))
    with pytest.raises(VerificationError) as caught:
        check_approximation_cell(
            lottery, replace(checked, cells={**checked.cells, name: bad}), name, 1
        )
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "internal_error_approximation_replay"


@pytest.mark.parametrize("alpha", [0, fmpq(2, 3), True, 1.0, "1", None])
def test_alpha_must_be_exact_and_at_least_one(alpha):
    from upper_bound_verifier.approximation import check_approximation_root

    lottery = lottery_fixture()
    root = comparison_cube(
        lottery.graph, ApproximationKey(ReportCandidate(0), (0, 0)), lottery
    )
    with pytest.raises(VerificationError) as caught:
        check_approximation_root(lottery, root, alpha)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code.startswith("approximation_alpha_")


def test_counterexample_keeps_actual_source_root_cell_candidate_and_exact_json():
    import json

    from upper_bound_verifier.approximation import check_approximation_root

    lottery = lottery_fixture(weight=lambda p: (fmpq(0), fmpq(0), fmpq(1)))
    key = ApproximationKey(ReportCandidate(1), (0, 0))
    root = comparison_cube(lottery.graph, key, lottery)
    root = replace(
        root,
        simplices=tuple(
            replace(
                c,
                location=SourceLocation(
                    "approximation.jsonl",
                    271,
                    ApproximationKey(ReportCandidate(0), (0, 0)),
                    c.id,
                ),
            )
            for c in root.simplices
        ),
    )
    result = check_approximation_root(lottery, root, fmpq(7, 3))
    assert (
        isinstance(result, Failure)
        and result.location is not None
        and result.witness is not None
    )
    assert result.location["root"] == key.to_data()
    assert (
        result.location["candidate"]
        == result.witness["candidate"]
        == key.candidate.to_data()
    )
    assert (
        result.location["file"] == "approximation.jsonl"
        and result.location["line"] == 271
    )
    assert result.location["cell"] in {c.id for c in root.simplices}
    assert json.loads(json.dumps(result.to_dict()))["witness"]["alpha"] == "7/3"


def test_approximation_interfaces_refuse_sp_raw_and_non_evidence_inputs():
    from upper_bound_verifier.approximation import (
        approximation_residual,
        check_approximation_cell,
        check_approximation_root,
    )

    lottery = lottery_fixture()
    root = comparison_cube(lottery.graph, SPKey(0, (0, 0, 0)), lottery)
    with pytest.raises(VerificationError) as caught:
        check_approximation_root(lottery, root, 1)
    assert caught.value.failure.code == "approximation_root_type"
    checked = check_comparison_root(lottery, root)
    with pytest.raises(VerificationError):
        approximation_residual(next(iter(checked.cells.values())), 1)
    with pytest.raises(VerificationError):
        check_approximation_root(cast(AdmissibleLottery, None), root, 1)
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    checked = check_comparison_root(
        lottery, comparison_cube(lottery.graph, key, lottery)
    )
    with pytest.raises(VerificationError) as caught:
        check_approximation_cell(lottery, checked, "missing", 1)
    assert caught.value.failure.code == "approximation_cell_reference"
    with pytest.raises(VerificationError):
        approximation_residual(cast(Any, None), 1)


def test_three_leaf_star_hub_detects_false_factor_that_report_candidates_miss():
    from upper_bound_verifier.approximation import approximation_residual

    graph = Graph(("h", "a", "b", "c"), (("h", "a"), ("h", "b"), ("h", "c")))
    lottery = graph_lottery(graph, 3)
    point = (fmpq(1),) * 3
    for candidate in approximation_candidates(graph, 3):
        key = ApproximationKey(candidate, (0, 1, 2))
        checked = check_comparison_root(lottery, approximation_grid(lottery, key))
        residuals = [
            evaluate(approximation_residual(c, 1), point)
            for c in checked.cells.values()
            if c.geometry.contains(point)
        ]
        assert residuals and all(
            x == (-1 if isinstance(candidate, VertexCandidate) else 0)
            for x in residuals
        )


def test_root_verification_reaches_negative_cell_after_a_verified_cell():
    from upper_bound_verifier.approximation import (
        check_approximation_cell,
        check_approximation_root,
    )

    lottery = lottery_fixture(3)
    key = ApproximationKey(ReportCandidate(1), (0, 0, 0))
    raw = comparison_cube(lottery.graph, key, lottery)
    checked = check_comparison_root(lottery, raw)
    good, bad = [], []
    for record in raw.simplices:
        result = check_approximation_cell(lottery, checked, record.id, 1)
        (good if isinstance(result, Verified) else bad).append(record)
    assert good and bad
    outcome = check_approximation_root(
        lottery, replace(raw, simplices=tuple(good + bad)), 1
    )
    assert isinstance(outcome, Failure) and outcome.location is not None
    assert outcome.location["cell"] in {r.id for r in bad}


def test_invalid_global_attribution_cannot_reach_approximation_counterexample():
    from upper_bound_verifier.approximation import check_approximation_root

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
        key = ApproximationKey(ReportCandidate(0), (0, 0))
        check_approximation_root(lottery, comparison_cube(graph, key, lottery), 1)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "probability_normalization"


def test_checked_stream_roots_certify_every_report_candidate():
    from upper_bound_verifier.approximation import check_checked_approximation_root
    from upper_bound_verifier.comparison import ComparisonStreams
    from upper_bound_verifier.reader import approximation_root_keys

    lottery = lottery_fixture()
    streams = ComparisonStreams(lottery)
    roots = (
        comparison_cube(lottery.graph, key, lottery)
        for key in approximation_root_keys(lottery.graph, lottery.agents)
    )
    count = 0
    for checked in streams.iter_approximation_roots(roots):
        assert isinstance(
            check_checked_approximation_root(lottery, checked, 1), Verified
        )
        count += 1
    assert count == 2
    # APX exhaustion alone is not full comparison exhaustion or acceptance.
    assert not streams.streams_exhausted
