# What the verifiers establish and what must be trusted

This document assesses the mathematical acceptance chains of the included lower and upper verifiers. It is a source-based explanation and review aid, not a formal verification of the programs or a new independent audit. Fresh execution results, where supplied, must identify the actual inputs, source, dependencies, command, exit status, and exact output. An earlier acceptance record and a checksum provide different evidence from a fresh execution.

The companion [theory and implementation comparison](THEORY-AND-IMPLEMENTATION.md) relates these checks to *Search and Verification for Strategyproof Facility Location on Metric Graphs*. The [upper format specification](../upper-bound/docs/SCHEMA.md) specifies the complete upper input. The supported claim throughout is ordinary strategyproofness in expectation for expected sum-distance cost on a continuous metric graph.

## The two accepted claims

Let `rho_SP*(G,n)` be the infimum approximation factor over all randomized mechanisms on continuous graph `G` that are SP in expectation, with `n` labeled agents. A mechanism is SP when every unilateral report change has expected cost at least the truthful expected cost, measured at the agent's original true location. Approximation means expected sum-distance cost is at most `alpha` times optimal social cost at every profile, including profiles with zero optimal cost.

| Result | Mathematical meaning after the required correspondence checks |
| --- | --- |
| Lower checker accepts exact value `L` | `L <= rho_SP*(G,n)`; it does not construct a mechanism or establish the finite LP optimum. |
| Complete upper checker accepts exact value `U` | The represented mechanism is SP in expectation and has approximation factor at most `U`, so `rho_SP*(G,n) <= U`. |
| Both accept for the same metric graph and agent count | `L <= rho_SP*(G,n) <= U`. Equality establishes the optimal value only when the endpoints are exactly equal. |

The current supported graph representation is finite, connected, simple, bipartite, and unit edged, with at least two vertices and at least two agents. The mathematical metric includes every real point of each edge. Certificate coordinates and arithmetic are rational; the conclusions concern all real reports, not just rational reports or mesh vertices.

An upper certificate establishes ordinary SP, not strong SP (SSP), universal truthfulness, completeness of its selector class, or optimality of a search procedure. An upper certificate obtained by rational recovery establishes a claim about the recovered mechanism and supplied exact factor. It does not automatically certify the original floating-point candidate or its sampled objective.

## Lower verifier acceptance chain

The entry point is [verify.py](../lower-bound/sparse_verifier/verify.py). Its essential components are small enough to review as one chain: [certificate.py](../lower-bound/sparse_verifier/certificate.py), [graph.py](../lower-bound/sparse_verifier/graph.py), [program.py](../lower-bound/sparse_verifier/program.py), and [dual.py](../lower-bound/sparse_verifier/dual.py).

1. The parser requires the explicit graph formulation, full output support, an unconditional scope declaration, subdivision field equal to one, and no nonempty graph symmetry declaration. These fields select the program to check; the word `unconditional` is not accepted as evidence of a theorem.
2. The graph checker verifies the stated graph class. Distances used in the LP are recomputed as shortest-path hop counts on that explicit unit graph.
3. The program builder reconstructs normalization, welfare, and incentive rows from canonical names. It does not accept an externally supplied matrix. An incentive compares the truthful and deviated lotteries at the original true vertex on both sides.
4. Every nonzero multiplier must name a real row. Equality multipliers are free and multipliers for stored `<=` inequalities must be nonpositive. Each touched probability column must have total dual coefficient at most zero; the nonnegative slack variable `t = alpha - 1` must have coefficient at most one.
5. The checker recomputes `1 + sum(multiplier * row_rhs)` and requires exact equality with the claimed bound. Its arithmetic uses Python integers and `fractions.Fraction`, with no LP solver or numerical tolerance in these checks.

### Why finite rows bound unrestricted continuous mechanisms

The finite program uses all graph vertices as both reports and outputs. Agent-permutation averaging preserves SP and the approximation guarantee, so anonymous profiles lose no power for this lower-bound argument. Restricting the reports and deviations to vertices keeps necessary constraints of every continuous SP mechanism.

For a true vertex `w` and adjacent vertices `u,v`, bipartiteness and unit lengths imply `|d(w,u)-d(w,v)| = 1`: distances differ by at most one and have opposite parity. Consequently, along that edge,

