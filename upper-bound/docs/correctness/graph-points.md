# Canonical graph points and the direct unit metric (G1)

## Claim and checked assumptions

`parse_graph` accepts exactly the graph object fields `vertices`, `edges`,
and optionally an empty JSON array `symmetries`. Both main fields are arrays;
each edge is an array of exactly two declared string labels. `Graph` checks
at least two distinct vertices, no loops or duplicate undirected edges,
connectedness and bipartiteness. Unknown graph fields, weights, supplied
distances and nonempty symmetry declarations are rejected. Vertex labels
are strings, including the empty string if declared: SCHEMA's nonempty record
IDs are separate from graph labels. Vertex order, edge order and each listed
orientation are retained, and no symmetry quotient is taken.

The resulting graph is a finite connected simple bipartite graph whose
continuous edges all have length one. `Graph.vertex_distance(u,v)` computes
the exact shortest-path length from those edges. `point_distance` computes
the continuous metric between canonical rational graph points. Chart
conversion and membership identify a graph endpoint consistently in every
incident edge chart (G1), including vertices of degree three or more.

`parse_point` accepts only `{vertex: label}` or `{edge: index, coordinate: q}`
with a declared label/edge and a strictly interior rational q. Exact field
sets exclude ambiguous combined forms. `exact.parse_rational` enforces
SCHEMA's canonical wire syntax; indices use built-in integers, excluding
booleans, floats, integer strings and out-of-range values. Wire coordinates
0 and 1 are rejected, rather than silently repaired. `point_from_chart` is
a separate internal interface: an integer or FLINT rational in [0,1] is
converted to canonical form, including endpoint vertex form at 0 and 1.

Point and selector records are frozen; graph/profile/family storage uses
tuples. Copies of decoded arrays do not retain mutable input containers.
The S02 trust boundary is parsed data, not deliberately executed Python
code that bypasses ordinary object construction or mutates frozen objects.
JSON token, duplicate-key and full certificate-stream checks belong to
the reader; these APIs consume already decoded values and provide no
certificate acceptance result.

## Exact vertex shortest paths

`Graph.__post_init__` constructs adjacency solely from validated edges.
A breadth-first traversal from the first vertex assigns alternating colors.
Every inspected edge must join opposite colors, and every vertex must be
reached. Thus the accepted graph is bipartite and connected.

A breadth-first traversal is then run from each vertex. Its queue processes
vertices in nondecreasing hop count. A newly reached neighbor gets the
current hop count plus one; a shorter path would have reached it from an
earlier queue layer. Hence the first assigned count is the minimum number
of edges in a path. Unit lengths make that integer exactly the graph metric
on vertices. All rows follow the declared vertex order. The distance table
is derived during construction and cannot be supplied as an input field.

## Canonical identity and G1

Each edge e=(u,v) has its declared coordinate 0 at u and 1 at v. Its strict
interior belongs only to that edge, since metric-graph gluing identifies
endpoints and never different interiors. `EdgePoint(e,q)` therefore has a
unique identity for 0<q<1. All occurrences of an endpoint become the same
`VertexPoint(label)`, irrespective of incident edge or orientation.

`point_in_chart` admits a vertex exactly when its label is one of that edge's
endpoints, and an interior point exactly when its edge index matches.
`chart_coordinate` returns the vertex's endpoint index or the interior
coordinate and rejects nonmembership. Loops are excluded, so the two endpoint
indices are unambiguous. For every closed chart coordinate q,
`chart_coordinate(graph, point_from_chart(graph,e,q),e)=q`. Conversely, for
every point admitted by that chart, conversion of its coordinate returns the
same canonical point.

Reversing a listed orientation exchanges q with 1-q while preserving the
represented graph location and metric. A branch vertex can have 0 in one
chart, 1 in another, and 0 in a third; its canonical label is identical in
all of them. Equality and hashing use these canonical record values, not
the chart used to obtain them. In a graph product the same argument applies
independently to every coordinate. `parse_profile` preserves exactly n
labeled coordinates for every integer n>=2; it imposes no permutation
identification. Injective ID tables and mesh conformity are later checks,
not claims made by this component.

