# Exact nonnegativity on an embedded rational simplex (K2)

`affine.check_nonnegative(quadratic, V)` decides whether
`q(x) = x^T H x + g^T x + c >= 0` for every **real** point in the closed
convex hull of the columns of `V`. The ambient dimension `d` may be zero;
the number of vertices `k` must be at least one. Embedded simplices with
`k-1 < d`, full-dimensional simplices, and singletons use the same forward map.

## Public inputs and checked assumptions

`affine.Quadratic(H, g, c)` is a frozen exact coefficient record. `H` must be
an already-exact FLINT `fmpq_mat` of shape `d by d` and symmetric. The
constructor checks shape and symmetry. `g` must be a list or tuple of length
`d`; its coordinates and `c` must be built-in integers or FLINT `fmpq` values.
Booleans, floats, strings, Fraction, Decimal, and other coercion types are
refused. Internally the record stores immutable tuples of rational entries;
the `H` property returns a fresh matrix. Changing input lists or matrices or
that returned matrix cannot change the quadratic.

`affine.transform(quadratic, V)` returns an exact symmetric `k by k` matrix
`B`. Both transform and check require a `Quadratic` record and an already-exact
FLINT matrix `V` of shape `d by k`, `k >= 1`. `_vertices` validates dimensions
and checks that the exact rank of `[V; 1^T]` equals `k`. This is equivalent to
affine independence: a dependence has coefficients `a` with `V a = 0` and
`1^T a = 0`. Thus repeated vertices, collinear claimed triangles, and any
`k > d+1` are refused. The validator copies `V` before calculations. No
inverse, square ambient map, or ambient rank condition on `V` is assumed.

`affine.evaluate(quadratic, point)` independently evaluates the original
polynomial by sums of products of its original coefficients. It checks a
list/tuple point of length `d` using the same strict scalar rules, and permits
points outside the simplex. Matrix provenance remains the caller's obligation:
this exact internal API cannot detect rounding/coercion performed before a
FLINT matrix was constructed. Wire values must first pass `exact.parse_rational`.

Malformed inputs raise `VerificationError` with kind `REFUSED`, separate from
mathematical violations. Stable codes are `affine_h_type`, `affine_h_shape`,
`affine_h_symmetry`, `affine_g_type`, `affine_g_dimension`, `affine_scalar_type`,
`affine_quadratic_type`, `affine_point_type`, `affine_point_dimension`,
`simplex_vertices_type`, `simplex_vertices_dimension`, `simplex_vertices_shape`,
and `simplex_affine_dependence`. Scalar errors identify the field and, for
vectors, its coordinate index.

## K2: barycentric identity and real-domain equivalence

Let `lambda` be any real vector with `lambda >= 0` and `1^T lambda = 1`, and
let `w = V^T g`. `_transform` uses exact matrix products and entrywise additions
to form the specified coefficient matrix

```text
B = V^T H V + (w 1^T + 1 w^T)/2 + c 1 1^T.
```

Symmetry of `H` makes the first term symmetric; the other two terms are also
symmetric. In real arithmetic,

```text
lambda^T V^T H V lambda = (V lambda)^T H (V lambda),
lambda^T (w 1^T + 1 w^T) lambda / 2
    = ((lambda^T w)(1^T lambda) + (lambda^T 1)(w^T lambda))/2
    = w^T lambda = g^T V lambda,
lambda^T c 1 1^T lambda = c (1^T lambda)^2 = c.
```

Therefore `lambda^T B lambda = q(V lambda)` throughout the complete real
standard simplex, including its boundary. Both linear half terms are needed;
the constant enters every entry, including off-diagonal entries. By the
definition of convex hull, `V` maps the standard simplex onto the claimed
closed simplex. Affine independence additionally makes barycentric coordinates
unique, but surjectivity and the identity need no ambient-map inverse. Thus
nonnegativity on that convex hull is equivalent to S04 nonnegativity of `B`.

The checker delegates exactly this `B` to the reviewed `simplex.check_nonnegative`.
K1 gives the complete real-domain decision, including singular, flat, boundary,
and zero minima. The affine layer does not enumerate separate candidates or
run another optimizer. A `simplex.Verified` result is returned unchanged.

For a negative kernel result, the code computes `point = V lambda` exactly,
then calls the original-polynomial evaluator and requires its value to equal
the kernel value and remain strictly negative. Inconsistency raises an internal
error. The returned frozen `affine.Violation` has the same `KernelStatus.VIOLATION`,
`barycentric` coordinates, original-coordinate `witness`, and original exact
negative `value`. K1 has already checked nonnegative barycentric coordinates
with sum one, so the transported point is in the convex hull. Rational input
and the rational K1 witness give a rational transported witness. The guarantee
concerns records returned by the checker; result constructors alone are data
containers and do not validate supplied witnesses.

## Boundaries, evidence, and scope

For a singleton, `lambda = (1)` and `B = [[q(v)]]`, in any ambient dimension.
For `d = 0`, take `H` of shape `0 by 0`, `g = ()`, and `V` of shape `0 by 1`.
The unique original point is `()`, all product sums vanish, and `q = c`.
The augmented matrix is `[1]` of rank one, and FLINT's empty-dimension matrix
products yield the required `B = [[c]]`. A negative constant returns original
witness `()` and barycentric witness `(1)`; nonnegative constants verify.
An empty hull or two copies of this unique point are refused. This explicitly
preserves S05's generic singleton scope rather than assuming `d >= 1`.

`tests/test_affine.py` uses independent Python Fraction evaluation of the
original polynomial to replay every reported test violation and confirm the
forward map. Cases include `x^2-6x+8` on `[2,4]` with witness `3`, its line
embedding in three dimensions, a nonzero singleton with value `-13`, a
triangle whose minimum `-1/6` needs full barycentric support, vertex violations,
an interior value `-1/10^100`, and negative ambient values outside a verified
simplex. A rational triangle checks every diagonal and off-diagonal entry via
the independent identity
`B_ij = 2 q((v_i+v_j)/2) - (q(v_i)+q(v_j))/2`.
Separate hand calculations check both linear halves and constant homogenization.
Zero-dimensional cases, malformed dimensions, dependence, inexact scalars, and
input mutation are exercised. A bounded 125-form one-dimensional family is
compared with direct polynomial minima on a rational interval.
