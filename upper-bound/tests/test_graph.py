import pytest

from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.graph import parse_graph


def test_graph_preserves_order_and_orientation_and_recomputes_vertex_distances():
    graph = parse_graph(
        {
            "vertices": ["d", "b", "a", "c"],
            "edges": [["b", "a"], ["b", "c"], ["c", "d"], ["d", "a"]],
        }
    )
    assert graph.vertices == ("d", "b", "a", "c")
    assert graph.edges == (("b", "a"), ("b", "c"), ("c", "d"), ("d", "a"))
    assert graph.vertex_distance("b", "d") == 2
    assert graph.vertex_distance("a", "a") == 0
    assert graph.vertex_distance("d", "a") == 1


@pytest.mark.parametrize(
    "data",
    [
        {"vertices": ["a", "b"], "edges": [["b", "a"]]},
        {
            "vertices": ["o", "a", "b", "c"],
            "edges": [["o", "a"], ["b", "o"], ["o", "c"]],
        },
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "symmetries": []},
    ],
)
def test_one_edge_branching_graph_and_empty_symmetries_are_valid(data):
    graph = parse_graph(data)
    assert graph.vertex_distance(graph.vertices[0], graph.vertices[1]) == 1


@pytest.mark.parametrize(
    "data",
    [
        {},
        None,
        [],
        {"vertices": ["a"], "edges": []},
        {"vertices": ["a", "a"], "edges": []},
        {"vertices": [True, "b"], "edges": [[True, "b"]]},
        {"vertices": [[], "b"], "edges": []},
        {"vertices": ("a", "b"), "edges": [["a", "b"]]},
        {"vertices": ["a", "b"], "edges": (["a", "b"],)},
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "weight": 1},
        {"vertices": ["a", "b"], "edges": [["a", "b", 1]]},
        {"vertices": ["a", "b"], "edges": [{"from": "a", "to": "b", "weight": 1}]},
        {"vertices": ["a", "b"], "edges": [("a", "b")]},
        {"vertices": ["a", "b"], "edges": [["a", "a"]]},
        {"vertices": ["a", "b"], "edges": [["a", "b"], ["b", "a"]]},
        {"vertices": ["a", "b"], "edges": [["a", "b"], ["a", "b"]]},
        {"vertices": ["a", "b"], "edges": [["a", "z"]]},
        {"vertices": ["a", "b"], "edges": [["a", 1]]},
        {"vertices": ["a", "b"], "edges": []},
        {"vertices": ["a", "b", "c"], "edges": [["a", "b"]]},
        {"vertices": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"], ["c", "a"]]},
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "symmetries": [{}]},
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "symmetries": None},
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "symmetries": {}},
        {"vertices": ["a", "b"], "edges": [["a", "b"]], "distances": [[0, 0], [0, 0]]},
    ],
)
def test_graph_rejects_bad_shapes_and_out_of_scope_graphs(data):
    with pytest.raises(VerificationError) as caught:
        parse_graph(data)
    assert caught.value.failure.kind is FailureKind.REFUSED


def test_branch_endpoint_has_one_identity_in_every_incident_chart():
    from upper_bound_verifier.graph import chart_coordinate, point_from_chart

    graph = parse_graph(
        {
            "vertices": ["o", "a", "b", "c"],
            "edges": [["o", "a"], ["b", "o"], ["o", "c"]],
        }
    )
    points = [
        point_from_chart(graph, edge, coordinate)
        for edge, coordinate in [(0, 0), (1, 1), (2, 0)]
    ]
    assert points[0] == points[1] == points[2]
    assert len(set(points)) == 1
    assert [chart_coordinate(graph, points[0], edge) for edge in range(3)] == [0, 1, 0]


