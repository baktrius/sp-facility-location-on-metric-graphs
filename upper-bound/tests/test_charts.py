"""Public graph-chart conformity on genuine, independently built local meshes."""

from dataclasses import replace
from itertools import pairwise, permutations

import pytest
from flint import fmpq

from upper_bound_verifier.charts import ProductFace, check_chart_conformity
from upper_bound_verifier.conformity import check_local_conformity
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.graph import Graph, VertexPoint, point_from_chart
from upper_bound_verifier.reader import (
    AttributionKey,
    AttributionSimplex,
    LeafNode,
    ProfileVertex,
    RootBlock,
    SourceLocation,
    SplitNode,
    attribution_root_keys,
)


def meshes(graph, agents=2, cuts=None):
    """Rectangular grids, each box triangulated by monotone coordinate orders.

    A real hyperplane routing tree splits slabs then orders their normalized
    coordinates. Canonical profiles are interned independently of the checker.
    """
    vertices = {}
    profiles = {}
    roots = []
    for key in attribution_root_keys(graph, agents):
        loc = SourceLocation("attribution.jsonl", len(roots) + 1, key)
        intervals = []
        for axis in range(agents):
            midpoints = () if cuts is None else cuts(key, axis)
            marks = (fmpq(0), *midpoints, fmpq(1))
            intervals.append(tuple(pairwise(marks)))
        cells, nodes = [], []

        def triangulate(bounds, name, key=key, loc=loc, cells=cells, nodes=nodes):
            orders = {}
            for index, order in enumerate(permutations(range(agents))):
                coordinates = [bound[0] for bound in bounds]
                ids = []
                for axis in (None, *order):
                    if axis is not None:
                        coordinates[axis] = bounds[axis][1]
                    profile = tuple(
                        point_from_chart(graph, edge, x)
                        for edge, x in zip(key.edges, coordinates, strict=True)
                    )
                    if profile not in profiles:
                        identifier = f"v{len(profiles)}"
                        profiles[profile] = identifier
                        vertices[identifier] = ProfileVertex(identifier, profile, loc)
                    ids.append(profiles[profile])
                cell = f"r{len(roots)}-{name}-{index}"
                cells.append(
                    AttributionSimplex(cell, tuple(ids), (), replace(loc, cell=cell))
                )
                orders[cell] = order

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
                widths = [b - a for a, b in bounds]
                normal = tuple(
                    fmpq(1) / widths[i]
                    if k == i
                    else -fmpq(1) / widths[j]
                    if k == j
                    else fmpq(0)
                    for k in range(agents)
                )
                offset = bounds[i][0] / widths[i] - bounds[j][0] / widths[j]
                nodes.append(
                    SplitNode(node, normal, offset, node + "m", node + "p", loc)
                )
                route(minus, rest, node + "m")
                route(plus, rest, node + "p")

            route(list(orders), [(i, j) for i in range(agents) for j in range(i)], name)

        def grid(
            options, axis, bounds, node, nodes=nodes, loc=loc, triangulate=triangulate
        ):
            if axis == agents:
                triangulate(bounds, node)
                return
            first, *rest = options[axis]
            if rest:
                normal = tuple(fmpq(int(k == axis)) for k in range(agents))
                nodes.append(
                    SplitNode(node, normal, first[1], node + "m", node + "p", loc)
                )
                grid(options, axis + 1, (*bounds, first), node + "m")
                remaining = list(options)
                remaining[axis] = tuple(rest)
                grid(remaining, axis, bounds, node + "p")
            else:
                grid(options, axis + 1, (*bounds, first), node)

        grid(intervals, 0, (), "root")
        roots.append(RootBlock(key, "root", (), tuple(cells), tuple(nodes), loc))
    return tuple(roots), vertices, profiles


def star():
    return Graph(
        ("o", "a", "b", "c", "d"), (("o", "a"), ("b", "o"), ("o", "c"), ("d", "o"))
    )


def test_degree_four_seam_rejects_two_coarse_and_two_fine_incident_roots():
    graph = star()
    roots, vertices, _ = meshes(
        graph,
        cuts=lambda key, axis: (fmpq(1, 2),) if key.edges[0] >= 2 and axis == 1 else (),
    )
    assert all(
        check_local_conformity(graph, root, vertices).coverage.volume == 1
        for root in roots
    )
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, roots, vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "chart_face_mismatch"


