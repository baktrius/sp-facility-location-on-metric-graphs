# Theory and implementation details for the certificate checkers

This comparison uses the November 2, 2026 revised companion draft *Search and Verification for Strategyproof Facility Location on Metric Graphs*, identified by SHA-256 `8152b5c688d0419b762bb65ee5c59496601fcdb6281ca14753f09616fcbb779c`. The identifiers below are its LaTeX labels, which are more stable than printed theorem numbers. The draft is not required to run the included tools. This document restates the relevant mathematical obligations and records the implementation details accompanying them.

The [trust assessment](VERIFIER-TRUST.md) states the accepted claims and trust boundaries. The [upper schema](../upper-bound/docs/SCHEMA.md) is the detailed wire specification; this document explains why the additional fields and checks exist. It does not propose changes to either verifier.

## Relation to the draft

| Draft result or section | Included implementation | Assessment |
| --- | --- | --- |
| PL attributions, `simp-new:def-pl-attribution` | Rational affine probabilities over report selectors and fixed rational graph-point selectors | A supported subclass of the draft's general PL selectors. |
| PQ costs, `quad-search:lem-quadratic-cost` | Regional weights and validated affine metric branches are multiplied to construct degree-at-most-two residuals | Same mathematical reduction, with explicit branch witnesses and exact arithmetic. |
| Global verification, `quad-search:prop-verification` | Full SP and approximation checking over the continuous report domain | Same conclusion for the supported input class; the code also checks the admissibility assumed by the proposition. |
| Finite input and comparison cells, `simp-new:verification-inputs` | Producers supply simplicial covers, references, branch choices, and separation trees; the checker validates them | The draft describes both constructed refinements and checked proposed covers, including disjoint interiors, volume, closed boundaries, and conformity requirements. |
| Quadratic nonnegativity, `simp-new:def-quadratic-oracle` and `simp-new:lem-quadratic-minimization` | Nonnegativity by enumerating supports on a standard simplex and solving nonsingular bordered systems | Implements the simplex step of the draft's single nonnegativity-or-negative-witness oracle, with the same smallest-support proof. General polytopes are triangulated in the mathematical procedure; the checker receives validated simplices. |
| Overlap constraints, `simp-new:app-attribution-constraints` | Whole-face selector equivalence classes and equal group masses | The mathematical requirement is in the draft. Canonical chart identities, exhaustive face traversal, and the concrete equality test are implementation details. |
| Benchmarks, `quad-search:lem-benchmarks` and `quad-search:remark-branching-benchmarks` | Reports and branching vertices, with all labeled report indices retained | Uses the draft's sharper benchmark observation; dropping other vertices is not an unsupported heuristic. |
| Compatible finite outputs, `lower-exp:lem-output-reduction`, `lower-exp:cor-bipartite` | Reports and outputs are every vertex of an explicit bipartite unit graph | Implements the bipartite specialization, rather than general compatible pairs `D subset B`. |
| Finite LP and dual, `lower-exp:app-dual` | Sparse exact row reconstruction with `alpha=1+t` | Same weak-duality certificate, with different stored multiplier signs and anonymous profile indexing. |
| Agent anonymity, `lower-exp:app-symmetry` | Anonymous profiles after agent-permutation averaging; no supplied graph-symmetry quotient | The draft justifies the anonymous representation and checks the final dual directly, without relying on a producer's lifting procedure. |
| Selected bounds, `lower-exp:table-verified-bounds` | Sixteen configurations, with thirteen paired bounds and three lower-only cases | The table uses outward-rounded endpoints from `scoreboard/results.json` and matches graphs up to uniform scaling and degree-two subdivision. |
| Exact recovered cycles, `lower-exp:app-legacy` | Four November 1 reconstructions at `q=4,8,12,16` have recorded full upper acceptances | The included five-file bundles and records support replay of ordinary SP and the submitted factors. Upper acceptance alone does not establish the draft's separate search-LP feasibility, ratio-drift, or near-tight witness claims. |

The draft gives the PQ reduction, a single exact nonnegativity oracle including singular quadratics, checked coverage, overlap consistency, finite benchmarks, the finite-domain reduction, duality, and agent-permutation averaging. The account below supplies the concrete input contract and checking details. Its lower-bound appendix retains the conceptual comparison with Chan–Lin–Wang certificates but makes no claim of a value-preserving embedding of those certificates.

## Upper certificate representation and obligations

A complete input directory has `manifest.json`, `vertices.jsonl`, `attribution.jsonl`, `sp.jsonl`, and `approximation.jsonl`. The manifest identifies the graph, agent count, selector order, and exact claimed factor. The other files supply the global attribution vertices, its regional affine probability rows, and the auxiliary comparison covers. The fixed file names prevent producer-controlled input indirection.

