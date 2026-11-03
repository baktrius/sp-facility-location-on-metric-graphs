"""Admissibility on real conforming meshes, keeping regional rows separate."""

from dataclasses import replace

import pytest
from flint import fmpq
from test_charts import meshes, star

from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.graph import (
    ConstantSelector,
    EdgePoint,
    Graph,
    PeakSelector,
    VertexPoint,
    chart_coordinate,
)
from upper_bound_verifier.lottery import check_lottery_admissibility


def weighted(roots, row):
    return tuple(
        replace(
            root,
            simplices=tuple(
                replace(cell, weights=tuple(row for _ in cell.vertices))
                for cell in root.simplices
            ),
        )
        for root in roots
    )


def test_all_zero_rows_cannot_establish_a_mechanism():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(0),))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), roots, vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "probability_normalization"
    assert caught.value.failure.location == roots[0].simplices[0].location.to_dict()


def test_negative_weight_is_rejected_even_when_row_sum_is_one():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(-1, 3), fmpq(4, 3)))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(
            graph, 2, (PeakSelector(0), PeakSelector(1)), roots, vertices
        )
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "probability_negative"


def test_missing_regional_rows_do_not_vacuously_verify():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), roots, vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "probability_shape"


def test_moving_peak_and_endpoint_mixture_agree_only_at_face_vertices():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    first, second = roots[0].simplices
    # On their diagonal x0=x1=t, delta_t and (1-t)delta_a+t delta_b
    # agree at t=0,1. At t=1/2, their mass at the midpoint is 1 versus 0.
    first = replace(first, weights=((fmpq(1), fmpq(0), fmpq(0)),) * 3)
    second = replace(
        second,
        weights=tuple(
            (
                fmpq(0),
                fmpq(point[0] == VertexPoint("a")),
                fmpq(point[0] == VertexPoint("b")),
            )
            for point in (vertices[v].point for v in second.vertices)
        ),
    )
    root = replace(roots[0], simplices=(first, second))
    selectors = (
        PeakSelector(0),
        ConstantSelector(VertexPoint("a")),
        ConstantSelector(VertexPoint("b")),
    )
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, selectors, (root,), vertices)
    assert caught.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert caught.value.failure.code == "lottery_consistency"


def test_duplicate_selectors_are_refused_at_the_admissibility_boundary():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(1), fmpq(0)))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(
            graph, 2, (PeakSelector(0), PeakSelector(0)), roots, vertices
        )
    assert caught.value.failure.kind == FailureKind.REFUSED
    assert caught.value.failure.code == "schema_duplicate_selector"


def test_different_columns_are_allowed_when_selectors_agree_on_whole_face():
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    first, second = roots[0].simplices
    first = replace(first, weights=((fmpq(1), fmpq(0)),) * 3)
    second = replace(second, weights=((fmpq(0), fmpq(1)),) * 3)
    root = replace(roots[0], simplices=(first, second))
    selectors = (PeakSelector(0), PeakSelector(1))
    result = check_lottery_admissibility(graph, 2, selectors, (root,), vertices)
    # x0=x1 on the shared diagonal. Distinct weights remain regional.
    assert result.regions[first.id].weights != result.regions[second.id].weights
    assert result.selectors == selectors
    assert result.geometry.roots[root.key].coverage.volume == 1


