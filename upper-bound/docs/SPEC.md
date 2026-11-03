# Upper bound verifier specification

Mathematical and algorithmic contracts for the included version-one verifier.
The [schema](SCHEMA.md) gives the wire format; [trust assessment](../../docs/VERIFIER-TRUST.md) explains its relationship to the mathematical claims.

## S01 Scope and meaning of success

Inputs describe a finite connected simple bipartite graph G with at least
two vertices, unit-length continuous edges, and an integer agent count n >= 2.
The graph encoding matches the existing lower verifier. Agent identities
remain labeled; impose neither anonymity nor graph symmetry.

A selector is either a reported location or a declared constant rational
graph point. The supplied nonempty selector family and attribution
triangulation determine a mechanism M through regional affine weights.

For every real profile x, agent i, and real deviation z, acceptance proves

\[
C(M(x),x_i)\le C(M(x[i:=z]),x_i).
\]

For every real profile x, it also proves

\[
\operatorname{SC}(M(x),x)\le \alpha\,\operatorname{OPT}(x),
\qquad \alpha\in\mathbb Q,\quad \alpha\ge1.
\]

Costs are expected distances and social cost is their sum. The comparison
with OPT uses inequalities directly, including profiles where OPT is zero.
No division by OPT is permitted.

A valid lower certificate L and upper certificate U for the same base graph
and agent count establish L <= rho_SP*(G,n) <= U, where rho_SP* is the infimum
approximation factor among unrestricted randomized SP mechanisms on that
continuous graph. The upper representation may be a restricted class.

## S02 Boundaries and trust

The verifier checks a supplied mechanism; it does not search for one.
The lower certificate's subdivision factor does not enter upper verification.
SSP, symmetry reduction, optimization, convergence, general edge lengths,
positivity hierarchies, and automatic production certificate generation are
outside version one. Small test-fixture generators are permitted outside the
trusted checker.

The package uses Python and python-flint for exact rational arithmetic and matrix
operations, with versions pinned in its dependency manifest and lockfile. Tests
use pytest. The upper checker imports neither the lower checker nor any solver.

Trusted inputs are parsed data, never executable expressions. Recompute
graph distances, affine functions, and residual coefficients. Solver
estimates, checksums, asserted minima, supplied residual matrices, and
provenance are not evidence of the mathematical claim.

Prefer a small set of ordinary functions and immutable value records.
There is no plugin architecture, generic verification framework, alternate
arithmetic backend, or cache layer in version one. Dependency direction is:
mechanism checks -> geometry and graph calculations -> exact arithmetic;
quadratic kernels do not import mechanism or certificate code.

## S03 Exact arithmetic and failures

All trusted numeric calculations use integers and exact rationals. Reject
JSON floating values, booleans in integer fields, nonfinite numbers, duplicate
object keys, zero denominators, and numeric expression strings.
[SCHEMA.md](SCHEMA.md) fixes accepted rational syntax.

Kernel results are VERIFIED or VIOLATION with a rational barycentric witness
and its negative value. Malformed inputs are separate errors. Mechanism
verification distinguishes:

- accepted: every required check completed successfully;
- invalid certificate: coverage, geometry, probabilities, references, or
  claimed formulas fail; this does not prove that some intended mechanism
  lacks SP;
- counterexample: a negative residual on a validated cell of a globally
  admissible mechanism supplies an actual violated guarantee;
- refused or incomplete: unreadable/malformed/unsupported input, resource
  exhaustion, interruption, or internal error; never acceptance.

No timeout, skipped root, unimplemented check, or unexpected exception may
be translated to acceptance. Failures retain a stable reason code and
available file, line, root, cell, and comparison information.

## S04 Standard simplex quadratic kernel

Public behavior: check a symmetric rational k by k matrix B, k >= 1, for
lambda^T B lambda >= 0 on lambda >= 0, sum(lambda) = 1.

Enumerate every nonempty coordinate subset I and solve exactly

