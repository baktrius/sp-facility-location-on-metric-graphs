import pytest
from flint import fmpq, fmpq_mat

from upper_bound_verifier.distance import (
    AffineExpression,
    EdgeExpression,
    check_distance_branch,
)
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.geometry import Simplex
from upper_bound_verifier.graph import (
    ConstantSelector,
    EdgePoint,
    Graph,
    PeakSelector,
    VertexPoint,
    point_distance,
    point_from_chart,
)


def square():
    return Graph(("a", "b", "c", "d"), (("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")))


def test_same_edge_signs_and_equality_return_exact_metric_formulas():
    graph = square()
    left = EdgeExpression(0, AffineExpression((1, 0), 0))
    right = EdgeExpression(0, AffineExpression((0, 1), 0))
    for branch, vertices, expected in [
        (0, [[0, 1, 1], [0, 0, 1]], (fmpq(1), fmpq(-1))),
        (1, [[0, 0, 1], [0, 1, 1]], (fmpq(-1), fmpq(1))),
    ]:
        cell = Simplex(fmpq_mat(vertices))
        result = check_distance_branch(graph, cell, left, right, branch)
        assert result.coefficients == expected
        assert result.constant == 0
        # Direct metric evaluation canonicalizes endpoints; it does not derive coefficients.
        for weights in [
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (fmpq(1, 6), fmpq(1, 3), fmpq(1, 2)),
        ]:
            point = tuple(
                sum((cell.vertices[i, j] * weights[j] for j in range(3)), fmpq(0))
                for i in range(2)
            )
            metric = point_distance(
                graph,
                point_from_chart(graph, 0, point[0]),
                point_from_chart(graph, 0, point[1]),
            )
            assert result.evaluate(point) == metric
    equality = Simplex(fmpq_mat([[0, 1], [0, 1]]))
    assert (
        check_distance_branch(graph, equality, left, right, 0).evaluate(
            (fmpq(2, 3), fmpq(2, 3))
        )
        == 0
    )
    assert (
        check_distance_branch(graph, equality, left, right, 1).evaluate(
            (fmpq(2, 3), fmpq(2, 3))
        )
        == 0
    )


def test_same_edge_branch_valid_at_only_some_vertices_is_rejected():
    cell = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    left = EdgeExpression(0, AffineExpression((1, 0), 0))
    right = EdgeExpression(0, AffineExpression((0, 1), 0))
    for branch in (0, 1):
        with pytest.raises(VerificationError) as error:
            check_distance_branch(square(), cell, left, right, branch)
        assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
        assert error.value.failure.code == "distance_branch"
        assert error.value.failure.witness is None


def test_opposite_square_edges_check_all_four_routes_and_closed_ties():
    graph = square()
    left = EdgeExpression(0, AffineExpression((1, 0), 0))
    right = EdgeExpression(2, AffineExpression((0, 1), 0))
    for branch, vertices, expected in [
        (2, [[0, 1, 1], [0, 0, 1]], (-1, 1)),
        (1, [[0, 0, 1], [0, 1, 1]], (1, -1)),
    ]:
        cell = Simplex(fmpq_mat(vertices))
        result = check_distance_branch(graph, cell, left, right, branch)
        assert result.coefficients == expected
        assert result.constant == 2
        for point in [
            (fmpq(1, 2), fmpq(1, 2)),
            (fmpq(3, 4), fmpq(1, 4)) if branch == 2 else (fmpq(1, 4), fmpq(3, 4)),
        ]:
            assert result.evaluate(point) == point_distance(
                graph,
                point_from_chart(graph, 0, point[0]),
                point_from_chart(graph, 2, point[1]),
            )
        for invalid in (0, 3, 3 - branch):
            with pytest.raises(VerificationError, match="distance_branch"):
                check_distance_branch(graph, cell, left, right, invalid)
    for coordinates, branches in [((0, 0), (0, 1, 2)), ((1, 1), (1, 2, 3))]:
        cell = Simplex(fmpq_mat([[coordinates[0]], [coordinates[1]]]))
        for branch in branches:
            assert (
                check_distance_branch(graph, cell, left, right, branch).evaluate(
                    coordinates
                )
                == 2
            )


