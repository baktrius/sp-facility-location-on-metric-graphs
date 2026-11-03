"""Small exact algebra for costs made of internally checked affine factors."""

from flint import fmpq, fmpq_mat

from .affine import Quadratic
from .distance import AffineExpression
from .failures import Failure, FailureKind, VerificationError


def cost_difference(
    positive_weights: tuple[AffineExpression, ...],
    positive_distances: tuple[AffineExpression, ...],
    negative_weights: tuple[AffineExpression, ...],
    negative_distances: tuple[AffineExpression, ...],
) -> Quadratic:
    """Sum positive weight*distance products minus the negative products.

    Factors must be internally derived exact expressions. This operation
    proves no geometry, metric, probability or mechanism property by itself.
    """
    groups = (
        positive_weights,
        positive_distances,
        negative_weights,
        negative_distances,
    )
    if (
        any(type(group) is not tuple or not group for group in groups)
        or len(positive_weights) != len(positive_distances)
        or len(negative_weights) != len(negative_distances)
        or any(
            not isinstance(factor, AffineExpression)
            for group in groups
            for factor in group
        )
    ):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "residual_factor_shape",
                "Need nonempty matching tuples of exact affine factors",
            )
        )
    dimension = len(positive_weights[0].coefficients)
    if any(
        len(factor.coefficients) != dimension for group in groups for factor in group
    ):
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "residual_factor_dimension",
                "Affine factors have different ambient dimensions",
            )
        )
    H = fmpq_mat(dimension, dimension)
    g = [fmpq(0)] * dimension
    c = fmpq(0)
    for sign, weights, distances in (
        (1, positive_weights, positive_distances),
        (-1, negative_weights, negative_distances),
    ):
        for weight, distance in zip(weights, distances, strict=True):
            a, b = weight.coefficients, distance.coefficients
            u, v = weight.constant, distance.constant
            for i in range(dimension):
                g[i] += sign * (v * a[i] + u * b[i])
                for j in range(dimension):
                    # x_i*x_j is counted in both symmetric matrix entries.
                    H[i, j] += sign * (a[i] * b[j] + b[i] * a[j]) / 2
            c += sign * u * v
    return Quadratic(H, g, c)
