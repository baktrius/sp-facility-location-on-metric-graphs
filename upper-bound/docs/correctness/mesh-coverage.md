# Root coverage and disjoint interiors (G2, SPEC S08)

`coverage.check_root_coverage(graph, root, attribution_vertices=None)` uses
decoded `reader.RootBlock` records and the validated `graph.Graph`. Attribution
vertices resolve from the explicit global mapping; auxiliary vertices resolve
only within their root. It returns `RootCoverage`, containing the original
root, read-only ID-to-`geometry.Simplex` and ID-to-derived-membership maps, and
the exact original-cell volume sum. This is evidence for one cube cover. It
does not establish conformity, probabilities, gluing, comparison completeness,
distance branches, residual signs or a mechanism bound.

## Assumptions checked by the code

Each root has a nonempty set of distinct original simplex IDs. Every vertex
reference resolves in the appropriate namespace. `geometry.simplex_in_root`
performs the reviewed conversion to the root's ordered, oriented edge charts
and `cube_simplex` checks affine independence, full root dimension and closed
cube containment. Thus the intrinsic cube has positive dimension `d` and
every simplex is the convex hull of `d+1` affinely independent vertices in
`[0,1]^d`. Conversion errors retain their existing codes/kinds and acquire
the simplex record's file, line, root and cell. Coverage/tree/reference failures
are `INVALID_CERTIFICATE`, have stable codes and available reader locations,
and never carry a mechanism counterexample witness.

Node IDs are distinct; the header root and all children and leaf simplex
references resolve. Each split has two distinct children and an exact nonzero
normal of dimension `d`. Parent counts require zero parents for the root and
one for every other node. Iterative traversal requires every node reachable
and no repeated node. These conditions give a finite binary rooted tree:
a reachable cycle would violate the root/unique-parent constraints (and
repeated traversal is also refused); a disconnected cycle is unreachable;
a disconnected acyclic component has an extra parentless node. Node order
does not matter. Traversal does not depend on Python recursion depth.

## Routing from original vertices

The initial membership is exactly all supplied original simplex IDs. For
every split `h(y)=a dot y-b`, the code evaluates `h` at **all original simplex
vertices**, even when earlier cuts have duplicated the simplex into several
paths. It never clips geometry and never accepts solver membership lists.
Affine linearity gives `h(sum lambda_j v_j)=sum lambda_j h(v_j)` for
nonnegative barycentric coordinates summing to one. Therefore all weakly
negative vertices place the whole simplex in the minus closed halfspace;
all weakly positive vertices place it in the plus closed halfspace. Route
only to that side, including any zero-valued vertices. Otherwise both strict
signs occur and the original ID goes to both children.

The weak-side tests cannot both succeed: an affine function zero at an
affine basis is zero everywhere, contradicting the nonzero normal. Full
dimension is essential here. At every leaf the computed membership must
equal exactly the singleton containing that leaf's declared simplex ID;
empty leaves, extra IDs and wrong names all fail. This condition concerns
original memberships, not whether a clipped spatial path is nonempty.

## Why routing proves disjoint interiors

Suppose two distinct original simplices have a common interior point. Their
interior intersection is open and nonempty. The finitely many cut hyperplanes
have empty interior because their normals are nonzero, so choose a point
`p` in that open intersection off **every** cut hyperplane. At any split on
the common path, `h(p)` has a strict sign. For each of the two simplices,
the barycentric identity ensures some original vertex has that sign. Its
routing therefore includes the corresponding child, whether it is routed
only there or duplicated. Both IDs start at the root and thus follow that
same uniquely chosen child at every step. The finite tree ends at a leaf
whose membership would contain both distinct IDs, contradicting the checked
singleton. Hence distinct original simplex interiors are disjoint.

This argument uses the original full vertex signs even far down a duplicated
path. Merely counting volumes, using asserted memberships, or classifying
clipped vertices would not establish this implementation's condition.

## Why volume proves the whole closed cube is covered

Two cells with disjoint interiors intersect only on their boundaries, which
are finite unions of facets and have `d`-dimensional measure zero. Their
finite union `C` consequently has volume equal to the sum of their individual
volumes. The reviewed determinant calculation gives each original cell's
exact positive rational volume. The code sums over the distinct original
ID map **once**, regardless of its number of leaf appearances, and requires
sum exactly one. Containment gives `C subset [0,1]^d` with volume one.

Every simplex is closed and there are finitely many, so `C` is closed. If
some cube point `p`, including a boundary point, were missing, its positive
distance from this finite closed union gives a ball around `p` disjoint
from `C`. The ball's intersection with the cube has positive `d`-volume:
move slightly toward the cube's center to find an interior point in the
ball, then a smaller ball contained in both the cube and that neighborhood.
This contradicts cube volume one and union volume one. Thus every point of
the whole closed cube is covered. No face-to-face conformity was used.

## Behavioral evidence and review

`test_exact_square_partition_has_closed_coverage_and_derived_memberships`
checks diagonal boundary ties and the closed cube corners. Crossing cells
occur at multiple leaves in
`test_crossing_original_cells_repeat_at_leaves_but_volume_counts_once`;
`test_descendant_cuts_use_original_vertices_even_beyond_path_clipping`
checks original vertex signs after successive crossing cuts.
`test_gap_with_equal_volume_overlap_cannot_fake_coverage` independently
checks a duplicated half-square's volume-one sum, a common interior point
and a missing point before requiring rejection.
`test_volume_gap_after_valid_singleton_leaf_is_rejected` isolates volume.

`test_nonconforming_auxiliary_partition_passes_with_local_vertex_namespace`
checks a six-triangle partition with a T junction. Its midpoint is inside
the left shared edge but is a right-side vertex: conformity would fail,
while coverage correctly passes. `test_sp_cube_partition_uses_the_same_public_coverage_boundary`
checks the six hand-computed volume-`1/6` tetrahedra of a three-dimensional
SP cube. Parametrized public attacks cover references, cycles, shared
children, unreachable nodes, degeneracies, empty leaves and exact tiny
scaled normals. Source-context and immutable-ownership tests exercise the
returned boundary. Tests support the argument; they do not replace it.
