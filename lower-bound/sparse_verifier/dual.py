"""The dual checks: rows, signs, columns, untouched columns and the objective.

Invariant: `check_dual` returns `None` only when every multiplier names a row of
the program, every inequality multiplier has the sign weak duality needs, every
column's dual constraint holds exactly, and the dual objective equals the
claimed bound. Otherwise it returns the first check that failed, in this order,
with how many failures that check found.

The program minimises `1 + t` over nonnegative columns, and its inequality rows
are `<=`, so a feasible dual has nonpositive multipliers on them and free ones
on equalities, and each column's sum of coefficient times multiplier over the
rows must not exceed the column's objective coefficient: 1 for `t`, 0 for a
probability column.

A row the certificate does not name has multiplier zero, so a column no named
row touches sums to zero. That holds against a probability column's cost of 0
and against `t`'s cost of 1, since 0 is at most either and every column is
nonnegative; this is the untouched-column condition, and it is the only reason
the columns the active rows miss need no visit. `t` is summed explicitly, over
every welfare row, even when none is active.

Touched columns are gathered one profile block at a time: for a block, only the
named rows that touch it are generated, one at a time, and only that block's
columns are kept. Memory follows the largest block, not the certificate. What
is kept for the whole certificate is one small record per named row.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

from sparse_verifier.program import (
    AT_MOST,
    SLACK_COLUMN,
    NonexistentRowError,
    column_block,
    generate_row,
)

if TYPE_CHECKING:
    from sparse_verifier.graph import Graph

ROWS = "rows"
SIGN = "sign"
COLUMN = "column"
OBJECTIVE = "objective"

OBJECTIVE_CONSTANT = Fraction(1)
"""The objective is `1 + t`, so the all-zero dual establishes 1."""

_SLACK_COST = Fraction(1)


@dataclass(frozen=True)
class Failure:
    """The first failure of the first check that failed.

    Attributes:
        check (str): The check's name.
        reason (str): What was wrong, for the first failure.
        count (int): How many failures that check found.

    """

    check: str
    reason: str
    count: int = 1


@dataclass
class _Scan:
    """What one pass over the named rows keeps, small per row.

    `touching` lists, per block, the names of the named rows with a column in
    it: references to names the certificate already holds, never coefficients.
    """

    touching: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    missing: list[str] = field(default_factory=list)
    wrong_signs: list[str] = field(default_factory=list)
    rhs_total: Fraction = Fraction(0)


def check_dual(
    graph: Graph, agents: int, multipliers: dict[str, Fraction], bound: Fraction
) -> Failure | None:
    """Check a certificate's multipliers against the program they name.

    Args:
        graph (Graph): The validated explicit graph.
        agents (int): The number of agents.
        multipliers (dict[str, Fraction]): The nonzero multipliers by row name.
        bound (Fraction): The claimed certified value.

    Returns:
        Failure | None: The first failing check, or None when all hold.

    """
    scan = _scan(graph, agents, multipliers)
    if scan.missing:
        return Failure(ROWS, scan.missing[0], len(scan.missing))
    if scan.wrong_signs:
        return Failure(SIGN, scan.wrong_signs[0], len(scan.wrong_signs))
    exceeded = _column_failures(graph, agents, multipliers, scan.touching)
    if exceeded:
        return Failure(COLUMN, exceeded[0], len(exceeded))
    value = OBJECTIVE_CONSTANT + scan.rhs_total
    if value != bound:
        return Failure(
            OBJECTIVE, f"the multipliers establish {value}, not the claimed {bound}"
        )
    return None


def _scan(graph: Graph, agents: int, multipliers: dict[str, Fraction]) -> _Scan:
    scan = _Scan()
    for name, multiplier in multipliers.items():
        try:
            row = generate_row(graph, agents, name)
        except NonexistentRowError as error:
            scan.missing.append(str(error))
            continue
        if row.sense == AT_MOST and multiplier > 0:
            scan.wrong_signs.append(
                f"row {name} is an inequality with the positive multiplier {multiplier}"
            )
        scan.rhs_total += multiplier * row.rhs
        blocks = {
            block
            for column in row.coefficients
            if (block := column_block(column)) is not None
        }
        for block in blocks:
            scan.touching[block].append(name)
    return scan


def _column_failures(
    graph: Graph,
    agents: int,
    multipliers: dict[str, Fraction],
    touching: dict[int, list[str]],
) -> list[str]:
    failures: list[str] = []
    slack = Fraction(0)
    for block in sorted(touching):
        totals: dict[str, Fraction] = defaultdict(Fraction)
        for name in touching[block]:
            row = generate_row(graph, agents, name)
            for column, coefficient in row.coefficients.items():
                if column == SLACK_COLUMN:
                    slack += multipliers[name] * coefficient
                elif column_block(column) == block:
                    totals[column] += multipliers[name] * coefficient
        failures.extend(
            f"column {column} sums to {total}, exceeding its objective "
            f"coefficient 0 by {total}"
            for column, total in totals.items()
            if total > 0
        )
    if slack > _SLACK_COST:
        failures.append(
            f"column {SLACK_COLUMN} sums to {slack}, exceeding its objective "
            f"coefficient {_SLACK_COST} by {slack - _SLACK_COST}"
        )
    return failures
