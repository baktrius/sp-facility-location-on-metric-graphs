import json

import pytest

from upper_bound_verifier.exact import parse_rational
from upper_bound_verifier.failures import Failure, FailureKind, VerificationError


def test_malformed_scalar_retains_reason_and_source_location():
    location = {"file": "sp.jsonl", "line": 7, "cell": "cell-2"}
    with pytest.raises(VerificationError) as caught:
        parse_rational(True, location=location)
    diagnostic = caught.value.failure.to_dict()
    assert diagnostic == {
        "kind": "refused",
        "code": "schema_exact_type",
        "message": "Expected a JSON integer or canonical rational string",
        "location": location,
    }
    assert caught.value.failure.kind is FailureKind.REFUSED
    assert json.loads(json.dumps(diagnostic)) == diagnostic


def test_failure_categories_keep_certificate_failure_separate_from_violation():
    invalid = Failure(
        FailureKind.INVALID_CERTIFICATE, "distance_branch_reference", "Bad branch"
    )
    counterexample = Failure(
        FailureKind.COUNTEREXAMPLE,
        "sp_violation",
        "Negative residual",
        witness={"barycentric": ["1/2", "1/2"], "residual": "-1/3"},
    )
    incomplete = Failure(FailureKind.INCOMPLETE, "resource_limit", "Limit reached")
    assert invalid.to_dict() == {
        "kind": "invalid_certificate",
        "code": "distance_branch_reference",
        "message": "Bad branch",
    }
    assert counterexample.to_dict() == {
        "kind": "counterexample",
        "code": "sp_violation",
        "message": "Negative residual",
        "witness": {"barycentric": ["1/2", "1/2"], "residual": "-1/3"},
    }
    assert incomplete.to_dict()["kind"] == "incomplete"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (1.0, "schema_exact_type"),
        ("2/4", "schema_rational_syntax"),
        ("-0", "schema_rational_syntax"),
        ("1/0", "schema_zero_denominator"),
    ],
)
def test_scalar_failure_codes_are_stable(value, code):
    with pytest.raises(VerificationError) as caught:
        parse_rational(value)
    assert caught.value.failure.to_dict()["kind"] == "refused"
    assert caught.value.failure.code == code