@pytest.mark.parametrize("agents", [2, 3])
def test_compatible_edge_and_square_seams_with_mixed_orientations(agents):
    graph = Graph(("o", "a", "b"), (("o", "a"), ("b", "o")))
    roots, vertices, profiles = meshes(
        graph, agents, cuts=lambda key, axis: (fmpq(1, 2),)
    )
    result = check_chart_conformity(graph, agents, iter(roots), vertices)
    face = ProductFace((VertexPoint("o"), *(0 for _ in range(agents - 1))))
    assert result.faces[face].roots == (
        AttributionKey((0,) * agents),
        AttributionKey((1, *(0 for _ in range(agents - 1)))),
    )
    assert all(root.coverage.volume == 1 for root in result.roots.values())
    assert {face.codimension for face in result.faces} == set(range(1, agents + 1))
    assert len(result.faces[face].maximal_simplices) == (2 if agents == 2 else 8)
    assert all(len(ids) == agents for ids in result.faces[face].maximal_simplices)
    assert len(profiles) == len(vertices)


def test_codimension_two_roots_are_directly_compared_on_their_shared_edge():
    graph = Graph(("o", "a", "b"), (("o", "a"), ("b", "o")))
    roots, vertices, _ = meshes(
        graph,
        3,
        cuts=lambda key, axis: (
            (fmpq(1, 2),) if key.edges[:2] == (1, 1) and axis == 2 else ()
        ),
    )
    assert all(
        check_local_conformity(graph, root, vertices).coverage.volume == 1
        for root in roots
    )
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 3, roots, vertices)
    failure = caught.value.failure
    assert failure.code == "chart_face_mismatch"
    assert failure.location is not None
    assert failure.location["root"] == {"edges": [1, 1, 0]}
    # First comparison root000 meets root110 only on o x o x edge0.
    assert "{'edges': [0, 0, 0]}" in failure.message
    assert "[{'vertex': 'o'}, {'vertex': 'o'}, {'edge': 0}]" in failure.message


def test_leaf_boundaries_and_nonempty_maximal_restrictions():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, profiles = meshes(graph)
    result = check_chart_conformity(graph, 2, roots, vertices)
    assert len(result.faces) == 8  # Four edges and four corners, no invented roots.
    face = ProductFace((VertexPoint("a"), 0))
    ends = frozenset(profiles[(VertexPoint("a"), VertexPoint(x))] for x in ("a", "b"))
    raw = {
        frozenset(
            identifier
            for identifier in cell.vertices
            if vertices[identifier].point[0] == VertexPoint("a")
        )
        for cell in roots[0].simplices
    }
    assert frozenset({profiles[(VertexPoint("a"), VertexPoint("a"))]}) in raw
    assert result.faces[face].maximal_simplices == frozenset({ends})
    assert all(
        data.roots == (AttributionKey((0, 0)),) for data in result.faces.values()
    )
    corner = ProductFace((VertexPoint("a"), VertexPoint("b")))
    corner_id = profiles[(VertexPoint("a"), VertexPoint("b"))]
    raw_corner = {
        frozenset(identifier for identifier in cell.vertices if identifier == corner_id)
        for cell in roots[0].simplices
    }
    assert frozenset() in raw_corner
    assert result.faces[corner].maximal_simplices == frozenset(
        {frozenset({profiles[(VertexPoint("a"), VertexPoint("b"))]})}
    )
    assert all(
        subset for data in result.faces.values() for subset in data.maximal_simplices
    )


@pytest.mark.parametrize(
    "attack", ["missing", "extra", "reordered", "duplicate", "empty"]
)
def test_complete_attribution_root_sequence_is_rechecked(attack):
    graph = Graph(("o", "a", "b"), (("o", "a"), ("b", "o")))
    roots, vertices, _ = meshes(graph)
    changed = {
        "missing": roots[:-1],
        "extra": (*roots, roots[0]),
        "reordered": (roots[1], roots[0], *roots[2:]),
        "duplicate": (roots[0], roots[0], *roots[2:]),
        "empty": (),
    }[attack]
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, changed, vertices)
    assert caught.value.failure.code == "chart_root_sequence"


def test_global_profile_injectivity_is_rechecked_even_for_unused_aliases():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    vertex = next(iter(vertices.values()))
    vertices["unused-alias"] = replace(vertex, id="unused-alias")
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, roots, vertices)
    assert caught.value.failure.code == "chart_duplicate_profile"


