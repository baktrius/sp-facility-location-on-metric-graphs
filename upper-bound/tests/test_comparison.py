"""Independent comparison enumeration and genuine covered-cell behavior."""

from dataclasses import replace
from itertools import permutations
from typing import cast

import pytest
from flint import fmpq
from test_charts import meshes
from test_reader import records, tiny_bundle, write_records

from upper_bound_verifier.distance import EdgeExpression
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.graph import (
    ConstantSelector,
    Graph,
    PeakSelector,
    VertexPoint,
    point_from_chart,
)
from upper_bound_verifier.lottery import check_lottery_admissibility
from upper_bound_verifier.reader import (
    ApproximationKey,
    AttributionKey,
    BundleReader,
    ComparisonSimplex,
    LeafNode,
    ProfileVertex,
    ReportCandidate,
    RootBlock,
    SourceLocation,
    SPKey,
    SplitNode,
    VertexCandidate,
    approximation_candidates,
    approximation_root_keys,
    attribution_root_keys,
    sp_root_keys,
)


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize("attack", ["outside_chart", "duplicate_id", "duplicate_point"])
def test_local_vertex_validation_retains_its_record_line_and_actual_root(
    stream, attack
):
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b", "c"), (("a", "b"), ("c", "b")))
    lottery = affine_lottery(graph)
    key = (
        SPKey(0, (0, 0, 0))
        if stream == "sp"
        else ApproximationKey(ReportCandidate(0), (0, 0))
    )
    root = comparison_cube(graph, key, lottery)
    # This unused record is still fully validated. Its source root is stale;
    # the diagnostic must retain its actual line and the checked block's key.
    stale = (
        SPKey(1, (0, 0, 0))
        if stream == "sp"
        else ApproximationKey(ReportCandidate(1), (0, 0))
    )
    loc = SourceLocation(stream + ".jsonl", 987, stale)
    if attack == "outside_chart":
        vertex = ProfileVertex(
            "unused",
            (VertexPoint("c"), *(VertexPoint("a") for _ in range(len(key.edges) - 1))),
            loc,
        )
        code = "simplex_root_chart"
    elif attack == "duplicate_id":
        vertex = ProfileVertex(
            root.vertices[0].id,
            tuple(
                point_from_chart(graph, 0, fmpq(i + 1, len(key.edges) + 2))
                for i in range(len(key.edges))
            ),
            loc,
        )
        code = "reference_duplicate_vertex"
    else:
        vertex = ProfileVertex("unused", root.vertices[0].point, loc)
        code = "reference_duplicate_vertex"
    root = replace(root, vertices=(*root.vertices, vertex))
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == code
    assert caught.value.failure.location == replace(loc, root=key).to_dict()


def test_independently_list_every_labeled_root_and_candidate():
    graph = Graph(("a", "b", "c"), (("b", "a"), ("b", "c")))
    pairs = [(0, 0), (0, 1), (1, 0), (1, 1)]
    triples = [
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 1, 1),
        (1, 0, 0),
        (1, 0, 1),
        (1, 1, 0),
        (1, 1, 1),
    ]
    assert list(attribution_root_keys(graph, 2)) == [AttributionKey(x) for x in pairs]
    assert list(sp_root_keys(graph, 2)) == [
        SPKey(i, edges) for i in (0, 1) for edges in triples
    ]
    assert approximation_candidates(graph, 2) == (
        ReportCandidate(0),
        ReportCandidate(1),
    )
    assert list(approximation_root_keys(graph, 2)) == [
        ApproximationKey(ReportCandidate(i), edges) for i in (0, 1) for edges in pairs
    ]
    # Branch vertices stay in document order rather than lexical label order.
    branching = Graph(
        ("z", "y", "a", "b", "c", "d"),
        (("z", "a"), ("z", "b"), ("z", "y"), ("y", "c"), ("y", "d")),
    )
    assert approximation_candidates(branching, 2) == (
        ReportCandidate(0),
        ReportCandidate(1),
        VertexCandidate("z"),
        VertexCandidate("y"),
    )
    assert len(list(sp_root_keys(branching, 2))) == 250
    assert len(list(approximation_root_keys(branching, 2))) == 100


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize(
    "attack",
    ["missing_last", "empty", "duplicate", "reordered", "wrong_index", "extra"],
)
def test_reader_requires_the_entire_comparison_sequence(tmp_path, stream, attack):
    tiny_bundle(tmp_path)
    filename = stream + ".jsonl"
    rows = records(tmp_path, filename)
    end = next(i for i, row in enumerate(rows) if row["type"] == "end") + 1
    first, second = rows[:end], rows[end:]
    changed = {
        "missing_last": first,
        "empty": [],
        "duplicate": first + first,
        "reordered": second + first,
        "wrong_index": second,
        "extra": rows + second,
    }[attack]
    write_records(tmp_path, filename, changed)
    reader = BundleReader(tmp_path)
    iterator = (
        reader.iter_sp_roots() if stream == "sp" else reader.iter_approximation_roots()
    )
    with pytest.raises(VerificationError) as caught:
        tuple(iterator)
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code in {
        "reference_root_sequence",
        "reference_root_order",
    }
    assert not reader.streams_exhausted


