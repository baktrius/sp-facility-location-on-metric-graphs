# Lower bound verifier

The `sparse_verifier` package checks an exact rational dual certificate for a
finite necessary relaxation of ordinary strategyproof facility location. Its
accepted bound lower-bounds the continuous problem on the certificate's explicit
unit-edge graph. The graph must be finite, connected, simple and bipartite.

The paper's equal-edge bipartite corollary (`lower-exp:cor-bipartite`)
supplies the finite programs used to search for these certificates. Every
vertex is available both as a report and as a facility output. Distance from
a true vertex is affine along each edge, so redistributing an interior output
to its endpoints preserves expected costs at all report vertices and transfers
every feasible dual bound to the unrestricted continuous problem. Uniform
subdivision adds report locations while preserving the continuous metric graph,
up to uniform scaling when the new edges are assigned unit length. Equal edge
lengths are essential to this specialization.

Agent-permutation averaging justifies the anonymous profile representation.
The checker reconstructs the LP on the explicit graph and checks the final dual
directly; it accepts no supplied graph-symmetry quotient. In the paper's
notation it checks `omega <= 1` and recomputes
`1 + sum(gamma) - omega`; it does not require normalization to `omega = 1`.
The archive retains the verifier, finished certificates and verification records,
not the search software that produced the graph-bound certificates.

Run from this directory with Python 3.12 or newer:

```sh
python -m sparse_verifier tests/fixtures/theta-m1-agents3.json
python ../scripts/verify.py --direction lower --case theta-n3
```

No solver or third-party runtime package is used. Exit 0 prints the exact bound
and one newline. Exit 1 rejects a failed mathematical check; exit 2 refuses malformed,
unreadable or unsupported input. Failures explain the check on stderr and print
no bound on stdout. The API is `sparse_verifier.verify(document)`; inspect the
returned verdict's `accepted` and `bound` fields.

See [the format](FORMAT.md), [trust assessment](../docs/VERIFIER-TRUST.md),
and [theory comparison](../docs/THEORY-AND-IMPLEMENTATION.md). The latter explains
why anonymous finite reports and vertex outcomes give a valid lower bound on
unrestricted labeled continuous mechanisms. The [metric helper](../scripts/metric.py)
separately confirms correspondence to the scoreboard's graph up to uniform scaling.

Twenty focused tests cover parsing/scope, malformed graphs, dual failures, exact
values and CLI behavior. They require pytest, available in the upper package's
locked development environment.

The archive license and citation are in the
[root README](../README.md#license-and-citation).