def test_vertex_constants_and_reversed_orientations_preserve_branch_order():
    graph = Graph(
        ("a", "b", "c", "d"), (("b", "a"), ("b", "c"), ("d", "c"), ("d", "a"))
    )
    segment = Simplex(fmpq_mat([[0, 1]]))
    report = EdgeExpression(0, AffineExpression((1,), 0))
    for left, right in [(VertexPoint("a"), report), (report, VertexPoint("a"))]:
        result = check_distance_branch(graph, segment, left, right, 1)
        assert result.coefficients == (-1,)
        assert result.constant == 1
        for coordinate in (0, fmpq(1, 3), fmpq(4, 5), 1):
            assert result.evaluate((coordinate,)) == point_distance(
                graph, VertexPoint("a"), point_from_chart(graph, 0, coordinate)
            )
        with pytest.raises(VerificationError, match="distance_branch"):
            check_distance_branch(graph, segment, left, right, 0)
    result = check_distance_branch(
        graph, segment, VertexPoint("a"), VertexPoint("c"), 0
    )
    assert result.coefficients == (0,)
    assert result.constant == 2
    assert result.evaluate((fmpq(2, 7),)) == point_distance(
        graph, VertexPoint("a"), VertexPoint("c")
    )
    # Reversing just one C4 opposite edge changes winners from 01/10 to 00/11.
    original = square()
    reversed_graph = Graph(
        original.vertices, (("a", "b"), ("b", "c"), ("d", "c"), ("d", "a"))
    )
    left = EdgeExpression(0, AffineExpression((1, 0), 0))
    right = EdgeExpression(2, AffineExpression((0, 1), 0))
    for branch, vertices, coefficients, constant in [
        (0, [[0, 1, 0], [0, 0, 1]], (1, 1), 1),
        (3, [[1, 1, 0], [1, 0, 1]], (-1, -1), 3),
    ]:
        result = check_distance_branch(
            reversed_graph, Simplex(fmpq_mat(vertices)), left, right, branch
        )
        assert (result.coefficients, result.constant) == (coefficients, constant)
        point = (fmpq(1, 4), fmpq(1, 3)) if branch == 0 else (fmpq(3, 4), fmpq(2, 3))
        assert result.evaluate(point) == point_distance(
            reversed_graph,
            point_from_chart(reversed_graph, 0, point[0]),
            point_from_chart(reversed_graph, 2, point[1]),
        )


def test_rational_constants_and_trusted_root_selector_constructors():
    from upper_bound_verifier.distance import (
        constant_expression,
        root_expressions,
        selector_expression,
    )

    graph = square()
    reports = root_expressions(graph, (0, 2))
    assert selector_expression(graph, PeakSelector(1), reports) == reports[1]
    assert selector_expression(
        graph, ConstantSelector(VertexPoint("a")), reports
    ) == VertexPoint("a")
    constant = selector_expression(
        graph, ConstantSelector(EdgePoint(0, fmpq(1, 3))), reports
    )
    assert isinstance(constant, EdgeExpression)
    assert constant.coordinate.coefficients == (0, 0)
    assert constant.coordinate.constant == fmpq(1, 3)
    for branch, vertices in [
        (0, [[fmpq(1, 3), 1, fmpq(1, 3)], [0, 0, 1]]),
        (1, [[0, fmpq(1, 3), 0], [0, 0, 1]]),
    ]:
        cell = Simplex(fmpq_mat(vertices))
        result = check_distance_branch(graph, cell, reports[0], constant, branch)
        point = tuple(
            sum((cell.vertices[i, j] for j in range(3)), fmpq(0)) / 3 for i in range(2)
        )
        assert result.evaluate(point) == point_distance(
            graph, point_from_chart(graph, 0, point[0]), EdgePoint(0, fmpq(1, 3))
        )
    other = constant_expression(graph, EdgePoint(2, fmpq(2, 3)), 2)
    for branch, vertices in [
        (1, [[0, fmpq(2, 3), 0], [0, 0, 1]]),
        (2, [[fmpq(2, 3), 1, fmpq(2, 3)], [0, 0, 1]]),
    ]:
        cell = Simplex(fmpq_mat(vertices))
        result = check_distance_branch(graph, cell, reports[0], other, branch)
        point = tuple(
            sum((cell.vertices[i, j] for j in range(3)), fmpq(0)) / 3 for i in range(2)
        )
        assert result.evaluate(point) == point_distance(
            graph, point_from_chart(graph, 0, point[0]), EdgePoint(2, fmpq(2, 3))
        )
    # Substitution of z into the agent's output changes no ambient coordinates.
    extended = root_expressions(graph, (0, 2, 1))
    deviated = (extended[2], extended[1])
    deviated_output = selector_expression(graph, PeakSelector(0), deviated)
    assert isinstance(deviated_output, EdgeExpression)
    assert deviated_output.coordinate.coefficients == (0, 0, 1)


