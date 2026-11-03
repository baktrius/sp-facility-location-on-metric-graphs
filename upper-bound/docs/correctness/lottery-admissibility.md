# Lottery admissibility (A1) and composition of G2–G4

`lottery.check_lottery_admissibility(graph, agents, selectors, roots,
attribution_vertices)` returns `AdmissibleLottery` only after recomputing the
global geometric attribution complex and checking every regional probability
row and every nonempty pairwise shared simplex face. This is the S08–S11
prerequisite for subsequent genuine mechanism counterexamples. It proves no
incentive inequality, approximation inequality, or complete upper bound.

## Checked assumptions and public boundary

The inputs are a validated `Graph` and immutable decoded reader records.
`Graph` checks finite connected simple bipartite unit-edge scope with at least
two vertices. The strict `BundleReader` checks the wire grammar, fields,
canonical rational syntax and source locations. This component does not
replace JSON decoding. It copies the global vertex mapping and first calls
`charts.check_chart_conformity`, which checks n >= 2, the entire expected root
sequence, canonical/injective global profiles including unused vertices,
global simplex IDs and references, and recomputes each root's geometry,
coverage, local conformity and all incident chart-face restrictions.

Only after those checks does this component revalidate a nonempty immutable,
distinct selector family. `graph.evaluate_selector` checks selector kind,
peak index range and canonical constant graph references on a valid dummy
profile. Every selector is checked, including zero-weight columns. Unknown
graph/agent references are invalid-certificate failures; malformed kinds and
duplicate descriptions are refused, consistently with the reader boundary.

For every simplex, require an immutable row tuple for each listed vertex and
exactly one column per selector. Decoded entries must be FLINT `fmpq` values;
the wire reader converts permitted integers and rational strings to that
type. Booleans, floats, strings or Python integers passed directly as decoded
weights are refused rather than implicitly coerced. Check every entry for
nonnegativity and every row for exact sum one. Negative or nonnormalized
weights and wrong dimensions are invalid-certificate failures, with the
original simplex's file, physical line, root and cell. Seam disagreement is
also invalid-certificate failure, never an SP/APX counterexample.

The result preserves graph, agent count, selector order, the recomputed
`ChartConformity`, separate regional simplex records and a copied global
vertex table. Both new maps are read-only. Vertex order and row order remain
the original reader order; no shared ID merges regional probabilities.
Later checks can retrieve a region's geometry through
`result.geometry.roots[key].coverage.simplices[cell_id]` and interpolate
`result.regions[cell_id].weights` in that same order using `Simplex.interpolate`.
Directly constructing the result record does not perform validation; the
successful public checker is the source of admissibility evidence.

## Vertex probabilities extend to every real point

For any real x in a validated simplex T, its unique barycentric coordinates
lambda_v are nonnegative and sum to one, by S07. Define each regional weight
by the affine extension

`a_T,f(x) = sum_v lambda_v a_T,f(v)`.

Every summand is nonnegative. Interchanging the two finite sums gives
`sum_f a_T,f(x) = sum_v lambda_v sum_f a_T,f(v) = sum_v lambda_v = 1`.
Thus every regional distribution is a probability lottery at every real
point, including its closed boundary. Rational vertex arithmetic establishes
these identities of affine functions on the real simplex; this argument does
not restrict x to rational profiles or to finitely many tested points.

## Pairwise faces and one partition per whole face

G3 and G4 establish that two attribution simplices have either empty
intersection or a common face. Global profile injectivity identifies this
face exactly by the intersection of the two global vertex-ID sets. The
checker enumerates every unordered pair of regional simplices, including
different root charts, skips only empty intersections, and sorts the common
IDs solely for a deterministic common ordering. It does not limit comparison
to facets, to tree neighbors, or to a selected pair of branch charts.

For a nonempty face Q, each selector's signature is the tuple of canonical
graph outputs at **all** Q vertices in that common order. Equal signatures
define one partition of the entire selector family for Q. This same partition
is then used at every face vertex. Regional rows are looked up by their
original global IDs rather than by matching row indices across regions.
For each group J, compare `sum_{f in J} a_T,f(v)` and
`sum_{f in J} a_U,f(v)` at every Q vertex v.

## Why graph-output signatures determine whole-face equality

