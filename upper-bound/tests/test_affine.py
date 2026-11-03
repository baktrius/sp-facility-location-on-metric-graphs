"""Public affine reduction behavior with independent exact value oracles."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from fractions import Fraction

import pytest
from flint import fmpq, fmpq_mat, fmpz_mat

from upper_bound_verifier.affine import (
    Quadratic,
    Violation,
    check_nonnegative,
    evaluate,
    transform,
)
from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.simplex import KernelStatus, Verified


def independent_value(H, g, c, point):
    """Direct original polynomial using Python Fraction, without reduction code."""
    point = tuple(Fraction(str(x)) for x in point)
    return (
        sum(
            point[i] * Fraction(str(H[i, j])) * point[j]
            for i in range(H.nrows())
            for j in range(H.ncols())
        )
        + sum(Fraction(str(a)) * x for a, x in zip(g, point, strict=True))
        + Fraction(str(c))
    )


def assert_replayed(quadratic, vertices, result):
    assert isinstance(result, Violation)
    assert result.status is KernelStatus.VIOLATION
    assert all(isinstance(x, fmpq) and x >= 0 for x in result.barycentric)
    assert sum(result.barycentric, fmpq(0)) == 1
    assert len(result.barycentric) == vertices.ncols()
    assert len(result.witness) == vertices.nrows()
    barycentric = tuple(Fraction(str(x)) for x in result.barycentric)
    expected_point = tuple(
        sum(Fraction(str(vertices[i, j])) * x for j, x in enumerate(barycentric))
        for i in range(vertices.nrows())
    )
    assert tuple(Fraction(str(x)) for x in result.witness) == expected_point
    assert (
        independent_value(quadratic.H, quadratic.g, quadratic.c, expected_point)
        == Fraction(str(result.value))
        < 0
    )
    assert evaluate(quadratic, result.witness) == result.value


def test_interior_violation_is_transported_to_original_coordinates():
    # q(x) = x^2 - 6x + 8 on [2, 4]; endpoints are zero, q(3) = -1.
    quadratic = Quadratic(fmpq_mat([[1]]), [-6], 8)
    result = check_nonnegative(quadratic, fmpq_mat([[2, 4]]))
    assert_replayed(quadratic, fmpq_mat([[2, 4]]), result)
    assert isinstance(result, Violation)
    assert result.barycentric == (fmpq(1, 2), fmpq(1, 2))
    assert result.witness == (fmpq(3),)
    assert result.value == -1
    assert result.witness[0] ** 2 - 6 * result.witness[0] + 8 == -1


def test_degenerate_claimed_simplex_is_refused_even_for_a_positive_constant():
    quadratic = Quadratic(fmpq_mat([[0, 0], [0, 0]]), [0, 0], 1)
    # Three collinear vertices are not a two-simplex.
    with pytest.raises(VerificationError) as caught:
        check_nonnegative(quadratic, fmpq_mat([[0, 1, 2], [0, 1, 2]]))
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "simplex_affine_dependence"


def test_quadratic_refuses_bool_instead_of_coercing_it_to_a_coefficient():
    with pytest.raises(VerificationError) as caught:
        Quadratic(fmpq_mat([[1]]), [True], 0)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "affine_scalar_type"
    assert caught.value.failure.location == {"field": "g", "coordinate": 0}


def test_midpoint_and_vertex_oracle_checks_every_transformed_entry():
    H = fmpq_mat([[2, 3], [3, -1]])
    g, c = [5, -7], 11
    vertices = fmpq_mat([[-1, 3, fmpq(1, 2)], [2, -2, fmpq(1, 3)]])
    B = transform(Quadratic(H, g, c), vertices)
    assert B == B.transpose()
    for i in range(3):
        vi = tuple(vertices[r, i] for r in range(2))
        qi = independent_value(H, g, c, vi)
        assert Fraction(str(B[i, i])) == qi
        for j in range(3):
            vj = tuple(vertices[r, j] for r in range(2))
            midpoint = tuple(
                (Fraction(str(a)) + Fraction(str(b))) / 2
                for a, b in zip(vi, vj, strict=True)
            )
            expected = (
                2 * independent_value(H, g, c, midpoint)
                - (qi + independent_value(H, g, c, vj)) / 2
            )
            assert Fraction(str(B[i, j])) == expected


def test_both_linear_half_terms_and_constant_homogenization():
    vertices = fmpq_mat([[1, 3], [-2, 1]])
    H = fmpq_mat(2, 2)
    # w = (10, 2); B_01 = (10+2)/2 + 7 = 13.
    assert transform(Quadratic(H, [2, -4], 7), vertices) == fmpq_mat(
        [[17, 13], [13, 9]]
    )
    assert transform(Quadratic(H, [0, 0], fmpq(-2, 3)), vertices) == fmpq_mat(
        [[fmpq(-2, 3)] * 2] * 2
    )


def test_line_embedded_in_three_dimensions_transports_an_interior_witness():
    quadratic = Quadratic(fmpq_mat([[1, 0, 0], [0, 0, 0], [0, 0, 0]]), [-6, 0, 0], 8)
    vertices = fmpq_mat([[2, 4], [7, 9], [-1, 3]])
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(3), fmpq(8), fmpq(1))
    assert result.value == -1


@pytest.mark.parametrize("c, verified", [(1, True), (0, True), (-1, False)])
@pytest.mark.parametrize("dimension", [0, 1, 3])
def test_singletons_including_zero_dimensional_ambient_space(dimension, c, verified):
    H = fmpq_mat(dimension, dimension)
    vertices = fmpq_mat(dimension, 1)
    quadratic = Quadratic(H, [0] * dimension, c)
    assert evaluate(quadratic, [0] * dimension) == c
    assert transform(quadratic, vertices) == fmpq_mat([[c]])
    result = check_nonnegative(quadratic, vertices)
    assert isinstance(result, Verified) == verified
    if not verified:
        assert_replayed(quadratic, vertices, result)
        assert isinstance(result, Violation)
        assert result.witness == (fmpq(0),) * dimension
        assert result.barycentric == (fmpq(1),)


def test_nonzero_singleton_checks_original_linear_and_quadratic_terms():
    quadratic = Quadratic(fmpq_mat([[1, 2], [2, 0]]), [-3, 5], 2)
    vertices = fmpq_mat([[2], [-1]])
    # 4 - 8 - 6 - 5 + 2 = -13.
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    assert isinstance(result, Violation)
    assert result.value == -13


def test_negative_vertex_and_tiny_negative_interior_are_replayed():
    vertices = fmpq_mat([[0, 1]])
    quadratic = Quadratic(fmpq_mat([[0]]), [-2], 1)
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    assert isinstance(result, Violation)
    assert result.barycentric == (fmpq(0), fmpq(1))
    epsilon = fmpq(1, 10**100)
    quadratic = Quadratic(fmpq_mat([[9]]), [-12], 4 - epsilon)
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(2, 3),)
    assert result.value == -epsilon


def test_negative_ambient_values_outside_simplex_do_not_prevent_verification():
    quadratic = Quadratic(fmpq_mat([[1]]), [2], fmpq(1, 2))
    assert evaluate(quadratic, [-1]) == fmpq(-1, 2)
    assert isinstance(check_nonnegative(quadratic, fmpq_mat([[1, 2]])), Verified)
    # Singular H with a zero minimum on an embedded line also verifies.
    quadratic = Quadratic(fmpq_mat([[1, 0], [0, 0]]), [0, 0], 0)
    assert isinstance(
        check_nonnegative(quadratic, fmpq_mat([[-1, 1], [2, 2]])), Verified
    )


@pytest.mark.parametrize(
    "H,g,c,code",
    [
        ([[1]], [0], 0, "affine_h_type"),
        (fmpz_mat([[1]]), [0], 0, "affine_h_type"),
        (fmpq_mat([[1, 0]]), [0], 0, "affine_h_shape"),
        (fmpq_mat([[1, 2], [0, 1]]), [0, 0], 0, "affine_h_symmetry"),
        (fmpq_mat([[1]]), None, 0, "affine_g_type"),
        (fmpq_mat([[1]]), fmpq_mat([[0]]), 0, "affine_g_type"),
        (fmpq_mat([[1]]), [], 0, "affine_g_dimension"),
        (fmpq_mat([[1]]), [0, 0], 0, "affine_g_dimension"),
        (fmpq_mat(0, 0), [0], 0, "affine_g_dimension"),
    ],
)
def test_invalid_quadratic_dimensions_symmetry_and_types_are_refused(H, g, c, code):
    with pytest.raises(VerificationError) as caught:
        Quadratic(H, g, c)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == code


@pytest.mark.parametrize(
    "bad", [True, 0.5, float("nan"), float("inf"), "1", Fraction(1), Decimal(1), 1j]
)
def test_all_coefficient_and_point_scalars_must_be_exact(bad):
    H = fmpq_mat([[1]])
    quadratic = Quadratic(H, [0], 0)
    for operation in (
        lambda: Quadratic(H, [bad], 0),
        lambda: Quadratic(H, [0], bad),
        lambda: evaluate(quadratic, [bad]),
    ):
        with pytest.raises(VerificationError) as caught:
            operation()
        assert caught.value.failure.kind is FailureKind.REFUSED
        assert caught.value.failure.code == "affine_scalar_type"


@pytest.mark.parametrize(
    "vertices,code",
    [
        ([[0, 1]], "simplex_vertices_type"),
        (fmpz_mat([[0, 1]]), "simplex_vertices_type"),
        (fmpq_mat(0, 1), "simplex_vertices_dimension"),
        (fmpq_mat([[0], [1]]), "simplex_vertices_dimension"),
        (fmpq_mat(1, 0), "simplex_vertices_shape"),
        (fmpq_mat([[2, 2]]), "simplex_affine_dependence"),
        (fmpq_mat([[0, 1, 2]]), "simplex_affine_dependence"),
    ],
)
def test_both_reduction_interfaces_refuse_invalid_vertex_matrices(vertices, code):
    quadratic = Quadratic(fmpq_mat([[0]]), [0], 1)
    for operation in (transform, check_nonnegative):
        with pytest.raises(VerificationError) as caught:
            operation(quadratic, vertices)
        assert caught.value.failure.kind is FailureKind.REFUSED
        assert caught.value.failure.code == code


def test_zero_dimensional_empty_hull_and_repeated_singletons_are_refused():
    quadratic = Quadratic(fmpq_mat(0, 0), [], 1)
    for count, code in [
        (0, "simplex_vertices_shape"),
        (2, "simplex_affine_dependence"),
    ]:
        with pytest.raises(VerificationError) as caught:
            check_nonnegative(quadratic, fmpq_mat(0, count))
        assert caught.value.failure.code == code


@pytest.mark.parametrize(
    "point,code",
    [
        (None, "affine_point_type"),
        (iter([0]), "affine_point_type"),
        ([], "affine_point_dimension"),
        ([0, 1], "affine_point_dimension"),
    ],
)
def test_original_evaluation_validates_point_shape(point, code):
    with pytest.raises(VerificationError) as caught:
        evaluate(Quadratic(fmpq_mat([[1]]), [0], 0), point)
    assert caught.value.failure.code == code


def test_public_operations_require_a_quadratic_record():
    for operation in (evaluate, transform, check_nonnegative):
        with pytest.raises(VerificationError) as caught:
            operation(None, fmpq_mat([[0]]))
        assert caught.value.failure.code == "affine_quadratic_type"


def test_records_and_results_do_not_alias_mutable_inputs():
    H, g = fmpq_mat([[1]]), [-6]
    quadratic = Quadratic(H, g, 8)
    H[0, 0] = 100
    g[0] = 100
    exposed_H = quadratic.H
    exposed_H[0, 0] = 100
    assert evaluate(quadratic, [3]) == -1
    with pytest.raises(FrozenInstanceError):
        quadratic.c = fmpq(100)  # ty: ignore[invalid-assignment]
    vertices = fmpq_mat([[2, 4]])
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    vertices[0, 0] = 100
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(3),)
    with pytest.raises(FrozenInstanceError):
        result.witness = (fmpq(100),)  # ty: ignore[invalid-assignment]


def test_triangle_full_support_violation_has_two_original_coordinates():
    # q = (7/4)((1-x-y)^2+x^2+y^2) - 3/4; every edge minimum is 1/8.
    quadratic = Quadratic(
        fmpq_mat([[fmpq(7, 2), fmpq(7, 4)], [fmpq(7, 4), fmpq(7, 2)]]),
        [fmpq(-7, 2), fmpq(-7, 2)],
        1,
    )
    vertices = fmpq_mat([[0, 1, 0], [0, 0, 1]])
    result = check_nonnegative(quadratic, vertices)
    assert_replayed(quadratic, vertices, result)
    assert isinstance(result, Violation)
    assert result.barycentric == (fmpq(1, 3),) * 3
    assert result.witness == (fmpq(1, 3),) * 2
    assert result.value == fmpq(-1, 6)


def test_small_one_dimensional_family_against_direct_polynomial_minima():
    left, right = Fraction(-1, 2), Fraction(3, 2)
    vertices = fmpq_mat([[fmpq(-1, 2), fmpq(3, 2)]])
    for a in range(-2, 3):
        for b in range(-2, 3):
            for c in range(-2, 3):
                candidates = [left, right]
                if a > 0:
                    stationary = Fraction(-b, 2 * a)
                    if left <= stationary <= right:
                        candidates.append(stationary)
                expected = min(a * x * x + b * x + c for x in candidates) >= 0
                quadratic = Quadratic(fmpq_mat([[a]]), [b], c)
                result = check_nonnegative(quadratic, vertices)
                assert isinstance(result, Verified) == expected
                if not expected:
                    assert_replayed(quadratic, vertices, result)
