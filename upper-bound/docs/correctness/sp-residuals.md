# Ordinary SP residuals and independent witness replay (R1)

The component claim is: for a globally admissible lottery and a validated SP
cell, `sp.check_sp_cell` either establishes ordinary SP in expectation for
every **real** point of that closed cell, or returns an exact graph-profile
and deviation that strictly decrease the agent's expected distance. A root
check returning Verified establishes nonnegativity for every cell of that
root; an early Failure establishes one genuine counterexample and need not
check the remaining residuals. These component
results never establish a complete upper bound or print its success format.

## Inputs, checks and caller obligations

`AdmissibleLottery` must be the actual result of successful
`lottery.check_lottery_admissibility`. That checker executes S08–S11, including
complete attribution coverage, conformity, probabilities and whole-face
lottery agreement. The graph and selectors have the permitted S01 scope.
Direct construction of an evidence dataclass is not validation, and no input
field can assert this precondition. This is the same internal-stage boundary
as comparison-domain component; Python record types are not a security boundary against arbitrary
executable mutation. Final composition must execute the actual check first.

`sp.check_sp_root(lottery, decoded_root)` calls
`comparison.check_comparison_root` before inspecting any residual. It checks
the entire auxiliary cover and all cells' regional references, projected
containment and distance branches. Therefore a malformed final branch or
region cannot be hidden by a negative residual in an earlier cell. It then
requires an SP key. There is no new certificate coefficient or weight field.

`sp.check_checked_sp_root(lottery, checked_root)` and
`sp.check_sp_cell(lottery, checked_root, cell_id)` require that checked_root
came from `comparison.check_comparison_root` **for this same lottery**, or
from that lottery's `ComparisonStreams.iter_sp_roots`. Manually constructed
checked records and mixing evidence from different lotteries do not satisfy
this obligation. The stage checks types, the SP key and cell membership;
`sp_residual` additionally checks deviated weights and exact factor counts.
`residual.cost_difference` requires nonempty matching immutable exact affine
factor tuples with a common ambient dimension. `affine.check_nonnegative`
checks the matrix/vector/vertex dimensions and affine independence again.

For complete verification a later caller must consume independently enumerated
SP roots through actual EOF, certify every returned cell, and complete all
approximation work and required streams. Neither `Verified` from this stage
nor comparison-domain component's exhaustion flag constitutes complete acceptance. A globally
admissible lottery and one validated cell already suffice for a genuine
early counterexample; incomplete future comparisons cannot remove that actual
profitable deviation.

## Tracing each factor to the mechanism

Let y=(x_0,...,x_(n-1),z) be the intrinsic coordinates in this root, let its
agent be i, and let P(y)=x and P'(y)=x[i:=z]. C1 proves the entire closed
cell projects into the two referenced attribution simplices. Its weight
pullbacks are exactly the existing regional functions
`a_f(y)=a_T,f(P(y))` and `a'_f(y)=a_U,f(P'(y))`, interpolated from their
original rows. Only report coordinate i changes. Refinement creates no new
weights. A1 makes each family a normalized distribution and makes the lottery
independent of any choice at attribution seams.

comparison-domain component generates all selector distances in truthful order followed by
deviated order. D1 proves the returned affine expressions throughout this
closed real cell are

```text
d_f(y)  = d(x_i, f(P(y))),
d'_f(y) = d(x_i, f(P'(y))).
```

The left operand is the same true x_i in both groups. In the deviated family
only peak_i's output is replaced by z; other peaks and constant selectors
retain their outputs. Changing probabilities can change every column's mass.
Terms with zero mass are still present and their branches have been checked.

`sp_residual` splits distances after |F| and forms

```text
q(y) = sum_f a'_f(y) d'_f(y) - sum_f a_f(y) d_f(y)
     = C(M(x[i:=z]), x_i) - C(M(x), x_i).
```

For one product `(a^T y+u)(b^T y+v)`, `cost_difference` adds

```text
H_ij = (a_i b_j + b_i a_j)/2,
g_i  = v a_i + u b_i,
c    = u v.
```

Indeed y^T H y=(a^T y)(b^T y): the two transposed outer products have equal
quadratic values. Diagonals are a_i b_i, while off-diagonal halves prevent
counting a cross coefficient twice. Linear and constant terms are the ordinary
product expansion. Add these coefficients for deviated costs and subtract
them for truthful costs. Every coefficient is rational and H is symmetric;
`Quadratic` copies and rechecks symmetry. These identities are algebraic over
all real y, not just the rational points used in tests. No solver-supplied
matrix, asserted minimum or sampled cost enters the construction.