## Direct continuous metric

Write D(u,v) for the recomputed vertex distance. For e=(u0,u1), define
endpoint offsets a0(s)=s and a1(s)=1-s. They are the lengths along e from
coordinate s to the corresponding endpoint. `point_distance` uses:

- Two vertices: D(u,v), returned as a FLINT rational.
- A vertex v and an interior point on e: min(D(v,u0)+s,
  D(v,u1)+1-s). Swapping the arguments gives the same value.
- Interior points on different edges e=(u0,u1), f=(v0,v1):
  min over a,b in {0,1} of A_a(s)+D(ua,vb)+B_b(t), where A and B are the
  endpoint offsets on e and f. All four endpoint pairs are considered in
  listed orientation.
- Two points on the same edge: |s-t|.

For different edges, every path from one interior to the other must leave
the first edge at an endpoint and enter the second from an endpoint. Its
middle portion has length at least D of those endpoints. Thus its length
is at least one of the four route candidates and hence at least their minimum.
Conversely, traversing the first segment, a shortest vertex path, and the
last segment gives a walk of each candidate length. Such walks remain valid
even if a shortest vertex path revisits one of the two edges. Metric distance
is at most every candidate length. The two inequalities establish the formula.
The same argument with one endpoint choice removed proves vertex/edge distance.

For the same edge, the direct segment has length |s-t|. To leave the edge,
a competing route must use endpoints. Routes via the same endpoint have
length at least s+t or 2-s-t, each at least |s-t|. Routes via opposite
endpoints have length at least s+1+(1-t) or (1-s)+1+t, also at least |s-t|
on [0,1]. Here D(u0,u1)=1: the edge itself has length one, and every
nonempty vertex path has at least one unit edge. This is the unit-edge
assumption behind the shortcut; it must not be reused for graphs with an
arbitrarily long edge and a shorter alternative path. No float conversion
or tolerance occurs in any of these comparisons.

Endpoint values are handled by canonical vertex or vertex/edge forms, and
agree with the limits of these formulas. Equal points have distance zero;
ties between routes return that same exact minimum. Branch vertices and
cycles need no special metric case. The formulas concern rational arguments
used by the verifier, with the same geometric argument valid for real chart
coordinates. This component does not produce regional affine branch formulas
or residual polynomials.

## Selectors and examples

`parse_agent_count` requires a JSON integer n>=2. `parse_selectors` requires
a nonempty array and exact peak/constant field sets. A peak index lies in
[0,n); a constant contains a validated canonical point. The family retains
column order and rejects equality of canonical descriptions. Different
peaks that happen to coincide on one profile remain distinct descriptions;
constant-only families are allowed. `evaluate_selector` chooses the named
labeled coordinate or constant on the validated graph and checks references.
There is no requirement here concerning selector weights.

The public tests in `tests/test_graph.py` include one edge, a square, and
branching trees; malformed graph/point/selector ingress; branch identity in
every incident orientation; and profiles with two and four labeled agents.
On the square a point at 1/4 of edge (a,b) and a point at 1/3 of opposite
edge (c,d) have four route lengths 31/12, 23/12, 25/12 and 41/12, so the
exact distance is 23/12. A branching example in opposing orientations has
distance 3/4+1/3=13/12 through its center. Same-edge points arbitrarily close
to opposite ends, constant vertices and equal-route square midpoints are
also exercised.

An independent supporting oracle splits every edge of a square and a
branching tree at 1/7, 1/2 and 4/5, then runs Floyd-Warshall using Python
`Fraction` segment lengths. It compares every resulting pair with the public
direct metric without calling the production vertex distances or route
formulas for the expected value. These finite examples support implementation
behavior; the arguments above establish the metric and chart claims.
