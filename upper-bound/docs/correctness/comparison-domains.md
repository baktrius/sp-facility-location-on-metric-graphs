# Comparison domains C1 and regional affine pullback (comparison-domain component)

The claim is complete preparation of SP and approximation comparisons, with
formulas valid on each closed auxiliary cell. It is not a residual sign claim
or a complete upper-bound acceptance. SPEC S12 and S13 and SCHEMA determine
the root, candidate and term orders.

The **admissibility precondition** is that the `AdmissibleLottery` argument is
the result of successful `lottery.check_lottery_admissibility`. That checker
establishes S08–S11 and retains the graph, labeled agents, selector order,
regional rows in their original vertex order, and checked attribution geometry.
The evidence dataclass is not a proof merely because a caller constructs it.
These APIs are internal mathematical stages whose caller must establish that
precondition; no certificate field can assert it. A type check prevents an
ordinary unvalidated record or boolean assertion from replacing the evidence.
The final verifier composition must obtain it by executing the checker.

## Exhaustion of the real comparison domain

Every point of the permitted connected graph lies in at least one closed
edge chart. An interior point has its unique edge; a graph vertex belongs to
each incident edge, with chart coordinate 0 or 1 according to orientation.
Connectedness and at least two vertices exclude an isolated graph vertex.
Thus every labeled profile belongs to at least one ordered n-edge product
chart. Every true profile and deviation belongs to an (n+1)-edge chart, with
coordinates ordered `(x_0,...,x_(n-1),z)`.

`reader.attribution_root_keys` supplies the lexicographic Cartesian product.
`reader.sp_root_keys` enumerates agents 0 through n-1, then that product with
n+1 coordinates. `reader.approximation_candidates` retains all report indices
0 through n-1, regardless of coincident locations, then exactly the graph
vertices of degree at least three in vertex-document order. The approximation
root enumerator takes these candidates first and all n-edge charts within
each. It never accepts a supplied root list, root count or location-dependent
candidate deduplication as authoritative. C1 exhausts the prescribed candidate
set; its sufficiency for comparison against OPT is the separate O1 obligation
of approximation-residual component, not a claim supplied by this stage.

`BundleReader` matches every header to the next independently generated key
and requires the expected sequence also to end at actual file EOF. A missing
interior root, missing suffix, empty stream, repeated root, extra root,
reordering or wrong agent/candidate cannot satisfy these conditions. The old
strict supplied-order check remains an additional diagnostic; attribution
sequence errors preserve their earlier reason-code precedence. The complete
comparison sequence check is the comparison-domain component strengthening of reader component.

`comparison.ComparisonStreams` independently repeats the sequence check for
decoded iterables, rather than assuming they came through `BundleReader`.
It checks one root at a time and yields only after coverage and all that root's
cells are checked. It does not retain earlier comparison roots. Its key
boundary requires immutable edge tuples of the exact dimension, valid edge
and agent indices with strict integer types, and precisely the permitted
candidate types. Booleans cannot alias index zero through dataclass equality.
Non-root values, including a trailing `None`, are refused; only actual
`StopIteration` is EOF. No supplied value serves as an exhaustion sentinel.

Both comparison iterators are one-shot. Completion flags are set only after
actual exhaustion of each input, including the check following its final
expected root. When the input is a reader iterator, this resumes the reader
through its trailing-record check before either layer records completion.
Stopping after the final yield, closing, interruption, a late malformed
record or any raised error cannot complete the stream. The flags express
completion of this preparation stage; residual and full-verification stages must also check every
residual and the entire composition before success. No API here prints a bound
or returns an accepted mechanism result.

## Coverage, attribution references and pullback

`check_comparison_root` reuses `coverage.check_root_coverage` on the auxiliary
root. G2 proves a finite cover of the whole closed cube with disjoint simplex
interiors. The local canonical vertex table is rechecked for chart membership
and injectivity. Each record retains its file and line while its root context
is replaced by the actual checked root key, including unused vertices and
duplicate ID/point failures. Header context is restored after the table scan
for coverage. No attribution conformity condition is imposed on auxiliary
cells: a T junction is allowed. Every real point, including an irrational
point or boundary point, belongs to a checked closed cell.