@pytest.mark.parametrize("disagree", [False, True])
def test_every_branch_seam_compares_whole_face_groups(disagree):
    graph = star()  # Four branches, two reversed orientations.
    roots, vertices, _ = meshes(graph)
    roots = tuple(
        weighted(
            (root,),
            (fmpq(1), fmpq(0), fmpq(0))
            if root.key.edges[0] < 2
            else (fmpq(0), fmpq(1), fmpq(0))
            if not disagree or root.key.edges[0] != 3
            else (fmpq(0), fmpq(0), fmpq(1)),
        )[0]
        for root in roots
    )
    selectors = (PeakSelector(0), ConstantSelector(VertexPoint("o")), PeakSelector(1))
    # On x0=o, peak0 and constant(o) coincide throughout the seam, while
    # peak1 varies. A third/fourth branch must not hide behind a matching pair.
    if disagree:
        with pytest.raises(VerificationError) as caught:
            check_lottery_admissibility(graph, 2, selectors, roots, vertices)
        assert caught.value.failure.code == "lottery_consistency"
        assert caught.value.failure.location is not None
        assert caught.value.failure.location["root"] == {"edges": [3, 0]}
    else:
        result = check_lottery_admissibility(graph, 2, selectors, roots, vertices)
        assert len(result.geometry.roots) == 16
        first = roots[0].simplices[0]
        last = roots[-1].simplices[0]
        face = set(first.vertices) & set(last.vertices)
        assert len(face) == 1  # Two branching coordinates fixed at o.
        vertex = next(iter(face))
        assert vertices[vertex].point == (VertexPoint("o"),) * 2
        assert (
            first.weights[first.vertices.index(vertex)]
            != last.weights[last.vertices.index(vertex)]
        )


@pytest.mark.parametrize("disagree", [False, True])
def test_singleton_contact_is_checked_directly(disagree):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, profiles = meshes(graph, cuts=lambda key, axis: (fmpq(1, 2),))
    roots = weighted(roots, (fmpq(1), fmpq(0)))
    root = roots[0]
    corner = profiles[(EdgePoint(0, fmpq(1, 2)),) * 2]
    # Opposite small boxes meet only at the center. Put these two first so
    # a missing singleton comparison cannot be masked by another failed pair.
    first = root.simplices[0]
    second = root.simplices[-1]
    assert set(first.vertices) & set(second.vertices) == {corner}
    if disagree:
        rows = tuple(
            (fmpq(0), fmpq(1)) if v == corner else row
            for v, row in zip(second.vertices, second.weights, strict=True)
        )
        second = replace(second, weights=rows)
    root = replace(
        root,
        simplices=(first, second, *root.simplices[1:-1]),
    )
    selectors = (PeakSelector(0), ConstantSelector(VertexPoint("a")))
    if disagree:
        with pytest.raises(VerificationError) as caught:
            check_lottery_admissibility(graph, 2, selectors, (root,), vertices)
        assert caught.value.failure.code == "lottery_consistency"
        assert f"face {(corner,)}" in caught.value.failure.message
        assert caught.value.failure.location is not None
        assert caught.value.failure.location["cell"] == second.id
    else:
        result = check_lottery_admissibility(graph, 2, selectors, (root,), vertices)
        assert len(result.regions) == 8


@pytest.mark.parametrize("weight", [fmpq(1, 2), fmpq(2), fmpq(1) + fmpq(1, 10**80)])
def test_nonnormalized_rows_are_exactly_rejected(weight):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (weight,))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), roots, vertices)
    assert caught.value.failure.code == "probability_normalization"


@pytest.mark.parametrize(
    "attack",
    ["extra_row", "missing_row", "short_column", "extra_column", "mutable_row"],
)
def test_every_weight_table_has_exact_vertex_and_selector_shape(attack):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(1), fmpq(0)))
    cell = roots[0].simplices[-1]
    rows = cell.weights
    changed = {
        "extra_row": (*rows, rows[0]),
        "missing_row": rows[:-1],
        "short_column": (*rows[:-1], (fmpq(1),)),
        "extra_column": (*rows[:-1], (*rows[-1], fmpq(0))),
        "mutable_row": (*rows[:-1], list(rows[-1])),
    }[attack]
    root = replace(
        roots[0], simplices=(*roots[0].simplices[:-1], replace(cell, weights=changed))
    )
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(
            graph, 2, (PeakSelector(0), PeakSelector(1)), (root,), vertices
        )
    assert caught.value.failure.code == "probability_shape"
    assert caught.value.failure.location is not None
    assert caught.value.failure.location["cell"] == cell.id


@pytest.mark.parametrize("scalar", [True, 1.0, "1", 1])
def test_decoded_weight_boundary_requires_flint_rationals(scalar):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (scalar,))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), roots, vertices)
    assert caught.value.failure.kind == FailureKind.REFUSED
    assert caught.value.failure.code == "probability_exact_type"


