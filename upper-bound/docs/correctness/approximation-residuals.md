# Candidate completeness O1 and approximation residuals R2

This note concerns SPEC S15 on a finite connected simple bipartite unit-edge
metric graph and n>=2 labeled agents. Reports range over all real edge points.
The mechanism is the globally admissible lottery established by successful
S08–S11 checking. The factor alpha is exact and at least one. Component results
certify only their checked cells/roots; complete bound acceptance additionally
requires ordinary SP, all independently enumerated roots and actual EOF.
Tests supply implementation evidence. The arguments below, with the reviewed
A1/C1/D1/K1/K2 arguments, establish the real continuum claims.

## O1: reports and branch vertices contain a minimum

Fix any real profile x. Let S be the set of distinct report points together
with every graph vertex of degree at least three. S is finite and nonempty.
For reasoning only, subdivide edges at interior reports, then cut at S.
All remaining vertices have degree at most two. Suppressing degree-two
vertices preserves path lengths and the metric: it only replaces successive
edge intervals by their concatenation. It does not discard a reported
degree-two point, since that point belongs to S and was cut first.

Each component of the complement has the shape of an arc. It has either two
ends incident to S, possibly the same point of S, or one end in S and an
unreported leaf. There is no component that is a closed cycle disjoint from
S: such a degree-two cycle would have no connection to S, contradicting
connectedness and S nonempty. A component with two unreported leaves and no
S end would likewise be disconnected from S. No other shape is possible:
all branching vertices have been removed, and the graph is finite. Ends in
S are understood as limits of the open component. A leaf end is included.

Consider a two-ended arc of length L, parametrized by s in [0,L], with ends
A,B in S. For any report r, which is outside the arc interior, a shortest
path from its interior to r must first leave through A or B. Consequently

```text
d(r,p(s)) = min(d(r,A)+s, d(r,B)+L-s).
```

The upper bound follows by concatenating each endpoint route. For the lower
bound, the first-exit segment of any path has length at least s or L-s;
its remaining part has length at least the corresponding endpoint distance.
Taking the shortest path yields equality. These statements also hold when
A=B; there are still two different directions of exit from the open arc.
Allowing a shortest endpoint-to-report route to traverse the arc again does
not invalidate the formula: its concatenation is still a path of the stated
length, while the first-exit lower bound applies to every path.

The minimum of two affine functions of s is concave. Their finite sum, the
social cost F(s)=sum_i d(x_i,p(s)), is concave as well. Thus for 0<=s<=L,

```text
F(s) >= (1-s/L) F(0) + (s/L) F(L) >= min(F(0),F(L)).
```

Every interior point has an endpoint with no greater social cost. On a pure
cycle the reports cut the cycle into such arcs. In particular, if every
report is a single point A on a four-cycle, its sole open complementary arc
has length four and both ends are A. For each report the distance is
min(s,4-s), and the minimum remains zero at A. A can be an interior edge
point: the same cut and parametrization apply. No unreported degree-two
vertex is needed as a comparison candidate.

On a terminal arc from A in S to an unreported leaf, every path to a report
must leave through A. Hence each report distance is d(r,A)+s and total cost
is F(0)+n*s. The leaf and all positive-s points strictly increase cost.
Reported leaves belong to S and are retained. This covers bridges and graph
orientations as well: coordinate orientation does not change arc length.

For every point outside S an S point therefore has no larger cost. Since
S is finite and nonempty, its finite minimum exists and is attained. It is
also the minimum over the entire metric graph, namely OPT(x). The graph's
compactness and continuity give the same existence conclusion, but are not
needed to turn an infimum into a minimum here. O1 holds for real profiles,
without a rationality assumption or a numerical optimization procedure.

`reader.approximation_candidates` retains every labeled report index, even
when reports coincide, followed by degree>=3 vertices in document order.
It omits only unreported leaves and unreported degree-two vertices. Duplicate
locations from different report indices are harmless repeated inequalities;
no index is dropped. `approximation_root_keys`, `BundleReader`, and
`ComparisonStreams` independently enumerate every candidate/profile edge
chart. C1 and closed root coverage include all real profiles and endpoints.

## R2: every candidate inequality is exactly the OPT guarantee

Write C(x)=SC(M(x),x) and F_x(t)=sum_i d(x_i,t). The desired guarantee is
C(x)<=alpha*OPT(x). If it holds, then OPT(x)<=F_x(t) and alpha>=1 implies
C(x)<=alpha*F_x(t) for every candidate t. Conversely, if all these
inequalities hold, choose a minimizing candidate supplied by O1 to obtain
C(x)<=alpha*OPT(x). This proves equivalence.

If any candidate has alpha*F_x(t)-C(x)<0, then

```text
C(x) > alpha*F_x(t) >= alpha*OPT(x).
```