The supported graph is connected, simple, bipartite, and unit edged. Listed edge endpoints fix each chart's coordinate orientation on `[0,1]`. Interior graph points use an edge index and strict rational coordinate; endpoints use canonical vertex references. A graph vertex can belong to several incident charts, but it has one canonical graph-point identity. Edge array order, selector array order, and each simplex's vertex order are substantive data.

The format uses only report selectors `f_j(x)=x_j` and constant selectors at rational graph points. It does not accept arbitrary finite descriptions of PL selectors, nonunit edge lengths, or declarations of symmetry reduction. These are limits of the implementation contract, not impossibility results about the draft's wider mathematical class.

### Exact syntax and stream completeness

Rational values are integers or canonical reduced rational strings. The upper reader rejects floating-point tokens, nonfinite numbers, booleans in numeric fields, duplicate JSON keys, unknown record fields, and noncanonical graph-point aliases. Large integer tokens are decoded without first converting to floating point. Additional documentary files do not override the five input files.

For `m` graph edges, `n` agents, and `b` vertices of degree at least three, the required root counts are:

```text
attribution:    m^n
SP:             n * m^(n+1)
approximation:  (n+b) * m^n
```

Roots occur in a prescribed lexicographic order. The checker generates the expected sequences itself, rather than accepting counts in the manifest. Both the parser and the checked-comparison layer require the entire sequence and actual end of file. Missing, duplicate, reordered, extra, or truncated data cannot count as complete verification. These details are not part of the draft's mathematical representation theorem, but are essential to a machine-readable certificate.

For SP, each auxiliary simplex references the truthful and deviated attribution regions and supplies exactly `2|F|` branch indices. The indices describe truthful selector distances first, then deviated selector distances, always measured at the original true location. Approximation uses `n|F|+n` branch indices: every agent/selector social-cost term followed by each agent's benchmark distance. Even terms whose probability is zero retain their required branch entries. The checker constructs polynomial coefficients itself; there is no trusted producer-supplied residual matrix.

### Coverage using a separation tree and exact volume

Every original cell must be a full-dimensional simplex inside its root cube. An auxiliary binary tree supplies affine hyperplane cuts. For each cut `h(y)=a dot y-c`, the checker evaluates `h` on all original vertices of each current simplex. A simplex wholly on a weak side follows that side; a simplex crossing the cut follows both children. Memberships are derived, not read as assertions. Each leaf must contain exactly its named original simplex. The tree must have valid references, one root, unique parents, and complete reachability.

This proves disjoint interiors. If two distinct cells had an interior intersection, choose a point in that open intersection off all finitely many cut hyperplanes. Both original cells would follow its strict side at each cut, reaching a common leaf with both memberships, a contradiction.

The checker then sums exact determinant volumes of the distinct original simplices once each and requires total volume one. Since all cells are contained in the unit cube and have disjoint interiors, their union has full cube volume. The finite union is closed. A missing cube point, including a boundary point, would have a neighborhood containing positive cube volume disjoint from the union, a contradiction. Thus the entire closed cube is covered.

Volume equality alone would not suffice: overlaps could compensate for holes. The routing proof supplies the missing disjointness condition. Conversely the tree alone would not exclude gaps. The draft summarizes this two-part coverage argument after its common-refinement construction; the detailed routing rules remain here and in the correctness notes.

Attribution covers additionally have to form conforming simplicial complexes locally and across all chart faces. Auxiliary comparison covers require coverage and disjoint interiors but may be nonconforming; they do not define the lottery. Shared boundaries are still checked because each cell is closed and its residual formula must represent the actual cost there.

### Lottery equality across a whole face

On a shared face `Q`, group selectors whose graph outputs agree throughout `Q`. For peak and constant selectors, equality can be decided by their output signatures at all vertices of `Q`: in a fixed graph-edge chart the selector maps are affine, and canonical vertices identify different incident charts correctly. Use this one grouping for the entire face.

For every group `J`, require equality of the two regional sums `sum_(f in J) a_f(v)` at every face vertex `v`. Affine interpolation makes the group sums agree everywhere, so the two distributions agree as measures. When separate groups collide at a special boundary point, their matching masses add on both sides.

Individual selector columns need not match when their selectors are identical on the face. However, equality of lotteries only at the vertices, with different selector groupings at each vertex, does not imply equality throughout the face. For example, on a segment, the moving atom `delta_s` and the endpoint lottery `(1-s)delta_0+s delta_1` agree at both endpoints but differ in the interior. The whole-face constraint excludes this error.

The checker compares all nonempty shared faces, including singleton intersections, and every incident edge chart at a branching vertex. Restricting checks to facets or to one chosen pair of charts would leave part of the global mechanism definition unchecked.

### Distance formulas and residual signs

