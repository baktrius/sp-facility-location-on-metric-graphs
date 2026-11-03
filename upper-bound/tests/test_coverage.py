"""Public exact root coverage behavior, independently hand-built meshes."""

from collections.abc import MutableMapping
from dataclasses import replace
from typing import cast

import pytest
from flint import fmpq

from upper_bound_verifier.coverage import check_root_coverage
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.geometry import Simplex
from upper_bound_verifier.graph import EdgePoint, VertexPoint, parse_graph
from upper_bound_verifier.reader import (
    ApproximationKey,
    AttributionKey,
    AttributionSimplex,
    ComparisonSimplex,
    LeafNode,
    ProfileVertex,
    ReportCandidate,
    RootBlock,
    SourceLocation,
    SPKey,
    SplitNode,
)


def square():
    graph = parse_graph({"vertices": ["a", "b"], "edges": [["a", "b"]]})
    key = AttributionKey((0, 0))
    loc = SourceLocation("attribution.jsonl", 3, key)
    vertices = {
        name: ProfileVertex(
            name, tuple(VertexPoint("b" if x else "a") for x in point), loc
        )
        for name, point in zip("abcd", ((0, 0), (1, 0), (1, 1), (0, 1)), strict=True)
    }
    cells = tuple(
        AttributionSimplex(name, tuple(ids), (), SourceLocation(loc.file, i, key, name))
        for i, (name, ids) in enumerate((("lower", "abc"), ("upper", "acd")), 4)
    )
    nodes = (
        SplitNode("root", (fmpq(1), fmpq(-1)), fmpq(0), "minus", "plus", loc),
        LeafNode("minus", "upper", loc),
        LeafNode("plus", "lower", loc),
    )
    return graph, RootBlock(key, "root", (), cells, nodes, loc), vertices


def test_exact_square_partition_has_closed_coverage_and_derived_memberships():
    graph, root, vertices = square()
    result = check_root_coverage(graph, root, vertices)
    assert result.volume == 1
    assert result.memberships["root"] == frozenset({"lower", "upper"})
    assert result.memberships["minus"] == frozenset({"upper"})
    assert result.memberships["plus"] == frozenset({"lower"})
    for point in ((0, 0), (1, 0), (1, 1), (0, 1), (fmpq(1, 2), fmpq(1, 2))):
        assert any(cell.contains(point) for cell in result.simplices.values())


def test_crossing_original_cells_repeat_at_leaves_but_volume_counts_once():
    graph, root, vertices = square()
    diagonal = root.nodes[0]
    assert isinstance(diagonal, SplitNode)
    nodes = (
        SplitNode(
            "root", (fmpq(1), fmpq(0)), fmpq(1, 2), "left", "right", root.location
        ),
        replace(diagonal, id="left", minus="lm", plus="lp"),
        replace(diagonal, id="right", minus="rm", plus="rp"),
        *(
            LeafNode(name, cell, root.location)
            for name, cell in (
                ("lm", "upper"),
                ("lp", "lower"),
                ("rm", "upper"),
                ("rp", "lower"),
            )
        ),
    )
    result = check_root_coverage(graph, replace(root, nodes=nodes), vertices)
    assert (
        result.memberships["left"]
        == result.memberships["right"]
        == frozenset({"lower", "upper"})
    )
    assert (
        sum(
            result.simplices[name].volume()
            for leaf in ("lm", "lp", "rm", "rp")
            for name in result.memberships[leaf]
        )
        == 2
    )
    assert result.volume == 1


def assert_rejected(graph, root, vertices, code):
    with pytest.raises(VerificationError) as caught:
        check_root_coverage(graph, root, vertices)
    failure = caught.value.failure
    assert failure.kind == FailureKind.INVALID_CERTIFICATE
    assert failure.code == code
    assert failure.witness is None
    assert failure.location is not None
    assert failure.location["root"] == root.key.to_data()
    assert "file" in failure.location and "line" in failure.location
    return failure