Thus the candidate need not itself minimize for the failure to be genuine.
No ratio is formed. If OPT(x)=0, a minimizing candidate's inequality requires
C(x)<=0. Admissibility and nonnegative distances make C(x)>=0, so this
correctly requires zero social cost. An SP constant mechanism with collocated
reports elsewhere fails every finite factor through this same inequality.

## Constructing and deciding the exact residual

`approximation_residual(cell, alpha)` requires a checked APX cell, no deviated
weights, positive selector count, ambient dimension n>=2 and n|F|+n distances.
`_alpha` accepts only internal integers (excluding bool) or FLINT fmpq values
and rejects factors below one. Wire parsing remains the reader's duty; a
decoded manifest already carries an fmpq, so no wire parser is reused here.

C1 proves that the whole closed cell lies in its referenced attribution
region and that the pulled affine weights a_f(x) equal the original regional
interpolants. A1 makes them a global probability lottery. D1 checks all
generated distance branches, including zero-weight selector terms. SCHEMA
orders the first n|F| terms by agent then selector and the final n by agent.
Repeating the entire selector-weight tuple n times gives precisely this order.
The assembler calls the existing `residual.cost_difference` with n constant
alpha factors on the positive side and n|F| affine weights on the negative
side. That helper permits these unequal group lengths and expands the
symmetric quadratic products exactly. Therefore throughout the closed cell,

```text
q(x) = alpha * sum_i d(x_i,t)
       - sum_i sum_f a_f(x) d(x_i,f(x))
     = alpha * F_x(t) - C(x).
```

Every labeled agent and declared selector remains in the sum. Rational
constants, affine probabilities, zero columns and coincident outputs are
covered by the same algebra. K2 reduces this quadratic to the standard
simplex and K1 decides nonnegativity on all real barycentric points, including
faces and flat/singular cases. A cell Verified therefore establishes its
candidate inequality everywhere, not merely at vertices or sampled points.

## Independent negative replay and component boundaries

The lottery must be an actual successful `check_lottery_admissibility` result.
Checked APIs require roots from `check_comparison_root` for that same lottery,
or its `ComparisonStreams`. Manually constructing records or mixing lotteries
does not satisfy the precondition; Python evidence records are not a security
boundary against executable mutation. The raw-root API checks the entire
cover and every branch/region before checking signs, so a malformed later
cell cannot become a genuine counterexample from an earlier negative cell.

A negative kernel result has rational barycentrics, an ambient point and
value. `check_approximation_cell` checks that geometry recovers the same
nonnegative barycentrics summing to one. Root-edge transport produces the
canonical labeled graph profile; the candidate is the specified report or
branch vertex. `_original_weights` resolves the original region in the
expected attribution root, recomputes its barycentrics, interpolates its
original vertex rows in order, and rechecks probabilities. It does not
evaluate the pulled weight formulas. Replay evaluates all selectors on the
actual profile and calls `graph.point_distance` for every agent/output and
agent/candidate pair, rather than using the checked branch expressions.

Only if alpha*candidate_cost-mechanism_cost equals both the negative kernel
value and direct polynomial evaluation is a COUNTEREXAMPLE returned.
Inconsistency raises REFUSED `internal_error_approximation_replay`, never
success or a purported real violation. Geometry, region, branch and global
attribution failures remain certificate failures. Unexpected exceptions and
resource failures cannot produce success; their complete API handling is
full-verification component's composition obligation.

The failure preserves source file/line, actual root, cell and candidate.
Its witness contains the canonical profile, candidate descriptor and point,
exact factor, cell barycentrics, rational difference and both costs. It is
JSON-compatible and can be independently replayed against original rows.

`check_checked_approximation_root` returns Verified only after every cell
passes; one genuine negative cell may stop it early. Such a counterexample
requires no claim about the remaining comparison roots. Complete success
requires all roots through actual EOF, all their cells, and SP; this remains
full-verification component's entry point. Auxiliary covers may be nonconforming. Closed
coverage, correct branches and the single global lottery handle boundaries
and seams without new regional weights or an arbitrary boundary convention.

## Tests and prerequisite scope

The public tests validate actual global lotteries and genuine covers. They
exercise two-agent dictatorship at alpha1; a constant mechanism with collocated
reports and factor one million; a three-agent affine lottery with positive
mass on constant(edge0,1/3), direct cost oracles and replayed negative witnesses;
an emitted nonoptimal hub candidate witness with OPT0; a three-leaf star where
report-candidate residuals are zero and hub residual is -1; omission of degree2
vertices and unreported leaves; and four-cycle interior collocation/returning
arc distances. Late invalid branches/regions/coverage, invalid attribution,
corrupted negative formulas, exact alpha boundaries, JSON source diagnostics,
wrong SP evidence and a root's late negative cell test the failure boundaries.
