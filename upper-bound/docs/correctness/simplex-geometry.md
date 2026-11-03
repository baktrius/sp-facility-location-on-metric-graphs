# Exact simplex geometry (SPEC S07)

The public boundary is `geometry.Simplex`, `AffineInterpolant`, `Facet`,
`cube_simplex`, `intrinsic_coordinates`, and `simplex_in_root`. It uses FLINT
`fmpq`/`fmpq_mat`, integers, and vertex **columns**, matching the reviewed S05
kernel. Generic operations accept embedded affinely independent faces and
singletons; mechanism cells must fill their checked root cube. This reads
S07's full-dimension restriction as a restriction on mechanism simplices,
consistent with simplex-geometry component's explicit requirement for generic embedded-face
operations. Neither an embedded face nor a successful operation here certifies
root coverage or a mechanism.

## Checked assumptions and failures

`Simplex` requires a nonempty exact matrix and checks full column rank of
`A=[V;1^T]`. This is exactly affine independence: a nonzero kernel vector would
give a dependence whose coefficients sum to zero. Duplicate, collinear and
overcomplete vertices therefore fail. Stored columns are immutable tuples;
the input matrix and every returned `vertices` matrix have separate ownership.

The existing affine kernel keeps its original source, behavior and review.
Both boundaries use the same augmented-rank criterion and column convention;
public cross-interface tests exercise full-dimensional, embedded and
zero-ambient examples and dependent inputs. Their error categories differ
deliberately: S05 malformed kernel inputs are refused; failed certificate
geometry in this S07 boundary is `INVALID_CERTIFICATE`.

`cube_simplex` additionally requires `dimension == ambient_dimension` and
every vertex coordinate in `[0,1]`. The cube is convex, so this contains the
entire simplex. `simplex_in_root` accepts a validated `Graph`, an ordered
nonempty sequence of root edge indices, and graph-point tuples. It requires
exactly root-dimension-plus-one vertices, converts every coordinate through
reviewed `graph.chart_coordinate`, and invokes `cube_simplex`. Thus canonical
endpoints follow their actual listed edge orientation, interiors belong to
their specified edge, and every point belongs to its root. This layer does
not determine whether a root is an attribution, SP or approximation root:
the reader/composition supplies its required dimension and comparison key.

Wrong shapes, nonexact scalar types (including bool/float), and malformed
point/index types are refused. Well-formed unresolved graph references, wrong
charts, affine dependence, wrong cell dimension, and out-of-box vertices are
invalid certificates. Unsupported embedded volume/ambient extension requests
are refused. Normal containment failure returns `False`; an off-hull
barycentric query returns `None`. Off-hull interpolation/support evaluation
raises `simplex_affine_hull`. Errors have stable codes and no mechanism
counterexample witness; later composition can add file/root/cell locations.

## Barycentric coordinates and closed containment

For a rational ambient point `p`, solve all equations
`A lambda = (p,1)` by exact row reduction of the augmented system.
`A` already has full column rank `k`; if the augmented rank exceeds `k`,
the system is inconsistent and `p` is outside the affine hull. Otherwise the
first `k` columns pivot, and the reduced last column gives the unique solution.
All ambient equations participate, including the coordinates discarded by
an arbitrary projection. No floating tolerance is used.

By the definition of convex hull, `p` lies in the closed simplex exactly when
this unique sum-one solution has every coordinate nonnegative. Equality
includes boundary faces and vertices; negative coordinates indicate points
on the hull outside the simplex. With a singleton the hull is that one point.
In zero ambient dimension, the `1 x 1` augmented vertex matrix has rank one
and the empty ambient tuple has barycentric coordinate `(1,)`.

## Interpolation and facets

For vertex values `a_j`, define `f(p)=sum_j a_j lambda_j(p)` on the affine
hull. The barycentric functions are affine there, and at vertex `v_i` their
values are the unit vector `e_i`. This proves interpolation and uniqueness:
the difference of two affine interpolants vanishes at an affine basis.
Evaluation permits points on the hull outside the closed simplex. For a
full-dimensional simplex, solving `[V^T,1] (g,c)=a` gives the unique ambient
formula `g dot p+c`. For an embedded simplex there are many ambient
extensions, so `coefficients()` refuses rather than choosing one silently.

For positive dimension, a facet opposite vertex `j` has exactly all other
vertex indices. Its supporting affine function is `lambda_j`, zero on those
vertices and one at the opposite vertex. Its sign is positive toward the
simplex interior. This characterizes a supporting hyperplane within the
affine hull, and supplies exact side tests there even for embedded faces.
For full dimension, `hyperplane()` exposes `(normal,offset)` with
`h(p)=normal dot p-offset=lambda_j(p)`; the normal is nonzero because its
vertex values include both zero and one. A reversed vertex order changes
indexing, not the geometry. Facet vertex indices are relative to the input
column order; later conformity code maps them to its own canonical IDs.
Zero-dimensional simplices have no nonempty facets.

## Determinant volume scope

For a full-dimensional `d`-simplex, let `E` have columns `v_j-v_0`,
`j=1,...,d`. The affine map from the standard coordinate simplex has volume
scale `abs(det(E))`. That standard simplex has volume `1/d!`, so the result
is exactly `abs(det(E))/d!`, invariant under orientation and vertex order.
This is rational Lebesgue volume in the supplied coordinates, in particular
the intrinsic unit-edge coordinates of graph-root cubes. Dimension zero
uses the usual `0 x 0` determinant and `0!`, giving volume one.

`volume()` refuses arbitrary embedded simplices. Euclidean length of the
diagonal segment from `(0,0)` to `(1,1)` is `sqrt(2)`, so there is no general
rational Euclidean embedded-volume result to return. A caller seeking a
coordinate volume in a lower-dimensional chart must supply that chart's
full-dimensional coordinates explicitly. No cover or intersection solver is
included in this component.

## Behavioral evidence and review