def test_global_check_recomputes_local_conformity():
    from test_conformity import attribution_t_junction

    graph, root, vertices = attribution_t_junction()
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, (root,), vertices)
    assert caught.value.failure.code == "conformity_internal_incidence"


@pytest.mark.parametrize("coordinate", [0, 1, "0", "1"])
def test_endpoint_aliases_are_rejected_at_the_reviewed_bundle_boundary(
    tmp_path, coordinate
):
    import json

    from test_reader import tiny_bundle

    from upper_bound_verifier.reader import BundleReader

    tiny_bundle(tmp_path)
    path = tmp_path / "vertices.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["point"][0] = {"edge": 0, "coordinate": coordinate}
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    with pytest.raises(VerificationError) as caught:
        BundleReader(tmp_path)
    assert caught.value.failure.kind == FailureKind.REFUSED
    assert caught.value.failure.code == "schema_point"


def test_chart_results_own_immutable_maps():
    from collections.abc import MutableMapping
    from typing import cast

    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    result = check_chart_conformity(graph, 2, roots, vertices)
    with pytest.raises(TypeError):
        cast(MutableMapping, result.roots)[roots[0].key] = None
    with pytest.raises(TypeError):
        cast(MutableMapping, result.faces)[ProductFace((VertexPoint("a"), 0))] = None


def test_successful_branch_face_records_all_four_actual_incident_roots():
    graph = star()
    roots, vertices, _ = meshes(graph)
    result = check_chart_conformity(graph, 2, roots, vertices)
    seam = result.faces[ProductFace((VertexPoint("o"), 0))]
    assert seam.roots == tuple(AttributionKey((edge, 0)) for edge in range(4))
    leaf = result.faces[ProductFace((VertexPoint("a"), 0))]
    assert leaf.roots == (AttributionKey((0, 0)),)


@pytest.mark.parametrize(
    "attack",
    [
        "mapping_id",
        "dimension",
        "duplicate_cell",
        "boolean_edge",
        "local_table",
        "auxiliary_cell",
    ],
)
def test_decoded_input_prerequisites_cannot_silently_establish_a_complex(attack):
    from upper_bound_verifier.reader import ComparisonSimplex

    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    root = roots[0]
    first, second = root.simplices
    vertex = next(iter(vertices.values()))
    expected = {
        "mapping_id": "chart_vertex_id",
        "dimension": "chart_profile_dimension",
        "duplicate_cell": "chart_simplex_id",
        "boolean_edge": "chart_root_sequence",
        "local_table": "chart_local_vertices",
        "auxiliary_cell": "chart_simplex_kind",
    }[attack]
    if attack == "mapping_id":
        vertices[vertex.id] = replace(vertex, id="different")
    elif attack == "dimension":
        vertices[vertex.id] = replace(vertex, point=vertex.point[:1])
    elif attack == "duplicate_cell":
        root = replace(root, simplices=(first, replace(second, id=first.id)))
    elif attack == "boolean_edge":
        root = replace(root, key=AttributionKey((False, 0)))
    elif attack == "local_table":
        root = replace(root, vertices=(vertex,))
    else:
        cell = ComparisonSimplex(
            first.id, first.vertices, "T0", None, (), first.location
        )
        root = replace(root, simplices=(cell, second))
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, (root,), vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == expected


@pytest.mark.parametrize(
    "point,code",
    [(VertexPoint("unknown"), "reference_vertex"), ("unknown-edge", "reference_index")],
)
def test_unknown_global_point_references_are_certificate_failures(point, code):
    from upper_bound_verifier.graph import EdgePoint

    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    vertex = next(iter(vertices.values()))
    if point == "unknown-edge":
        point = EdgePoint(9, fmpq(1, 2))
    vertices[vertex.id] = replace(vertex, point=(point, vertex.point[1]))
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, roots, vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == code
    assert caught.value.failure.location == vertex.location.to_dict()


def test_missing_root_retains_expected_root_without_inventing_source_location():
    graph = Graph(("a", "b"), (("a", "b"),))
    with pytest.raises(VerificationError) as caught:
        check_chart_conformity(graph, 2, (), {})
    assert caught.value.failure.location == {"root": {"edges": [0, 0]}}
