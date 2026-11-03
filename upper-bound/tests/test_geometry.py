import pytest
from flint import fmpq, fmpq_mat

from upper_bound_verifier.failures import FailureKind, VerificationError
from upper_bound_verifier.geometry import (
    AffineInterpolant,
    Facet,
    Simplex,
    cube_simplex,
    intrinsic_coordinates,
    simplex_in_root,
)
from upper_bound_verifier.graph import EdgePoint, Graph, VertexPoint


def test_cube_simplex_volume_is_absolute_and_exact():
    # Columns trace one of the six tetrahedra partitioning a unit cube.
    vertices = fmpq_mat([[0, 1, 1, 1], [0, 0, 1, 1], [0, 0, 0, 1]])
    assert Simplex(vertices).volume() == fmpq(1, 6)
    # Swap only the first two columns: an odd permutation changes determinant sign.
    reversed_vertices = fmpq_mat([[1, 0, 1, 1], [0, 0, 1, 1], [0, 0, 0, 1]])
    assert Simplex(reversed_vertices).volume() == fmpq(1, 6)


def test_embedded_containment_checks_every_ambient_coordinate():
    # x=2t, y=3t, z=5t: looking only at x,y would falsely accept z=0.
    segment = Simplex(fmpq_mat([[0, 2], [0, 3], [0, 5]]))
    assert segment.barycentric((1, fmpq(3, 2), fmpq(5, 2))) == (
        fmpq(1, 2),
        fmpq(1, 2),
    )
    assert segment.contains((0, 0, 0))
    assert segment.contains((2, 3, 5))
    assert not segment.contains((1, fmpq(3, 2), 0))
    assert segment.barycentric((1, fmpq(3, 2), 0)) is None
    assert segment.barycentric((4, 6, 10)) == (fmpq(-1), fmpq(2))
    assert not segment.contains((4, 6, 10))


def test_interpolation_reproduces_values_and_independent_interior_formula():
    triangle = Simplex(fmpq_mat([[1, 3, 1], [2, 2, 5]]))
    # f(x,y)=7+2x-3y; at vertices: 3,7,-6.
    interpolant = triangle.interpolate((3, 7, -6))
    assert [interpolant.evaluate(p) for p in [(1, 2), (3, 2), (1, 5)]] == [3, 7, -6]
    assert interpolant.evaluate((fmpq(3, 2), fmpq(11, 4))) == fmpq(7, 4)
    assert interpolant.coefficients() == ((fmpq(2), fmpq(-3)), fmpq(7))
    assert interpolant.evaluate((10, 10)) == -3  # Defined on the affine hull.


def test_facets_have_exact_zero_support_and_positive_opposite_vertex():
    triangle = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    facets = triangle.facets()
    assert tuple(f.vertex_indices for f in facets) == ((1, 2), (0, 2), (0, 1))
    for opposite, facet in enumerate(facets):
        for j, point in enumerate([(0, 0), (1, 0), (0, 1)]):
            assert facet.side(point) == int(j == opposite)
    normal, offset = facets[0].hyperplane()
    assert normal == (fmpq(-1), fmpq(-1))
    assert offset == -1  # h=1-x-y: the simplex occupies h>=0.
    assert facets[0].side((1, 1)) < 0
    neighbor = Simplex(fmpq_mat([[1, 0, 1], [0, 1, 1]]))
    assert facets[0].side((1, 1)) * facets[0].side((0, 0)) < 0
    assert neighbor.facets()[2].side((0, 0)) < 0