def affine_lottery(graph, agents=2, reverse_vertices=False, coefficients=None):
    roots, vertices, _ = meshes(graph, agents)
    changed = []
    for root in roots:
        cells = []
        for cell in root.simplices:
            ids = tuple(reversed(cell.vertices)) if reverse_vertices else cell.vertices
            rows = []
            for v in ids:
                # This is one global affine lottery on a single edge; for
                # multi-edge tests use constant weights to make seams agree.
                x = (
                    fmpq(1, 3)
                    if len(graph.edges) > 1
                    else sum(
                        (
                            a * fmpq(p == VertexPoint(graph.edges[0][1]))
                            for a, p in zip(
                                coefficients
                                or (fmpq(1), *(fmpq(0) for _ in range(agents - 1))),
                                vertices[v].point,
                                strict=True,
                            )
                        ),
                        fmpq(0),
                    )
                )
                rows.append((x, 1 - x, fmpq(0)))
            cells.append(replace(cell, vertices=ids, weights=tuple(rows)))
        changed.append(replace(root, simplices=tuple(cells)))
    return check_lottery_admissibility(
        graph,
        agents,
        (
            PeakSelector(0),
            PeakSelector(agents - 1),
            ConstantSelector(VertexPoint(graph.vertices[0])),
        ),
        changed,
        vertices,
    )