For an SP key with agent i, define coordinate projections

`P_T(y) = (y_0,...,y_(n-1))`,

`P_D(y)_j = y_n if j=i, otherwise y_j`.

For APX use `P_T` only. The truthful attribution key is the first n edges.
The deviated key replaces only edge i by the last edge. Region IDs must resolve
in the checked geometry of these **expected** attribution roots, not merely in
the global ID namespace. APX cannot carry a deviated region; SP must carry one.
This prevents a plausible region from a different chart from supplying a
different formula. Endpoint-valued projections keep these prescribed charts;
canonical point identity and global lottery agreement make chart overlaps
consistent without dropping a comparison.

For each auxiliary simplex S, the code tests every vertex v of S for closed
containment of `P_T(v)` and, for SP, `P_D(v)` in the claimed attribution
simplex. Exact barycentric containment includes all ambient equations and
nonnegative coordinates. If `y=sum_j lambda_j v_j` with real nonnegative
lambda summing to one, affinity gives `P(y)=sum_j lambda_j P(v_j)`. Convexity
of the attribution simplex therefore implies containment throughout S.
Checking only some vertices, or only one plausible representative point,
would not establish this implication.

Let a regional selector column have original vertex values w_j on attribution
simplex T with original ordered geometry columns v_j. Its unique affine
interpolant `a_T(t)=b dot t+c` is recovered from those exact values in that
original order using `Simplex.interpolate(...).coefficients()`. The comparison
weight is precisely `a_T(P(y))`; composing b with the coordinate projection
gives the returned `AffineExpression` coefficients and retains c. In SP only
coefficient i moves to coordinate n for the deviated weights. No auxiliary
weight rows, new variables, independent refits or seam choices are accepted.
All weights are the existing admissible regional functions restricted to S.
Vertex order changes in an attribution record preserve the formula because
the checked geometry and rows keep that same order.

## Internally generated distance terms

`comparison_distance_terms` constructs root report expressions with
`distance.root_expressions`, preserving edge expressions even at endpoints.
Truthful selectors are evaluated on the first n reports; deviated selectors
are evaluated on the tuple replacing only report i by the final expression z.
For SP, all |F| truthful selector distances precede all |F| deviated selector
distances. **Both groups start at true x_i**. Only the deviated peak_i output
changes to z. Other peaks and canonical constant selectors retain their
outputs. This is ordinary SP's cost comparison, not a cost from the deviation.

For APX, n|F| social-cost distances are agent-major and selector-minor, then
n distances to the current candidate appear in agent order. Report candidates
use their labeled root expression; branching vertex candidates are canonical
constants. Terms are neither merged nor omitted, including zero-weight terms.
`distance.check_distance_terms` requires exactly 2|F| or n|F|+n branches and
checks every generated operand pair. D1 establishes their metric equality on
the entire closed cell from the affine vertex inequalities. Returned cells
retain the record, checked geometry, weight expressions, ordered operands and
checked distance expressions for residual construction and source/witness
provenance in SP and approximation stages.

Region, coverage, root-sequence and distance failures are invalid certificates,
not mechanism counterexamples. Malformed numeric types are refused. Available
root, cell and source location are retained; distance failures also retain
their term index. Resource exhaustion and unexpected errors cannot become
successful exhaustion. No polynomial assembly or quadratic sign check occurs
in this component.

Public tests independently list/count tiny roots, preserve report candidates
at coincident endpoints, attack both wire and decoded sequences, and check
both EOF layers. Genuine admissible meshes exercise affine weights in reversed
vertex order, wrong-chart regions, the last projected vertex, all branches
including unused selectors, nonconforming auxiliary coverage, and a focused
three-agent/agent-2 SP root with four coordinates and 24 simplices. Exact
hand formulas at vertices and centroids verify the intended costs and pullback;
the convexity/affinity and coverage arguments establish the universal real
claim. Tests fabricate neither validated meshes nor admissibility results.