Vertex distances are recomputed by shortest-path BFS. For two distinct edge charts, the distance is the minimum over the four endpoint-to-endpoint routes. A branch index selects one such affine formula, and its being no larger than every alternative is checked at all cell vertices. Affinity propagates those inequalities over the real simplex. For the same unit edge the distance is `|s-t|`; the selected signed branch must have its required sign throughout the cell. At a route tie either minimizing branch is valid. Report expressions retain their original edge charts at endpoints, so branch enumeration cannot silently change midway through a cell.

Let `a_f` be the truthful weight, `a'_f` its value at the deviated profile, and let distance factors denote the validated affine formulas. The residual signs are:

```text
SP:   sum_f a'_f d(x_i, f(x with report i replaced by z))
      - sum_f a_f d(x_i, f(x)) >= 0

APX:  alpha * sum_i d(x_i, benchmark(x))
      - sum_(i,f) a_f d(x_i, f(x)) >= 0.
```

The true location in the deviated term is still `x_i`, not `z`. The approximation inequality is tested without dividing by `OPT`, which also handles zero-optimum profiles. A negative benchmark residual proves failure even if that benchmark is not minimizing, because its cost is at least `OPT` and `alpha >= 1`.

The residuals are quadratic because each term is a product of affine functions. Validating affine distances at vertices is sufficient; validating the quadratic residual only at vertices is not. The next kernel supplies the missing continuum decision.

## The exact quadratic nonnegativity oracle

The draft's oracle accepts a nonempty compact polytope and a polynomial of degree
at most two, certifies nonnegativity throughout that polytope or returns a negative
point, and assumes exact arithmetic and comparisons. Its finite procedure
triangulates the polytope in its affine hull and applies the following simplex
test to each cell. The implementation uses the same test on the supplied,
validated comparison simplices.

For a cell with vertex matrix `V` and quadratic

```text
q(x) = x^T H x + g^T x + c,
```

the checker verifies affine independence and writes `x=V lambda`, where `lambda >= 0` and `1^T lambda=1`. With `w=V^T g`, it constructs

```text
B = V^T H V + (w 1^T + 1 w^T)/2 + c 1 1^T.
```

Then `q(V lambda)=lambda^T B lambda` on the standard simplex. This needs no inverse of the ambient affine map, so the kernel also supports embedded simplices and singleton faces. Actual root-cover cells still satisfy the stronger full-dimension requirement.

For each nonempty support `I`, solve exactly the bordered system

```text
[B_II  -1] [u]   [0]
[ 1^T   0] [t] = [1].
```

A nonsingular solution with nonnegative `u` supplies a feasible point of quadratic value `t`; coordinates outside `I` are zero. A strictly negative value is replayed directly before a violation is returned. The algorithm skips singular bordered systems and accepts only after exhausting every support without finding a negative point. It decides nonnegativity; it need not return the global minimum when the result is nonnegative.

### Proof that skipping singular supports preserves completeness

Choose a global minimizer on the compact simplex with the smallest support `I`. It lies in the relative interior of that face. Stationarity gives `B_II u=t 1`, with every component of `u` positive and `1^T u=1`.

If the bordered matrix were singular, a nonzero null vector `(h,s)` would satisfy `B_II h=s 1` and `1^T h=0`. Symmetry and stationarity imply

```text
s = u^T B_II h = (B_II u)^T h = t 1^T h = 0.
```

Hence `h` is nonzero, `B_II h=0`, and the quadratic is constant along `u+tau h`. A nonzero zero-sum vector has both signs. Increasing positive `tau` until the first component becomes zero keeps the point in the simplex and preserves its minimum value, contradicting minimal support. Therefore that minimizer has a nonsingular bordered system and will be found in the enumeration.

This argument covers flat minimizing faces, singular quadratics, boundary minima, and exact zero minima without a positive-definite Hessian or genericity assumption. It is the proof used in the draft's finite nonnegativity lemma. Global verification, separation, and approximation bisection require only its nonnegativity verdict or negative witness; none requires an exact minimum or a minimizing point.

There are `2^k-1` nonempty supports for a simplex with `k` vertices. Exact linear algebra and large rational coefficients add further cost. The graph-root counts also grow exponentially in the number of agents, and face comparisons can be quadratic in the number of attribution simplices. Neither the draft's finite existence result nor this implementation implies practical polynomial complexity.

## Lower certificate conventions and their mathematical translation

The lower checker uses anonymous sorted multisets `P` of `n` vertex indices, ordered lexicographically. Let `p[P,v]` be an output probability and `t=alpha-1 >= 0`. Its reconstructed rows are