def test_graph_root_conversion_respects_orientation_and_full_dimension():
    graph = Graph(("a", "b", "c"), (("a", "b"), ("c", "b")))
    points = (
        (VertexPoint("a"), VertexPoint("c")),
        (VertexPoint("b"), VertexPoint("c")),
        (VertexPoint("b"), VertexPoint("b")),
    )
    assert intrinsic_coordinates(graph, (0, 1), points[2]) == (1, 1)
    assert intrinsic_coordinates(
        graph, (1, 0), (EdgePoint(1, fmpq(1, 3)), VertexPoint("a"))
    ) == (fmpq(1, 3), 0)
    simplex = simplex_in_root(graph, (0, 1), points)
    assert simplex.vertices == fmpq_mat([[0, 1, 1], [0, 0, 1]])
    assert simplex.volume() == fmpq(1, 2)
    with pytest.raises(VerificationError) as error:
        simplex_in_root(graph, (0, 1), points[:2])
    assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert error.value.failure.code == "simplex_full_dimension"
    with pytest.raises(VerificationError) as error:
        simplex_in_root(graph, (1, 0), points)
    assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    assert error.value.failure.code == "simplex_root_chart"


def test_embedded_interpolation_and_facet_sides_are_unique_only_on_the_hull():
    segment = Simplex(fmpq_mat([[1, 3], [4, 7], [2, 7]]))
    interpolant = segment.interpolate((2, 10))
    assert interpolant.evaluate((2, fmpq(11, 2), fmpq(9, 2))) == 6
    assert interpolant.evaluate((5, 10, 12)) == 18
    assert segment.facets()[0].side((2, fmpq(11, 2), fmpq(9, 2))) == fmpq(1, 2)
    assert segment.facets()[1].vertex_indices == (0,)
    with pytest.raises(VerificationError, match="outside interpolant's affine hull"):
        interpolant.evaluate((2, fmpq(11, 2), 0))
    with pytest.raises(VerificationError, match="unique ambient extension"):
        interpolant.coefficients()
    with pytest.raises(VerificationError, match="unique ambient extension"):
        segment.facets()[0].hyperplane()
    with pytest.raises(VerificationError) as error:
        segment.volume()
    assert error.value.failure.code == "unsupported_embedded_volume"
    assert error.value.failure.kind == FailureKind.REFUSED


@pytest.mark.parametrize("ambient", [0, 1, 3])
def test_singleton_and_zero_ambient_space(ambient):
    vertex = (fmpq(7),) * ambient
    matrix = fmpq_mat(ambient, 1)
    for i in range(ambient):
        matrix[i, 0] = 7
    simplex = Simplex(matrix)
    assert simplex.dimension == 0
    assert simplex.barycentric(vertex) == (fmpq(1),)
    assert simplex.contains(vertex)
    assert simplex.interpolate((11,)).evaluate(vertex) == 11
    assert simplex.facets() == ()
    if ambient:
        assert not simplex.contains((8,) * ambient)
        with pytest.raises(VerificationError):
            simplex.volume()
    else:
        assert simplex.volume() == 1
        assert simplex.interpolate((11,)).coefficients() == ((), fmpq(11))


def test_embedded_triangle_affine_hull_and_boundary():
    # Independent x,y coordinates; the last coordinate must satisfy z=x+2y+3.
    triangle = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1], [3, 4, 5]]))
    assert triangle.barycentric((fmpq(1, 4), fmpq(1, 2), fmpq(17, 4))) == (
        fmpq(1, 4),
        fmpq(1, 4),
        fmpq(1, 2),
    )
    assert triangle.contains((fmpq(1, 2), fmpq(1, 2), fmpq(9, 2)))
    assert not triangle.contains((fmpq(1, 4), fmpq(1, 2), 0))
    assert not triangle.contains((1, 1, 6))  # On hull but outside simplex.


@pytest.mark.parametrize(
    "vertices",
    [
        fmpq_mat([[0, 0], [1, 1]]),
        fmpq_mat([[0, 1, 2], [0, 1, 2]]),
        fmpq_mat([[0, 1, 0, 1], [0, 0, 1, 1]]),
        fmpq_mat(0, 2),
    ],
)
def test_repeated_and_dependent_vertices_are_certificate_failures(vertices):
    with pytest.raises(VerificationError) as error:
        Simplex(vertices)
    assert error.value.failure.code == "simplex_affine_dependence"
    assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE


def test_cube_validation_rejects_out_of_box_and_embedded_cells():
    tiny = fmpq(1, 10**80 + 7)
    with pytest.raises(VerificationError) as error:
        cube_simplex(fmpq_mat([[0, 1, 0], [0, 0, -tiny]]))
    assert error.value.failure.code == "simplex_out_of_box"
    assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    with pytest.raises(VerificationError) as error:
        cube_simplex(fmpq_mat([[0, 1], [0, 0]]))
    assert error.value.failure.code == "simplex_full_dimension"
    assert cube_simplex(fmpq_mat([[0, 1, 0], [0, 0, tiny]])).volume() == tiny / 2


def test_tiny_exact_exterior_coordinate_is_never_tolerated():
    tiny = fmpq(1, 10**100 + 3)
    simplex = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    assert simplex.barycentric((tiny, -tiny)) == (fmpq(1), tiny, -tiny)
    assert not simplex.contains((tiny, -tiny))
    assert simplex.facets()[2].side((tiny, -tiny)) == -tiny


def test_vertex_order_and_owned_copy_preserve_geometry():
    vertices = fmpq_mat([[0, 1, 0], [0, 0, 1]])
    simplex = Simplex(vertices)
    vertices[0, 0] = 10
    retrieved = simplex.vertices
    retrieved[1, 0] = 20
    assert simplex.volume() == fmpq(1, 2)
    assert simplex.barycentric((fmpq(1, 4), fmpq(1, 2))) == (
        fmpq(1, 4),
        fmpq(1, 4),
        fmpq(1, 2),
    )
    reordered = Simplex(fmpq_mat([[0, 0, 1], [1, 0, 0]]))
    assert reordered.barycentric((fmpq(1, 4), fmpq(1, 2))) == (
        fmpq(1, 2),
        fmpq(1, 4),
        fmpq(1, 4),
    )
    assert reordered.volume() == simplex.volume()


@pytest.mark.parametrize(
    "point", [(True, 0), (0.5, 0), ("1/2", 0), (0,), [0, 0, 0], None]
)
def test_malformed_exact_points_are_refused(point):
    simplex = Simplex(fmpq_mat([[0, 1, 0], [0, 0, 1]]))
    with pytest.raises(VerificationError) as error:
        simplex.contains(point)
    assert error.value.failure.kind == FailureKind.REFUSED


@pytest.mark.parametrize("vertices", [None, [[0, 1]], 3])
def test_malformed_vertex_matrix_is_refused(vertices):
    with pytest.raises(VerificationError) as error:
        Simplex(vertices)
    assert error.value.failure.code == "simplex_vertices_type"
    assert error.value.failure.kind == FailureKind.REFUSED


def test_empty_vertex_set_and_bad_interpolation_values_fail():
    with pytest.raises(VerificationError) as error:
        Simplex(fmpq_mat(2, 0))
    assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE
    simplex = Simplex(fmpq_mat([[0, 1]]))
    for values in [(1,), (1, 2, 3), (1, True), (1, 0.5)]:
        with pytest.raises(VerificationError) as error:
            simplex.interpolate(values)
        assert error.value.failure.kind == FailureKind.REFUSED
    with pytest.raises(VerificationError):
        AffineInterpolant(None, (fmpq(1),))  # ty: ignore[invalid-argument-type]
    with pytest.raises(VerificationError):
        Facet(simplex, True)
    with pytest.raises(VerificationError):
        Facet(simplex, 2)