def comparison_cube(graph, key, lottery):
    """A real monotone triangulation and exact routing tree, no forged checks.

    On a one-edge cube each coordinate order fixes all metric signs and both
    profile projections. Region selection uses independent order inequalities.
    """
    dimension = len(key.edges)
    loc = SourceLocation(
        "sp.jsonl" if isinstance(key, SPKey) else "approximation.jsonl", 1, key
    )
    local, ids_by_point, cells, nodes, orders = [], {}, [], [], {}
    for order in permutations(range(dimension)):
        point = [0] * dimension
        ids = []
        for axis in (None, *order):
            if axis is not None:
                point[axis] = 1
            intrinsic = tuple(point)
            if intrinsic not in ids_by_point:
                name = f"w{len(local)}"
                ids_by_point[intrinsic] = name
                local.append(
                    ProfileVertex(
                        name,
                        tuple(
                            point_from_chart(graph, e, x)
                            for e, x in zip(key.edges, point, strict=True)
                        ),
                        loc,
                    )
                )
            ids.append(ids_by_point[intrinsic])
        axes = tuple(range(lottery.agents))
        altered = (
            tuple(dimension - 1 if j == key.agent else j for j in axes)
            if isinstance(key, SPKey)
            else None
        )

        def region(projection, order=order):
            expected = AttributionKey(tuple(key.edges[j] for j in projection))
            # meshes() lists simplices in permutation order, with those same
            # monotone 0->1 chains. Sorting axes by this cell's order selects it.
            projected_order = tuple(
                sorted(range(lottery.agents), key=lambda j: order.index(projection[j]))
            )
            index = list(permutations(range(lottery.agents))).index(projected_order)
            return lottery.geometry.roots[expected].coverage.root.simplices[index].id

        agent = key.agent if isinstance(key, SPKey) else None

        def branch(left, right, order=order):
            return 0 if order.index(left) < order.index(right) else 1

        # selector0=peak0, selector1=peak(n-1), selector2=constant(first endpoint).
        if agent is not None:
            branches = tuple(branch(agent, j) for j in (0, lottery.agents - 1)) + (0,)
            branches += tuple(
                branch(agent, dimension - 1 if j == agent else j)
                for j in (0, lottery.agents - 1)
            ) + (0,)
        else:
            branches = tuple(
                b
                for i in axes
                for b in (branch(i, 0), branch(i, lottery.agents - 1), 0)
            )
            if isinstance(key.candidate, ReportCandidate):
                branches += tuple(branch(i, key.candidate.agent) for i in axes)
            else:
                branches += (0,) * lottery.agents
        name = f"S{len(cells)}"
        cells.append(
            ComparisonSimplex(
                name,
                tuple(ids),
                region(axes),
                region(altered) if altered is not None else None,
                branches,
                replace(loc, cell=name),
            )
        )
        orders[name] = order

    def route(names, pairs, node):
        if len(names) == 1:
            nodes.append(LeafNode(node, names[0], loc))
            return
        (i, j), *rest = pairs
        minus = [x for x in names if orders[x].index(i) > orders[x].index(j)]
        plus = [x for x in names if x not in minus]
        if not minus or not plus:
            route(names, rest, node)
            return
        nodes.append(
            SplitNode(
                node,
                tuple(fmpq(int(k == i) - int(k == j)) for k in range(dimension)),
                fmpq(0),
                node + "m",
                node + "p",
                loc,
            )
        )
        route(minus, rest, node + "m")
        route(plus, rest, node + "p")

    route(list(orders), [(i, j) for i in range(dimension) for j in range(i)], "root")
    return RootBlock(key, "root", tuple(local), tuple(cells), tuple(nodes), loc)


def test_covered_sp_root_recovers_original_ordered_affine_weights():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph, reverse_vertices=True)
    root = comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery)
    checked = check_comparison_root(lottery, root)
    assert checked.coverage.volume == 1
    assert len(checked.cells) == 6
    for cell in checked.cells.values():
        assert cell.deviated_weights is not None
        x = tuple(
            sum((cell.geometry.vertices[i, j] for j in range(4)), fmpq(0)) / 4
            for i in range(3)
        )
        assert tuple(w.evaluate(x) for w in cell.truthful_weights) == (
            x[0],
            1 - x[0],
            0,
        )
        assert tuple(w.evaluate(x) for w in cell.deviated_weights) == (
            x[2],
            1 - x[2],
            0,
        )
        assert len(cell.distances) == 6  # The zero-weight constant is retained.
        assert tuple(d.evaluate(x) for d in cell.distances) == (
            0,
            abs(x[0] - x[1]),
            x[0],
            abs(x[0] - x[2]),
            abs(x[0] - x[1]),
            x[0],
        )


def test_typed_extra_nonroot_cannot_be_mistaken_for_eof():
    from upper_bound_verifier.comparison import ComparisonStreams

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    streams = ComparisonStreams(lottery)
    tuple(
        streams.iter_sp_roots(
            comparison_cube(graph, SPKey(i, (0, 0, 0)), lottery) for i in (0, 1)
        )
    )
    roots = [
        comparison_cube(graph, ApproximationKey(ReportCandidate(i), (0, 0)), lottery)
        for i in (0, 1)
    ]
    with pytest.raises(VerificationError) as caught:
        tuple(streams.iter_approximation_roots([*roots, cast(RootBlock, None)]))
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "comparison_root_type"
    assert not streams.streams_exhausted