def test_ordered_terms_require_all_branches_even_for_unused_outputs():
    from upper_bound_verifier.distance import (
        DistanceTerm,
        check_distance_terms,
        root_expressions,
    )

    graph = square()
    reports = root_expressions(graph, (0, 0))
    cell = Simplex(fmpq_mat([[0, 1, 1], [0, 0, 1]]))
    terms = (
        DistanceTerm(reports[0], reports[1]),
        DistanceTerm(reports[0], VertexPoint("a")),
    )
    location = {
        "file": "sp.jsonl",
        "line": 17,
        "root": {"agent": 0, "edges": [0, 0, 0]},
        "cell": "C",
    }
    formulas = check_distance_terms(graph, cell, terms, (0, 0), location=location)
    assert tuple((f.coefficients, f.constant) for f in formulas) == (
        ((1, -1), 0),
        ((1, 0), 0),
    )
    for branches in [(0,), (0, 0, 0), (0, 1)]:
        with pytest.raises(VerificationError) as error:
            check_distance_terms(graph, cell, terms, branches, location=location)
        assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
        assert error.value.failure.code in {"distance_branch", "distance_branch_count"}
        assert error.value.failure.location is not None
        assert error.value.failure.location["file"] == "sp.jsonl"
        assert error.value.failure.location["cell"] == "C"
        assert error.value.failure.witness is None
    with pytest.raises(VerificationError) as error:
        check_distance_terms(graph, cell, terms, (0, 1), location=location)
    assert error.value.failure.location is not None
    assert error.value.failure.location["term"] == 1


@pytest.mark.parametrize(
    "left,right,branch,code,kind",
    [
        (
            EdgeExpression(0, AffineExpression((1,), 0)),
            EdgeExpression(0, AffineExpression((1,), 0)),
            -1,
            "distance_branch",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            EdgeExpression(0, AffineExpression((1,), 0)),
            EdgeExpression(0, AffineExpression((1,), 0)),
            2,
            "distance_branch",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            VertexPoint("b"),
            1,
            "distance_branch",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            EdgeExpression(0, AffineExpression((1,), 0)),
            2,
            "distance_branch",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            EdgeExpression(0, AffineExpression((1,), 0)),
            EdgeExpression(2, AffineExpression((1,), 0)),
            4,
            "distance_branch",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            VertexPoint("b"),
            True,
            "distance_branch_type",
            FailureKind.REFUSED,
        ),
        (
            VertexPoint("a"),
            VertexPoint("b"),
            0.0,
            "distance_branch_type",
            FailureKind.REFUSED,
        ),
        (
            VertexPoint("ghost"),
            VertexPoint("b"),
            0,
            "reference_vertex",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            EdgeExpression(9, AffineExpression((1,), 0)),
            0,
            "reference_index",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            EdgeExpression(0, AffineExpression((1, 0), 0)),
            0,
            "distance_expression_dimension",
            FailureKind.REFUSED,
        ),
        (
            VertexPoint("a"),
            EdgeExpression(0, AffineExpression((1,), fmpq(1, 10**90))),
            0,
            "distance_expression_domain",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            EdgeExpression(0, AffineExpression((1,), -fmpq(1, 10**90))),
            0,
            "distance_expression_domain",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            VertexPoint("a"),
            EdgePoint(0, fmpq(1, 2)),
            0,
            "distance_expression_type",
            FailureKind.REFUSED,
        ),
    ],
)
def test_distance_boundary_refuses_inexact_and_rejects_bad_references(
    left, right, branch, code, kind
):
    with pytest.raises(VerificationError) as error:
        check_distance_branch(
            square(), Simplex(fmpq_mat([[0, 1]])), left, right, branch
        )
    assert (error.value.failure.code, error.value.failure.kind) == (code, kind)
    assert error.value.failure.witness is None


