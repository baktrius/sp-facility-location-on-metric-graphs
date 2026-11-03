"""Exact quadratic nonnegativity on embedded rational simplices (SPEC S05)."""

from dataclasses import dataclass, field

from flint import fmpq, fmpq_mat

from . import simplex
from .failures import Failure, FailureKind, VerificationError
from .simplex import KernelStatus, Verified


def _refuse(code: str, message: str) -> VerificationError:
    return VerificationError(Failure(FailureKind.REFUSED, code, message))


def _scalar(value: object, field_name: str, coordinate: int | None = None) -> fmpq:
    if type(value) is int:
        return fmpq(value)
    if isinstance(value, fmpq):
        return value
    location: dict[str, object] = {"field": field_name}
    if coordinate is not None:
        location["coordinate"] = coordinate
    raise VerificationError(
        Failure(
            FailureKind.REFUSED,
            "affine_scalar_type",
            "Expected a built-in integer or FLINT rational",
            location=location,
        )
    )


def _vector(value: object, dimension: int, field_name: str) -> tuple[fmpq, ...]:
    if not isinstance(value, (list, tuple)):
        raise _refuse(f"affine_{field_name}_type", "Expected a list or tuple")
    if len(value) != dimension:
        raise _refuse(
            f"affine_{field_name}_dimension",
            "Coordinate count does not match ambient dimension",
        )
    return tuple(_scalar(x, field_name, i) for i, x in enumerate(value))


@dataclass(frozen=True, init=False)
class Quadratic:
    """Exact coefficients of x^T H x + g^T x + c; H is copied on access."""

    _h: tuple[tuple[fmpq, ...], ...] = field(repr=False)
    g: tuple[fmpq, ...]
    c: fmpq

    def __init__(self, H: object, g: object, c: object) -> None:
        if not isinstance(H, fmpq_mat):
            raise _refuse("affine_h_type", "Expected an exact FLINT fmpq_mat")
        if H.nrows() != H.ncols():
            raise _refuse("affine_h_shape", "Expected a square matrix")
        if H != H.transpose():
            raise _refuse("affine_h_symmetry", "Expected a symmetric matrix")
        object.__setattr__(
            self,
            "_h",
            tuple(tuple(H[i, j] for j in range(H.ncols())) for i in range(H.nrows())),
        )
        object.__setattr__(self, "g", _vector(g, H.nrows(), "g"))
        object.__setattr__(self, "c", _scalar(c, "c"))

    @property
    def H(self) -> fmpq_mat:
        matrix = fmpq_mat(len(self.g), len(self.g))
        for i, row in enumerate(self._h):
            for j, coefficient in enumerate(row):
                matrix[i, j] = coefficient
        return matrix


def _quadratic(value: object) -> Quadratic:
    if not isinstance(value, Quadratic):
        raise _refuse("affine_quadratic_type", "Expected a Quadratic record")
    return value


@dataclass(frozen=True)
class Violation:
    barycentric: tuple[fmpq, ...]
    witness: tuple[fmpq, ...]
    value: fmpq
    status: KernelStatus = field(default=KernelStatus.VIOLATION, init=False)


def evaluate(quadratic: object, point: object) -> fmpq:
    """Evaluate the original quadratic exactly at an ambient point."""
    quadratic = _quadratic(quadratic)
    point = _vector(point, len(quadratic.g), "point")
    H = quadratic.H
    return (
        sum(
            (
                point[i] * H[i, j] * point[j]
                for i in range(H.nrows())
                for j in range(H.ncols())
            ),
            fmpq(0),
        )
        + sum((g * x for g, x in zip(quadratic.g, point, strict=True)), fmpq(0))
        + quadratic.c
    )


def _vertices(quadratic: Quadratic, vertices: object) -> fmpq_mat:
    if not isinstance(vertices, fmpq_mat):
        raise _refuse("simplex_vertices_type", "Expected an exact FLINT fmpq_mat")
    if vertices.nrows() != len(quadratic.g):
        raise _refuse("simplex_vertices_dimension", "Vertex ambient dimension mismatch")
    if vertices.ncols() < 1:
        raise _refuse("simplex_vertices_shape", "Expected at least one vertex column")
    vertices = fmpq_mat(vertices)
    # Full column rank of [V; 1^T] is affine independence, even when V is rectangular.
    augmented = fmpq_mat(vertices.nrows() + 1, vertices.ncols())
    for j in range(vertices.ncols()):
        for i in range(vertices.nrows()):
            augmented[i, j] = vertices[i, j]
        augmented[vertices.nrows(), j] = 1
    if augmented.rank() != vertices.ncols():
        raise _refuse(
            "simplex_affine_dependence", "Vertices must be affinely independent"
        )
    return vertices


def transform(quadratic: object, vertices: object) -> fmpq_mat:
    """Return B for vertex columns, with q(V lambda)=lambda^T B lambda on sum one."""
    quadratic = _quadratic(quadratic)
    vertices = _vertices(quadratic, vertices)
    return _transform(quadratic, vertices)


def _transform(quadratic: Quadratic, vertices: fmpq_mat) -> fmpq_mat:
    B = vertices.transpose() * quadratic.H * vertices
    w = tuple(
        sum((vertices[i, j] * g for i, g in enumerate(quadratic.g)), fmpq(0))
        for j in range(vertices.ncols())
    )
    for i in range(vertices.ncols()):
        for j in range(vertices.ncols()):
            # Sum-one homogenization: both linear half terms and the constant survive.
            B[i, j] += (w[i] + w[j]) / 2 + quadratic.c
    return B


def check_nonnegative(quadratic: object, vertices: object) -> Verified | Violation:
    """Check q on the closed convex hull and replay a violation in ambient space."""
    quadratic = _quadratic(quadratic)
    vertices = _vertices(quadratic, vertices)
    result = simplex.check_nonnegative(_transform(quadratic, vertices))
    if isinstance(result, Verified):
        return result
    point = tuple(
        sum((vertices[i, j] * x for j, x in enumerate(result.witness)), fmpq(0))
        for i in range(vertices.nrows())
    )
    value = evaluate(quadratic, point)
    if value != result.value or value >= 0:
        raise RuntimeError("Transported quadratic witness failed re-evaluation")
    return Violation(result.witness, point, value)