def test_three_agents_agent_two_four_coordinates_replaces_only_its_report():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(
        graph,
        agents=3,
        reverse_vertices=True,
        coefficients=(fmpq(1, 6), fmpq(1, 3), fmpq(1, 2)),
    )
    root = comparison_cube(graph, SPKey(2, (0, 0, 0, 0)), lottery)
    checked = check_comparison_root(lottery, root)
    assert len(checked.cells) == 24
    for cell in checked.cells.values():
        assert cell.deviated_weights is not None
        matrix = cell.geometry.vertices
        samples = [tuple(matrix[i, j] for i in range(4)) for j in range(5)]
        samples.append(
            tuple(sum((matrix[i, j] for j in range(5)), fmpq(0)) / 5 for i in range(4))
        )
        for x in samples:
            assert tuple(d.evaluate(x) for d in cell.distances) == (
                abs(x[2] - x[0]),
                0,
                x[2],
                abs(x[2] - x[0]),
                abs(x[2] - x[3]),
                x[2],
            )
            truth = (x[0] + 2 * x[1] + 3 * x[2]) / 6
            deviation = (x[0] + 2 * x[1] + 3 * x[3]) / 6
            assert tuple(w.evaluate(x) for w in cell.truthful_weights) == (
                truth,
                1 - truth,
                0,
            )
            assert tuple(w.evaluate(x) for w in cell.deviated_weights) == (
                deviation,
                1 - deviation,
                0,
            )
        # The term descriptors keep true x2 on both sides of the group split,
        # peak0 fixed, and only peak2 uses the last (z) coordinate.
        x = (fmpq(1, 7), fmpq(2, 7), fmpq(3, 7), fmpq(4, 7))
        left, kept, replaced = (
            cell.terms[3].left,
            cell.terms[3].right,
            cell.terms[4].right,
        )
        assert isinstance(left, EdgeExpression)
        assert isinstance(kept, EdgeExpression)
        assert isinstance(replaced, EdgeExpression)
        assert left.coordinate.evaluate(x) == x[2]
        assert kept.coordinate.evaluate(x) == x[0]
        assert replaced.coordinate.evaluate(x) == x[3]


@pytest.mark.parametrize("agent", [0, 1])
def test_apx_agent_major_selector_minor_order_and_coincident_report_candidates(agent):
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    root = comparison_cube(
        graph, ApproximationKey(ReportCandidate(agent), (0, 0)), lottery
    )
    checked = check_comparison_root(lottery, root)
    for cell in checked.cells.values():
        assert cell.deviated_weights is None
        matrix = cell.geometry.vertices
        x = tuple(sum((matrix[i, j] for j in range(3)), fmpq(0)) / 3 for i in range(2))
        gap = abs(x[0] - x[1])
        assert tuple(d.evaluate(x) for d in cell.distances) == (
            0,
            gap,
            x[0],
            gap,
            0,
            x[1],
            abs(x[0] - x[agent]),
            abs(x[1] - x[agent]),
        )
        # Reports coincide at endpoints; each candidate remains a separate root.
        assert tuple(d.evaluate((0, 0)) for d in cell.distances) == (0,) * 8


def test_branching_vertex_candidate_has_all_social_and_candidate_terms():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("hub", "a", "b", "c"), (("hub", "a"), ("b", "hub"), ("hub", "c")))
    lottery = affine_lottery(graph)
    root = comparison_cube(
        graph, ApproximationKey(VertexCandidate("hub"), (0, 0)), lottery
    )
    checked = check_comparison_root(lottery, root)
    for cell in checked.cells.values():
        x = tuple(
            sum((cell.geometry.vertices[i, j] for j in range(3)), fmpq(0)) / 3
            for i in range(2)
        )
        gap = abs(x[0] - x[1])
        assert tuple(d.evaluate(x) for d in cell.distances) == (
            0,
            gap,
            x[0],
            gap,
            0,
            x[1],
            x[0],
            x[1],
        )