def test_report_endpoints_keep_their_root_edge_arity():
    from upper_bound_verifier.distance import constant_expression, root_expressions

    graph = square()
    reports = root_expressions(graph, (0, 1))
    cell = Simplex(fmpq_mat([[1], [0]]))
    # Both reports canonicalize to b, but still have four-route type.
    result = check_distance_branch(graph, cell, reports[0], reports[1], 2)
    assert result.evaluate((1, 0)) == 0
    with pytest.raises(VerificationError, match="distance_branch"):
        check_distance_branch(graph, cell, reports[0], reports[1], 0)
    constant = constant_expression(graph, VertexPoint("b"), 2)
    assert isinstance(constant, VertexPoint)
    assert (
        check_distance_branch(graph, cell, constant, constant, 0).evaluate((1, 0)) == 0
    )
    with pytest.raises(VerificationError, match="distance_branch"):
        check_distance_branch(graph, cell, constant, constant, 2)


def test_general_affine_coordinates_on_embedded_and_zero_dimensional_cells():
    # An ambient cell may lie outside [0,1]^d: its edge coordinate maps must stay in [0,1].
    graph = square()
    cell = Simplex(fmpq_mat([[2, 4], [-3, -1], [8, 8]]))
    left = EdgeExpression(0, AffineExpression((fmpq(1, 4), 0, 0), -fmpq(1, 2)))
    right = EdgeExpression(0, AffineExpression((0, 0, 0), fmpq(3, 4)))
    formula = check_distance_branch(graph, cell, left, right, 1)
    for point in [(2, -3, 8), (4, -1, 8), (fmpq(8, 3), -fmpq(7, 3), 8)]:
        assert formula.evaluate(point) == point_distance(
            graph,
            point_from_chart(graph, 0, (point[0] - 2) / fmpq(4)),
            EdgePoint(0, fmpq(3, 4)),
        )
    zero = Simplex(fmpq_mat(0, 1))
    formula = check_distance_branch(
        graph,
        zero,
        EdgeExpression(0, AffineExpression((), fmpq(1, 4))),
        EdgeExpression(0, AffineExpression((), fmpq(3, 4))),
        1,
    )
    assert formula.evaluate(()) == fmpq(1, 2)
    assert (
        check_distance_branch(
            graph, zero, VertexPoint("a"), VertexPoint("c"), 0
        ).evaluate(())
        == 2
    )


@pytest.mark.parametrize("value", [True, 0.5, "1/2", None])
def test_internal_affine_constructors_refuse_nonexact_scalars(value):
    with pytest.raises(VerificationError) as error:
        AffineExpression((value,), 0)
    assert error.value.failure.kind == FailureKind.REFUSED
    with pytest.raises(VerificationError):
        AffineExpression((0,), value)


