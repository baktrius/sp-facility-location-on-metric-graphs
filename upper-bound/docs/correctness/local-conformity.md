# Local attribution conformity (G3, SPEC S09)

`conformity.check_local_conformity(graph, root, attribution_vertices)` accepts
decoded attribution records and the global vertex table. It first runs the
reviewed `coverage.check_root_coverage` boundary. Its `RootConformity` result
contains that `RootCoverage`, a read-only map from sorted global facet-ID
tuples to immutable `FacetIncidence(cell, opposite)` tuples, and the set of
cube-boundary facet keys. Opposite indices retain the reader's vertex order.
This establishes one root's geometric triangulation. It does not establish
cross-root conformity, admissibility, SP, approximation, or a mechanism bound.

## Assumptions and exact checks

The graph and record syntax/global profile injectivity have the reviewed
reader/graph contracts. S08 is recomputed, rather than supplied as an asserted
flag or a caller-constructed evidence object. It supplies a finite family of
distinct, closed, full-dimensional simplices contained in `C = [0,1]^d`,
covering C with pairwise disjoint interiors. S07 validates every original
simplex and supplies exact facet support and coordinates. Global IDs resolve
from the same table in every original cell; matching facet ID sets therefore
already determine identical geometry. The implementation also compares their
actual coordinate sets. No floating arithmetic or general intersection solver
is used.

A simplex facet is in a cube-boundary hyperplane if and only if all its
vertices have coordinate zero on one fixed axis, or all have coordinate one
on one fixed axis. The forward direction uses vertex membership; the reverse
uses affine interpolation. Checking each vertex merely lies somewhere on the
cube boundary would be wrong: a square diagonal has two boundary endpoints
and is internal. Containment in C and full dimension imply that a facet not
on a single cube-boundary hyperplane has relative interior in the cube
interior: if a relative-interior convex combination has an extreme coordinate,
every facet vertex must have that same extreme coordinate.

Every boundary facet key must have one incidence. Every other facet key must
have two incidences. The identical facets' opposite vertices must be strictly
on opposite sides. The reviewed `Facet.side` is the first cell's opposite
barycentric coordinate, equal to one at its own opposite vertex and zero on
its facet, so evaluating the second opposite vertex must give a strictly
negative rational. Affine independence excludes a zero opposite side.
Failures retain the original cell's source file, physical line, root and cell,
are invalid-certificate errors, and have no mechanism counterexample witness.

## G3: facet pairing implies all intersections are common faces

We prove the claim over real coordinates. The dimension is positive; for
dimension one the lower-face skeleton below is empty and the same argument
uses intervals. No lower-dimensional input cell is permitted by S08.

Fix any p in C. Because the cells and all their facets are finite and closed,
choose a sufficiently small open Euclidean ball B around p missing every
cell and every facet that does not contain p. There is a positive distance
to each such nonincident closed set, and a finite minimum of those distances.
Consequently every cell or facet met inside B contains p. Choose points in
the full-dimensional interiors of any two cells containing p, arbitrarily
close to p and inside B. Such points exist by approaching p along a segment
from a cell interior point. They also lie in the cube interior, even if p is
on any cube face, edge or corner. The set `D = B intersect interior(C)` is
nonempty, open and convex.

These two points can be joined in D by a generic polygonal path that avoids
every face of every cell of dimension at most d-2 and crosses facet
hyperplanes transversely. To see the avoidance explicitly, for an endpoint a
off every facet hyperplane and a lower face with affine hull L of dimension
at most d-2, intermediate points z for which segment [a,z] meets L lie in
the affine hull of a and L, of dimension at most d-1. Avoiding the finitely
many such proper affine sets for both endpoints, and the finitely many facet
hyperplanes, gives a permissible intermediate point z in the open set D.
Endpoints can also be chosen generically in their open cell interiors. The
two resulting segments have finitely many facet crossings. The path stays
in the cube interior, so it never crosses a cube-boundary facet.

There is a small geometric point to check here: at a crossing q in the
relative interior of an internal facet H of a cell T, its identical partner
U is the cell on the other side. Since all non-H barycentric coordinates of
q in both T and U are positive, a small ball around q meets T and U as the
two closed halves cut out by H's hyperplane. Their opposite-side condition
provides the two halves. No third full-dimensional cell can contain q:
its interior points approach q, some off that hyperplane, and would intersect
one of these two open halves, contradicting disjoint interiors. This also
excludes a hidden crossing of two different facet interiors. Thus each
generic crossing moves exactly from T to its checked partner U. Coverage
ensures that the path always belongs to some cell.

For a simplex T containing p, let F_T(p) be its minimal face containing p:
the convex hull of its vertices with strictly positive barycentric coordinates
at p. At a crossing, the crossed facet H contains p by the choice of B.
The minimal face of T at p is the minimal face of H at p: the barycentric
coordinate opposite H is zero. H is identical as a geometric simplex in U,
so that same minimal face is also F_U(p). Each crossing preserves the minimal
face. Connecting any two incident cells by the path proves that every cell
containing p has the same geometric minimal face F(p). This works without
moving p off the cube boundary; only the path's nearby endpoints and segments
are in the cube interior.

Now let A and B be two cells with nonempty intersection Q. Choose p in the
relative interior of the convex set Q. The preceding argument gives the same
minimal face F of A and B at p. Hence F is contained in Q. To show Q has
no additional point, expose F in A with the affine functional ell equal to
the sum of A's barycentric coordinates at vertices outside F. It is
nonnegative on A, and its zero set in A is exactly F. If q in Q were outside
F, then ell(q)>0 and ell(p)=0. Relative interior of Q implies that, for a
sufficiently small epsilon>0, `r = p + epsilon(p-q)` is also in Q. But
`ell(r) = -epsilon ell(q) < 0`, contradicting Q being contained in A.
Thus Q=F, a common face of both cells. Empty intersections need no condition;
singleton intersections are included by the same minimal-face argument.

This formalization resolves two compressed steps in HANDOFF: why a generic
crossing actually reaches the matched cell, and why a relative-interior point
of the intersection rules out points outside its common minimal face. No
weaker guarantee or specification change is needed. The fresh independent
reviewer must assess this argument; the author's explanation is not a verdict.

## Behavior, preconditions and review

`test_covering_attribution_t_junction_is_rejected_after_coverage` establishes
genuine S08 coverage and midpoint incidence before requiring S09 rejection
of a missing full-facet partner. `test_square_facets_use_global_sets_despite_reversed_vertex_order`
checks canonical keys and reader opposite indices. The cube test pairs six
tetrahedra and permits a shared edge. `test_lower_dimensional_contacts_interior_and_cube_boundary`
checks common vertices at interior and boundary points, including a rational
cut at `1/10^80`. `test_diagonal_with_boundary_vertices_is_actually_an_internal_facet`
exposes the tempting wrong boundary classification. Source and ownership
tests check the public diagnostics and immutable incidence map.

Missing cells, more than two cells sharing a full internal facet, or two
full-facet partners on the same side cannot pass genuine S08 coverage with
disjoint interiors. More than one incidence on a boundary facet similarly
forces local interior overlap. The public attack test rejects these inputs
at coverage, rather than forging a successful RootCoverage to exercise
unreachable branches. Their explicit incidence/opposite-side guards remain
auditable checks; the coordinate-equality guard is additionally redundant
under the single-global-table contract. We do not claim public test execution
of these mathematically unreachable post-S08 failure branches.

Auxiliary roots continue using S08 alone. The nonconforming auxiliary fixture
still passes coverage; explicitly requesting this attribution-only checker
on it is refused by `conformity_root_kind` rather than imposing S09 on it.