@pytest.mark.parametrize("mode", ["truthful", "deviated"])
def test_plausible_region_from_the_wrong_edge_root_is_rejected(mode):
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b", "c"), (("a", "b"), ("b", "c")))
    lottery = affine_lottery(graph)
    key = SPKey(1, (0, 0, 1))
    root = comparison_cube(graph, key, lottery)
    wrong = lottery.geometry.roots[AttributionKey((1, 0))].coverage.root.simplices[0].id
    first, *rest = root.simplices
    root = replace(root, simplices=(replace(first, **{mode: wrong}), *rest))
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.code == "region_root"
    assert caught.value.failure.kind is FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["cell"] == first.id
    assert caught.value.failure.location["root"] == key.to_data()


@pytest.mark.parametrize("mode", ["truthful", "deviated"])
def test_region_containment_checks_the_last_projected_vertex(mode):
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    root = comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery)
    # The first chain has only one offending projection in the opposite
    # triangle. Put that point last so checks that skip a final vertex fail.
    first, *rest = root.simplices
    opposite = next(r for r in lottery.regions if r != getattr(first, mode))
    missed = 1 if mode == "truthful" else 2
    first = replace(
        first,
        vertices=tuple(v for j, v in enumerate(first.vertices) if j != missed)
        + (first.vertices[missed],),
        **{mode: opposite},
    )
    root = replace(root, simplices=(first, *rest))
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.code == "region_containment"
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["cell"] == first.id


@pytest.mark.parametrize("stream", ["sp", "approximation"])
@pytest.mark.parametrize(
    "attack", ["missing", "empty", "duplicate", "reordered", "extra"]
)
def test_checked_streams_independently_require_exact_completeness(stream, attack):
    from upper_bound_verifier.comparison import ComparisonStreams

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    keys = [
        SPKey(i, (0, 0, 0))
        if stream == "sp"
        else ApproximationKey(ReportCandidate(i), (0, 0))
        for i in (0, 1)
    ]
    roots = [comparison_cube(graph, k, lottery) for k in keys]
    changed = {
        "missing": roots[:1],
        "empty": [],
        "duplicate": roots[:1] * 2,
        "reordered": roots[::-1],
        "extra": roots + roots[-1:],
    }[attack]
    streams = ComparisonStreams(lottery)
    iterator = (
        streams.iter_sp_roots(changed)
        if stream == "sp"
        else streams.iter_approximation_roots(changed)
    )
    with pytest.raises(VerificationError) as caught:
        tuple(iterator)
    assert caught.value.failure.code == "reference_root_sequence"
    assert not streams.streams_exhausted


def test_checked_streams_do_not_mark_completion_after_last_yield_or_close():
    from upper_bound_verifier.comparison import ComparisonStreams

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    streams = ComparisonStreams(lottery)
    sp = streams.iter_sp_roots(
        comparison_cube(graph, SPKey(i, (0, 0, 0)), lottery) for i in (0, 1)
    )
    apx = streams.iter_approximation_roots(
        comparison_cube(graph, ApproximationKey(ReportCandidate(i), (0, 0)), lottery)
        for i in (0, 1)
    )
    tuple(sp)
    next(apx)
    last = next(apx)
    assert last.coverage.root.key == ApproximationKey(ReportCandidate(1), (0, 0))
    assert not streams.streams_exhausted
    with pytest.raises(StopIteration):
        next(apx)
    assert streams.streams_exhausted
    with pytest.raises(ValueError):
        streams.iter_sp_roots([])
    closed = ComparisonStreams(lottery)
    unfinished = closed.iter_sp_roots(
        [comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery)]
    )
    next(unfinished)
    unfinished.close()
    assert not closed.streams_exhausted