@pytest.mark.parametrize(
    "selectors,code,kind",
    [
        ((), "schema_selectors", FailureKind.REFUSED),
        ([PeakSelector(0)], "schema_selectors", FailureKind.REFUSED),
        ((object(),), "schema_selector", FailureKind.REFUSED),
        (
            (PeakSelector(0), PeakSelector(2)),
            "reference_index",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            (PeakSelector(0), ConstantSelector(VertexPoint("unknown"))),
            "reference_vertex",
            FailureKind.INVALID_CERTIFICATE,
        ),
        (
            (PeakSelector(0), ConstantSelector(EdgePoint(3, fmpq(1, 2)))),
            "reference_index",
            FailureKind.INVALID_CERTIFICATE,
        ),
    ],
)
def test_selector_family_is_checked_even_for_zero_weight_columns(selectors, code, kind):
    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(1), fmpq(0)))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, selectors, roots, vertices)
    assert caught.value.failure.kind == kind
    assert caught.value.failure.code == code


def test_geometry_is_recomputed_before_probabilities():
    from test_conformity import attribution_t_junction

    graph, root, vertices = attribution_t_junction()
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), (root,), vertices)
    assert caught.value.failure.code == "conformity_internal_incidence"
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(graph, 2, (PeakSelector(0),), (), vertices)
    assert caught.value.failure.code == "chart_root_sequence"


@pytest.mark.parametrize("negative", [False, True])
def test_last_regional_vertex_cannot_hide_invalid_mass(negative):
    graph = star()
    roots, vertices, _ = meshes(graph)
    roots = weighted(roots, (fmpq(1), fmpq(0)))
    cell = roots[-1].simplices[-1]
    tiny = fmpq(1, 10**80)
    row = (1 + tiny, -tiny) if negative else (1 + tiny, fmpq(0))
    cell = replace(cell, weights=(*cell.weights[:-1], row))
    root = replace(roots[-1], simplices=(*roots[-1].simplices[:-1], cell))
    with pytest.raises(VerificationError) as caught:
        check_lottery_admissibility(
            graph, 2, (PeakSelector(0), PeakSelector(1)), (*roots[:-1], root), vertices
        )
    assert caught.value.failure.code == (
        "probability_negative" if negative else "probability_normalization"
    )
    assert caught.value.failure.location == cell.location.to_dict()


def test_admissible_data_supports_exact_interpolation_and_owns_immutable_maps():
    from collections.abc import MutableMapping
    from fractions import Fraction
    from typing import cast

    graph = Graph(("a", "b"), (("a", "b"),))
    roots, vertices, _ = meshes(graph)
    cells = []
    for cell in roots[0].simplices:
        ids = tuple(reversed(cell.vertices))
        rows = tuple(
            (1 - (x := chart_coordinate(graph, vertices[v].point[0], 0)), x)
            for v in ids
        )
        cells.append(replace(cell, vertices=ids, weights=rows))
    root = replace(roots[0], simplices=tuple(cells))
    result = check_lottery_admissibility(
        graph, 2, (PeakSelector(0), PeakSelector(1)), iter((root,)), vertices
    )
    for cell in cells:
        shape = result.geometry.roots[root.key].coverage.simplices[cell.id]
        matrix = shape.vertices
        point = tuple(
            sum((matrix[i, j] for j in range(3)), fmpq(0)) / 3 for i in range(2)
        )
        weights = tuple(
            shape.interpolate(
                tuple(row[j] for row in result.regions[cell.id].weights)
            ).evaluate(point)
            for j in range(2)
        )
        oracle = sum((Fraction(str(matrix[0, j])) for j in range(3)), Fraction(0)) / 3
        assert tuple(Fraction(str(w)) for w in weights) == (1 - oracle, oracle)
        assert sum(weights, fmpq(0)) == 1 and min(weights) >= 0
    for mapping in (result.regions, result.vertices, result.geometry.roots):
        with pytest.raises(TypeError):
            cast(MutableMapping, mapping)["forged"] = None
    vertices.clear()
    assert len(result.vertices) == 4  # Caller changes cannot remove checked vertices.
