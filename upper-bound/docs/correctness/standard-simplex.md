# Exact nonnegativity on the standard simplex (K1)

The public `simplex.check_nonnegative(B)` decides whether
`lambda^T B lambda >= 0` for every real `lambda >= 0` with coordinate sum one.
Assumptions: `B` is an already-exact FLINT `fmpq_mat`, square, symmetric, and
of order at least one. The common `_validated_matrix` boundary checks all
three mathematical assumptions and takes a matrix copy. Raw lists, strings,
bools, floats, and other matrix types produce structured `VerificationError`
with kind `REFUSED`; they never produce a mathematical violation. The matrix
API is for exact internal calculations, including affine-reduction component's affine
reduction. Wire/sequence parsing remains upstream: constructing a FLINT
matrix outside this API does not validate how its entries were obtained.
Use `exact.parse_rational` on wire scalars before constructing a matrix.

`simplex.evaluate_quadratic(B, point)` returns the exact `fmpq` value of
`point^T B point`, allowing points outside the simplex. A point must be a list
or tuple of built-in integers or FLINT `fmpq` coordinates of the correct length.
Bool, float, nonfinite values, strings, and other numeric/coercion types are
refused. No generic numeric conversion or floating arithmetic enters either
public operation. Stable reason codes are `kernel_matrix_type`,
`kernel_matrix_shape`, `kernel_matrix_symmetry`, `kernel_point_type`,
`kernel_point_dimension`, and `kernel_coordinate_type`; the last includes the
coordinate index. No exact-arithmetic component interface or guarantee changes.

The result is a frozen `Verified` record with `status == KernelStatus.VERIFIED`,
or a frozen `Violation` with `status == KernelStatus.VIOLATION`, a tuple of
FLINT rational `witness` coordinates, and FLINT rational `value < 0`. These are
kernel results: a negative quadratic on its own is not a counterexample to an
unvalidated mechanism. Later certificate checks must establish global
admissibility and the residual interpretation. Public record constructors are
data containers; the guarantees here concern results returned by the checker.

## Enumeration and sound negative witnesses

For each size from one through the matrix order, the code enumerates every
coordinate subset `I` of that size, once, including singletons. It constructs
and solves exactly the SPEC S04 system

```text
[B_II  -1] [u]   [0]
[ 1^T   0] [t] = [1].
```

FLINT `fmpq_mat.solve` performs an exact rational solve. In the pinned
python-flint 0.9.0, a singular coefficient matrix raises `ZeroDivisionError`;
only this solve is in the handler that skips a singular support. Other errors
propagate. A nonsingular solution with any negative coordinate is discarded;
all nonnegative solutions are retained, including those with zero coordinates.
There is no Hessian filter or test on multipliers outside the support.

The system gives `B_II u = t 1` and `1^T u = 1`. Thus a retained `u`, extended
by zeros outside `I`, is feasible, and `u^T B_II u = t`. When `t < 0`, the code
rechecks nonnegativity and sum one, calls the public quadratic evaluator, and
requires exact equality with `t` and a strictly negative replayed value before
returning a violation. Any inconsistency raises an internal error; it cannot
produce verification. A negative feasible witness proves failure immediately.
The only VERIFIED return is after every nonempty support has been considered.

## K1: why singular supports may be skipped

Continuity on the compact real standard simplex gives a global minimizer.
Choose one, `lambda`, with the smallest possible support cardinality, and let
`I` be its nonempty support. Write `u = lambda_I`. Every coordinate of `u` is
strictly positive, so `u` is in the relative interior of its face. First-order
stationarity on that face applies: for every vector `h` with `1^T h = 0`, the
derivative is `2 h^T B_II u = 0`. Symmetry of `B` therefore gives a scalar `t`
with `B_II u = t 1`; also `1^T u = 1`. This includes singleton faces, where the
zero-sum tangent space has dimension zero.

Suppose the bordered coefficient matrix on `I` were singular. A nonzero
null vector `(h,s)` would satisfy

```text
B_II h = s 1,    1^T h = 0.
```

Using stationarity and symmetry,
`s = u^T (s 1) = u^T B_II h = (B_II u)^T h = t 1^T h = 0`.
Consequently `h != 0` and `B_II h = 0`. The quadratic is constant along
`u + tau h`: its linear change `2 tau u^T B_II h` and quadratic change
`tau^2 h^T B_II h` both vanish. A nonzero zero-sum vector has positive and
negative coordinates. Take
`tau = min_{h_j < 0} u_j / (-h_j) > 0`. Then `u + tau h` is nonnegative,
has coordinate sum one, and has at least one newly zero coordinate. It is a
global minimizer on a strictly smaller support, a contradiction.

Thus a global minimizer of smallest support has a nonsingular bordered system.
Its unique solution is rational because the matrix and right side are rational.
Its coordinates are positive and its `t` equals the global minimum. Enumeration
will retain it. If any negative value exists, this candidate has negative `t`,
so the algorithm returns a negative witness before it can verify. Conversely,
every returned witness is directly re-evaluated and negative. Therefore the
complete enumeration decides the stated real-domain inequality.

No genericity, strict convexity, nonsingularity of `B` itself, isolated minimum,
or interior minimum assumption is used. Singleton bordered matrices always
have determinant one, even for a zero diagonal entry. Constant quadratics may
have singular higher-support systems; a vertex is a smallest-support minimizer.
Flat minimizing faces reach a smaller face along the null direction. Exact
zero minima verify because rejection requires strict negativity. For
`(lambda_0-lambda_1)^2`, `B` is singular but its full-support bordered system is
nonsingular and captures the zero interior minimum. The argument concerns the
bordered matrix, not the rank of `B` alone.

## Behavior evidence and limits

`tests/test_simplex.py` checks positive diagonals, last-coordinate negative
vertices, positive vertices with an interior negative value, a three-coordinate
negative minimum after all proper faces pass, a late proper-face violation
with zeros off its support, constant/flat/singular forms, exact zero minima,
a negative stationary point outside the simplex that must be discarded, and
a rational interior violation of magnitude `1/10^100`. Every emitted test
witness is replayed with independent Python `Fraction` arithmetic and the
public evaluator. A bounded 125-matrix two-by-two family uses the independent
criterion `a,c >= 0` and `(b >= 0 or b^2 <= a*c)`. Input refusals and immutable
result behavior are also checked. These examples support implementation
confidence; K1 supplies completeness over the real continuum.

This algorithm enumerates `2^k - 1` supports. It provides no resource limit,
minimum-reporting diagnostic, general positivity hierarchy, or full mechanism
verification. Resource/internal exceptions and interruptions propagate; there
is no path that interprets incomplete enumeration as VERIFIED.
