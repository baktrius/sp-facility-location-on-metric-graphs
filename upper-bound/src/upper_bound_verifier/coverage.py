"""Certify one closed root cube cover, without conformity or admissibility."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NoReturn

from flint import fmpq

from .failures import Failure, FailureKind, VerificationError
from .geometry import Simplex, simplex_in_root
from .graph import Graph
from .reader import AttributionKey, LeafNode, ProfileVertex, RootBlock, SourceLocation


@dataclass(frozen=True)
class RootCoverage:
    """Checked geometry and derived memberships; no mechanism acceptance.

    Maps preserve original simplex/node IDs and have immutable ownership.
    Each simplex volume contributes once even when it occurs at many leaves.
    """

    root: RootBlock
    simplices: Mapping[str, Simplex]
    memberships: Mapping[str, frozenset[str]]
    volume: fmpq


def check_root_coverage(
    graph: Graph,
    root: RootBlock,
    attribution_vertices: Mapping[str, ProfileVertex] | None = None,
) -> RootCoverage:
    """Check S08 using decoded records and the reviewed S07 geometry boundary.

    Attribution roots resolve vertices only from the global supplied mapping;
    comparison roots resolve only their local tuple. No weights, branch claims,
    conformity, comparison completeness, or SP/APX signs are checked here.
    """

    def reject(
        code: str, message: str, location: SourceLocation | None = None
    ) -> NoReturn:
        loc = root.location if location is None else location
        loc = replace(loc, root=root.key)
        raise VerificationError(
            Failure(FailureKind.INVALID_CERTIFICATE, code, message, loc.to_dict())
        )

    if not root.simplices:
        reject("coverage_empty", "A root needs at least one simplex")
    cells: dict[str, Simplex] = {}
    if isinstance(root.key, AttributionKey):
        if attribution_vertices is None:
            reject("coverage_vertices", "Attribution requires its global vertex table")
        vertices = attribution_vertices
    else:
        vertices = {vertex.id: vertex for vertex in root.vertices}
        if len(vertices) != len(root.vertices):
            reject("coverage_duplicate_vertex", "Duplicate local vertex ID")
    for cell in root.simplices:
        loc = replace(cell.location, root=root.key, cell=cell.id)
        if cell.id in cells:
            reject("coverage_duplicate_simplex", "Duplicate original simplex ID", loc)
        try:
            points = tuple(vertices[name].point for name in cell.vertices)
        except KeyError:
            reject("coverage_vertex_reference", "Unresolved simplex vertex ID", loc)
        try:
            cells[cell.id] = simplex_in_root(graph, root.key.edges, points)
        except VerificationError as error:
            # Keep the reviewed geometric reason and add the reader's context.
            raise VerificationError(
                replace(error.failure, location=loc.to_dict())
            ) from error

    nodes = {node.id: node for node in root.nodes}
    if len(nodes) != len(root.nodes):
        reject("coverage_duplicate_node", "Duplicate tree node ID")
    if root.tree not in nodes:
        reject("coverage_tree_reference", "Unresolved tree root ID")
    parents = {name: 0 for name in nodes}
    for node in root.nodes:
        if isinstance(node, LeafNode):
            if node.simplex not in cells:
                reject(
                    "coverage_simplex_reference",
                    "Unresolved leaf simplex",
                    node.location,
                )
            continue
        if len(node.normal) != len(root.key.edges) or not all(
            isinstance(value, fmpq) or type(value) is int
            for value in (*node.normal, node.offset)
        ):
            reject(
                "coverage_hyperplane",
                "Cut must have exact root coordinates",
                node.location,
            )
        if not any(node.normal):
            reject("coverage_zero_normal", "Cut normal must be nonzero", node.location)
        if node.minus == node.plus:
            reject(
                "coverage_distinct_children",
                "Split needs two distinct children",
                node.location,
            )
        for child in (node.minus, node.plus):
            if child not in nodes:
                reject(
                    "coverage_child_reference", "Unresolved tree child", node.location
                )
            parents[child] += 1
    if parents[root.tree] != 0 or any(
        count != 1 for name, count in parents.items() if name != root.tree
    ):
        reject(
            "coverage_tree_parent", "Root needs no parent; every other node needs one"
        )

    memberships = {root.tree: frozenset(cells)}
    pending = [root.tree]
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            reject("coverage_tree_cycle", "Tree contains a cycle", nodes[name].location)
        visited.add(name)
        node = nodes[name]
        membership = memberships[name]
        if isinstance(node, LeafNode):
            if membership != frozenset({node.simplex}):
                reject(
                    "coverage_leaf_membership",
                    "Leaf must contain exactly its named simplex",
                    node.location,
                )
            continue
        minus, plus = set(), set()
        for cell_id in membership:
            # Always evaluate every ORIGINAL vertex, never a clipped cell.
            matrix = cells[cell_id].vertices
            signs = tuple(
                sum((a * matrix[i, j] for i, a in enumerate(node.normal)), fmpq(0))
                - node.offset
                for j in range(matrix.ncols())
            )
            if all(value <= 0 for value in signs):
                minus.add(cell_id)
            elif all(value >= 0 for value in signs):
                plus.add(cell_id)
            else:
                minus.add(cell_id)
                plus.add(cell_id)
        memberships[node.minus] = frozenset(minus)
        memberships[node.plus] = frozenset(plus)
        pending.extend((node.minus, node.plus))
    if visited != nodes.keys():
        reject("coverage_tree_unreachable", "Every tree node must be reachable")
    # Repeated leaf appearances must never increase the original-cell sum.
    volume = sum((cell.volume() for cell in cells.values()), fmpq(0))
    if volume != 1:
        reject("coverage_volume", "Distinct original simplex volumes must sum to one")
    return RootCoverage(
        root, MappingProxyType(cells), MappingProxyType(memberships), volume
    )
