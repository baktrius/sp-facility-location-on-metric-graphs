# Upper bound certificate schema

Version-one wire format accompanying [SPEC.md](SPEC.md). Syntax validation
does not certify the mathematical claim.

## Files and exact values

A certificate directory contains exactly these trusted data files:

| File | Contents |
| --- | --- |
| manifest.json | One manifest JSON object |
| vertices.jsonl | Global attribution profile vertices |
| attribution.jsonl | Attribution roots in canonical order |
| sp.jsonl | SP roots in canonical order |
| approximation.jsonl | Approximation roots in canonical order |

Additional documentation files may be present and are ignored; they cannot
override required data. Filenames are fixed, with no manifest path indirection.
Read JSON Lines incrementally; each nonempty line is one object. Blank lines
are allowed. Reject duplicate JSON keys, unknown fields in the records below,
floats, NaN, Infinity, and trailing non-JSON content. All required fields
must be present.

Reject booleans in every numeric position, including rational coordinates
and weights. Indices and schema versions are JSON integers. IDs are
nonempty strings. An exact rational is either a JSON integer, a canonical
integer string, or a reduced p/q string with q > 1 positive and gcd(|p|,q)=1.
Rational strings have no plus signs, leading zeros, whitespace, decimal or
exponent notation, negative zero, or denominator 1 in fractional form.
JSON integer tokens follow standard JSON syntax; integer -0 decodes as 0.
Output uses an integer
string when the denominator is 1. Arbitrarily large integers must not pass
through a float; any imposed resource limit produces an incomplete result.

A graph point P has exactly one of these forms:

- {"vertex":"c0"}
- {"edge":0,"coordinate":"1/3"}

Edge coordinates must be strictly between 0 and 1. Endpoints use vertex form.

## Manifest

Example showing the fields, with two peak selectors:

~~~json
{
  "schema_version": 1,
  "identity": {
    "formulation": "metric_graph_upper",
    "result": "unconditional",
    "graph": {
      "vertices": ["c0", "c1", "c2", "c3"],
      "edges": [["c0", "c1"], ["c1", "c2"], ["c2", "c3"], ["c3", "c0"]]
    },
    "agents": 2,
    "selectors": [
      {"kind": "peak", "agent": 0},
      {"kind": "peak", "agent": 1}
    ]
  },
  "certified_value": 1
}
~~~

A constant selector is {"kind":"constant","point":P}.
Require a nonempty selector list. Peak agent indices range from 0 to n-1.
Reject duplicate selectors by their canonical descriptions. Selector array
order is the weight-column order. A peak need not have positive weight.
The graph may also contain "symmetries":[]; no nonempty declaration is allowed.
Its only allowed keys are vertices, edges, and optional symmetries. Require
at least two distinct string vertex labels. Each edge is a list of exactly
two declared labels. Reject self-loops and repeated undirected edges, including
reversed duplicates. Check connectedness and bipartiteness; edge weights are
not accepted.
Vertex and edge array order are preserved. The graph must satisfy SPEC S01.
The agent count is at least two; the certified value is rational and at least one.
No solver coefficients or asserted graph distances appear in the schema.

## Global attribution vertices

Each line of vertices.jsonl is:

~~~json
{"id":"v0","point":[{"vertex":"c0"},{"edge":1,"coordinate":"1/2"}]}
~~~

The tuple has length n. Reject duplicate IDs and duplicate canonical profile
points. Every vertex reference must resolve. Declared unused vertices are
allowed but still fully validated.

## Root keys and ordering

All edge indices refer to the manifest edge array. A root key is:

- Attribution: {"edges":[e_0,...,e_(n-1)]}
  with exactly n entries.
- SP: {"agent":i,"edges":[e_0,...,e_(n-1),e_z]}
  with exactly n+1 entries, representing (x_0,...,x_(n-1),z).
- Approximation: {"candidate":K,"edges":[e_0,...,e_(n-1)]}
  with exactly n entries.

The displayed arrays use mathematical placeholders, not literal JSON values.
Candidate K is {"kind":"report","agent":j} or
{"kind":"vertex","vertex":"label"}.

The verifier generates the ordered required root sequence:

1. Attribution: all n-edge tuples in lexicographic order.
2. SP: agents in increasing order, then all (n+1)-edge tuples lexicographically.
3. Approximation: report candidates in increasing agent order, then graph
   vertices of degree at least three in document order; within each candidate,
   all n-edge tuples lexicographically.

A root block must match the next expected root. End of stream must coincide
with the end of the generated sequence. This detects missing, extra, repeated,
and reordered roots without trusting a manifest root count.

## Root block records

Each root starts with:

~~~json
{"type":"root","key":{"edges":[0,0]},"tree":"node0"}
~~~

The key has the appropriate form above. Each block ends with exactly
{"type":"end"}. Records cannot occur outside a block.

