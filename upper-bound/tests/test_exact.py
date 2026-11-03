import json

import pytest
from flint import fmpq

from upper_bound_verifier.exact import format_rational, parse_rational


def test_large_integer_and_reduced_rational_round_trip():
    integer = 2**100 + 1
    parsed = parse_rational(integer)
    assert isinstance(parsed, fmpq)
    assert format_rational(parsed) == "1267650600228229401496703205377"
    assert format_rational(parse_rational("-7/3")) == "-7/3"


@pytest.mark.parametrize(
    "value",
    [True, False, 1.0, 0.5, float("nan"), float("inf"), float("-inf")],
)
def test_nonexact_python_numbers_are_refused(value):
    with pytest.raises(ValueError):
        parse_rational(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "+1",
        "01",
        "-01",
        "-0",
        " 1",
        "1 ",
        "1\n",
        "1.0",
        "1e3",
        "NaN",
        "Infinity",
        "1+2",
        "2/4",
        "0/3",
        "-0/3",
        "1/1",
        "0/1",
        "1/0",
        "1/-2",
        "1/+2",
        "1/02",
        "１",
        "1/２",
        "1/2/3",
        None,
        [],
        {},
    ],
)
def test_noncanonical_or_nonnumeric_values_are_refused(value):
    with pytest.raises(ValueError):
        parse_rational(value)


@pytest.mark.parametrize("value", [0, -1, 1, "0", "-1", "1", "1/2", "-1/2"])
def test_canonical_values(value):
    assert format_rational(parse_rational(value)) == str(value)


def test_json_integer_negative_zero_and_string_negative_zero_differ():
    assert format_rational(parse_rational(json.loads("-0"))) == "0"
    with pytest.raises(ValueError):
        parse_rational(json.loads('"-0"'))


def test_exact_cancellation_retains_a_tiny_negative_sign():
    left = parse_rational("9007199254740992")
    right = parse_rational("9007199254740993")
    assert format_rational(left - right) == "-1"
    assert left - right < 0
    epsilon = parse_rational("1/1000000000000000000000000000000")
    assert (parse_rational(1) + epsilon) - parse_rational(1) == epsilon


def test_integers_beyond_python_decimal_conversion_limit():
    digits = "1" + "0" * 5000 + "1"
    assert format_rational(parse_rational(digits)) == digits
    assert format_rational(parse_rational(10**5001 + 1)) == digits
    assert format_rational(parse_rational(digits + "/3")) == digits + "/3"


@pytest.mark.parametrize("value", [True, 1, 0.5, "1/2", None])
def test_formatter_requires_a_flint_rational(value):
    with pytest.raises(TypeError):
        format_rational(value)


def test_formatter_normalizes_computed_values():
    assert format_rational(parse_rational("1/3") + parse_rational("2/3")) == "1"
    assert format_rational(-parse_rational("1/3")) == "-1/3"
