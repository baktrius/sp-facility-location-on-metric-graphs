"""Exact quadratic nonnegativity on a standard simplex (SPEC S04)."""

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import combinations

from flint import fmpq, fmpq_mat

from .failures import Failure, FailureKind, VerificationError


def _validated_matrix(matrix: object) -> fmpq_mat:
    if not isinstance(matrix, fmpq_mat):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED, "kernel_matrix_type", "Expected a FLINT fmpq_mat"
            )
        )
    if matrix.nrows() < 1 or matrix.nrows() != matrix.ncols():
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "kernel_matrix_shape",
                "Expected a nonempty square matrix",
            )
        )
    if matrix != matrix.transpose():
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "kernel_matrix_symmetry",
                "Expected a symmetric matrix",
            )
        )
    return fmpq_mat(matrix)


class KernelStatus(StrEnum):
    VERIFIED = "VERIFIED"
    VIOLATION = "VIOLATION"


@dataclass(frozen=True)
class Verified:
    status: KernelStatus = field(default=KernelStatus.VERIFIED, init=False)


@dataclass(frozen=True)
class Violation:
    witness: tuple[fmpq, ...]
    value: fmpq
    status: KernelStatus = field(default=KernelStatus.VIOLATION, init=False)


def evaluate_quadratic(matrix: object, point: object) -> fmpq:
    """Evaluate x^T B x at any exact point, without simplex restrictions.

    Matrices are already-exact FLINT matrices. Coordinates must be a list or
    tuple of built-in integers or FLINT rationals; no numeric coercion is used.
    """
    matrix = _validated_matrix(matrix)
    if not isinstance(point, (list, tuple)):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "kernel_point_type",
                "Expected a list or tuple of exact coordinates",
            )
        )
    if len(point) != matrix.nrows():
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "kernel_point_dimension",
                "Point dimension does not match matrix order",
            )
        )
    coordinates: list[fmpq] = []
    for i, coordinate in enumerate(point):
        if type(coordinate) is int:
            coordinates.append(fmpq(coordinate))
        elif isinstance(coordinate, fmpq):
            coordinates.append(coordinate)
        else:
            raise VerificationError(
                Failure(
                    FailureKind.REFUSED,
                    "kernel_coordinate_type",
                    "Expected a built-in integer or FLINT rational",
                    location={"coordinate": i},
                )
            )
    vector = fmpq_mat([[coordinate] for coordinate in coordinates])
    return (vector.transpose() * matrix * vector)[0, 0]


def check_nonnegative(matrix: object) -> Verified | Violation:
    """Decide lambda^T B lambda >= 0 on the complete standard simplex.

    Accept only an already-exact FLINT fmpq_mat, not raw wire/sequence values.
    A negative candidate may return early; verification exhausts all supports.
    """
    matrix = _validated_matrix(matrix)
    order = matrix.nrows()
    for size in range(1, order + 1):
        for support in combinations(range(order), size):
            bordered = fmpq_mat(size + 1, size + 1)
            for i, row in enumerate(support):
                for j, col in enumerate(support):
                    bordered[i, j] = matrix[row, col]
                bordered[i, size] = -1
                bordered[size, i] = 1
            rhs = fmpq_mat(size + 1, 1)
            rhs[size, 0] = 1
            try:
                solution = bordered.solve(rhs)
            except ZeroDivisionError:
                # K1: a smallest-support minimizer has a nonsingular system.
                continue
            coordinates = tuple(solution[i, 0] for i in range(size))
            if any(x < 0 for x in coordinates):
                continue
            value = solution[size, 0]
            if value < 0:
                witness = [fmpq(0) for _ in range(order)]
                for i, coordinate in zip(support, coordinates, strict=True):
                    witness[i] = coordinate
                exact_witness = tuple(witness)
                replayed_value = evaluate_quadratic(matrix, exact_witness)
                if (
                    any(x < 0 for x in exact_witness)
                    or sum(exact_witness, fmpq(0)) != 1
                    or replayed_value != value
                    or replayed_value >= 0
                ):
                    # An internal inconsistency must never become acceptance.
                    raise RuntimeError("Exact stationary witness failed re-evaluation")
                return Violation(exact_witness, replayed_value)
    return Verified()