def test_direct_metric_uses_shortest_endpoint_routes_on_a_square():
    from flint import fmpq

    from upper_bound_verifier.graph import parse_point, point_distance

    graph = parse_graph(
        {
            "vertices": ["a", "b", "c", "d"],
            "edges": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        }
    )
    left = parse_point(graph, {"edge": 0, "coordinate": "1/4"})
    right = parse_point(graph, {"edge": 2, "coordinate": "1/3"})
    # Endpoint routes 00, 01, 10, 11 have lengths 31/12, 23/12, 25/12, 41/12.
    assert point_distance(graph, left, right) == fmpq(23, 12)
    assert point_distance(graph, right, left) == fmpq(23, 12)
    assert point_distance(graph, left, parse_point(graph, {"vertex": "c"})) == fmpq(
        7, 4
    )
    assert point_distance(
        graph, left, parse_point(graph, {"edge": 0, "coordinate": "3/4"})
    ) == fmpq(1, 2)


@pytest.mark.parametrize("agents", [2, 4])
def test_selectors_preserve_column_order_and_labeled_profile_order(agents):
    from upper_bound_verifier.graph import (
        evaluate_selector,
        parse_profile,
        parse_selectors,
        point_to_data,
    )

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["b", "a"]]})
    family = parse_selectors(
        graph,
        [
            {"kind": "peak", "agent": agents - 1},
            {"kind": "constant", "point": {"edge": 0, "coordinate": "1/3"}},
            {"kind": "peak", "agent": 0},
        ],
        agents,
    )
    profile_data = [{"vertex": "b"}] * (agents - 1) + [{"vertex": "a"}]
    profile = parse_profile(graph, profile_data, agents)
    assert [
        point_to_data(evaluate_selector(graph, selector, profile))
        for selector in family
    ] == [{"vertex": "a"}, {"edge": 0, "coordinate": "1/3"}, {"vertex": "b"}]


def test_empty_string_vertex_label_is_preserved_and_is_a_canonical_endpoint():
    from upper_bound_verifier.graph import (
        chart_coordinate,
        parse_point,
        point_from_chart,
        point_to_data,
    )

    graph = parse_graph({"vertices": ["", "b"], "edges": [["b", ""]]})
    point = parse_point(graph, {"vertex": ""})
    assert point == point_from_chart(graph, 0, 1)
    assert chart_coordinate(graph, point, 0) == 1
    assert graph.vertex_distance("", "b") == 1
    assert point_to_data(point) == {"vertex": ""}


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"vertex": "unknown"},
        {"vertex": False},
        {"vertex": "a", "edge": 0, "coordinate": "1/2"},
        {"vertex": "a", "extra": 0},
        {"edge": 0},
        {"edge": 0, "coordinate": "1/2", "extra": 0},
        *[
            {"edge": bad, "coordinate": "1/2"}
            for bad in [True, False, 0.0, "0", -1, 1, [], None]
        ],
        *[
            {"edge": 0, "coordinate": bad}
            for bad in [
                0,
                1,
                "0",
                "1",
                "-1/2",
                "3/2",
                True,
                False,
                0.5,
                "2/4",
                "1/1",
                "0.5",
                [],
                None,
            ]
        ],
    ],
)
def test_wire_point_rejects_bad_references_noncanonical_endpoints_and_numbers(data):
    from upper_bound_verifier.graph import parse_point

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    with pytest.raises(VerificationError):
        parse_point(graph, data)


def test_chart_membership_uses_all_and_only_incident_edges():
    from flint import fmpq

    from upper_bound_verifier.graph import (
        chart_coordinate,
        parse_point,
        point_from_chart,
        point_in_chart,
        point_to_data,
    )

    graph = parse_graph(
        {
            "vertices": ["o", "a", "b", "c", "d"],
            "edges": [["o", "a"], ["b", "o"], ["o", "c"], ["c", "d"]],
        }
    )
    vertex = parse_point(graph, {"vertex": "o"})
    assert [point_in_chart(graph, vertex, edge) for edge in range(4)] == [
        True,
        True,
        True,
        False,
    ]
    with pytest.raises(VerificationError):
        chart_coordinate(graph, vertex, 3)
    interior = point_from_chart(graph, 1, fmpq(2, 3))
    assert [point_in_chart(graph, interior, edge) for edge in range(4)] == [
        False,
        True,
        False,
        False,
    ]
    assert chart_coordinate(graph, interior, 1) == fmpq(2, 3)
    assert parse_point(graph, point_to_data(interior)) == interior
    with pytest.raises(VerificationError):
        chart_coordinate(graph, interior, 0)
    assert graph.degree("o") == 3
    assert graph.degree("c") == 2


