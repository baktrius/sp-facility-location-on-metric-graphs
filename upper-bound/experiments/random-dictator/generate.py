"""Untrusted Random Dictator certificate producer (stdlib only).

The folded triangulation and decision tree generalize tests/generate_four_cycle.py.
No verifier implementation is imported. Only ordinary complete verification can
certify these files. See README.md for the construction and experiment protocol.
"""

import argparse
import json
import math
import time
from collections import deque
from collections.abc import Sequence
from fractions import Fraction
from itertools import pairwise, permutations, product
from pathlib import Path

HALF = Fraction(1, 2)
type Coordinates = tuple[Fraction, ...]
type CellKey = tuple[tuple[int, ...], tuple[int, ...]]


def cells(dimension: int) -> dict[CellKey, tuple[Coordinates, ...]]:
    """Each half-box is the image of 0<=u[p0]<=...<=u[p_last]<=1/2."""
    result = {}
    for halves in product((0, 1), repeat=dimension):
        for order in permutations(range(dimension)):
            folded = [Fraction(0)] * dimension
            corners = []
            for index in (None, *reversed(order)):
                if index is not None:
                    folded[index] = HALF
                corners.append(
                    tuple(
                        1 - u if high else u
                        for high, u in zip(halves, folded, strict=True)
                    )
                )
            result[halves, order] = tuple(corners)
    return result


def tree(dimension: int, names: dict[CellKey, str]) -> list[dict[str, object]]:
    """Half cuts followed by fold-order cuts; every emitted node is untrusted."""
    nodes: list[dict[str, object]] = []

    def node(keys: Sequence[CellKey], half_axis: int = 0) -> str:
        name = f"n{len(nodes)}"
        row: dict[str, object] = {"id": name}
        nodes.append(row)
        if len(keys) == 1:
            row.update(type="leaf", simplex=names[keys[0]])
            return name
        normal = [0] * dimension
        if half_axis < dimension:
            normal[half_axis] = 1
            offset = "1/2"
            minus = [k for k in keys if k[0][half_axis] == 0]
            plus = [k for k in keys if k[0][half_axis] == 1]
            next_axis = half_axis + 1
        else:
            # All keys now have the same half bits. Pick a pair not yet ordered.
            left, right = next(
                (i, j)
                for i in range(dimension)
                for j in range(i + 1, dimension)
                if len({k[1].index(i) < k[1].index(j) for k in keys}) == 2
            )
            halves = keys[0][0]
            normal[left] = 1 - 2 * halves[left]
            normal[right] = -(1 - 2 * halves[right])
            # u_left-u_right = normal dot t + half_left-half_right.
            offset = str(halves[right] - halves[left])
            minus = [k for k in keys if k[1].index(left) < k[1].index(right)]
            plus = [k for k in keys if k[1].index(left) > k[1].index(right)]
            next_axis = half_axis
        row.update(
            type="split",
            normal=normal,
            offset=offset,
            minus=node(minus, next_axis),
            plus=node(plus, next_axis),
        )
        return name

    assert node(tuple(names)) == "n0"
    return nodes


def preset(name: str) -> dict:
    if name in {"edge", "path2"}:
        count = 2 if name == "edge" else 3
        vertices = [f"v{i}" for i in range(count)]
        edges = list(pairwise(vertices))
    elif name == "star3":
        vertices = ["o", "a", "b", "c"]
        edges = [("o", v) for v in vertices[1:]]
    elif name in {"c4", "c6", "c4_pendant"}:
        count = 6 if name == "c6" else 4
        vertices = [f"c{i}" for i in range(count)]
        edges = [(vertices[i], vertices[(i + 1) % count]) for i in range(count)]
        if name == "c4_pendant":
            vertices.append("p")
            edges.append(("c0", "p"))
    elif name in {"theta", "k2_4", "k3_3"}:
        left, right = (3, 3) if name == "k3_3" else (2, 4 if name == "k2_4" else 3)
        vertices = [f"a{i}" for i in range(left)] + [f"b{i}" for i in range(right)]
        edges = [(f"a{i}", f"b{j}") for i in range(left) for j in range(right)]
    elif name == "cube":
        vertices = [f"v{i}" for i in range(8)]
        edges = [
            (vertices[i], vertices[i ^ (1 << j)])
            for i in range(8)
            for j in range(3)
            if i < (i ^ (1 << j))
        ]
    else:
        raise ValueError(f"Unknown graph preset: {name}")
    return {"vertices": vertices, "edges": edges}