\[
\begin{pmatrix}B_{II}&-\mathbf1\\ \mathbf1^\mathsf T&0\end{pmatrix}
\binom{u}{t}=\binom0 1.
\]

Skip a singular bordered matrix or a solution with a negative coordinate.
A retained solution is feasible and has value t. Return a negative witness
as soon as t < 0; accept only after all subsets are checked. No Hessian or
multiplier-sign condition is required. Singleton subsets are included.
A minimum-reporting diagnostic is optional and is not needed by later checks.

Correctness obligation K1: a global minimizer of smallest support has a
nonsingular bordered system. The handoff's null-direction argument must be
written beside the implementation's correctness explanation and independently
reviewed. Tests exercise degeneracy; they do not replace this argument.

## S05 Affine reduction

Public behavior: check q(x) = x^T H x + g^T x + c on the convex hull of
rational affinely independent vertices v_1,...,v_k. H is symmetric.
Embedded lower-dimensional simplices and a singleton are supported.

With columns V = [v_1 ... v_k], w = V^T g, construct

\[
B=V^\mathsf T H V+
\tfrac12(w\mathbf1^\mathsf T+\mathbf1w^\mathsf T)
+c\mathbf1\mathbf1^\mathsf T.
\]

Delegate to S04. Transport a violating lambda to x = V lambda and re-evaluate
q(x) exactly before reporting it. Validate dimensions and affine independence.
Midpoint evaluation supplies an independent test oracle for the transformation.

Correctness obligation K2: q(V lambda) equals lambda^T B lambda on the
standard simplex, including lower-dimensional embeddings.

## S06 Graphs points and charts

Validate the graph and compute vertex distances from its edge list by exact
unweighted shortest-path calculations. The listed edge orientation defines
coordinate 0 at its first endpoint and 1 at its second endpoint; edges are
undirected as metric edges.

A canonical graph point is a graph vertex, or an edge index with a rational
coordinate strictly between 0 and 1. Endpoints always use vertex form.
Membership in an edge chart is checked from the actual graph.

The original profile vertex table is injective: one ID per canonical tuple
of n graph points across all charts. A vertex can legitimately belong to
several charts. Weights remain regional and are not attached to this global
vertex ID. Auxiliary tables are local to a comparison root.

Correctness obligation G1: canonical points and chart coordinates represent
the same graph-product point across all incident edges.

## S07 Simplex geometry

Public geometry operations validate affine independence, convert to
barycentric coordinates in a simplex's affine hull, test closed containment,
interpolate vertex values, extract facets, and compute exact volumes.

Attribution and approximation simplices are full dimensional in an n-cube;
SP simplices are full dimensional in an (n+1)-cube. Their coordinates lie in
[0,1]. Use absolute determinant divided by dimension factorial for volume.
Only the generic S05 kernel accepts lower-dimensional simplices.

A cell's affine projection is contained in an attribution simplex precisely
when each projected cell vertex belongs to it. Checks must include the affine
hull as well as barycentric nonnegativity. Do not apply floating tolerances.

## S08 Root coverage

Every root carries a finite binary hyperplane tree and a nonempty list of
distinct full-dimensional simplices contained in that root cube. The root
membership is exactly the supplied simplex set. The verifier computes every
child membership from signs at every original simplex vertex.

A split has a nonzero normal. A simplex entirely in one closed halfspace is
routed only there; a simplex with vertices of both strict signs goes to both.
Full dimension and a nonzero normal exclude a simplex lying entirely on the
cut. Nodes do not carry trusted memberships or clipped simplex geometry.

Require a genuine rooted tree: every node reachable, one parent except the
root, no cycles, two distinct children for each split. Every leaf's computed
membership must consist exactly of its named simplex. A simplex may occur at
several leaves. Count its volume once, by its original simplex ID.

The total simplex volume must equal 1, the root cube's volume.

Correctness obligation G2: routing proves disjoint interiors; containment,
finitely many closed simplices, and exact total volume imply coverage of
the whole cube, including its boundary.

## S09 Attribution conformity inside a root

