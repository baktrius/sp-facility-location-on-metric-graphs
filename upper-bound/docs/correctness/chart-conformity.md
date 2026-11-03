# Chart conformity (G4)

`charts.check_chart_conformity(graph, agents, roots, attribution_vertices)`
checks S10 and returns `ChartConformity`. Its immutable maps contain each
recomputed `RootConformity` and every positive-codimension `ProductFace` with
its actual incident roots and common maximal restricted global ID sets.
This establishes the geometric common-face prerequisite for lottery component;
probability weights, lottery agreement, incentives and a complete bound are
not checked here.

## Assumptions checked at the boundary

The `Graph` constructor checks the finite connected simple bipartite unit-edge
scope. `parse_agent_count` checks n >= 2. Input records are decoded immutable
reader records; wire syntax, exact number grammar and endpoint aliases belong
to the reviewed `BundleReader`/graph parsing boundary. `VertexPoint` and
`EdgePoint` constructors enforce canonical forms; `point_in_chart` rechecks
graph references, even when a point does not lie on the tested first edge.
As at the reviewed reader/geometry certificate boundaries, well-formed unknown
vertex/edge references are invalid-certificate failures; only the two reference
codes are translated. Malformed point forms remain refused. Missing-root
failures retain the expected root without inventing file or line information.

The chart boundary rechecks mapping keys against nonempty vertex IDs, profile
length and canonical references, and profile injectivity including unused
entries. It independently generates the complete required root sequence with
`reader.attribution_root_keys` and rejects missing, extra, reordered or repeated
roots. Edge indices must be actual integers, excluding boolean aliases. Roots
must use the global table and contain attribution records with globally unique
nonempty simplex IDs. Each root then goes through `check_local_conformity`,
which recomputes S08 coverage and S09 common-face conformity. No asserted
coverage or local-complex result can substitute for these checks.

These rechecks resolve the component-boundary contract: a collection of
unvalidated or incomplete meshes cannot establish a global complex merely by
matching its available seams. Decoding is still required for a complete
certificate, and there is no duplicate JSON parser here. No prerequisite
source or mathematical guarantee is changed.

## Every face and every incidence

A graph-product face fixes each coordinate either to a graph vertex or to
one entire listed edge. `ProductFace.coordinates` uses `VertexPoint` for the
former and the edge-array integer for the latter. Enumerating the Cartesian
product of those choices and omitting the all-edge choices enumerates every
face of codimension 1 through n. It includes boundary faces with only one
incident root and all graph-vertex corners.

For a fixed vertex coordinate, enumerate every edge having that vertex as
one of its endpoints. For a whole-edge coordinate, the containing root must
use exactly that edge. Taking the Cartesian product gives precisely all
containing roots, independent of orientation or supplied mesh records.
Connectedness and at least two vertices ensure every graph vertex has an
incident edge. A leaf supplies one choice, so no artificial partner appears.
Every resulting root was previously validated; compare each restriction with
the first root's restriction. Equality with one common reference forces
pairwise equality of all incident restrictions. Finding a matching pair does
not stop the enumeration.

## Restriction is a simplex face

Take a simplex T contained in one root cube and a product face C of that cube.
In intrinsic coordinates each fixed graph vertex is an endpoint, hence fixes
one coordinate to 0 or 1. The other coordinates are unrestricted. Every
point of T has unique barycentric coordinates lambda_j >= 0, summing to 1.
If its i-th coordinate is 0, all vertices with positive lambda_j must have
coordinate 0, since every vertex coordinate is nonnegative. If it is 1,
apply the same argument to the nonnegative values 1 minus that coordinate.
Apply this to every fixed coordinate simultaneously. Thus every point of
T intersect C is a convex combination only of T vertices belonging to C.
Conversely those vertices lie in both convex sets, so their convex hull is
contained in the intersection. Therefore

`T intersect C = conv(vertices of T lying in C)`.

An empty selected set means empty intersection. A nonempty subset is a face
of the affinely independent simplex T, including singleton corners. Restrict
all simplices and all their faces in a reviewed local complex this way. The
intersections remain common faces, so the restriction is itself a geometric
simplicial complex covering C.

## Maximal sets determine the complex

For each original simplex the checker selects its nonempty global vertex-ID
subset on C. It deduplicates the subsets and removes only sets strictly
contained in another selected set. All faces of every selected simplex belong
to the restricted complex. Conversely each restricted face is a subset of
some original simplex's selected set. Since there are finitely many selected
sets, every one lies in an inclusion-maximal one. The maximal sets therefore
determine the entire restricted complex by taking all their nonempty subsets.

The global profile table is injective and canonical. Identical ID sets thus
identify identical graph-product geometry across incident charts. Free edge
coordinates have the same listed orientation in every containing root;
fixed vertex coordinates retain their canonical vertex identity even when
one chart represents that endpoint by 0 and another by 1. Local coordinates
alone cannot identify the geometry, and are not used as seam identities.

## Gluing proves the global common-face claim

Two distinct edges in a simple graph have empty intersection or a single
common endpoint; equal edges have their whole edge as intersection. Taking
coordinate products shows any two root charts are disjoint or intersect in
exactly one enumerated positive-codimension product face C. Within one root,
G3 gives the common-face property. For simplices T and U from different roots,
their intersection is `(T intersect C) intersect (U intersect C)`. Both
restrictions belong to the same checked boundary complex, because every
incident root has equal maximal restrictions there. Their intersection is
empty or a common face of both restrictions, hence a common face of T and U
(a face of a simplex face is a simplex face). This proves the global
geometric attribution complex, including every lower-dimensional contact.
Explicit higher-codimension checks are retained even where other seam
agreements would make them redundant.

## Public evidence and limits

`test_degree_four_seam_rejects_two_coarse_and_two_fine_incident_roots` checks
genuine local triangulations before their mismatched global seam is rejected.
`test_successful_branch_face_records_all_four_actual_incident_roots` records
all four choices and the single choice at a leaf.
`test_compatible_edge_and_square_seams_with_mixed_orientations` covers
subdivided edges and square faces in two and three agent dimensions.
`test_codimension_two_roots_are_directly_compared_on_their_shared_edge` directly
compares roots 000 and 110 on vertex o times vertex o times edge 0; their
root intersection has codimension two. Their different edge subdivisions
are rejected on that face, after genuine local conformity succeeds.

`test_leaf_boundaries_and_nonempty_maximal_restrictions` exercises discarded
contained singleton sets, singleton corners, and absence of empty maximal
sets. `test_endpoint_aliases_are_rejected_at_the_reviewed_bundle_boundary`
uses actual wire input at the reviewed reader boundary. Tests for incomplete
roots, unused canonical aliases and a covering local T-junction ensure the
public boundary rechecks its prerequisites. The fixture generator uses exact
grid boxes, monotone simplices and actual routing trees; no arithmetic mocks
or fabricated successful local results are used.

Enumeration is finite but exponential in n; no large-instance efficiency is
claimed. Exhaustion or an exception cannot yield a successful result. The
returned evidence concerns geometry only, and is not mechanism acceptance.