Within a block, records occur in this order: auxiliary vertices, simplices,
then tree nodes. Attribution blocks have no local vertex records; their
simplices use vertices.jsonl. Auxiliary blocks have local records

~~~json
{"type":"vertex","id":"w0","point":[{"vertex":"c0"},{"vertex":"c1"},{"vertex":"c0"}]}
~~~

The point tuple has the root dimension. IDs are unique within that block,
and all local points must be canonical and lie in the root's edge charts.
Separate IDs for an identical local point are rejected. Auxiliary IDs may
repeat across roots because their scope is local.

An attribution simplex has:

~~~json
{"type":"simplex","id":"T0","vertices":["v0","v1","v2"],
 "weights":[[1,0],[1,0],[1,0]]}
~~~

Its ID is global across attribution roots. Vertex IDs are distinct and number
dimension+1. Rows of weights correspond to the listed vertex order, columns
to selector order. All entries are rational. Global vertex IDs never imply
that weights on different attribution simplices are identical.

An SP simplex has:

~~~json
{"type":"simplex","id":"S0","vertices":["w0","w1","w2","w3"],
 "truthful":"T0","deviated":"T1","branches":[0,0,0,0]}
~~~

An approximation simplex has:

~~~json
{"type":"simplex","id":"A0","vertices":["w0","w1","w2"],
 "truthful":"T0","branches":[0,0,0,0,0,0]}
~~~

Auxiliary simplex IDs are local to the root. The illustrated branch lengths
assume n=2 and two selectors. Actual lengths are exactly 2|F| for SP and
n|F|+n for approximation. Branch lists retain zero-weight terms. Reference
and containment checks are in SPEC S12; branch semantics are in S13.

These record examples illustrate shapes and do not together constitute a
complete passing certificate.

## Tree node records

A split node is:

~~~json
{"type":"split","id":"node0","normal":[1,-1],"offset":0,
 "minus":"node1","plus":"node2"}
~~~

It represents h(y)=normal dot y-offset. Normal length equals the root
dimension and is nonzero. Coefficients and offset are rationals.
Minus denotes h<=0; plus denotes h>=0. Routing follows SPEC S08.

A leaf is {"type":"leaf","id":"node1","simplex":"T0"}.
Node IDs are unique within the root. Children may be declared later.
At block end validate the entire tree, its references, and its computed
memberships. The header's tree ID is its unique root. Leaves may name the
same simplex on different paths because crossing simplices are duplicated
during routing. Every supplied simplex is counted once in the volume sum.

## Distance term enumeration

For SP, generate terms (truthful,f) for each selector in list order, then
(deviated,f) in the same order. Both groups measure distance from x_i.
Truthful peak j evaluates at x_j. Deviated peak j evaluates at z if j=i,
otherwise x_j.

For approximation, generate (social_cost,i,f) in agent-major,
selector-minor order, then (candidate,i) in agent order. All are ordered
distances from the true report x_i to the relevant output.

Branch numbers refer only to formulas derived by the verifier:

| Distance type | Branch numbers |
| --- | --- |
| Vertex to vertex | 0, the fixed computed distance |
| Vertex and edge point | 0 or 1, routes through listed edge endpoints |
| Different edges | 0=00, 1=01, 2=10, 3=11 |
| Same edge | 0=s-t with s>=t; 1=t-s with t>=s |

For two edges the first endpoint index refers to the left distance argument,
the second to the right. Vertex-edge formulas use the sole edge's orientation.
A report expression retains its root edge at boundary vertices, so branch
arity does not change from vertex to vertex within one cell.

## Results and diagnostics

Python results distinguish acceptance, invalid certificate, counterexample,
and refusal or incompletion as in SPEC S03. A failure diagnostic emitted to
stderr contains:

~~~json
{"kind":"invalid_certificate","code":"coverage_volume",
 "message":"Simplex volumes do not sum to the root volume",
 "location":{"file":"sp.jsonl","root":{"agent":0,"edges":[0,0,0]}}}
~~~

kind, code, and message are required. location and witness are included when
available. Location may contain file, line, root, cell, agent, and candidate.
Witness data uses canonical graph points and normalized rational strings;
it includes barycentric coordinates and the exact negative residual.
Input-specific identifiers belong in fields rather than changing reason codes.

Initial reason families are schema, unsupported, graph, reference, simplex,
tree, coverage, conformity, probability, lottery_consistency, region,
distance_branch, sp_violation, approximation_violation, resource_limit,
and internal_error. Tickets may add precise suffixes consistently.
A failed branch reference is a certificate failure, not an SP violation.

An acceptance prints only alpha followed by a newline and exits zero.
No JSON success banner, partial-stage success, or approximate numeric output
may be mistaken for the final mathematical result.