```text
d(w, (uv,s)) = (1-s) d(w,u) + s d(w,v),  0 <= s <= 1.
```

Replace each interior output by a lottery on the edge endpoints with masses `1-s,s`. This preserves expected distance to every true vertex simultaneously, for truthful and deviated lotteries. It applies to arbitrary probability distributions by integrating the pointwise identity. Sum-distance is affine on each edge at a vertex profile, so a vertex attains its continuous optimum. The transformed lottery is feasible in the finite program with the same approximation factor. Weak duality then transfers every accepted dual value to the unrestricted continuous problem.

### Why sparsity does not omit constraints

Omitted row multipliers are zero. A probability column not touched by any nonzero row therefore has dual sum zero, equal to its objective coefficient. The `t` column has objective coefficient one; zero is also feasible there, and its active contributions are accumulated explicitly. These facts justify checking touched blocks without materializing the full LP. They depend on nonnegative primal variables and the exact objective coefficients; this shortcut would not be valid for an arbitrary LP.

The checker uses combinatorial rank and unrank operations on sorted vertex multisets to address anonymous profile blocks. This is part of the trusted row reconstruction. A wrong profile ranking or a changed vertex order could interpret a multiplier as a different constraint, so graph vertex order is substantive certificate data.

### Lower-specific trust limits

The parser ignores a supplied `model_hash`: trust comes from reconstructing the rows from the graph, count, and row names. It also accepts extra top-level metadata. Such text cannot override the checked value. The lower CLI uses ordinary Python JSON decoding rather than the upper checker's stricter duplicate-key and canonical-number grammar. Duplicate object keys are consequently interpreted according to that decoder, and rational parsing is more permissive. Publish unambiguous JSON with unique keys and exact rational strings, and keep the original certificate bytes identified by a checksum. These ingress differences are a hardening opportunity, not an additional theorem established by the checker.

The checker verifies the explicitly supplied expanded graph. It does not validate a producer's account of how that graph was obtained from another graph or why two graph names mean the same metric. That transfer needs the correspondence described below.

## Upper verifier acceptance chain

The authority for a complete upper bound is [verification.verify_directory](../upper-bound/src/upper_bound_verifier/verification.py), exposed through the ordinary module CLI. Instantiating an `Accepted` record, checking one cell, or obtaining a nonnegative quadratic does not run this chain.

| Stage | What must be established | Principal code |
| --- | --- | --- |
| Exact input | Fixed five-file grammar, canonical rational values and graph points, valid references, complete ordered root streams | `reader.py`, `exact.py`, `graph.py` |
| Local coverage | Full-dimensional simplices lie in each cube, their interiors are disjoint, and their union is the whole closed cube | `geometry.py`, `coverage.py` |
| Global attribution geometry | Local intersections are common faces and every incident chart agrees on every graph-product face | `conformity.py`, `charts.py` |
| Admissible lottery | Nonnegative normalized weights and equal lottery measures on shared faces | `lottery.py` |
| Comparison interpretation | Every required SP and approximation root, attribution-region containment, substituted report coordinates, and valid distance branches | `comparison.py`, `distance.py` |
| Exact inequalities | Internally assembled residuals are nonnegative throughout all cells, with actual negative witnesses independently replayed | `sp.py`, `approximation.py`, `affine.py`, `simplex.py` |
| Whole-input completion | All roots and both actual stream end checks complete before the sole acceptance return | `verification.py` |

The five data files are untrusted inputs. They supply a mechanism and geometric witnesses that the checker validates. They are not trusted declarations of coverage, distances, costs, matrices, or acceptance.

### From the mesh to one mechanism

Attribution weights are affine on each simplex. Nonnegative vertex weights with row sum one extend to valid probabilities throughout the real simplex by barycentric interpolation. Coverage includes boundaries. Global face checks ensure that a profile represented in two edge charts denotes the same lottery.

Equality of individual selector weights across a face is unnecessarily strong: two different selectors can output the same graph point throughout that face. The checker partitions selectors by equality of their output functions on the entire face and compares total weight in each group at every face vertex. These group sums are affine, so equality extends over the face. Using a new collision partition separately at each vertex would be unsound: selectors can coincide at the vertices without representing the same lottery in the face interior. The whole-face grouping is an essential design choice.

