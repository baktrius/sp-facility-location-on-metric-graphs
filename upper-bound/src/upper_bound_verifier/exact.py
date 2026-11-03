"""Scalar input and output using FLINT rationals directly."""

import re
from collections.abc import Mapping

from flint import fmpq, fmpz

from .failures import Failure, FailureKind, VerificationError

_CANONICAL_PARTS = re.compile(r"(0|-?[1-9][0-9]*)(?:/([1-9][0-9]*|0))?")


def parse_rational(
    value: object, *, location: Mapping[str, object] | None = None
) -> fmpq:
    """Parse a decoded JSON integer or canonical rational string into FLINT.

    JSON document/token validation belongs to the reader, not this scalar API.
    No decimal-to-Python-int conversion is used for strings, so Python's digit
    limit does not reject large exact rational strings.
    """
    if type(value) is int:
        return fmpq(value)
    if type(value) is not str:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "schema_exact_type",
                "Expected a JSON integer or canonical rational string",
                location=location,
            )
        )
    match = _CANONICAL_PARTS.fullmatch(value)
    if match is None:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "schema_rational_syntax",
                "Noncanonical rational string",
                location=location,
            )
        )
    numerator, denominator = match.groups()
    if denominator == "0":
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "schema_zero_denominator",
                "Zero denominator",
                location=location,
            )
        )
    result = fmpq(fmpz(numerator), fmpz(denominator or "1"))
    # Equality with FLINT's normal form enforces coprimality and forbids p/1.
    if format_rational(result) != value:
        raise VerificationError(
            Failure(
                FailureKind.REFUSED,
                "schema_rational_syntax",
                "Noncanonical rational string",
                location=location,
            )
        )
    return result


def format_rational(value: fmpq) -> str:
    """Return a normalized integer or rational string."""
    if not isinstance(value, fmpq):
        raise TypeError("Expected a FLINT fmpq")
    return str(value)