@pytest.mark.parametrize("edge", [True, False, 0.0, "0", -1, 1, [], None])
def test_chart_indices_are_strict_json_integers(edge):
    from upper_bound_verifier.graph import VertexPoint, point_from_chart, point_in_chart

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    with pytest.raises(VerificationError):
        point_from_chart(graph, edge, 0)
    with pytest.raises(VerificationError):
        point_in_chart(graph, VertexPoint("a"), edge)


@pytest.mark.parametrize("coordinate", [True, False, 0.0, "0", "1/2", -1, 2, None])
def test_internal_chart_conversion_requires_exact_closed_unit_coordinate(coordinate):
    from upper_bound_verifier.graph import point_from_chart

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    with pytest.raises(VerificationError):
        point_from_chart(graph, 0, coordinate)


@pytest.mark.parametrize(
    "family",
    [
        None,
        {},
        [],
        (),
        [None],
        [{}],
        [{"kind": True}],
        [{"kind": []}],
        [{"kind": "peak"}],
        [{"kind": "constant"}],
        [{"kind": "report", "agent": 0}],
        [{"kind": "peak", "agent": 0, "point": {"vertex": "a"}}],
        [{"kind": "constant", "point": {"vertex": "a"}, "agent": 0}],
        [{"kind": "constant", "point": {"vertex": "a"}, "weight": 1}],
        *[
            [{"kind": "peak", "agent": bad}]
            for bad in [True, False, 0.0, "0", -1, 2, None, []]
        ],
        [{"kind": "constant", "point": {"edge": 0, "coordinate": 0}}],
        [{"kind": "constant", "point": {"vertex": "unknown"}}],
        [{"kind": "peak", "agent": 0}, {"kind": "peak", "agent": 0}],
        [
            {"kind": "constant", "point": {"vertex": "a"}},
            {"kind": "constant", "point": {"vertex": "a"}},
        ],
        [
            {"kind": "constant", "point": {"edge": 0, "coordinate": "1/3"}},
            {"kind": "constant", "point": {"coordinate": "1/3", "edge": 0}},
        ],
    ],
)
def test_selector_family_rejects_malformed_indices_shapes_and_duplicates(family):
    from upper_bound_verifier.graph import parse_selectors

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    with pytest.raises(VerificationError):
        parse_selectors(graph, family, 2)


@pytest.mark.parametrize("agents", [True, False, 2.0, "2", 1, 0, -1, None, []])
def test_agent_counts_are_strict_in_all_profile_and_family_interfaces(agents):
    from upper_bound_verifier.graph import (
        parse_agent_count,
        parse_profile,
        parse_selectors,
    )

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    for action in [
        lambda: parse_agent_count(agents),
        lambda: parse_profile(graph, [{"vertex": "a"}, {"vertex": "b"}], agents),
        lambda: parse_selectors(graph, [{"kind": "peak", "agent": 0}], agents),
    ]:
        with pytest.raises(VerificationError):
            action()


def test_profile_shape_and_selector_ranges_and_constant_only_family():
    from upper_bound_verifier.graph import (
        PeakSelector,
        VertexPoint,
        evaluate_selector,
        parse_profile,
        parse_selectors,
    )

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    for bad in [
        None,
        [],
        [{"vertex": "a"}],
        [{"vertex": "a"}] * 3,
        ({"vertex": "a"}, {"vertex": "b"}),
        [{"vertex": "a"}, {"vertex": "z"}],
    ]:
        with pytest.raises(VerificationError):
            parse_profile(graph, bad, 2)
    profile = parse_profile(graph, [{"vertex": "a"}, {"vertex": "a"}], 2)
    family = parse_selectors(graph, [{"kind": "constant", "point": {"vertex": "b"}}], 2)
    assert evaluate_selector(graph, family[0], profile) == VertexPoint("b")
    with pytest.raises(VerificationError):
        evaluate_selector(graph, PeakSelector(2), profile)


