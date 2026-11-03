"""Untrusted stdlib-only producer of two complete negative segment bundles.

Reuse the stored dictator's checked geometry, then supply explicit original
weights and derive every ordered segment branch from the cell vertices.
The ordinary verifier never executes this producer.
"""

import json
from fractions import Fraction
from pathlib import Path

DATA_FILES = (
    "manifest.json",
    "vertices.jsonl",
    "attribution.jsonl",
    "sp.jsonl",
    "approximation.jsonl",
)
SOURCE = Path(__file__).parent / "fixtures" / "single-edge-dictator"


def coordinate(point):
    return (
        Fraction(point["vertex"] == "b")
        if "vertex" in point
        else Fraction(point["coordinate"])
    )


def read_rows(directory, name):
    return [json.loads(line) for line in (directory / name).read_text().splitlines()]


def write_rows(directory, name, rows):
    (directory / name).write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    )


def generate(directory: Path, *, constant: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    manifest["identity"]["selectors"] = [
        {"kind": "peak", "agent": 0},
        {"kind": "peak", "agent": 1},
        {"kind": "constant", "point": {"vertex": "a"}},
    ]
    manifest["certified_value"] = 1
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    vertices = read_rows(SOURCE, "vertices.jsonl")
    write_rows(directory, "vertices.jsonl", vertices)
    global_points = {row["id"]: row["point"] for row in vertices}
    rows = read_rows(SOURCE, "attribution.jsonl")
    for row in rows:
        if row["type"] == "simplex":
            row["weights"] = [
                ["0", "0", "1"]
                if constant
                else [
                    str(coordinate(global_points[v][0])),
                    str(1 - coordinate(global_points[v][0])),
                    "0",
                ]
                for v in row["vertices"]
            ]
    write_rows(directory, "attribution.jsonl", rows)
    for name in ("sp.jsonl", "approximation.jsonl"):
        rows = read_rows(SOURCE, name)
        local = {}
        key = None
        for row in rows:
            if row["type"] == "root":
                local, key = {}, row["key"]
            elif row["type"] == "vertex":
                local[row["id"]] = tuple(map(coordinate, row["point"]))
            elif row["type"] == "simplex":
                assert key is not None
                points = [local[v] for v in row["vertices"]]

                def branch(left, right, points=points):
                    if all(p[left] >= p[right] for p in points):
                        return 0
                    assert all(p[left] <= p[right] for p in points)
                    return 1

                if name == "sp.jsonl":
                    agent = key["agent"]
                    row["branches"] = [branch(agent, 0), branch(agent, 1), 0]
                    row["branches"] += [
                        branch(agent, 2 if agent == j else j) for j in (0, 1)
                    ] + [0]
                else:
                    candidate = key["candidate"]["agent"]
                    row["branches"] = [
                        b for i in (0, 1) for b in (branch(i, 0), branch(i, 1), 0)
                    ] + [branch(i, candidate) for i in (0, 1)]
        write_rows(directory, name, rows)


if __name__ == "__main__":
    base = Path(__file__).parent / "fixtures"
    generate(base / "single-edge-non-sp", constant=False)
    generate(base / "single-edge-false-factor", constant=True)
