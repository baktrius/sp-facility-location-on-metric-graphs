# Exact scalar boundary (exact-arithmetic component)

Claim: for every supported decoded scalar, `parse_rational` returns its exact
rational value as a FLINT `fmpq`. Unsupported types or noncanonical strings
raise a structured refusal. `format_rational` maps FLINT rationals to the
schema's unique integer or reduced fraction spelling. This claim covers the
scalar boundary, not JSON transport or completed certificate verification.

Assumptions and checks: a decoded JSON integer is a built-in `int`, not a bool
or another numeric class. The `type(value) is int` check excludes bool even
though Python makes it an int subclass. No float or conversion from a float
appears in either accepted path. Strings must match an ASCII numerator with
no whitespace, plus sign, leading zero, or negative zero, and an optional
nonnegative denominator with no leading zero. A literal zero denominator
raises `schema_zero_denominator` before FLINT construction. All other lexical
failures use `schema_rational_syntax`; unsupported types use
`schema_exact_type`. Source context is retained separately from stable codes.

Why the check suffices: integers enter FLINT directly. String components enter
FLINT as arbitrary-precision `fmpz` values; they never pass through Python's
decimal `int(string)` conversion or a float. The `fmpq` constructor normalizes
the numerator/denominator exactly. Comparing the normalized output with the
input spelling ensures coprimality, denominator greater than one for fraction
forms, and integer spelling for integral values. In particular, `2/4`, `1/1`,
and `0/3` cannot be accepted by relying on FLINT's permissive normalization.
Computed values can freely normalize: `1/3 + 2/3` formats as `1`.

Boundary cases: zero integers and the string `0` are accepted. JSON integer
token `-0` is decoded as integer zero and is accepted; string `"-0"` fails the
lexical check. Negative rationals have the minus sign only on the numerator.
ASCII digit classes and full-string matching reject Unicode digits and a
trailing newline. There is no chosen magnitude/digit cap in the scalar API.
Tests exercise a 5,002-digit numerator as a string, a built-in integer, and a
fraction. Available memory remains a practical limit; unexpected exceptions
propagate and never return an acceptance value.

Representative tests: the hand-computed integer `2**100 + 1` round-trips as
`1267650600228229401496703205377`; `-7/3` preserves its reduced spelling.
Subtracting `9007199254740993` from `9007199254740992` yields `-1`, whereas
binary64 can merge these integers. Adding and subtracting one retains an
exact `1/10**30` perturbation. Adversarial syntax and type cases verify refusal
instead of coerced values. The failure tests compare diagnostic outputs and
show that a bad branch reference remains an invalid certificate, separate
from a claimed negative SP residual.

Failure contract: `Failure` is a frozen record; its optional diagnostic
mappings are caller-supplied metadata treated as read-only (not recursively
immutable). Refusal, incompletion, certificate invalidity, and mathematical
counterexample have separate kinds. A record is not proof of a witness;
later kernels/composition must validate witnesses and global admissibility
before emitting counterexamples. No acceptance/result/CLI API exists yet.

Deferred ingress: reader component owns strict JSON parsing, duplicate keys, trailing
content, unknown fields, global float/NaN/Infinity rejection, and integer token
decoding beyond CPython's default decimal digit limit. Tickets 04/05 must
check integer-only positions without using the rational-string allowance.
Later arithmetic must keep FLINT types and exact integer constants; this
component cannot establish that future modules never introduce floats.

Assessed choices to review: exact Python patch pinning records the only tested
interpreter; `incomplete` is explicit alongside `refused`; diagnostic context
is intentionally schema-shaped metadata, not a general serializer. These
choices do not change certificate guarantees. No unresolved mathematical or
schema conflict was found by the implementer. Independent review determines
approval of the code and this note.