def test_public_records_are_immutable_and_raw_data_cannot_change_the_metric():
    from dataclasses import FrozenInstanceError

    from upper_bound_verifier.graph import parse_profile, parse_selectors

    data = {"vertices": ["a", "b"], "edges": [["a", "b"]]}
    graph = parse_graph(data)
    profile = parse_profile(graph, [{"vertex": "a"}, {"vertex": "b"}], 2)
    family = parse_selectors(graph, [{"kind": "peak", "agent": 0}], 2)
    data["vertices"][0] = "changed"
    data["edges"][0][0] = "changed"
    assert graph.vertices == ("a", "b")
    assert graph.edges == (("a", "b"),)
    assert graph.vertex_distance("a", "b") == 1
    for record, attribute, value in [
        (graph, "vertices", ()),
        (profile[0], "vertex", "b"),
        (family[0], "agent", 1),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(record, attribute, value)


def test_direct_metric_vertex_constants_branch_ties_and_tiny_interior_coordinates():
    from flint import fmpq

    from upper_bound_verifier.graph import parse_point, point_distance

    graph = parse_graph(
        {
            "vertices": ["o", "a", "b", "c"],
            "edges": [["o", "a"], ["b", "o"], ["o", "c"]],
        }
    )
    point_data = [
        {"vertex": "a"},
        {"edge": 1, "coordinate": "1/4"},
        {"edge": 0, "coordinate": "1/3"},
        {"vertex": "o"},
    ]
    points = [parse_point(graph, p) for p in point_data]
    assert point_distance(graph, points[0], points[1]) == fmpq(7, 4)
    assert point_distance(graph, points[1], points[2]) == fmpq(13, 12)
    assert point_distance(graph, points[0], points[3]) == 1
    assert point_distance(graph, points[0], parse_point(graph, {"vertex": "c"})) == 2
    for point in points:
        assert point_distance(graph, point, point) == 0
    epsilon = fmpq(1, 10**40)
    from upper_bound_verifier.graph import point_from_chart

    near_start, near_end = [
        point_from_chart(graph, 0, t) for t in [epsilon, 1 - epsilon]
    ]
    assert point_distance(graph, near_start, near_end) == 1 - 2 * epsilon
    assert point_distance(graph, points[3], near_start) == epsilon
    square = parse_graph(
        {
            "vertices": ["a", "b", "c", "d"],
            "edges": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        }
    )
    # Opposite midpoints tie via both sides; an edge endpoint canonicalizes
    # to the opposite square vertex with the same exact boundary distance.
    assert (
        point_distance(
            square,
            point_from_chart(square, 0, fmpq(1, 2)),
            point_from_chart(square, 2, fmpq(1, 2)),
        )
        == 2
    )
    assert (
        point_distance(
            square, parse_point(square, {"vertex": "a"}), point_from_chart(square, 1, 1)
        )
        == 2
    )


def test_metric_and_charts_refuse_foreign_points_and_unknown_vertices():
    from typing import cast

    from flint import fmpq

    from upper_bound_verifier.graph import (
        EdgePoint,
        GraphPoint,
        VertexPoint,
        point_distance,
        point_in_chart,
    )

    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    for point in [VertexPoint("z"), EdgePoint(1, fmpq(1, 2)), None, {"vertex": "a"}]:
        # Deliberately bypass static types to exercise rejection at the API.
        point = cast(GraphPoint, point)
        with pytest.raises(VerificationError):
            point_distance(graph, point, point)
        with pytest.raises(VerificationError):
            point_in_chart(graph, point, 0)
    for bad in ["z", False, None, []]:
        with pytest.raises(VerificationError):
            graph.vertex_distance("a", cast(str, bad))
        with pytest.raises(VerificationError):
            graph.degree(cast(str, bad))


def test_edge_orientation_reversal_preserves_the_metric_and_changes_chart_coordinate():
    from flint import fmpq

    from upper_bound_verifier.graph import (
        chart_coordinate,
        point_distance,
        point_from_chart,
    )

    original = parse_graph(
        {
            "vertices": ["o", "a", "b", "c"],
            "edges": [["o", "a"], ["b", "o"], ["o", "c"]],
        }
    )
    reversed_graph = parse_graph(
        {
            "vertices": list(original.vertices),
            "edges": [list(reversed(e)) for e in original.edges],
        }
    )
    positions = [
        (0, fmpq(0)),
        (0, fmpq(1, 4)),
        (1, fmpq(1, 3)),
        (2, fmpq(4, 5)),
        (2, fmpq(1)),
    ]
    for edge, coordinate in positions:
        left = point_from_chart(original, edge, coordinate)
        flipped_left = point_from_chart(reversed_graph, edge, 1 - coordinate)
        assert chart_coordinate(original, left, edge) == coordinate
        assert chart_coordinate(reversed_graph, flipped_left, edge) == 1 - coordinate
        for other_edge, other_coordinate in positions:
            right = point_from_chart(original, other_edge, other_coordinate)
            flipped_right = point_from_chart(
                reversed_graph, other_edge, 1 - other_coordinate
            )
            assert point_distance(original, left, right) == point_distance(
                reversed_graph, flipped_left, flipped_right
            )


@pytest.mark.parametrize("branching", [False, True])
def test_direct_metric_matches_independent_fraction_subdivision_shortest_paths(
    branching,
):
    # Independent oracle: split each edge into rational segments, then use
    # Floyd-Warshall over all resulting vertices. No production vertex-distance
    # matrix or endpoint-route formulas are used to obtain the expected values.
    from fractions import Fraction
    from itertools import pairwise

    from flint import fmpq

    from upper_bound_verifier.graph import (
        GraphPoint,
        VertexPoint,
        point_distance,
        point_from_chart,
    )

    data = (
        {
            "vertices": ["o", "a", "b", "c", "d"],
            "edges": [["a", "o"], ["o", "b"], ["c", "o"], ["c", "d"]],
        }
        if branching
        else {
            "vertices": ["a", "b", "c", "d"],
            "edges": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        }
    )
    graph = parse_graph(data)
    nodes: list[str | tuple[int, Fraction]] = list(graph.vertices)
    points: list[GraphPoint] = [VertexPoint(v) for v in graph.vertices]
    segments = []
    for edge_index, (first, second) in enumerate(graph.edges):
        chain: list[tuple[Fraction, str | tuple[int, Fraction]]] = [
            (Fraction(0), first)
        ]
        for coordinate in [Fraction(1, 7), Fraction(1, 2), Fraction(4, 5)]:
            key = (edge_index, coordinate)
            nodes.append(key)
            points.append(
                point_from_chart(
                    graph,
                    edge_index,
                    fmpq(coordinate.numerator, coordinate.denominator),
                )
            )
            chain.append((coordinate, key))
        chain.append((Fraction(1), second))
        for (a, left), (b, right) in pairwise(chain):
            segments.append((left, right, b - a))
    distances = {
        (left, right): (Fraction(0) if left == right else None)
        for left in nodes
        for right in nodes
    }
    for left, right, length in segments:
        distances[left, right] = distances[right, left] = length
    for via in nodes:
        for left in nodes:
            for right in nodes:
                a, b = distances[left, via], distances[via, right]
                if a is not None and b is not None:
                    previous = distances[left, right]
                    if previous is None or a + b < previous:
                        distances[left, right] = a + b
    for left_node, left in zip(nodes, points, strict=True):
        for right_node, right in zip(nodes, points, strict=True):
            expected = distances[left_node, right_node]
            assert expected is not None
            assert point_distance(graph, left, right) == fmpq(
                expected.numerator, expected.denominator
            )
