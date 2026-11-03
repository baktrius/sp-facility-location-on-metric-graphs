"""Public local attribution conformity, after genuine root coverage."""

from collections.abc import MutableMapping
from dataclasses import replace
from itertools import permutations
from typing import cast

import pytest
from flint import fmpq
from test_coverage import auxiliary_rectangles, square

from upper_bound_verifier.conformity import check_local_conformity
from upper_bound_verifier.coverage import check_root_coverage
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.graph import EdgePoint, VertexPoint
from upper_bound_verifier.reader import (
    AttributionKey,
    AttributionSimplex,
    LeafNode,
    ProfileVertex,
    RootBlock,
    SourceLocation,
    SplitNode,
)


def attribution_t_junction():
    graph, auxiliary = auxiliary_rectangles()
    key = AttributionKey(auxiliary.key.edges)
    loc = replace(auxiliary.location, file="attribution.jsonl", root=key)
    root = replace(
        auxiliary,
        key=key,
        vertices=(),
        simplices=tuple(
            AttributionSimplex(cell.id, cell.vertices, (), replace(loc, cell=cell.id))
            for cell in auxiliary.simplices
        ),
        location=loc,
    )
    return graph, root, {vertex.id: vertex for vertex in auxiliary.vertices}


def test_covering_attribution_t_junction_is_rejected_after_coverage():
    graph, root, vertices = attribution_t_junction()
    covered = check_root_coverage(graph, root, vertices)
    assert covered.volume == 1
    midpoint = (fmpq(1, 2), fmpq(1, 2))
    assert all(
        covered.simplices[name].contains(midpoint) for name in ("Lp", "Bm", "Tm")
    )

    with pytest.raises(VerificationError) as caught:
        check_local_conformity(graph, root, vertices)
    failure = caught.value.failure
    assert failure.kind == FailureKind.INVALID_CERTIFICATE
    assert failure.code == "conformity_internal_incidence"
    assert failure.witness is None
    assert failure.location is not None
    assert failure.location["root"] == root.key.to_data()
    assert failure.location["cell"] in {cell.id for cell in root.simplices}


def test_square_facets_use_global_sets_despite_reversed_vertex_order():
    graph, root, vertices = square()
    lower, upper = root.simplices
    root = replace(root, simplices=(replace(lower, vertices=("c", "b", "a")), upper))
    result = check_local_conformity(graph, root, vertices)
    assert len(result.facets) == 5
    assert result.boundary_facets == frozenset(
        {("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")}
    )
    assert {(x.cell, x.opposite) for x in result.facets[("a", "c")]} == {
        ("lower", 1),
        ("upper", 2),
    }
    assert result.coverage.volume == 1


def grid_square(cut: fmpq):
    """Four rectangles with matching edge subdivisions, each split diagonally."""
    graph, original, _ = square()
    loc = original.location
    points = {}
    cells = []
    nodes = [
        SplitNode("root", (fmpq(1), fmpq(0)), cut, "l", "r", loc),
        SplitNode("l", (fmpq(0), fmpq(1)), cut, "bl", "tl", loc),
        SplitNode("r", (fmpq(0), fmpq(1)), cut, "br", "tr", loc),
    ]
    for name, x0, x1, y0, y1 in (
        ("bl", 0, cut, 0, cut),
        ("tl", 0, cut, cut, 1),
        ("br", cut, 1, 0, cut),
        ("tr", cut, 1, cut, 1),
    ):
        ids = []
        for point in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            if point not in points:
                profile = tuple(
                    VertexPoint("a" if x == 0 else "b")
                    if x in (0, 1)
                    else EdgePoint(0, x)
                    for x in point
                )
                points[point] = ProfileVertex(f"v{len(points)}", profile, loc)
            ids.append(points[point].id)
        for suffix, indices in (("p", (0, 1, 2)), ("m", (0, 2, 3))):
            cell = name + suffix
            cells.append(
                AttributionSimplex(
                    cell, tuple(ids[j] for j in indices), (), replace(loc, cell=cell)
                )
            )
            nodes.append(LeafNode(cell, cell, loc))
        height, width = fmpq(y1 - y0), fmpq(x1 - x0)
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
    root = replace(original, simplices=tuple(cells), nodes=tuple(nodes))
    return graph, root, {v.id: v for v in points.values()}, points


