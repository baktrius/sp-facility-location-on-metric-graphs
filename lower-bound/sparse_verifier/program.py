"""The program the verifier defines, one row at a time.

Invariant: `generate_row` returns exactly the row of the unreduced anonymous
program over an explicit graph (subdivision factor 1, vertices in document
order) that carries the requested name, or raises `NonexistentRowError` when
the program has no such row. Profiles are the sorted multisets of `k` vertex
indices, numbered by block in lexicographic order; a block number is mapped to
its profile and back by unranking and ranking, so the cost of a row follows the
row and never the number of profiles. Hop distances come from a breadth-first
search over the explicit graph, run only from the vertices a row needs.

The program, in hop units, with `D` the hop distance and `o_P` the optimal
social cost of profile `P`:

    normalization_<P>:  sum_v p[P, v] == 1
    welfare_<P>:        sum_v (sum_a D(a, v)) p[P, v] - o_P t <= o_P
    incentive_<P>_<a>_<b>, for `a` occupied in `P` and `b != a`:
                        sum_v D(a, v) p[P, v] - sum_v D(a, v) p[Q, v] <= 0,
                        `Q` being `P` with one copy of `a` replaced by `b`

Columns are `t` and `p_<block>_<vertex>`; a coefficient that is zero is omitted.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from math import comb
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sparse_verifier.graph import Graph

AT_MOST = "<="
EQUAL = "=="

SLACK_COLUMN = "t"
MIN_AGENTS = 2

_NORMALIZATION = re.compile(r"normalization_([0-9]+)")
_WELFARE = re.compile(r"welfare_([0-9]+)")
_INCENTIVE = re.compile(r"incentive_([0-9]+)_([0-9]+)_([0-9]+)")


class NonexistentRowError(ValueError):
    """The name is not a row of the program."""


@dataclass(frozen=True)
class Row:
    """One generated row.

    Attributes:
        sense (str): `"<="` or `"=="`.
        coefficients (dict[str, int]): Nonzero coefficient by column name.
        rhs (int): The right-hand side.

    """

    sense: str
    coefficients: dict[str, int]
    rhs: int


def column_name(block: int, vertex: int) -> str:
    """Return the name of the probability column of a block at a vertex."""
    return f"p_{block}_{vertex}"


def column_block(column: str) -> int | None:
    """Return the block of a probability column, or None for `t`."""
    if column == SLACK_COLUMN:
        return None
    return int(column.split("_")[1])


def generate_row(graph: Graph, agents: int, name: str) -> Row:
    """Generate one row of the unreduced anonymous program.

    Args:
        graph (Graph): The explicit graph, vertices in document order.
        agents (int): The number of agents.
        name (str): `normalization_<block>`, `welfare_<block>` or
            `incentive_<block>_<true type>_<report>`.

    Returns:
        Row: The row's sense, coefficients by column name and right-hand side.

    Raises:
        ValueError: If there are fewer than `MIN_AGENTS` agents.
        NonexistentRowError: If the program has no row of that name.

    """
    if agents < MIN_AGENTS:
        msg = f"there must be at least {MIN_AGENTS} agents, got {agents}"
        raise ValueError(msg)
    vertices = len(graph.labels)
    if match := _NORMALIZATION.fullmatch(name):
        block = _block(match.group(1), name, vertices, agents)
        return _normalization(vertices, block)
    if match := _WELFARE.fullmatch(name):
        block = _block(match.group(1), name, vertices, agents)
        return _welfare(graph, _unrank(block, vertices, agents), block)
    if match := _INCENTIVE.fullmatch(name):
        block = _block(match.group(1), name, vertices, agents)
        true_type = _canonical(match.group(2), name)
        report = _canonical(match.group(3), name)
        return _incentive(graph, agents, block, true_type, report)
    msg = f"{name!r} is not a row name"
    raise NonexistentRowError(msg)


def _canonical(digits: str, name: str) -> int:
    """Read a number written once and only one way, so a row has one name."""
    if digits != str(int(digits)):
        msg = f"{name!r} writes a number with leading zeros"
        raise NonexistentRowError(msg)
    return int(digits)


def _block(digits: str, name: str, vertices: int, agents: int) -> int:
    block = _canonical(digits, name)
    if block >= _profile_count(vertices, agents):
        msg = f"{name!r} names a block beyond the program's profiles"
        raise NonexistentRowError(msg)
    return block


def _profile_count(vertices: int, agents: int) -> int:
    return comb(vertices + agents - 1, agents)


def _multisets(vertices: int, first: int, size: int) -> int:
    """Count the sorted tuples of `size` indices drawn from `first` upward."""
    return comb(vertices - first + size - 1, size)


def _unrank(block: int, vertices: int, agents: int) -> tuple[int, ...]:
    """Return the profile numbered `block`, in lexicographic order."""
    profile: list[int] = []
    previous = 0
    for position in range(agents):
        remaining = agents - position - 1
        vertex = previous
        while block >= (skipped := _multisets(vertices, vertex, remaining)):
            block -= skipped
            vertex += 1
        profile.append(vertex)
        previous = vertex
    return tuple(profile)


def _rank(profile: tuple[int, ...], vertices: int) -> int:
    """Return the block number of a sorted profile."""
    block = 0
    previous = 0
    for position, vertex in enumerate(profile):
        remaining = len(profile) - position - 1
        block += sum(
            _multisets(vertices, skipped, remaining)
            for skipped in range(previous, vertex)
        )
        previous = vertex
    return block


def _hops(graph: Graph, source: int) -> list[int]:
    """Breadth-first hop distances from one vertex; the graph is connected."""
    neighbours: list[list[int]] = [[] for _ in graph.labels]
    for u, v in graph.edges:
        neighbours[u].append(v)
        neighbours[v].append(u)
    hops = [-1] * len(graph.labels)
    hops[source] = 0
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v in neighbours[u]:
            if hops[v] < 0:
                hops[v] = hops[u] + 1
                queue.append(v)
    return hops


def _normalization(vertices: int, block: int) -> Row:
    return Row(
        sense=EQUAL,
        coefficients={column_name(block, vertex): 1 for vertex in range(vertices)},
        rhs=1,
    )


def _welfare(graph: Graph, profile: tuple[int, ...], block: int) -> Row:
    costs = [0] * len(graph.labels)
    for report in profile:
        for vertex, hops in enumerate(_hops(graph, report)):
            costs[vertex] += hops
    optimum = min(costs)
    coefficients = {
        column_name(block, vertex): cost
        for vertex, cost in enumerate(costs)
        if cost != 0
    }
    if optimum != 0:
        coefficients[SLACK_COLUMN] = -optimum
    return Row(sense=AT_MOST, coefficients=coefficients, rhs=optimum)


def _incentive(
    graph: Graph, agents: int, block: int, true_type: int, report: int
) -> Row:
    vertices = len(graph.labels)
    profile = _unrank(block, vertices, agents)
    if true_type not in profile:
        msg = f"vertex {true_type} is not in profile {block}"
        raise NonexistentRowError(msg)
    if report >= vertices or report == true_type:
        msg = f"report {report} is not another vertex than {true_type}"
        raise NonexistentRowError(msg)
    remaining = list(profile)
    remaining.remove(true_type)
    deviated = _rank(tuple(sorted([*remaining, report])), vertices)
    coefficients: dict[str, int] = {}
    for vertex, hops in enumerate(_hops(graph, true_type)):
        coefficients[column_name(block, vertex)] = hops
        deviated_column = column_name(deviated, vertex)
        coefficients[deviated_column] = coefficients.get(deviated_column, 0) - hops
    return Row(
        sense=AT_MOST,
        coefficients={c: v for c, v in coefficients.items() if v != 0},
        rhs=0,
    )