@pytest.mark.parametrize(
    "edges,point,kind",
    [
        ((True,), (VertexPoint("a"),), FailureKind.REFUSED),
        ((3,), (VertexPoint("a"),), FailureKind.INVALID_CERTIFICATE),
        ((-1,), (VertexPoint("a"),), FailureKind.INVALID_CERTIFICATE),
        ((0,), (VertexPoint("ghost"),), FailureKind.INVALID_CERTIFICATE),
        ((0,), (EdgePoint(1, fmpq(1, 2)),), FailureKind.INVALID_CERTIFICATE),
        ((0,), (None,), FailureKind.REFUSED),
        ((0,), (), FailureKind.REFUSED),
        ((), (), FailureKind.REFUSED),
    ],
)
def test_graph_root_errors_separate_geometry_references_and_syntax(edges, point, kind):
    graph = Graph(("a", "b", "c"), (("a", "b"), ("b", "c")))
    with pytest.raises(VerificationError) as error:
        intrinsic_coordinates(graph, edges, point)
    assert error.value.failure.kind == kind


def test_graph_root_repeated_and_collinear_vertices_fail_exactly():
    graph = Graph(("a", "b"), (("a", "b"),))
    origin = (VertexPoint("a"), VertexPoint("a"))
    mid = (EdgePoint(0, fmpq(1, 2)), EdgePoint(0, fmpq(1, 2)))
    end = (VertexPoint("b"), VertexPoint("b"))
    for points in [(origin, origin, end), (origin, mid, end)]:
        with pytest.raises(VerificationError) as error:
            simplex_in_root(graph, (0, 0), points)
        assert error.value.failure.code == "simplex_affine_dependence"
        assert error.value.failure.kind == FailureKind.INVALID_CERTIFICATE


@pytest.mark.parametrize(
    "vertices",
    [
        fmpq_mat([[0, 1, 0], [0, 0, 1]]),
        fmpq_mat([[1, 3], [4, 7], [2, 7]]),
        fmpq_mat([[0, 1, 0], [0, 0, 1], [3, 4, 5]]),
        fmpq_mat(0, 1),
    ],
)
def test_geometry_and_quadratic_kernel_share_vertex_column_convention(vertices):
    from upper_bound_verifier.affine import Quadratic, check_nonnegative, transform
    from upper_bound_verifier.simplex import Verified

    simplex = Simplex(vertices)
    quadratic = Quadratic(
        fmpq_mat(vertices.nrows(), vertices.nrows()), [0] * vertices.nrows(), 7
    )
    assert transform(quadratic, simplex.vertices) == fmpq_mat(
        vertices.ncols(), vertices.ncols(), [7] * vertices.ncols() ** 2
    )
    assert isinstance(check_nonnegative(quadratic, simplex.vertices), Verified)
    for j in range(vertices.ncols()):
        point = tuple(vertices[i, j] for i in range(vertices.nrows()))
        assert simplex.barycentric(point) == tuple(
            fmpq(int(i == j)) for i in range(vertices.ncols())
        )


@pytest.mark.parametrize(
    "vertices", [fmpq_mat([[0, 0]]), fmpq_mat([[0, 1, 2], [0, 1, 2]]), fmpq_mat(0, 2)]
)
def test_geometry_and_quadratic_kernel_agree_on_affine_dependence(vertices):
    from upper_bound_verifier.affine import Quadratic, transform

    quadratic = Quadratic(
        fmpq_mat(vertices.nrows(), vertices.nrows()), [0] * vertices.nrows(), 0
    )
    for operation in [
        lambda: Simplex(vertices),
        lambda: transform(quadratic, vertices),
    ]:
        with pytest.raises(VerificationError) as error:
            operation()
        assert error.value.failure.code == "simplex_affine_dependence"


def test_full_dimensional_simplex_is_not_assumed_to_be_an_origin_simplex():
    # Edge determinant 2*3*5=30, tetrahedron volume 5.
    simplex = Simplex(fmpq_mat([[10, 12, 10, 10], [-7, -7, -4, -7], [4, 4, 4, 9]]))
    assert simplex.volume() == 5
    assert simplex.contains((fmpq(21, 2), fmpq(-25, 4), fmpq(21, 4)))
