"""Public exact-simplex behavior, using hand-computed quadratic values."""

from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest
from flint import fmpq, fmpq_mat

from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.simplex import (
    KernelStatus,
    Verified,
    Violation,
    check_nonnegative,
    evaluate_quadratic,
)


def assert_negative_witness(matrix: fmpq_mat, result: Verified | Violation):
    """Replay by independent Python Fraction arithmetic as well as public FLINT."""
    assert isinstance(result, Violation)
    assert result.status is KernelStatus.VIOLATION
    assert len(result.witness) == matrix.nrows()
    assert all(isinstance(x, fmpq) and x >= 0 for x in result.witness)
    assert sum(result.witness, fmpq(0)) == 1
    coordinates = tuple(Fraction(str(x)) for x in result.witness)
    independent_value = sum(
        coordinates[i] * Fraction(str(matrix[i, j])) * coordinates[j]
        for i in range(matrix.nrows())
        for j in range(matrix.ncols())
    )
    assert independent_value == Fraction(str(result.value)) < 0
    assert evaluate_quadratic(matrix, result.witness) == result.value


def test_positive_diagonal_is_verified():
    result = check_nonnegative(fmpq_mat([[2, 0], [0, 3]]))
    assert isinstance(result, Verified)
    assert result.status is KernelStatus.VERIFIED


def test_empty_matrix_is_refused_instead_of_vacuous_verification():
    with pytest.raises(VerificationError) as caught:
        check_nonnegative(fmpq_mat(0, 0))
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == "kernel_matrix_shape"


def test_interior_negative_witness_is_exact_and_publicly_replayable():
    matrix = fmpq_mat([[1, -2], [-2, 1]])
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(1, 2), fmpq(1, 2))
    assert result.value == fmpq(-1, 2)


@pytest.mark.parametrize("order", [1, 4])
def test_negative_last_diagonal_has_a_vertex_witness(order):
    matrix = fmpq_mat(order, order)
    for i in range(order):
        matrix[i, i] = 2
    matrix[order - 1, order - 1] = -7
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.witness == tuple(fmpq(int(i == order - 1)) for i in range(order))
    assert result.value == -7


def test_negative_full_support_after_every_proper_face_is_nonnegative():
    # q = (7/4) sum(lambda_i^2) - 3/4; every edge minimum is 1/8.
    matrix = fmpq_mat(
        [[1 if i == j else fmpq(-3, 4) for j in range(3)] for i in range(3)]
    )
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(1, 3),) * 3
    assert result.value == fmpq(-1, 6)


def test_late_proper_face_yields_a_witness_with_zero_off_support():
    # The negative two-coordinate face is the last pair, {2, 3}.
    matrix = fmpq_mat([[1 if i == j else 0 for j in range(4)] for i in range(4)])
    matrix[2, 3] = matrix[3, 2] = -2
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(0), fmpq(0), fmpq(1, 2), fmpq(1, 2))


@pytest.mark.parametrize(
    "entries",
    [
        [[0]],
        [[0, 0], [0, 0]],
        [[3, 3, 3], [3, 3, 3], [3, 3, 3]],  # Constant positive.
        [[0, 0, 1], [0, 0, 1], [1, 1, 2]],  # Flat minimizing edge.
        [[1, -1], [-1, 1]],  # (lambda_0 - lambda_1)^2.
        [[1, -2], [-2, 4]],  # Rational zero at (2/3, 1/3).
    ],
)
def test_constant_flat_and_singular_quadratics_verify_exact_zeros(entries):
    assert check_nonnegative(fmpq_mat(entries)).status is KernelStatus.VERIFIED


def test_constant_negative_quadratic_has_a_valid_witness():
    matrix = fmpq_mat([[-2, -2, -2]] * 3)
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.value == -2


def test_stationary_point_outside_simplex_is_not_a_counterexample():
    # Stationarity gives u=(2,-1), t=-2, but all entries of B are positive.
    matrix = fmpq_mat([[1, 4], [4, 10]])
    assert evaluate_quadratic(matrix, (2, -1)) == -2
    assert check_nonnegative(matrix).status is KernelStatus.VERIFIED