class Graph:
    def __init__(self, data: dict):
        self.vertices = tuple(data["vertices"])
        self.edges = tuple(tuple(e) for e in data["edges"])
        if (
            len(self.vertices) < 2
            or len(set(self.vertices)) != len(self.vertices)
            or any(not isinstance(v, str) or not v for v in self.vertices)
        ):
            raise ValueError("Need distinct nonempty vertex labels")
        adjacency = {v: [] for v in self.vertices}
        seen = set()
        for edge in self.edges:
            if len(edge) != 2 or any(v not in adjacency for v in edge):
                raise ValueError("Malformed edge")
            a, b = edge
            key = frozenset(edge)
            if a == b or key in seen:
                raise ValueError("Need a simple graph")
            seen.add(key)
            adjacency[a].append(b)
            adjacency[b].append(a)
        self.distances = {}
        for start in self.vertices:
            distances = {start: 0}
            queue = deque([start])
            while queue:
                v = queue.popleft()
                for w in adjacency[v]:
                    if w not in distances:
                        distances[w] = distances[v] + 1
                        queue.append(w)
            if len(distances) != len(self.vertices):
                raise ValueError("Graph must be connected")
            self.distances[start] = distances
        parity = self.distances[self.vertices[0]]
        if any(parity[a] % 2 == parity[b] % 2 for a, b in self.edges):
            raise ValueError("Only bipartite unit-edge graphs are supported")
        self._pair_cache = {}
        self._vertex_cache = {}
        self.branching = tuple(v for v in self.vertices if len(adjacency[v]) >= 3)

    def point(self, edge, t):
        if t in (0, 1):
            return {"vertex": self.edges[edge][int(t)]}
        return {"edge": edge, "coordinate": str(t)}

    def profile(self, edges, coordinates):
        return [self.point(e, t) for e, t in zip(edges, coordinates, strict=True)]

    def pair_branch(self, e, f, coordinates):
        if e == f:
            for branch, sign in enumerate((1, -1)):
                if all(sign * (s - t) >= 0 for s, t in coordinates):
                    return branch
        else:
            routes = [
                tuple(
                    (s if a == 0 else 1 - s)
                    + self.distances[self.edges[e][a]][self.edges[f][b]]
                    + (t if b == 0 else 1 - t)
                    for a, b in product((0, 1), repeat=2)
                )
                for s, t in coordinates
            ]
            for branch in range(4):
                if all(row[branch] == min(row) for row in routes):
                    return branch
        raise ValueError("Distance branch changes inside a proposed cell")

    def branch(self, edges, corners, i, j):
        coordinates = tuple(sorted({(v[i], v[j]) for v in corners}))
        key = (edges[i], edges[j], coordinates)
        if key not in self._pair_cache:
            self._pair_cache[key] = self.pair_branch(*key)
        return self._pair_cache[key]

    def vertex_branch(self, edge, vertex, coordinates):
        key = (edge, vertex, coordinates)
        if key in self._vertex_cache:
            return self._vertex_cache[key]
        routes = [
            (
                t + self.distances[self.edges[edge][0]][vertex],
                1 - t + self.distances[self.edges[edge][1]][vertex],
            )
            for t in coordinates
        ]
        for branch in (0, 1):
            if all(row[branch] == min(row) for row in routes):
                self._vertex_cache[key] = branch
                return branch
        raise ValueError("Vertex distance branch changes inside a proposed cell")


def estimate(graph: Graph, agents: int) -> dict:
    m = len(graph.edges)
    b = len(graph.branching)
    sizes = {d: 2**d * math.factorial(d) for d in (agents, agents + 1)}
    roots = {
        "attribution": m**agents,
        "sp": agents * m ** (agents + 1),
        "approximation": (agents + b) * m**agents,
    }
    counts = {
        key: value * sizes[agents + (key == "sp")] for key, value in roots.items()
    }
    return {
        "agents": agents,
        "vertices": len(graph.vertices),
        "edges": m,
        "branching_vertices": b,
        "certified_value": str(Fraction(2 * agents - 2, agents)),
        "roots": roots,
        "simplices": counts,
        "global_vertices": (len(graph.vertices) + m) ** agents,
    }