```text
normalization_P: sum_v p[P,v] = 1
welfare_P:       sum_v SC(P,v) p[P,v] - OPT(P) t <= OPT(P)
incentive_P_a_b:  sum_v d(a,v) p[P,v] - sum_v d(a,v) p[Q,v] <= 0,
                 Q = P with one occurrence of a replaced by b.
```

Names encode the integer profile block and, for incentives, true and reported vertex indices. The certificate supplies a sparse map of row names to exact multipliers and a claimed exact objective. The graph and vertex ordering determine the meaning of those names; no solver matrix is accepted.

The draft writes nonnegative welfare multipliers `lambda_P`, nonnegative incentive multipliers `beta_e`, and free normalization multipliers `gamma_P`. The stored convention is

```text
stored welfare multiplier   = -lambda_P
stored incentive multiplier = -beta_e
stored normalization        = gamma_P.
```

Consequently the checked `t` coefficient is `omega=sum_P lambda_P OPT(P) <= 1`. The probability-column condition is `gamma_P-D_P(v) <= 0`, exactly the draft's `D_P(v) >= gamma_P`. The computed objective is `1 + sum_P gamma_P - omega`. Negative stored inequality multipliers therefore agree with the draft's positive multipliers after this sign translation.

The checker does not require `omega=1`. The draft's short comparison with the
symmetry-based circle certificates of Chan, Lin and Wang identifies the analogous
weights; it supplies no lifting theorem for their certificate representation.

Full support means every graph vertex is an allowed facility output for every profile, including untouched columns. It does not mean every multiplier is nonzero. Omitted multipliers are zero. Columns untouched by any active row automatically satisfy their constraints because their sums are zero and their objective coefficients are nonnegative. The `t` coefficient is accumulated explicitly, while probability checks are performed one touched profile block at a time. These details explain how a sparse certificate can certify a much larger LP.

Agent anonymity is justified by averaging a continuous mechanism over all permutations independently of reports. This preserves SP and every approximation guarantee. Graph-symmetry quotients are a different operation: the checker refuses their declarations and requires an explicit graph and lifted multiplier map. The correctness of a lifting producer is not trusted when its output is subsequently checked in this explicit program.

## Pairing graphs and rational recovery

A lower certificate often uses a subdivided graph to supply more report constraints, whereas an upper mechanism may use a smaller equivalent continuous realization. A different number of vertices need not mean a different continuous instance. Conversely a shared informal graph label is not a proof of equivalence.

A correspondence must preserve junction/leaf incidences, cycle structure, and relative path lengths after degree-two suppression, allowing one global positive scale. That scale multiplies every expected cost and `OPT` equally and preserves SP inequalities and approximation factors. Agent counts must also match. This matching is outside the individual verifier claims and belongs in the reproducible scoreboard association.

Rational reconstruction changes the represented mechanism. A complete acceptance establishes the recovered rational weights' factor; it is not an error bound for rounding the original floating solution. Recovered examples should therefore include the exact mechanism encoded in a complete five-file certificate and the exact ordinary-verifier result. The [included LSP certificates](../certificates/upper/lsp-recovered/README.md) supply these directly; the recovery script and intermediate coefficient tables are not needed for replay. A coefficient file or a sampled LP objective by itself supplies none of the auxiliary completeness evidence required above.

## Division between article and accompanying documentation

| Material | Placement |
| --- | --- |
| Ordinary SP and expected sum-distance claim; unrestricted lower-bound transfer; distinction from SSP and finite-family optimality | Main article or a concise verification subsection. |
| Actual supported graph and selector class; exact arithmetic; the fact that admissibility and coverage are checked | Main article implementation summary, with a link to the specification. |
| Barycentric quadratic transformation and smallest-support proof for singular-system skipping | Mathematical appendix, `simp-new:app-quadratic-minimization`, with the same argument in the kernel correctness note. |
| Separation-tree disjointness plus volume proof, and why comparison covers may be nonconforming | Appendix, `simp-new:verification-inputs`, with concrete checking rules in the accompanying correctness notes. |
| Whole-face lottery grouping, endpoint chart identities, every-root/EOF completeness, original-row witness replay | Accompanying correctness and trust documentation; brief article summary for the most consequential choices. |
| JSON/JSONL fields, canonical rational grammar, record ordering, branch indices, CLI status meanings, dependency pins | Versioned accompanying format and usage documentation. |
| Lower sign translation, rank/unrank row naming, sparse untouched-column condition | Accompanying lower specification; appendix cross-reference if discussing the exact certificate encoding. |
| Exact graph correspondence, certificate identities, current verification records, storage and runtime observations | Dataset/scoreboard documentation and reproduction records. |

The acceptance contract remains with the implementation, including where the article now states the underlying proofs. Later certificate additions should update data and execution records without silently changing that contract. Release citations and large-file download locations remain to be supplied; this local archive does not identify a published version.