K2 turns this internally constructed q on vertex columns V into the standard
simplex form, and K1 decides its nonnegativity on every real barycentric point.
Thus `Verified` implies q>=0 everywhere on the cell, which is precisely the
ordinary SP inequality for this comparison. This proof uses the complete
quadratic decision, not nonnegativity at cell vertices.

## Negative transport and independent replay

K1/K2 return exact nonnegative barycentric coordinates lambda of sum one,
an ambient point y=V lambda and a negative value. K2 already re-evaluates q
there. The SP layer independently checks `cell.geometry.barycentric(y)` equals
lambda, with nonnegative coordinates and exact sum one. The root-edge map
`point_from_chart` transports every y coordinate to canonical graph points;
0/1 become graph vertices and strict interior coordinates remain rational
edge points. The first n are the true profile, the last is the deviation.

The replay path does **not** evaluate pulled-back weight or distance formulas.
For each original referenced region it projects y to the appropriate original
coordinates, recomputes barycentrics in that attribution simplex, checks
closed containment, and sums the **original vertex weight rows** in their
original order. It rechecks that these interpolated weights are nonnegative
and sum to one. It evaluates selectors on the actual true/altered graph
profiles and calls `graph.point_distance`. Both sums use the same captured
`true_point=profile[i]`; the altered tuple replaces only element i.

The actual deviated cost minus truthful cost must equal both the kernel's
negative value and `affine.evaluate(q,y)`, and must remain strictly negative.
Only then is `Failure(kind=COUNTEREXAMPLE, code=sp_violation)` returned.
Diagnostic location retains source file, physical line, actual root, cell,
agent and comparison. Witness data includes the labeled true profile,
deviation, agent, exact cell barycentrics, normalized negative `difference`,
and both exact costs. It is SCHEMA JSON-compatible and independently auditable.

Input/branch/region/admissibility failures propagate as refused or invalid
certificate, never an SP counterexample. Replay inconsistencies raise a
REFUSED `internal_error_sp_replay` with source location; they cannot return
Verified or a false counterexample. Other unexpected exceptions and resource
failures also cannot produce success. The complete entry point's exception
and exhaustion handling remains a later composition obligation.

## Boundaries and examples

Closed regions and cells include endpoint coordinates, branch ties and
attribution seams. A1 supplies identical lotteries even if individual columns
have different seam representations. Expected graph costs therefore do not
depend on choosing one containing region. Duplicate selector outputs simply
contribute summed masses. Zero weights, exact-zero residuals, constant/linear
quadratics, flat faces and singular Hessians need no special shortcut; K1/K2
retain their reviewed degeneracy handling. Actual SP cells have dimension
n+1 by coverage, while the algebra itself needs no fixed agent count.

The public tests use genuine complete admissibility checks and validated
auxiliary geometry. Dictatorship gives q=|z-x_0| for agent0 and q=0 for other
agents, in two- and three-agent roots. A two-edge mixed-orientation deviation
checks the actual cross-edge metric. A report-dependent lottery
`M(x)=x_0 delta_x0+(1-x_0) delta_x1` has truthful cost9/16 at x=(1/4,1)
and deviated cost1/2 at z=1/2, difference -1/16. Its first emitted witness is
x=(0,1), z=1/2, difference -1/4; the offending cell has no negative vertex,
so vertex sampling would miss it. Original-row/graph replay checks the result.
At x=(1/2,1), z=1 the true-location residual is +1/4, whereas erroneously
evaluating the deviated lottery at z would give -1/4; this regression fixes
the evaluation location independently of whether a root has other violations.

A genuine three-agent mechanism uses peak0, peak2 and constant(edge0,1/3),
with weights (1-x_2,0,x_2). A bounded 384-cell root splits each coordinate at
1/3 so constant-distance kinks and report orders have actual valid branches.
For agent2 at (x_0,x_1,x_2,z)=(1,0,1/3,1), the constant mass changes1/3 to1;
truthful cost4/9 and deviated cost0 give residual -4/9. This exercises a
rational **interior** constant with positive mass and the fourth coordinate.
The returned witness is replayed independently. Hand expansion checks every
symmetric coefficient of a rational two-variable product difference; direct
costs at cell vertices and centroids check the assembled mechanism formulas.
Late malformed branches, bad/missed regions, deficient coverage, all-zero
attribution, source-location retention and deliberately corrupted negative
internal evidence exercise the failure boundaries. Finite tests support the
implementation; C1/D1/A1, the product identity and K1/K2 prove the continuum
claim. Support enumeration remains exponential and no performance guarantee
for large mechanisms is made.
