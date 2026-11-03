"""Exact metric equivalence for accepted unit graphs; no producer sidecars are read."""

import math
import time
from collections import Counter
from functools import reduce


class Unpaired(ValueError):
    """Matching is unsupported or exceeded its bounded work allowance."""


def normalize(graph: dict) -> dict:
    vertices, edges = graph["vertices"], graph["edges"]
    if not isinstance(vertices, list) or len(vertices) < 2 or len(vertices) > 100_000:
        raise Unpaired("unsupported vertex count")
    if not all(isinstance(v, str) for v in vertices) or len(set(vertices)) != len(
        vertices
    ):
        raise Unpaired("invalid vertex labels")
    adj = {v: set() for v in vertices}
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2:
            raise Unpaired("invalid edge")
        a, b = edge
        if a not in adj or b not in adj or a == b or b in adj[a]:
            raise Unpaired("not a simple graph")
        adj[a].add(b)
        adj[b].add(a)
    colors = {vertices[0]: 0}
    pending = [vertices[0]]
    while pending:
        v = pending.pop()
        for w in adj[v]:
            if w not in colors:
                colors[w] = 1 - colors[v]
                pending.append(w)
            elif colors[w] == colors[v]:
                raise Unpaired("not bipartite")
    if len(colors) != len(vertices):
        raise Unpaired("not connected")
    anchors = [v for v in vertices if len(adj[v]) != 2]
    if not anchors:
        return {
            "vertices": 1,
            "paths": [[0, 0, 1]],
            "scale": len(edges),
            "cyclic": True,
            "witness": "connected degree-two graph: circle",
        }
    visited = set()
    paths, witness = [], []
    indices = {v: i for i, v in enumerate(anchors)}
    for start in anchors:
        for neighbor in sorted(adj[start]):
            if frozenset((start, neighbor)) in visited:
                continue
            trail = [start, neighbor]
            visited.add(frozenset((start, neighbor)))
            previous, current = start, neighbor
            while current not in indices:
                nxt = next(v for v in adj[current] if v != previous)
                if frozenset((current, nxt)) in visited:
                    raise Unpaired("path repeats an edge")
                visited.add(frozenset((current, nxt)))
                trail.append(nxt)
                previous, current = current, nxt
            a, b = sorted((indices[start], indices[current]))
            paths.append([a, b, len(trail) - 1])
            witness.append(trail)
    if len(visited) != len(edges):
        raise Unpaired("suppression did not cover every edge")
    scale = reduce(math.gcd, (p[2] for p in paths))
    return {
        "vertices": len(anchors),
        "paths": sorted([[a, b, length // scale] for a, b, length in paths]),
        "scale": scale,
        "cyclic": len(edges) >= len(vertices),
        "witness": {"anchors": anchors, "paths": witness},
    }


def correspondence(
    source: dict, target: dict, *, max_states: int = 100_000, seconds: float = 2.0
) -> dict | None:
    """Return and independently check a length/incidence preserving vertex bijection."""
    start = time.monotonic()
    n = source["vertices"]
    if n > 500:
        raise Unpaired("exact correspondence supports at most 500 junctions/leaves")
    if n != target["vertices"] or len(source["paths"]) != len(target["paths"]):
        return None

    def pairs(rep):
        result = {}
        for a, b, length in rep["paths"]:
            result.setdefault((min(a, b), max(a, b)), []).append(length)
        return {key: tuple(sorted(lengths)) for key, lengths in result.items()}

    left, right = pairs(source), pairs(target)

    def signatures(rep):
        out = [[] for _ in range(n)]
        for a, b, length in rep["paths"]:
            out[a].append((a == b, length))
            out[b].append((a == b, length))
        return [tuple(sorted(x)) for x in out]

    sl, sr = signatures(source), signatures(target)
    if Counter(sl) != Counter(sr):
        return None
    candidates = {a: [b for b in range(n) if sl[a] == sr[b]] for a in range(n)}
    order = sorted(range(n), key=lambda a: (len(candidates[a]), -len(sl[a])))
    mapping, used = {}, set()
    states = 0

    def search(depth):
        nonlocal states
        states += 1
        if states > max_states or time.monotonic() - start > seconds or depth > 500:
            raise Unpaired("exact correspondence resource limit")
        if depth == n:
            return True
        a = order[depth]
        for b in candidates[a]:
            if b in used or left.get((a, a), ()) != right.get((b, b), ()):
                continue
            if any(
                left.get(tuple(sorted((a, c))), ())
                != right.get(tuple(sorted((b, d))), ())
                for c, d in mapping.items()
            ):
                continue
            mapping[a] = b
            used.add(b)
            if search(depth + 1):
                return True
            used.remove(b)
            del mapping[a]
        return False

    if not search(0):
        return None
    mapped = Counter(
        (min(mapping[a], mapping[b]), max(mapping[a], mapping[b]), length)
        for a, b, length in source["paths"]
    )
    expected = Counter(tuple(path) for path in target["paths"])
    if set(mapping.values()) != set(range(n)) or mapped != expected:
        raise Unpaired("correspondence witness failed independent check")
    return {
        "vertices": mapping,
        "source_scale": source["scale"],
        "target_scale": target["scale"],
        "checked": "bijection and all normalized path incidences/length multiplicities",
    }