@pytest.mark.parametrize(
    "attack,code",
    [
        ("missing", "coverage_simplex_reference"),
        ("overlap", "coverage_leaf_membership"),
        ("wrong_leaf", "coverage_leaf_membership"),
        ("zero_normal", "coverage_zero_normal"),
        ("same_children", "coverage_distinct_children"),
        ("shared_child", "coverage_tree_parent"),
        ("self_cycle", "coverage_tree_parent"),
        ("root_parent", "coverage_tree_parent"),
        ("unreachable_leaf", "coverage_tree_parent"),
        ("unreachable_cycle", "coverage_tree_unreachable"),
        ("missing_child", "coverage_child_reference"),
        ("missing_root", "coverage_tree_reference"),
        ("duplicate_node", "coverage_duplicate_node"),
        ("duplicate_cell", "coverage_duplicate_simplex"),
        ("unknown_leaf", "coverage_simplex_reference"),
        ("missing_vertex", "coverage_vertex_reference"),
        ("dependent", "simplex_affine_dependence"),
        ("embedded", "simplex_full_dimension"),
        ("wrong_chart", "simplex_root_chart"),
        ("normal_dimension", "coverage_hyperplane"),
        ("empty", "coverage_empty"),
    ],
)
def test_adversarial_tree_references_and_geometry(attack, code):
    graph, root, vertices = square()
    split, minus, plus = root.nodes
    assert isinstance(split, SplitNode)
    lower, upper = root.simplices
    if attack == "missing":
        root = replace(root, simplices=(lower,))
    elif attack == "overlap":
        root = replace(root, simplices=(lower, replace(upper, vertices=lower.vertices)))
    elif attack == "wrong_leaf":
        root = replace(root, nodes=(split, replace(minus, simplex="lower"), plus))
    elif attack == "zero_normal":
        root = replace(
            root, nodes=(replace(split, normal=(fmpq(0), fmpq(0))), minus, plus)
        )
    elif attack == "same_children":
        root = replace(root, nodes=(replace(split, plus="minus"), minus, plus))
    elif attack == "shared_child":
        root = replace(
            root,
            nodes=(
                split,
                replace(split, id="minus", minus="plus", plus="extra"),
                plus,
                LeafNode("extra", "lower", root.location),
            ),
        )
    elif attack == "self_cycle":
        root = replace(root, nodes=(replace(split, minus="root"), minus, plus))
    elif attack == "root_parent":
        root = replace(
            root, nodes=(*root.nodes, replace(split, id="extra", minus="root"))
        )
    elif attack == "unreachable_leaf":
        root = replace(
            root, nodes=(*root.nodes, LeafNode("extra", "upper", root.location))
        )
    elif attack == "unreachable_cycle":
        root = replace(
            root,
            nodes=(
                *root.nodes,
                replace(split, id="x", minus="y", plus="xl"),
                replace(split, id="y", minus="x", plus="yl"),
                LeafNode("xl", "upper", root.location),
                LeafNode("yl", "lower", root.location),
            ),
        )
    elif attack == "missing_child":
        root = replace(root, nodes=(replace(split, minus="absent"), minus, plus))
    elif attack == "missing_root":
        root = replace(root, tree="absent")
    elif attack == "duplicate_node":
        root = replace(root, nodes=(*root.nodes, plus))
    elif attack == "duplicate_cell":
        root = replace(root, simplices=(*root.simplices, lower))
    elif attack == "unknown_leaf":
        root = replace(root, nodes=(split, replace(minus, simplex="absent"), plus))
    elif attack == "missing_vertex":
        root = replace(
            root, simplices=(replace(lower, vertices=("absent", "b", "c")), upper)
        )
    elif attack == "dependent":
        root = replace(
            root, simplices=(replace(lower, vertices=("a", "a", "c")), upper)
        )
    elif attack == "embedded":
        root = replace(root, simplices=(replace(lower, vertices=("a", "b")), upper))
    elif attack == "wrong_chart":
        graph = parse_graph(
            {"vertices": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"]]}
        )
        vertices["a"] = replace(
            vertices["a"], point=(VertexPoint("c"), VertexPoint("a"))
        )
    elif attack == "normal_dimension":
        root = replace(root, nodes=(replace(split, normal=(fmpq(1),)), minus, plus))
    elif attack == "empty":
        root = replace(root, simplices=())
    failure = assert_rejected(graph, root, vertices, code)
    if attack in {"missing_vertex", "dependent", "embedded", "wrong_chart"}:
        assert failure.location["cell"] == "lower"
        assert failure.location["line"] == 4


def auxiliary_rectangles():
    """Six triangles; a T junction at (1/2,1/2) on the left shared edge."""
    graph, attribution, _ = square()
    key = ApproximationKey(ReportCandidate(0), (0, 0))
    loc = SourceLocation("approximation.jsonl", 2, key)
    vertices = {}
    cells = []
    nodes = [
        SplitNode("root", (fmpq(1), fmpq(0)), fmpq(1, 2), "L", "right", loc),
        SplitNode("right", (fmpq(0), fmpq(1)), fmpq(1, 2), "B", "T", loc),
    ]
    for name, x0, x1, y0, y1 in (
        ("L", fmpq(0), fmpq(1, 2), fmpq(0), fmpq(1)),
        ("B", fmpq(1, 2), fmpq(1), fmpq(0), fmpq(1, 2)),
        ("T", fmpq(1, 2), fmpq(1), fmpq(1, 2), fmpq(1)),
    ):
        ids = []
        for point in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            if point not in vertices:
                vertex_id = f"v{len(vertices)}"
                profile = tuple(
                    VertexPoint("a" if x == 0 else "b")
                    if x in (0, 1)
                    else EdgePoint(0, x)
                    for x in point
                )
                vertices[point] = ProfileVertex(vertex_id, profile, loc)
            ids.append(vertices[point].id)
        for suffix, indices in (("p", (0, 1, 2)), ("m", (0, 2, 3))):
            cells.append(
                ComparisonSimplex(
                    name + suffix,
                    tuple(ids[i] for i in indices),
                    attribution.simplices[0].id,
                    None,
                    (),
                    replace(loc, cell=name + suffix),
                )
            )
            nodes.append(LeafNode(name + suffix, name + suffix, loc))
        height, width = y1 - y0, x1 - x0
        nodes.append(
            SplitNode(
                name,
                (height, -width),
                height * x0 - width * y0,
                name + "m",
                name + "p",
                loc,
            )
        )
    return graph, RootBlock(
        key, "root", tuple(vertices.values()), tuple(cells), tuple(nodes), loc
    )


def test_nonconforming_auxiliary_partition_passes_with_local_vertex_namespace():
    graph, root = auxiliary_rectangles()
    result = check_root_coverage(graph, root, {})
    assert result.volume == 1
    assert len(result.simplices) == 6
    midpoint = (fmpq(1, 2), fmpq(1, 2))
    assert result.simplices["Lp"].contains(midpoint)
    matrix = result.simplices["Lp"].vertices
    assert midpoint not in tuple(
        tuple(matrix[i, j] for i in range(2)) for j in range(3)
    )
    assert result.simplices["Bm"].contains(midpoint)
    assert result.simplices["Tm"].contains(midpoint)
    assert sum(cell.volume() for cell in result.simplices.values()) == 1


def test_gap_with_equal_volume_overlap_cannot_fake_coverage():
    graph, root, vertices = square()
    lower, upper = root.simplices
    attacked = replace(
        root, simplices=(lower, replace(upper, vertices=("c", "a", "b")))
    )
    from upper_bound_verifier.geometry import simplex_in_root

    shapes = [
        simplex_in_root(
            graph, root.key.edges, tuple(vertices[v].point for v in cell.vertices)
        )
        for cell in attacked.simplices
    ]
    assert sum(shape.volume() for shape in shapes) == 1
    assert all(shape.contains((fmpq(3, 4), fmpq(1, 4))) for shape in shapes)
    assert not any(shape.contains((fmpq(1, 4), fmpq(3, 4))) for shape in shapes)
    assert_rejected(graph, attacked, vertices, "coverage_leaf_membership")


def test_volume_gap_after_valid_singleton_leaf_is_rejected():
    graph, root, vertices = square()
    root = replace(
        root,
        simplices=(root.simplices[0],),
        nodes=(LeafNode("root", "lower", root.location),),
    )
    assert_rejected(graph, root, vertices, "coverage_volume")


@pytest.mark.parametrize("scale", [fmpq(1), fmpq(-1), fmpq(1, 10**80)])
def test_exact_boundary_ties_route_only_to_the_weak_side(scale):
    graph, root, vertices = square()
    node = root.nodes[0]
    assert isinstance(node, SplitNode)
    cut = replace(node, normal=tuple(scale * x for x in node.normal))
    if scale < 0:
        cut = replace(cut, minus=node.plus, plus=node.minus)
    result = check_root_coverage(
        graph, replace(root, nodes=(cut, *root.nodes[1:])), vertices
    )
    assert result.memberships["minus"] == frozenset({"upper"})
    assert result.memberships["plus"] == frozenset({"lower"})


def test_coverage_maps_are_immutable_and_geometry_keeps_ownership():
    graph, root, vertices = square()
    result = check_root_coverage(graph, root, vertices)
    with pytest.raises(TypeError):
        cast(MutableMapping[str, frozenset[str]], result.memberships)["root"] = (
            frozenset()
        )
    with pytest.raises(TypeError):
        cast(MutableMapping[str, Simplex], result.simplices)["lower"] = (
            result.simplices["upper"]
        )
    matrix = result.simplices["lower"].vertices
    matrix[0, 0] = 99
    assert result.simplices["lower"].vertices[0, 0] == 0


def test_descendant_cuts_use_original_vertices_even_beyond_path_clipping():
    graph, root, vertices = square()
    diagonal = root.nodes[0]
    assert isinstance(diagonal, SplitNode)
    loc = root.location
    nodes = [
        SplitNode("root", (fmpq(1), fmpq(0)), fmpq(1, 2), "left", "R", loc),
        SplitNode("left", (fmpq(1), fmpq(0)), fmpq(3, 4), "LL", "LR", loc),
    ]
    for name in ("R", "LL", "LR"):
        nodes.extend(
            (
                replace(diagonal, id=name, minus=name + "m", plus=name + "p"),
                LeafNode(name + "m", "upper", loc),
                LeafNode(name + "p", "lower", loc),
            )
        )
    result = check_root_coverage(graph, replace(root, nodes=tuple(nodes)), vertices)
    # The LR spatial path is empty, but original simplices still cross BOTH
    # hyperplanes. It must retain both original IDs, without clipping them.
    assert result.memberships["LR"] == frozenset({"upper", "lower"})
    assert result.volume == 1


def test_sp_cube_partition_uses_the_same_public_coverage_boundary():
    from itertools import permutations

    graph, _, _ = square()
    key = SPKey(0, (0, 0, 0))
    loc = SourceLocation("sp.jsonl", 2, key)
    vertices = {}
    cells = []
    orders = {}
    for index, order in enumerate(permutations(range(3))):
        point = [0, 0, 0]
        ids = []
        for axis in (None, *order):
            if axis is not None:
                point[axis] = 1
            bits = tuple(point)
            if bits not in vertices:
                name = f"v{len(vertices)}"
                vertices[bits] = ProfileVertex(
                    name, tuple(VertexPoint("b" if x else "a") for x in bits), loc
                )
            ids.append(vertices[bits].id)
        name = f"s{index}"
        cells.append(
            ComparisonSimplex(name, tuple(ids), "T0", "T1", (), replace(loc, cell=name))
        )
        orders[name] = order
    nodes = []

    def tree(names, pairs, name):
        if len(names) == 1:
            nodes.append(LeafNode(name, names[0], loc))
            return
        first, *rest = pairs
        i, j = first
        minus = [n for n in names if orders[n].index(i) > orders[n].index(j)]
        plus = [n for n in names if n not in minus]
        if not minus or not plus:
            tree(names, rest, name)
            return
        normal = tuple(fmpq(int(k == i) - int(k == j)) for k in range(3))
        nodes.append(SplitNode(name, normal, fmpq(0), name + "m", name + "p", loc))
        tree(minus, rest, name + "m")
        tree(plus, rest, name + "p")

    tree(list(orders), [(0, 1), (0, 2), (1, 2)], "root")
    root = RootBlock(
        key, "root", tuple(vertices.values()), tuple(cells), tuple(nodes), loc
    )
    result = check_root_coverage(graph, root)
    assert len(result.simplices) == 6
    assert all(cell.volume() == fmpq(1, 6) for cell in result.simplices.values())
    assert result.volume == 1


@pytest.mark.parametrize("offset", [fmpq(1), fmpq(-1)])
def test_empty_computed_leaf_is_rejected_even_when_original_volume_is_one(offset):
    graph, root, vertices = square()
    split = root.nodes[0]
    assert isinstance(split, SplitNode)
    root = replace(root, nodes=(replace(split, offset=offset), *root.nodes[1:]))
    assert_rejected(graph, root, vertices, "coverage_leaf_membership")


def test_global_table_is_required_and_local_auxiliary_ids_are_not_overridden():
    graph, root, _ = square()
    assert_rejected(graph, root, None, "coverage_vertices")
    graph, root = auxiliary_rectangles()
    bad = replace(
        root.simplices[0], vertices=("absent", *root.simplices[0].vertices[1:])
    )
    root = replace(root, simplices=(bad, *root.simplices[1:]))
    external = {"absent": root.vertices[0]}
    assert_rejected(graph, root, external, "coverage_vertex_reference")


def test_auxiliary_local_duplicate_ids_are_rejected():
    graph, root = auxiliary_rectangles()
    root = replace(root, vertices=(*root.vertices, root.vertices[0]))
    assert_rejected(graph, root, {}, "coverage_duplicate_vertex")


def test_node_failure_preserves_its_reader_file_and_physical_line():
    graph, root, vertices = square()
    split = root.nodes[0]
    assert isinstance(split, SplitNode)
    loc = SourceLocation("/tmp/bundle/attribution.jsonl", 81, root.key)
    root = replace(
        root,
        nodes=(
            replace(split, normal=(fmpq(0), fmpq(0)), location=loc),
            *root.nodes[1:],
        ),
    )
    failure = assert_rejected(graph, root, vertices, "coverage_zero_normal")
    assert failure.location == {
        "file": loc.file,
        "line": 81,
        "root": root.key.to_data(),
    }