@pytest.mark.parametrize(
    "key",
    [
        SPKey(False, (0, 0, 0)),
        SPKey(0, (False, 0, 0)),
        ApproximationKey(ReportCandidate(False), (0, 0)),
        ApproximationKey(VertexCandidate("a"), (0, 0)),
        SPKey(2, (0, 0, 0)),
        SPKey(0, (0, 0)),
        SPKey(0, (0, 0, 1)),
    ],
)
def test_direct_typed_root_boundary_rejects_aliases_and_wrong_references(key):
    from upper_bound_verifier.comparison import comparison_distance_terms

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    with pytest.raises(VerificationError):
        comparison_distance_terms(lottery, key)


@pytest.mark.parametrize(
    "attack", ["short", "extra", "bool", "zero_weight_wrong_branch"]
)
@pytest.mark.parametrize("stream", ["sp", "approximation"])
def test_every_branch_is_required_and_checked_including_zero_weight_terms(
    attack, stream
):
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    key = (
        SPKey(0, (0, 0, 0))
        if stream == "sp"
        else ApproximationKey(ReportCandidate(0), (0, 0))
    )
    root = comparison_cube(graph, key, lottery)
    first, *rest = root.simplices
    changed = {
        "short": first.branches[:-1],
        "extra": (*first.branches, 0),
        "bool": (*first.branches[:-1], False),
        "zero_weight_wrong_branch": (*first.branches[:5], 1, *first.branches[6:]),
    }[attack]
    root = replace(root, simplices=(replace(first, branches=changed), *rest))
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.code in {
        "distance_branch_count",
        "distance_branch_type",
        "distance_branch",
    }
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["cell"] == first.id
    if attack == "zero_weight_wrong_branch":
        assert caught.value.failure.location["term"] == 5


def test_substituted_selectors_keep_the_expected_edge_and_coordinate_at_endpoints():
    from upper_bound_verifier.comparison import comparison_distance_terms

    graph = Graph(("a", "b", "c"), (("a", "b"), ("c", "b")))
    lottery = affine_lottery(graph, agents=3)
    terms = comparison_distance_terms(lottery, SPKey(2, (0, 1, 0, 1)))
    assert len(terms) == 6
    left, kept, altered = terms[4].left, terms[3].right, terms[4].right
    assert (
        isinstance(left, EdgeExpression)
        and isinstance(kept, EdgeExpression)
        and isinstance(altered, EdgeExpression)
    )
    assert left.edge == kept.edge == 0
    assert altered.edge == 1
    for y in ((0, 1, 0, 1), (1, 0, 1, 0)):
        assert left.coordinate.evaluate(y) == y[2]
        assert kept.coordinate.evaluate(y) == y[0]
        assert altered.coordinate.evaluate(y) == y[3]


def test_typed_key_failure_retains_available_root_source_context():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    root = comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery)
    root = replace(root, key=SPKey(False, (0, 0, 0)))
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.code == "comparison_agent_type"
    assert (
        caught.value.failure.location == replace(root.location, root=root.key).to_dict()
    )


def test_genuine_cross_edge_deviation_uses_the_replacement_root_and_metric():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b", "c"), (("a", "b"), ("c", "b")))
    lottery = affine_lottery(graph)
    root = comparison_cube(graph, SPKey(1, (0, 0, 1)), lottery)
    # The two edges share their second endpoint b. The unique path between
    # their interior points has length (1-x1)+(1-z), endpoint route 11.
    root = replace(
        root,
        simplices=tuple(
            replace(c, branches=(*c.branches[:4], 3, c.branches[5]))
            for c in root.simplices
        ),
    )
    checked = check_comparison_root(lottery, root)
    truthful_ids = set(
        lottery.geometry.roots[AttributionKey((0, 0))].coverage.simplices
    )
    deviated_ids = set(
        lottery.geometry.roots[AttributionKey((0, 1))].coverage.simplices
    )
    for cell in checked.cells.values():
        assert cell.record.truthful in truthful_ids
        assert cell.record.deviated in deviated_ids
        matrix = cell.geometry.vertices
        samples = [tuple(matrix[i, j] for i in range(3)) for j in range(4)]
        samples.append(
            tuple(sum((matrix[i, j] for j in range(4)), fmpq(0)) / 4 for i in range(3))
        )
        for x in samples:
            assert tuple(d.evaluate(x) for d in cell.distances) == (
                abs(x[1] - x[0]),
                0,
                x[1],
                abs(x[1] - x[0]),
                2 - x[1] - x[2],
                x[1],
            )