For precision, embed the simple graph into R^|V|: map each graph vertex u to
its standard basis vector e_u, and map coordinate t on the listed edge (u,w)
to `(1-t)e_u + t e_w`. This is an injective representation of graph points.
A vertex has support size one; an interior edge point has support exactly
its two endpoints, with both coefficients positive. Distinct simple edges
have distinct unordered endpoint pairs, and the listed orientation fixes
the coefficient interpretation. Thus two embedded points coincide exactly
when their canonical graph points coincide. No metric preservation is used.

Choose either containing root as coordinates for Q. Each report coordinate
on this face lies in one fixed edge or at a fixed graph vertex. Every embedded
peak selector is therefore affine on Q, and every embedded constant selector
is constant. Affine maps agree throughout a simplex precisely when they agree
at all its vertices. Consequently the canonical signatures describe exactly
the equality classes of selector outputs throughout Q. This holds even when
the other containing root uses a different incident edge at a fixed vertex:
its output there has the same canonical vertex and embedding. Regional
weight restrictions also use the same barycentric face parameters, so their
group sums are affine on this common geometric Q.

## Sufficiency of the group equations

For each group J the two group sums are affine functions on Q. Equality at
all Q vertices implies equality at every real point of Q. All selectors
within J produce the same graph point throughout Q. Each regional lottery
can therefore be written as the sum, over groups, of its group mass times
the Dirac measure at that group's output. Equal group masses give equal
measures pointwise. At exceptional points where different groups collide,
their already equal masses simply add at the coincident output. Individual
selector columns need not agree when they lie in the same whole-face group.

## Necessity: a dense complement of proper collision affine sets

Suppose dim(Q) >= 1 and the two regional lotteries agree at every point of Q.
Take representatives from two distinct whole-face groups J and K. Their
embedded affine selector maps differ somewhere on Q by the definition of
the groups. Their collision set is the intersection of Q with the zero
set of their affine vector difference. This zero set is empty or a proper
affine subset of aff(Q): if it contained all of aff(Q), the maps would
agree throughout Q and the two groups would be one. Each such subset has
empty relative interior. There are finitely many group pairs, so the union
of all their collision sets has a dense complement in Q. In detail, the
relative interior of Q is dense in Q, and removing finitely many proper
affine subsets leaves a dense subset of that relative interior, hence of Q.

At every point of this complement, different groups have distinct graph
outputs. Equality of the two atomic probability measures forces the mass at
each distinct output, and thus each group's total weight, to agree. The
difference of the two group sums is affine and continuous on Q. Vanishing
on the dense complement makes it zero everywhere, in particular at all
Q vertices. This proves necessity without requiring selectors to remain
distinct at boundary vertices or assuming strictly positive weights.

If Q is a singleton, its signatures are just the selector outputs at that
one point. The groups are exactly the distinct atoms there, and equality
of the lotteries is exactly equality of their group masses. The checker
performs this direct comparison. No generic-point or positive-dimension
argument is applied to a singleton.

## G2–G4 and A1 define one mechanism on G^n

Every graph point lies in some closed edge chart: an interior point has its
own edge, and every vertex has an incident edge by connectedness and the
at-least-two-vertices hypothesis. Thus the independently enumerated edge
products cover all of G^n. G2 supplies closed full-simplex coverage of every
root cube, with disjoint interiors. G3 makes each local cover a geometric
simplicial complex. G4 compares all actual incident root restrictions on
every product face and glues those complexes, so pairwise intersections are
the common faces used above, including branch seams and higher codimensions.

At a real profile x choose any containing attribution simplex. Its regional
formula is a normalized probability distribution by A1's vertex argument.
Any other containing simplex has a common face containing x, and the
whole-face equations prove the two regional lotteries equal there. Therefore
the choice is independent, defining one lottery M(x) on the entire continuous
graph product. There are no uncovered profiles or conflicting boundary
decompositions. This is the milestone-10 admissibility composition; later
validated comparison domains, distance branches and residual checks are
still required to establish any incentive or approximation guarantee.

## Public examples and limits

The public tests reject all-zero, negative, nonnormalized and missing rows,
including a tiny exact error at the last vertex of the last branch root.
They reject the seam attack `delta_t` versus `(1-t)delta_0+t delta_1`, which
agrees at endpoints but differs at the midpoint. They accept different
individual columns for peak0 and peak1 on the entire diagonal x0=x1 and
for peak0 and constant(o) on every x0=o branching seam. Singleton tests
place a genuine opposite-box singleton pair first and require its failure
to name that face. Successful branch data also has different regional
decompositions at a cross-chart singleton corner. Exact interpolation tests
reverse vertex/row order together and replay interior weights independently
with `Fraction`; geometry-first tests use a real covering T-junction.