def test_tiny_negative_interior_value_survives_exact_cancellation():
    epsilon = fmpq(1, 10**100)
    matrix = fmpq_mat([[1 - epsilon, -2 - epsilon], [-2 - epsilon, 4 - epsilon]])
    result = check_nonnegative(matrix)
    assert_negative_witness(matrix, result)
    assert isinstance(result, Violation)
    assert result.witness == (fmpq(2, 3), fmpq(1, 3))
    assert result.value == -epsilon


@pytest.mark.parametrize(
    ("matrix", "code"),
    [
        (fmpq_mat(0, 1), "kernel_matrix_shape"),
        (fmpq_mat(1, 0), "kernel_matrix_shape"),
        (fmpq_mat([[1, 2]]), "kernel_matrix_shape"),
        (fmpq_mat([[1, 0], [1, 1]]), "kernel_matrix_symmetry"),
        ([[1]], "kernel_matrix_type"),
        ([[True]], "kernel_matrix_type"),
        ([[1.0]], "kernel_matrix_type"),
        (1.0, "kernel_matrix_type"),
        (True, "kernel_matrix_type"),
    ],
)
def test_invalid_matrix_is_separate_from_a_violation(matrix, code):
    for public_operation in (
        check_nonnegative,
        lambda matrix: evaluate_quadratic(matrix, [1]),
    ):
        with pytest.raises(VerificationError) as caught:
            public_operation(matrix)
        assert caught.value.failure.kind is FailureKind.REFUSED
        assert caught.value.failure.code == code


@pytest.mark.parametrize(
    ("point", "code"),
    [
        (None, "kernel_point_type"),
        (iter([1]), "kernel_point_type"),
        ([], "kernel_point_dimension"),
        ([1, 0], "kernel_point_dimension"),
        ([True], "kernel_coordinate_type"),
        ([1.0], "kernel_coordinate_type"),
        ([float("nan")], "kernel_coordinate_type"),
        ([float("inf")], "kernel_coordinate_type"),
        (["1"], "kernel_coordinate_type"),
        ([Fraction(1)], "kernel_coordinate_type"),
    ],
)
def test_evaluation_rejects_wrong_or_inexact_coordinates(point, code):
    with pytest.raises(VerificationError) as caught:
        evaluate_quadratic(fmpq_mat([[1]]), point)
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert caught.value.failure.code == code
    if code == "kernel_coordinate_type":
        assert caught.value.failure.location == {"coordinate": 0}


def test_public_evaluation_allows_exact_points_outside_the_simplex():
    assert evaluate_quadratic(fmpq_mat([[2, 1], [1, 3]]), [fmpq(-1, 2), 2]) == fmpq(
        21, 2
    )


def test_results_are_immutable_and_witnesses_are_independent_of_input_mutation():
    matrix = fmpq_mat([[-1]])
    result = check_nonnegative(matrix)
    assert isinstance(result, Violation)
    with pytest.raises(FrozenInstanceError):
        result.value = fmpq(0)  # ty: ignore[invalid-assignment]
    with pytest.raises(FrozenInstanceError):
        result.status = KernelStatus.VERIFIED  # ty: ignore[invalid-assignment]
    matrix[0, 0] = 100
    assert result.witness == (fmpq(1),)
    assert result.value == -1
    verified = check_nonnegative(matrix)
    with pytest.raises(FrozenInstanceError):
        verified.status = KernelStatus.VIOLATION  # ty: ignore[invalid-assignment]


def test_small_integer_two_by_two_family_against_independent_criterion():
    # For a,c >= 0, copositivity is b >= 0 or b^2 <= a*c.
    for a in range(-2, 3):
        for b in range(-2, 3):
            for c in range(-2, 3):
                matrix = fmpq_mat([[a, b], [b, c]])
                expected = a >= 0 and c >= 0 and (b >= 0 or b * b <= a * c)
                result = check_nonnegative(matrix)
                assert (result.status is KernelStatus.VERIFIED) == expected
                if not expected:
                    assert_negative_witness(matrix, result)
