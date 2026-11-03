"""Untrusted deterministic producer for this one C4, n=2, peak0 fixture.

Only stdlib construction code lives here; no verifier geometry or acceptance
routine is imported. The stored output is checked by the ordinary verifier.
"""

import json
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import permutations, product
from pathlib import Path

VERTICES = ("c0", "c1", "c2", "c3")
EDGES = ((0, 1), (1, 2), (2, 3), (3, 0))
HALF = Fraction(1, 2)
type Coordinates = tuple[Fraction, ...]
type CellKey = tuple[tuple[int, ...], tuple[int, ...]]


def point(edge: int, coordinate: Fraction) -> dict[str, object]:
    """Canonical endpoints identify one point across oppositely oriented charts."""
    if coordinate in (0, 1):
        return {"vertex": VERTICES[EDGES[edge][int(coordinate)]]}
    return {"edge": edge, "coordinate": str(coordinate)}


def profile(
    edges: tuple[int, ...], coordinates: Coordinates
) -> list[dict[str, object]]:
    return [point(e, t) for e, t in zip(edges, coordinates, strict=True)]


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


def branch(
    edges: tuple[int, ...], corners: tuple[Coordinates, ...], i: int, j: int
) -> int:
    """Choose the first route valid at every vertex, preserving ordered operands.

    C4 endpoint distances are computed here independently, not read from the
    trusted checker. Validity on the closed cell is rechecked by that checker.
    """
    if edges[i] == edges[j]:
        for sign in (1, -1):
            if all(sign * (v[i] - v[j]) >= 0 for v in corners):
                return int(sign == -1)
        raise ValueError("Same-edge branch changes inside the proposed cell")

    def routes(v: Coordinates) -> tuple[Fraction, ...]:
        values = []
        for a, b in product((0, 1), repeat=2):
            difference = abs(EDGES[edges[i]][a] - EDGES[edges[j]][b])
            distance = min(difference, 4 - difference)
            values.append(
                (v[i] if a == 0 else 1 - v[i])
                + distance
                + (v[j] if b == 0 else 1 - v[j])
            )
        return tuple(values)

    vertex_routes = tuple(routes(v) for v in corners)
    for selected in range(4):
        if all(values[selected] == min(values) for values in vertex_routes):
            return selected
    raise ValueError("Endpoint-route branch changes inside the proposed cell")


def write_lines(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def generate(directory: Path) -> None:
    """Write all five files. No certificates are accepted or blessed here."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "identity": {
            "formulation": "metric_graph_upper",
            "result": "unconditional",
            "graph": {
                "vertices": VERTICES,
                "edges": [(VERTICES[a], VERTICES[b]) for a, b in EDGES],
            },
            "agents": 2,
            "selectors": [{"kind": "peak", "agent": 0}],
        },
        "certified_value": "1",
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    mesh2, mesh3 = cells(2), cells(3)
    global_rows = []
    global_ids: dict[str, str] = {}
    attribution = []
    regions: dict[tuple[tuple[int, ...], CellKey], str] = {}
    for edges in product(range(4), repeat=2):
        names = {}
        attribution.append({"type": "root", "key": {"edges": edges}, "tree": "n0"})
        for key, corners in mesh2.items():
            name = f"T{len(regions)}"
            regions[edges, key] = name
            names[key] = name
            ids = []
            for corner in corners:
                value = profile(edges, corner)
                token = json.dumps(value, separators=(",", ":"))
                if token not in global_ids:
                    identifier = f"v{len(global_ids)}"
                    global_ids[token] = identifier
                    global_rows.append({"id": identifier, "point": value})
                ids.append(global_ids[token])
            attribution.append(
                {"type": "simplex", "id": name, "vertices": ids, "weights": [["1"]] * 3}
            )
        attribution.extend(tree(2, names))
        attribution.append({"type": "end"})
    write_lines(directory / "vertices.jsonl", global_rows)
    write_lines(directory / "attribution.jsonl", attribution)

    def region(edges: tuple[int, ...], key: CellKey, axes: tuple[int, int]) -> str:
        halves, order = key
        projected = (
            tuple(halves[a] for a in axes),
            tuple(axes.index(a) for a in order if a in axes),
        )
        return regions[tuple(edges[a] for a in axes), projected]

    for filename, dimension in (("sp.jsonl", 3), ("approximation.jsonl", 2)):
        rows = []
        mesh = mesh3 if dimension == 3 else mesh2
        for comparison in range(2):
            for edges in product(range(4), repeat=dimension):
                root_key: dict[str, object] = {"edges": edges}
                if dimension == 3:
                    root_key["agent"] = comparison
                else:
                    root_key["candidate"] = {"kind": "report", "agent": comparison}
                rows.append({"type": "root", "key": root_key, "tree": "n0"})
                local_ids = {}
                for coordinates in product(
                    (Fraction(0), HALF, Fraction(1)), repeat=dimension
                ):
                    identifier = f"w{len(local_ids)}"
                    local_ids[coordinates] = identifier
                    rows.append(
                        {
                            "type": "vertex",
                            "id": identifier,
                            "point": profile(edges, coordinates),
                        }
                    )
                names = {}
                for key, corners in mesh.items():
                    name = f"C{len(names)}"
                    names[key] = name
                    cell: dict[str, object] = {
                        "type": "simplex",
                        "id": name,
                        "vertices": [local_ids[v] for v in corners],
                        "truthful": region(edges, key, (0, 1)),
                    }
                    if dimension == 3:
                        axes = (2, 1) if comparison == 0 else (0, 2)
                        cell["deviated"] = region(edges, key, axes)
                        terms = (
                            (comparison, 0),
                            (comparison, 2 if comparison == 0 else 0),
                        )
                    else:
                        terms = ((0, 0), (1, 0), (0, comparison), (1, comparison))
                    cell["branches"] = [branch(edges, corners, i, j) for i, j in terms]
                    rows.append(cell)
                rows.extend(tree(dimension, names))
                rows.append({"type": "end"})
        write_lines(directory / filename, rows)


if __name__ == "__main__":
    generate(
        Path(sys.argv[1])
        if len(sys.argv) == 2
        else Path("tests/fixtures/four-cycle-dictator")
    )
