# Lower certificate format and checks

The CLI accepts one JSON object. The minimal factor-one example below is a valid
certificate because an all-zero dual establishes the objective constant 1.

```json
{
  "identity": {
    "formulation": "graph",
    "result": "unconditional",
    "support": "full",
    "subdivision": 1,
    "agents": 2,
    "graph": {
      "vertices": ["a", "b"],
      "edges": [["a", "b"]]
    }
  },
  "certified_value": "1",
  "multipliers": {}
}
```

## Scope and exact data

`formulation`, `result`, `support` and `subdivision` must have exactly the values
shown above. They are required scope gates, not solver assessments. `agents` must
be a non-boolean integer at least 2. The graph has distinct string labels, at least
two vertices, no loops, no parallel undirected edges, and is connected and bipartite.
Edges all have unit length. A nonempty `symmetries` declaration is refused.
An expanded subdivision must appear as an explicit graph with subdivision 1.

Vertex order is significant: row names refer to indices in the `vertices` array.
`certified_value` and each multiplier accept JSON integers or strings parsed by
Python `Fraction`; floats and booleans are rejected. Unlike the upper format, the
lower parser does not require a canonical reduced wire spelling. Use reduced
integer or p/q strings when producing new certificates for consistent output.
Zero multipliers are omitted from the active row set.

Only `identity`, `certified_value` and `multipliers` are needed. Unknown metadata is
ignored, including `model_hash`; the checker rebuilds the mathematical rows.
The CLI uses Python's JSON decoder rather than the upper verifier's stricter token
reader, so it does not reject duplicate JSON object keys (the last value wins).
New certificates should have unique keys. Its proof concerns the decoded object;
no external solver status or hash can establish acceptance.

## Rows and their numbering

For N vertices and n agents, profiles are sorted multisets of n vertex indices,
listed lexicographically and numbered from zero. There are binomial(N+n-1,n)
profiles. Ranking and unranking in `sparse_verifier/program.py` define the exact
index convention without materializing every profile. Let P be a profile,
D(a,v) the hop distance, W(P,v) its sum-distance cost, and O(P)=min_v W(P,v).
The implicit primal minimizes 1+t over t >= 0 and probabilities p[P,v] >= 0.

| Row key | Constraint |
| --- | --- |
| `normalization_P` | sum_v p[P,v] = 1 |
| `welfare_P` | sum_v W(P,v)p[P,v] - O(P)t <= O(P) |
| `incentive_P_a_b` | sum_v D(a,v)p[P,v] - sum_v D(a,v)p[Q,v] <= 0 |

In the incentive row, a occurs in P, b != a is a vertex index, and Q replaces one
copy of a by b. Both lottery costs are measured at the true location a. Strings
must match a valid row; the graph determines the distances. The graph and profile
order cannot be changed without updating the multipliers.

## Exact acceptance conditions

Equality-row multipliers are unrestricted. Every active inequality-row multiplier
is nonpositive. For each column, the sum of its coefficients times the supplied
multipliers must be at most its objective coefficient: 1 for t and 0 for p[P,v].
Finally, 1 plus the sum of row right-hand sides times multipliers must equal
`certified_value` exactly. These are weak-duality conditions for nonnegative
primal variables. No optimality or primal solution is required.

The implementation regenerates named rows, checks their signs, scans touched
probability columns by profile block, and sums the t column explicitly. An
untouched column has dual sum zero, satisfying its constraint. The column scan
therefore omits no necessary constraint despite using sparse data.

Checks occur in this order: certificate parsing, scope, graph validity, row existence,
multiplier signs, column inequalities, exact objective. A refusal or rejection
establishes no lower bound. Scope and graph correspondence are separate: two accepted
certificates should be paired only after graph metric and agent-count matching.