def test_constructor_references_shapes_and_owned_coefficients():
    from upper_bound_verifier.distance import (
        DistanceTerm,
        check_distance_terms,
        constant_expression,
        coordinate_expression,
        root_expressions,
        selector_expression,
    )

    coefficients = [fmpq(1), fmpq(0)]
    expression = AffineExpression(coefficients, 2)
    coefficients[0] = 99
    assert expression.evaluate((3, 7)) == 5
    for function in [
        lambda: root_expressions(square(), (9,)),
        lambda: root_expressions(square(), (-1,)),
        lambda: constant_expression(square(), EdgePoint(9, fmpq(1, 2)), 2),
        lambda: constant_expression(square(), VertexPoint("ghost"), 2),
        lambda: selector_expression(
            square(), PeakSelector(2), root_expressions(square(), (0, 1))
        ),
        lambda: coordinate_expression(2, 2),
    ]:
        with pytest.raises(VerificationError) as error:
            function()
        assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    for function in [
        lambda: root_expressions(square(), (True,)),
        lambda: root_expressions(square(), ()),
        lambda: root_expressions(square(), [0, 1]),
        lambda: root_expressions(None, (0,)),
        lambda: coordinate_expression(True, 0),
        lambda: coordinate_expression(2, True),
        lambda: constant_expression(square(), None, 2),
        lambda: selector_expression(square(), None, root_expressions(square(), (0, 1))),
        lambda: selector_expression(square(), PeakSelector(0), ()),
        lambda: selector_expression(
            square(),
            PeakSelector(0),
            (
                EdgeExpression(0, AffineExpression((1,), 0)),
                EdgeExpression(1, AffineExpression((0, 1), 0)),
            ),
        ),
        lambda: EdgeExpression(True, AffineExpression((1,), 0)),
        lambda: EdgeExpression(0, None),
        lambda: DistanceTerm(VertexPoint("a"), None),
        lambda: check_distance_branch(
            None, Simplex(fmpq_mat([[0, 1]])), VertexPoint("a"), VertexPoint("b"), 0
        ),
        lambda: check_distance_branch(
            square(), None, VertexPoint("a"), VertexPoint("b"), 0
        ),
        lambda: check_distance_terms(square(), Simplex(fmpq_mat([[0, 1]])), [], ()),
        lambda: check_distance_terms(square(), Simplex(fmpq_mat([[0, 1]])), (), []),
    ]:
        with pytest.raises(VerificationError) as error:
            function()
        assert error.value.failure.kind == FailureKind.REFUSED


def split_edge_metric(graph, left, right):
    """Independent Fraction oracle: subdivide at query points and relax paths.

    This uses neither vertex_distance/point_distance nor endpoint-route formulas.
    """
    from fractions import Fraction
    from itertools import pairwise

    def rational(q):
        return Fraction(int(q.p), int(q.q))

    def node(point):
        if isinstance(point, VertexPoint):
            return ("v", point.vertex)
        return ("e", point.edge, rational(point.coordinate))

    arcs = []
    nodes = {("v", v) for v in graph.vertices}
    for edge_index, (start, end) in enumerate(graph.edges):
        positions = {Fraction(0): ("v", start), Fraction(1): ("v", end)}
        for point in (left, right):
            if isinstance(point, EdgePoint) and point.edge == edge_index:
                positions[rational(point.coordinate)] = node(point)
        ordered = sorted(positions)
        for a, b in pairwise(ordered):
            u, v = positions[a], positions[b]
            nodes.update((u, v))
            arcs.extend(((u, v, b - a), (v, u, b - a)))
    distances = {node(left): Fraction(0)}
    for _ in range(len(nodes) - 1):
        for start, end, length in arcs:
            if start in distances and (
                end not in distances or distances[start] + length < distances[end]
            ):
                distances[end] = distances[start] + length
    return distances[node(right)]