def generate(directory: Path, graph: Graph, agents: int, alpha=None) -> dict:
    if agents < 2:
        raise ValueError("Need at least two agents")
    # Refuse to clobber an existing bundle or a partially generated experiment.
    directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    factor = Fraction(2 * agents - 2, agents) if alpha is None else Fraction(alpha)
    manifest = {
        "schema_version": 1,
        "identity": {
            "formulation": "metric_graph_upper",
            "result": "unconditional",
            "graph": {"vertices": graph.vertices, "edges": graph.edges},
            "agents": agents,
            "selectors": [{"kind": "peak", "agent": i} for i in range(agents)],
        },
        "certified_value": str(factor),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    meshes = {d: cells(d) for d in (agents, agents + 1)}
    names = {
        d: {key: f"C{i}" for i, key in enumerate(mesh)} for d, mesh in meshes.items()
    }
    trees = {d: tree(d, names[d]) for d in meshes}
    regions = {}
    global_ids = {}

    def emit(stream, row):
        stream.write(json.dumps(row, separators=(",", ":")) + "\n")

    with (
        (directory / "vertices.jsonl").open("w") as vertices_file,
        (directory / "attribution.jsonl").open("w") as stream,
    ):
        for edges in product(range(len(graph.edges)), repeat=agents):
            emit(stream, {"type": "root", "key": {"edges": edges}, "tree": "n0"})
            local_names = {}
            for key, corners in meshes[agents].items():
                name = f"T{len(regions)}"
                regions[edges, key] = name
                local_names[key] = name
                ids = []
                for corner in corners:
                    value = graph.profile(edges, corner)
                    token = json.dumps(value, separators=(",", ":"))
                    if token not in global_ids:
                        identifier = f"v{len(global_ids)}"
                        global_ids[token] = identifier
                        emit(vertices_file, {"id": identifier, "point": value})
                    ids.append(global_ids[token])
                emit(
                    stream,
                    {
                        "type": "simplex",
                        "id": name,
                        "vertices": ids,
                        "weights": [[str(Fraction(1, agents))] * agents] * (agents + 1),
                    },
                )
            # Reuse the tree structure, substituting globally unique region IDs.
            translation = {names[agents][k]: v for k, v in local_names.items()}
            for row in trees[agents]:
                emit(
                    stream,
                    {**row, "simplex": translation[str(row["simplex"])]}
                    if row["type"] == "leaf"
                    else row,
                )
            emit(stream, {"type": "end"})

    def region(edges, key, axes):
        halves, order = key
        projected = (
            tuple(halves[a] for a in axes),
            tuple(axes.index(a) for a in order if a in axes),
        )
        return regions[tuple(edges[a] for a in axes), projected]

    candidates = [{"kind": "report", "agent": i} for i in range(agents)]
    candidates += [{"kind": "vertex", "vertex": v} for v in graph.branching]
    for filename, dimension in (
        ("sp.jsonl", agents + 1),
        ("approximation.jsonl", agents),
    ):
        mesh = meshes[dimension]
        is_sp = filename == "sp.jsonl"
        with (directory / filename).open("w") as stream:
            for comparison in range(agents) if is_sp else candidates:
                for edges in product(range(len(graph.edges)), repeat=dimension):
                    root_key = {
                        "edges": edges,
                        "agent" if is_sp else "candidate": comparison,
                    }
                    emit(stream, {"type": "root", "key": root_key, "tree": "n0"})
                    local_ids = {}
                    for coordinates in product(
                        (Fraction(0), HALF, Fraction(1)), repeat=dimension
                    ):
                        identifier = f"w{len(local_ids)}"
                        local_ids[coordinates] = identifier
                        emit(
                            stream,
                            {
                                "type": "vertex",
                                "id": identifier,
                                "point": graph.profile(edges, coordinates),
                            },
                        )
                    for key, corners in mesh.items():
                        cell = {
                            "type": "simplex",
                            "id": names[dimension][key],
                            "vertices": [local_ids[v] for v in corners],
                            "truthful": region(edges, key, tuple(range(agents))),
                        }
                        if is_sp:
                            assert isinstance(comparison, int)
                            axes = tuple(
                                agents if a == comparison else a for a in range(agents)
                            )
                            cell["deviated"] = region(edges, key, axes)
                            terms = [(comparison, j) for j in range(agents)] + [
                                (comparison, j) for j in axes
                            ]
                            branches = [
                                graph.branch(edges, corners, i, j) for i, j in terms
                            ]
                        else:
                            assert isinstance(comparison, dict)
                            branches = [
                                graph.branch(edges, corners, i, j)
                                for i in range(agents)
                                for j in range(agents)
                            ]
                            if comparison["kind"] == "report":
                                branches += [
                                    graph.branch(edges, corners, i, comparison["agent"])
                                    for i in range(agents)
                                ]
                            else:
                                branches += [
                                    graph.vertex_branch(
                                        edges[i],
                                        comparison["vertex"],
                                        tuple(sorted({v[i] for v in corners})),
                                    )
                                    for i in range(agents)
                                ]
                        cell["branches"] = branches
                        emit(stream, cell)
                    for row in trees[dimension]:
                        emit(stream, row)
                    emit(stream, {"type": "end"})
    result = estimate(graph, agents)
    result["certified_value"] = str(factor)
    result["generation_wall_s"] = time.perf_counter() - started
    result["files"] = {p.name: p.stat().st_size for p in sorted(directory.iterdir())}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--graph", help="edge,path2,star3,c4,c6,c4_pendant,theta,k2_4,k3_3,cube"
    )
    group.add_argument(
        "--graph-json",
        type=Path,
        help="Graph object, or lower/upper certificate with identity.graph",
    )
    parser.add_argument("--agents", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument(
        "--alpha", help="Override factor for a negative-control experiment"
    )
    args = parser.parse_args()
    if args.agents < 2:
        parser.error("--agents must be at least 2")
    if args.graph_json:
        data = json.loads(args.graph_json.read_text())
        data = data.get("identity", data)
        data = data.get("graph", data)
        # Symmetry declarations are irrelevant to the explicit upper mesh.
        if set(data) - {"vertices", "edges", "symmetries"}:
            parser.error("Graph JSON has unsupported fields")
    else:
        data = preset(args.graph)
    graph = Graph(data)
    if args.estimate:
        result = estimate(graph, args.agents)
    else:
        if args.output is None:
            parser.error("--output is required unless --estimate is used")
        result = generate(args.output, graph, args.agents, args.alpha)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
