# Checked affine metric branches (D1)

`distance.check_distance_branch` returns an internally derived ambient affine
function that equals continuous graph distance throughout the supplied closed
simplex, provided it returns successfully. `check_distance_terms` checks all
ordered terms and returns exactly one formula for each. These are component
claims, not SP, approximation, comparison completeness or mechanism acceptance.

The inputs are a validated immutable `Graph`, a validated rational `Simplex`,
and internally constructed point expressions. Graph construction recomputes
vertex distances by BFS and checks the finite connected simple bipartite
unit-edge scope. Simplex construction checks affine independence of nonempty
vertex columns. The distance boundary checks the graph/simplex types, every
point reference, every affine coordinate's ambient dimension and its value
in [0,1] at **every** cell vertex. Integer and FLINT rational scalars alone are
allowed. Convexity then keeps each affine edge coordinate in [0,1] throughout
the real cell. No full-dimensional or origin-simplex assumption is needed;
embedded faces, singletons and a zero-dimensional ambient space work too.
Actual comparison cells obtain their full-dimensional root validation from
the geometry/coverage and comparison layers.

An `EdgeExpression(e,s)` retains its closed root chart even where s=0 or s=1.
A `VertexPoint(v)` denotes a canonical fixed constant. `root_expressions`
derives report coordinates as ambient projections from the ordered edge root;
`coordinate_expression` supports later explicit coordinate maps.
`selector_expression` uses labeled reports or their trusted substituted tuple;
it does not change the original ambient coordinates. `constant_expression`
keeps vertex constants as vertices, and turns a strict interior `EdgePoint`
into its own edge with a zero-linear, rational constant coordinate. References
are rechecked even for columns that later carry zero probability. These
constructors are for trusted code: there is no wire polynomial decoder, and
future comparison code must generate operands from roots, agents, selectors
and candidates. A caller's construction of an expression is not evidence of
comparison completeness or of having used the required reports.

Write the listed endpoints of edge e as e_0,e_1. Its offsets are
`o_0(s)=s` and `o_1(s)=1-s`. Denote the recomputed vertex metric by D.
The checker derives exactly these candidates, using rational arithmetic:

| Types | Branches and formulas |
| --- | --- |
| Two vertex constants u,v | 0: D(u,v) |
| Vertex constant v and edge e,s, in either argument order | a=0,1: D(v,e_a)+o_a(s) |
| Different edges e,s and f,t | 0=00, 1=01, 2=10, 3=11: o_a(s)+D(e_a,f_b)+o_b(t) |
| Same edge e,s and e,t | 0: s-t with s-t>=0; 1: t-s with t-s>=0 |

The first bit on different edges is always the **left** argument's endpoint;
vertex-edge order uses the sole edge's orientation. Swapping different-edge
arguments exchanges the two bits. Edge/vertex classification does not change
as a cell vertex reaches a graph endpoint. Only the canonical constants have
vertex type. Thus one branch arity and ordering applies to the whole cell.

For different edges, any shortest path leaves the first edge and reaches the
second through listed endpoints. The segment offsets and the shortest
vertex-to-vertex path yield one of the four candidates no longer than that
path. Conversely each candidate is the length of a graph walk, and deleting
loops, or stopping when the destination is first reached, can only shorten it;
metric distance is therefore no larger than any candidate. The minimum is
exactly the metric. The same argument with a fixed vertex gives the two-route
formula. Endpoint offsets can be zero; the walk argument still holds when
an endpoint is shared by the edges. For two vertices BFS gives the metric.

For the same unit edge, the direct segment has length |s-t|. Every path that
leaves the edge must reach one endpoint and finally return from one endpoint.
Using endpoint 0 for both exit and return has length at least s+t, and using
endpoint 1 for both exit and return has length at least 2-s-t; both dominate
|s-t| for s,t in [0,1]. Using different
endpoints costs at least one unit between distinct graph vertices: the unit
metric gives D(e_0,e_1)=1 (any actual detour avoiding the edge costs at least
as much). Such walks have lengths at least 2+s-t or 2-s+t, which also dominate
|s-t| because |s-t|<=1. Paths that remain in the edge cannot beat its segment.
This proves that the direct same-edge segment is shortest. Bipartiteness is
part of the permitted scope; the argument here only needs the unit-edge and
validated graph metric assumptions. Arbitrary edge lengths could let a long
edge's exterior detour beat its direct segment and are outside this proof.

For a minimum branch b the code checks `route_b(v)<=route_a(v)` for every
candidate a and every vertex v. Each difference `route_a-route_b` is affine.
For any real point x in the closed simplex, write
`x=sum_j lambda_j v_j`, with real `lambda_j>=0` and `sum_j lambda_j=1`.
An affine difference at x is its vertex values' barycentric sum, hence is
nonnegative. Therefore the selected candidate remains a minimum everywhere
on the closed real cell, including irrational points and its boundary.
For a same-edge branch the code instead checks its sign at all vertices;
the same affine argument fixes that sign everywhere. It consequently equals
absolute value. Taking a minimum of the two signed expressions would give
a negative value and is never used. Tied minimum branches and either
same-edge branch at equality are allowed. Even on a singleton, the expression
retains its original ambient coefficients; its guarantee is on that cell.

The generated branch list must have exactly the term count. The ordered
checker processes every term without inspecting weights, merging terms or
skipping a zero-weight selector. It preserves supplied source context and
adds the failed term index. Out-of-range integer branches, failed vertex
inequalities and reference/domain failures are invalid certificates; malformed
numeric types and expression dimensions are refusals. None is a mechanism
counterexample. Successful formulas expose copied immutable exact linear
coefficients and a constant for later residual construction. Their values
outside the checked cell do not inherit the metric guarantee. An unexpected
exception or exhausted resource cannot return success.

The public tests exercise both signs and equality, competing C4 routes and
closed ties, every arity, reversed orientations, swapped argument route bits,
canonical vertices and rational interior constants, endpoint chart retention,
late vertex failure, tiny exact coordinate violations, generic embedded maps
and zero-dimensional cells. Accepted formulas are replayed against the direct
graph metric at vertices and rational interior points. A second independent
oracle splits the declared edges at query points and uses Fraction path
relaxation; it imports no route or coefficient derivation and checks branching
C4s in four orientation patterns. These finite tests support the implementation;
the affine barycentric and path arguments establish the universal real claim.