### From comparison cells to global inequalities

The checker evaluates SP on the full product of truthful report charts and deviation charts, for every agent. It pulls back the truthful and deviated regional weights and evaluates both expected costs at the same original true location. Every metric branch is derived from graph distances and validated at every cell vertex; affine inequalities then establish that branch on the entire closed cell. Zero-weight terms remain subject to validation.

For approximation, it is enough to compare against every reported point and every graph vertex of degree at least three. Between such points the graph splits into unbranched arcs; social cost is concave along a two-ended arc and minimized at an end, while an arc ending at an unreported leaf has strictly increasing social cost away from its attachment. Thus this finite candidate set contains an optimum. Every candidate inequality is checked, without dividing by the optimum, so unanimous profiles are included.

Weights and branch distances are affine on a validated cell. Their products produce quadratic residuals. Exact quadratic nonnegativity extends to every real point of the cell; testing vertices alone would not suffice. The complete checker performs both SP and approximation checks and requires all expected roots and actual EOF before accepting.

### Why singular quadratic systems are safe here

The [implementation comparison](THEORY-AND-IMPLEMENTATION.md) supplies the algebra and proof. The short reason is that a global minimum on a simplex has a minimizer with smallest support. Its bordered stationarity system is nonsingular; otherwise a null direction preserves its value while reaching a smaller support. Enumerating all nonsingular supports therefore finds a negative point whenever one exists, even if other supports are singular. This is a specific theorem about this algorithm, not permission to ignore singular systems in general optimization.

### Failures and negative witnesses

An invalid mesh, missing root, bad distance branch, or inconsistent seam establishes that the supplied certificate failed; it does not establish that its intended mechanism is non-SP. A genuine counterexample is reported only after global attribution admissibility and the relevant comparison interpretation have been checked, and after replay against the original weights, selectors, and actual graph metric. A counterexample can return before later comparison roots have been read; it does not imply that all remaining file content is valid.

A timeout, interruption, resource exhaustion, refusal, or internal error supplies no bound. On success the CLI must complete with exit zero and print the exact rational factor. Process output, status, and the checked input identity belong together.

## Trust boundaries and evidence

The lower trusted computation includes its Python parser, integer and Fraction arithmetic, graph validation, row reconstruction, and dual checks. The upper trusted computation additionally includes the geometric and comparison pipeline and python-flint/FLINT rational arithmetic and linear algebra. Both rely on the interpreter, runtime, operating system, hardware, and the correspondence between the files read and those identified in the execution record. Dependency pins aid reproduction; they do not prove those dependencies correct.

Search software, optimization heuristics, solver termination messages, floating-point objective values, rational-recovery procedures, and certificate exporters need not be trusted for mathematical acceptance. A faulty producer should yield rejection or a different exact mechanism whose actual bound is checked. Any preprocessing that changes the files must be followed by verification of the changed files.

The source contains detailed proof notes and tests for exact zeros, singular systems, seams, missing roots, malformed branches, and real negative examples. Tests exercise cases; mathematical arguments justify the continuum implications. Neither is a machine-checked proof of all implementation behavior. This assessment does not substitute for independently reviewing the full code and its arithmetic dependencies.

## Matching the endpoints and extending the collection

To combine lower and upper values, check agent counts and graph metric correspondence, rather than labels or filenames. Uniform scaling of every distance preserves each SP inequality and each approximation factor. Suppressing degree-two subdivisions preserves the continuous metric; comparing the resulting path incidences and relative path lengths can therefore identify two encodings of the same instance up to uniform scale. The included [metric helper](../scripts/metric.py) is additional trusted code for this association, separate from either verifier. Unsupported or failed matching must leave the results unpaired.

Future recovered cycle mechanisms should be admitted through the same ordinary five-file upper interface. A rational coefficient table alone is not that interface: it still needs the complete attribution, coverage, SP and approximation data. A small complete recovered certificate can be a useful installation check. It should retain its exact recovered coefficients and certified factor, and its successful check should not be generalized to a larger mesh or another numerical run.