def test_auxiliary_coverage_runs_before_region_formulas():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    root = comparison_cube(graph, SPKey(0, (0, 0, 0)), lottery)
    root = replace(root, simplices=root.simplices[:-1])
    with pytest.raises(VerificationError) as caught:
        check_comparison_root(lottery, root)
    assert caught.value.failure.code == "coverage_simplex_reference"


def test_nonconforming_auxiliary_cover_keeps_existing_mechanism_weights():
    from upper_bound_verifier.comparison import check_comparison_root

    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = tuple(
        replace(
            r,
            simplices=tuple(replace(c, weights=((fmpq(1),),) * 3) for c in r.simplices),
        )
        for r in roots
    )
    lottery = check_lottery_admissibility(
        graph, 2, (ConstantSelector(VertexPoint("a")),), roots, vertices
    )
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    loc = SourceLocation("approximation.jsonl", 1, key)
    points = ((0, 0), (1, 0), (1, 1), (0, 1), (fmpq(1, 2), fmpq(1, 2)))
    local = tuple(
        ProfileVertex(f"w{j}", tuple(point_from_chart(graph, 0, x) for x in p), loc)
        for j, p in enumerate(points)
    )
    lower, upper = roots[0].simplices
    # Split only the lower triangle at a midpoint of the shared diagonal.
    # Its two short edges meet the upper triangle's single long edge.
    cells = (
        ComparisonSimplex(
            "low0",
            ("w0", "w1", "w4"),
            lower.id,
            None,
            (0, 0, 0, 1),
            replace(loc, cell="low0"),
        ),
        ComparisonSimplex(
            "low1",
            ("w1", "w2", "w4"),
            lower.id,
            None,
            (0, 0, 0, 1),
            replace(loc, cell="low1"),
        ),
        ComparisonSimplex(
            "up",
            ("w0", "w2", "w3"),
            upper.id,
            None,
            (0, 0, 0, 0),
            replace(loc, cell="up"),
        ),
    )
    nodes = (
        SplitNode("root", (fmpq(1), fmpq(-1)), fmpq(0), "up", "lower", loc),
        LeafNode("up", "up", loc),
        SplitNode("lower", (fmpq(1), fmpq(1)), fmpq(1), "l0", "l1", loc),
        LeafNode("l0", "low0", loc),
        LeafNode("l1", "low1", loc),
    )
    checked = check_comparison_root(
        lottery, RootBlock(key, "root", local, cells, nodes, loc)
    )
    assert checked.coverage.volume == 1
    assert len(checked.cells) == 3
    assert all(
        c.truthful_weights[0].coefficients == (0, 0)
        and c.truthful_weights[0].constant == 1
        for c in checked.cells.values()
    )