After S08, hash facets by their canonical vertex-ID sets. A facet contained
in a cube boundary hyperplane has exactly one incident simplex in the root.
Every other facet has exactly two incidences and identical geometry; the
vertices opposite the facet lie on opposite sides of its supporting hyperplane.

Correctness obligation G3: with coverage and disjoint interiors, these
conditions imply pairwise intersection in a common face. Review the handoff's
local path argument, including points on the cube boundary. Do not silently
substitute the weaker condition of interior disjointness.

Auxiliary comparison meshes do not need this condition.

## S10 Attribution conformity across roots

Enumerate every shared graph-product face and all incident edge-product
roots, including faces of codimension greater than one. On each face C,
restrict every incident attribution simplex to the subset of its vertices
lying in C. Discard empty subsets and retain inclusion-maximal vertex sets.

Every incident root must induce exactly the same family of maximal subsets.
Leaf boundaries have only their actual incident roots; do not invent a
partner. Comparing just one matching root at a branching vertex is insufficient.

Correctness obligation G4: restriction to a box face selects exactly its
simplex vertices on that face, and equal induced complexes glue the local
triangulations into a geometric attribution complex.

## S11 Probability and lottery consistency

At every regional vertex, all selector weights are nonnegative and sum to
one. Interpolate these weights affinely within the attribution simplex.

For every nonempty shared face Q of attribution simplices T and U, group
selectors by equality of their outputs throughout Q. Equality is determined
by each selector's tuple of graph-point values on all vertices of Q.
Compare the sum of weights in each group between T and U at every vertex of Q.
Include zero-dimensional intersections and intersections across root charts.

Once S09-S10 establish the complex, the intersection of two simplices is
the face on their common global vertex IDs. Use that fact instead of adding
a general polytope-intersection solver.

Do not require each individual selector weight to agree on a seam. Conversely,
pointwise grouping performed separately at each vertex is too weak.

Correctness obligation A1: vertex probability checks extend to the simplex;
whole-face group equations are equivalent to equality of regional lotteries.
The generic-point argument and its zero-dimensional case require review.
The combined S08-S11 checks establish one globally defined mechanism.

## S12 Comparison roots and region references

Enumerate required roots independently of the input. Attribution roots are
all ordered n-tuples of edges. SP roots are every agent index together with
every ordered (n+1)-tuple of edges for (x_0,...,x_(n-1),z).

Approximation candidates are, in order, every report index, followed by every
graph vertex of degree at least three in vertex-document order. Retain
different report indices even when the corresponding locations coincide.
Approximation roots pair every candidate with every ordered n-tuple of edges.

Reject missing, extra, duplicate, or out-of-order roots. Each comparison root
passes S08. Each cell references its truthful attribution simplex; SP cells
also reference a deviated simplex. References must belong to the expected
edge roots. The deviated profile replaces coordinate i by z and retains
every other coordinate. Validate containment at every cell vertex and pull
back the existing regional affine weights. Refinement creates no new weights.

Correctness obligation C1: these roots exhaust all profiles, agents,
deviations, and prescribed candidates; closed cells include boundary cases.

## S13 Checked distance formulas

A distance term has affine graph-point expressions determined by its root,
selector, agent, and comparison, never by an input polynomial.

- Two graph vertices: the fixed computed vertex distance.
- A graph vertex and a point on an edge: the minimum of two affine endpoint
  routes, ordered by the edge's listed endpoints.
- Points on different edges: the minimum of four affine endpoint routes,
  ordered (0,0), (0,1), (1,0), (1,1).
- Points on the same edge: |s-t|. Branch 0 is s-t, requiring s-t >= 0;
  branch 1 is t-s, requiring t-s >= 0.

For a minimum branch, require its value no larger than every alternative at
each cell vertex. For a same-edge branch, check the stated sign at each vertex.
Ties are allowed. Variable report points keep their root-edge expressions
even at endpoint vertices; constant selectors keep their canonical point type.