@pytest.mark.parametrize("cut", [fmpq(1, 2), fmpq(1, 10**80)])
def test_lower_dimensional_contacts_interior_and_cube_boundary(cut):
    graph, root, vertices, points = grid_square(cut)
    result = check_local_conformity(graph, root, vertices)
    assert len(result.coverage.simplices) == 8
    assert len(result.boundary_facets) == 8
    cells = {cell.id: cell for cell in root.simplices}
    for left, right, point in (
        ("blp", "brp", (cut, fmpq(0))),  # Cube boundary, only a common vertex.
        ("blp", "trm", (cut, cut)),  # Interior, only a common vertex.
    ):
        common = set(cells[left].vertices) & set(cells[right].vertices)
        assert common == {points[point].id}
        for name in (left, right):
            shape = result.coverage.simplices[name]
            assert shape.contains(point)
            coordinates = shape.barycentric(point)
            assert coordinates is not None
            assert sum(value > 0 for value in coordinates) == 1
    # This edge is internal even though one endpoint lies on the cube boundary.
    diagonal = tuple(sorted((points[(0, 0)].id, points[(cut, cut)].id)))
    assert diagonal not in result.boundary_facets
    assert len(result.facets[diagonal]) == 2


def cube():
    """Six monotone tetrahedra, routed by the three coordinate comparisons."""
    graph, _, _ = square()
    key = AttributionKey((0, 0, 0))
    loc = SourceLocation("attribution.jsonl", 3, key)
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
                vertices[bits] = ProfileVertex(
                    f"v{len(vertices)}",
                    tuple(VertexPoint("b" if x else "a") for x in bits),
                    loc,
                )
            ids.append(vertices[bits].id)
        name = f"s{index}"
        cells.append(AttributionSimplex(name, tuple(ids), (), replace(loc, cell=name)))
        orders[name] = order
    nodes = []

    def tree(names, pairs, name):
        if len(names) == 1:
            nodes.append(LeafNode(name, names[0], loc))
            return
        (i, j), *rest = pairs
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
    root = RootBlock(key, "root", (), tuple(cells), tuple(nodes), loc)
    return graph, root, {v.id: v for v in vertices.values()}


def test_cube_triangulation_pairs_facets_and_allows_common_edges():
    graph, root, vertices = cube()
    result = check_local_conformity(graph, root, vertices)
    assert len(result.facets) == 18
    assert len(result.boundary_facets) == 12
    assert all(
        shape.volume() == fmpq(1, 6) for shape in result.coverage.simplices.values()
    )
    first, last = root.simplices[0], root.simplices[-1]
    assert len(set(first.vertices) & set(last.vertices)) == 2
    midpoint = (fmpq(1, 2),) * 3
    assert result.coverage.simplices[first.id].contains(midpoint)
    assert result.coverage.simplices[last.id].contains(midpoint)


def test_diagonal_with_boundary_vertices_is_actually_an_internal_facet():
    graph, root, vertices = square()
    result = check_local_conformity(graph, root, vertices)
    assert ("a", "c") not in result.boundary_facets
    assert len(result.facets[("a", "c")]) == 2


@pytest.mark.parametrize("attack", ["missing", "excess", "same_side"])
def test_missing_excess_and_same_side_cells_fail_coverage_before_facet_pairing(attack):
    """These pathologies cannot satisfy S08; never forge validated evidence."""
    graph, root, vertices = square()
    lower, upper = root.simplices
    if attack == "missing":
        root = replace(root, simplices=(lower,))
    elif attack == "excess":
        root = replace(root, simplices=(*root.simplices, replace(lower, id="extra")))
    else:
        root = replace(root, simplices=(lower, replace(upper, vertices=lower.vertices)))
    with pytest.raises(VerificationError) as caught:
        check_local_conformity(graph, root, vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code.startswith("coverage_")
    assert caught.value.failure.witness is None


def test_auxiliary_t_junction_keeps_coverage_without_attribution_requirement():
    graph, root = auxiliary_rectangles()
    assert check_root_coverage(graph, root).volume == 1
    with pytest.raises(VerificationError) as caught:
        check_local_conformity(graph, root, {})
    assert caught.value.failure.kind == FailureKind.REFUSED
    assert caught.value.failure.code == "conformity_root_kind"


def test_conformity_result_keeps_incidence_ownership():
    graph, root, vertices = square()
    result = check_local_conformity(graph, root, vertices)
    with pytest.raises(TypeError):
        cast(MutableMapping, result.facets)[("a", "c")] = ()


def test_facet_failure_keeps_original_simplex_source_location():
    graph, root, vertices = attribution_t_junction()
    loc = replace(
        root.simplices[0].location, file="/tmp/bundle/attribution.jsonl", line=91
    )
    root = replace(
        root, simplices=(replace(root.simplices[0], location=loc), *root.simplices[1:])
    )
    with pytest.raises(VerificationError) as caught:
        check_local_conformity(graph, root, vertices)
    assert caught.value.failure.location == {
        "file": loc.file,
        "line": 91,
        "root": root.key.to_data(),
        "cell": "Lp",
    }