def real_wire_bundle(directory):
    """Write real checked geometry with all one-edge comparison roots."""
    import json

    from upper_bound_verifier.graph import point_to_data

    graph = Graph(("a", "b"), (("a", "b"),))
    lottery = affine_lottery(graph)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "identity": {
                    "formulation": "metric_graph_upper",
                    "result": "unconditional",
                    "graph": {"vertices": ["a", "b"], "edges": [["a", "b"]]},
                    "agents": 2,
                    "selectors": [
                        {"kind": "peak", "agent": 0},
                        {"kind": "peak", "agent": 1},
                        {"kind": "constant", "point": {"vertex": "a"}},
                    ],
                },
                "certified_value": 1,
            }
        )
    )
    write_records(
        directory,
        "vertices.jsonl",
        [
            {"id": v.id, "point": [point_to_data(p) for p in v.point]}
            for v in lottery.vertices.values()
        ],
    )

    def write_roots(filename, roots):
        rows = []
        for root in roots:
            rows.append({"type": "root", "key": root.key.to_data(), "tree": root.tree})
            rows.extend(
                {
                    "type": "vertex",
                    "id": v.id,
                    "point": [point_to_data(p) for p in v.point],
                }
                for v in root.vertices
            )
            for c in root.simplices:
                data = {"type": "simplex", "id": c.id, "vertices": list(c.vertices)}
                if isinstance(c, ComparisonSimplex):
                    data.update(truthful=c.truthful, branches=list(c.branches))
                    if c.deviated is not None:
                        data["deviated"] = c.deviated
                else:
                    data["weights"] = [[str(w) for w in row] for row in c.weights]
                rows.append(data)
            for node in root.nodes:
                if isinstance(node, LeafNode):
                    rows.append(
                        {"type": "leaf", "id": node.id, "simplex": node.simplex}
                    )
                else:
                    rows.append(
                        {
                            "type": "split",
                            "id": node.id,
                            "normal": [str(x) for x in node.normal],
                            "offset": str(node.offset),
                            "minus": node.minus,
                            "plus": node.plus,
                        }
                    )
            rows.append({"type": "end"})
        write_records(directory, filename, rows)

    write_roots(
        "attribution.jsonl", [c.coverage.root for c in lottery.geometry.roots.values()]
    )
    write_roots(
        "sp.jsonl",
        [comparison_cube(graph, SPKey(i, (0, 0, 0)), lottery) for i in (0, 1)],
    )
    write_roots(
        "approximation.jsonl",
        [
            comparison_cube(
                graph, ApproximationKey(ReportCandidate(i), (0, 0)), lottery
            )
            for i in (0, 1)
        ],
    )


@pytest.mark.parametrize("trailing", [False, True])
def test_reader_and_checked_streams_complete_only_after_real_eof(tmp_path, trailing):
    from upper_bound_verifier.comparison import ComparisonStreams

    real_wire_bundle(tmp_path)
    reader = BundleReader(tmp_path)
    lottery = check_lottery_admissibility(
        reader.manifest.graph,
        reader.manifest.agents,
        reader.manifest.selectors,
        reader.attribution,
        reader.vertices,
    )
    streams = ComparisonStreams(lottery)
    tuple(streams.iter_sp_roots(reader.iter_sp_roots()))
    assert not streams.streams_exhausted and not reader.streams_exhausted
    if trailing:
        with (tmp_path / "approximation.jsonl").open("a") as target:
            target.write('{"type":"end"}\n')
    apx = streams.iter_approximation_roots(reader.iter_approximation_roots())
    next(apx)
    next(apx)
    assert not streams.streams_exhausted and not reader.streams_exhausted
    if trailing:
        with pytest.raises(VerificationError):
            next(apx)
        assert not streams.streams_exhausted and not reader.streams_exhausted
    else:
        with pytest.raises(StopIteration):
            next(apx)
        assert streams.streams_exhausted and reader.streams_exhausted


@pytest.mark.parametrize("stream", ["sp", "approximation"])
def test_final_root_is_not_eof_and_trailing_records_cannot_establish_exhaustion(
    tmp_path, stream
):
    tiny_bundle(tmp_path)
    reader = BundleReader(tmp_path)
    other = (
        reader.iter_approximation_roots() if stream == "sp" else reader.iter_sp_roots()
    )
    tuple(other)
    filename = stream + ".jsonl"
    with (tmp_path / filename).open("a") as target:
        target.write('{"type":"end"}\n')
    iterator = (
        reader.iter_sp_roots() if stream == "sp" else reader.iter_approximation_roots()
    )
    next(iterator)
    next(iterator)
    assert not reader.streams_exhausted
    with pytest.raises(VerificationError) as caught:
        next(iterator)
    assert caught.value.failure.code == "schema_fields"
    assert not reader.streams_exhausted