SP term order is truthful selector distances, then deviated selector
distances, both evaluated at the same true x_i. Approximation term order is
social-cost distances in agent-major, selector-minor order, then distances
to the candidate in agent order. Keep terms even if their weight is zero.
The supplied branch list must have exactly the generated length.

Correctness obligation D1: the branches equal metric distance throughout the
closed cell. The same-edge formula depends on the permitted unit-edge model.

## S14 SP residuals

For a validated SP cell form, from checked affine weights and distances,

\[
q_{\rm SP}=C(M(x[i:=z]),x_i)-C(M(x),x_i).
\]

Represent this quadratic with symmetric H, g, c and call S05. Never trust
solver-supplied coefficients. A violation includes x, z, agent i, the cell's
barycentric coordinates, and the exact negative difference.

Correctness obligation R1: the expression is the actual incentive difference
throughout the cell, and its nonnegativity is ordinary SP for that comparison.
In particular the true location in the deviated cost remains x_i.

## S15 Approximation residuals

For each checked candidate t form

\[
q_{\rm APX}=\alpha\sum_i d(x_i,t)-\operatorname{SC}(M(x),x).
\]

Derive its coefficients and call S05. A violation includes x, the candidate,
barycentric coordinates, and exact negative residual.

Correctness obligation O1: reports and vertices of degree at least three
contain a social-cost minimizer. Components after removing this candidate
set may have two ends mapping to the same candidate; include the four-cycle
with all reports at one point. Unreported leaves cannot improve the minimum.

Correctness obligation R2: checking every candidate is equivalent to the
approximation inequality against OPT. A negative residual for any candidate
already disproves the claimed factor; the candidate need not itself minimize.

## S16 Composition and command line

One public Python entry point verifies a certificate directory and returns
a structured result. A CLI adapts that result:

- python -m upper_bound_verifier CERTIFICATE_DIRECTORY
- Exit 0: print only the normalized rational factor and a newline to stdout.
- Exit 1: a certificate check failed or a genuine counterexample was found.
- Exit 2: unreadable, malformed, unsupported, incomplete, or internal failure.
- Failures print structured JSON diagnostics to stderr and no bound to stdout.

Diagnostics distinguish invalid_certificate from counterexample and include
exact rational witness data when available. A test re-evaluates witnesses
directly from graph distances and mechanism weights, outside the polynomial
assembly path.

Parse and validate the whole attribution before interpreting a negative
residual as a mechanism counterexample. Process comparison roots one at a time;
all required roots and the ends of all required streams must be checked before
acceptance. Extra roots or trailing records cannot be ignored. No partial
mechanism-certification mode may emit the success format.

Correctness obligation C2: accepted means graph validity, global admissibility,
coverage, all SP comparisons, and all approximation comparisons were established.
Tests must also establish that incomplete work cannot produce success.

## S17 Evidence fixtures and lower comparison

Maintain small checked-in certificate fixtures with readable descriptions.
Start with two agents on one edge, selecting agent 0 deterministically and
claiming factor 1. Then check the same mechanism on a four-cycle to exercise
multiple charts and distance branches. Both have social cost d(x_0,x_1),
which equals OPT for two agents. Fixture-generation helpers are untrusted;
the stored certificates must pass the ordinary verifier.

Add a truly non-SP example, an SP mechanism with a false approximation claim,
and corruptions of coverage, branching-vertex conformity, probabilities,
root indices, and formulas. A mesh error must never be mislabeled as an
incentive counterexample. Focused synthetic geometry tests can supply the
branching-vertex cases without a large full mechanism fixture.

For a small lower certificate, run the lower verifier separately and match the
explicit graph metric and agent count to the upper fixture. The included metric
helper verifies path incidences and relative lengths after degree-two suppression,
allowing one global positive scale. A producer's subdivision metadata is not proof
of this correspondence. Uniform scaling preserves SP and approximation factors.

The lower program's use of anonymous profiles is compatible with labeled
upper mechanisms: averaging over agent permutations preserves SP and the
factor. Include that argument in the comparison explanation. Keep the lower
checker and its dependencies outside the upper verifier's trusted code.