@pytest.mark.parametrize(
    "reverse", [(False, False), (True, False), (False, True), (True, True)]
)
def test_every_accepted_route_on_branching_cycles_matches_split_edge_metric(reverse):
    from fractions import Fraction

    from upper_bound_verifier.distance import constant_expression, root_expressions

    edges = (("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "leaf"))
    graph = Graph(
        ("a", "b", "c", "d", "leaf"),
        tuple(edge[::-1] if reverse[i % 2] else edge for i, edge in enumerate(edges)),
    )
    accepted = rejected = 0
    for left_edge in range(len(edges)):
        for right_edge in range(len(edges)):
            left, right = root_expressions(graph, (left_edge, right_edge))
            for vertices in (
                [[0, 1, 1], [0, 0, 1]],
                [[0, 1, 0], [0, 0, 1]],
                [[1, 1, 0], [1, 0, 1]],
                [[0, 0, 1], [0, 1, 1]],
            ):
                cell = Simplex(fmpq_mat(vertices))
                samples = [
                    tuple(cell.vertices[i, j] for i in range(2)) for j in range(3)
                ]
                samples.extend(
                    tuple(
                        sum(
                            (cell.vertices[i, j] * weights[j] for j in range(3)),
                            fmpq(0),
                        )
                        for i in range(2)
                    )
                    for weights in [
                        (fmpq(1, 3),) * 3,
                        (fmpq(1, 7), fmpq(2, 7), fmpq(4, 7)),
                    ]
                )
                for branch in range(2 if left_edge == right_edge else 4):
                    try:
                        formula = check_distance_branch(
                            graph, cell, left, right, branch
                        )
                    except VerificationError as error:
                        assert error.failure.code == "distance_branch"
                        rejected += 1
                        continue
                    accepted += 1
                    for point in samples:
                        actual = formula.evaluate(point)
                        assert Fraction(
                            int(actual.p), int(actual.q)
                        ) == split_edge_metric(
                            graph,
                            point_from_chart(graph, left_edge, point[0]),
                            point_from_chart(graph, right_edge, point[1]),
                        )
            # Constant pairs use all canonical types, including strict interior constants.
            constants = [VertexPoint(v) for v in graph.vertices] + [
                EdgePoint(right_edge, fmpq(1, 4)),
                EdgePoint(right_edge, fmpq(3, 4)),
            ]
            for constant in constants:
                constant_right = constant_expression(graph, constant, 2)
                for coordinate in (0, fmpq(1, 4), fmpq(1, 2), fmpq(3, 4), 1):
                    cell = Simplex(fmpq_mat([[coordinate], [fmpq(2, 3)]]))
                    valid = 0
                    for branch in range(4):
                        try:
                            formula = check_distance_branch(
                                graph, cell, left, constant_right, branch
                            )
                        except VerificationError as error:
                            assert error.failure.code == "distance_branch"
                            rejected += 1
                            continue
                        valid += 1
                        accepted += 1
                        actual = formula.evaluate((coordinate, fmpq(2, 3)))
                        assert Fraction(
                            int(actual.p), int(actual.q)
                        ) == split_edge_metric(
                            graph,
                            point_from_chart(graph, left_edge, coordinate),
                            constant,
                        )
                    assert valid >= 1
    assert accepted > 500 and rejected > 1000


def test_route_bits_follow_the_left_argument_when_arguments_swap():
    from upper_bound_verifier.distance import root_expressions

    graph = Graph(("a", "b", "c", "d"), (("a", "b"), ("b", "c"), ("c", "d")))
    left, right = root_expressions(graph, (0, 2))
    cell = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    forward = check_distance_branch(graph, cell, left, right, 2)  # exit b, enter c: 10
    reverse = check_distance_branch(graph, cell, right, left, 1)  # exit c, enter b: 01
    assert forward == reverse
    assert (forward.coefficients, forward.constant) == ((-1, 1), 2)
    point = (fmpq(1, 3), fmpq(1, 4))
    assert forward.evaluate(point) == point_distance(
        graph,
        point_from_chart(graph, 0, point[0]),
        point_from_chart(graph, 2, point[1]),
    )
    with pytest.raises(VerificationError, match="distance_branch"):
        check_distance_branch(graph, cell, right, left, 2)


def test_two_interior_constants_and_vertex_constant_use_exact_metric():
    from upper_bound_verifier.distance import constant_expression

    graph = square()
    cell = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    for left, right, branch in [
        (EdgePoint(0, fmpq(1, 3)), EdgePoint(0, fmpq(3, 4)), 1),
        (EdgePoint(0, fmpq(1, 3)), EdgePoint(2, fmpq(3, 4)), 1),
        (VertexPoint("c"), EdgePoint(0, fmpq(1, 3)), 1),
    ]:
        formula = check_distance_branch(
            graph,
            cell,
            constant_expression(graph, left, 2),
            constant_expression(graph, right, 2),
            branch,
        )
        assert formula.coefficients == (0, 0)
        assert formula.constant == point_distance(graph, left, right)
        assert formula.evaluate((fmpq(2, 7), fmpq(3, 7))) == point_distance(
            graph, left, right
        )
