"""A certificate document, read and confined to the scope this verifier takes.

Invariant: a `Certificate` names the graph formulation, an unconditional
result, the full support regime, subdivision factor 1, at least `MIN_AGENTS`
agents and a graph document that declares no symmetries. Its bound and every
multiplier are exact `Fraction`s; no float ever enters. `model_hash` is never
read, so a certificate with, without or with a wrong one reads the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TypeGuard

from sparse_verifier.errors import MalformedError, OutOfScopeError
from sparse_verifier.graph import SYMMETRIES

MIN_AGENTS = 2
"""The fewest agents the program builders accept."""

_FORMULATION = "graph"
_UNCONDITIONAL = "unconditional"
_FULL_SUPPORT = "full"


@dataclass(frozen=True)
class Certificate:
    """What the verifier reads of a certificate.

    Attributes:
        graph (object): The embedded graph document, not yet validated.
        agents (int): The number of agents.
        bound (Fraction): The claimed certified value.
        multipliers (dict[str, Fraction]): The nonzero multipliers by row name.

    """

    graph: object
    agents: int
    bound: Fraction
    multipliers: dict[str, Fraction]


def read_certificate(document: object) -> Certificate:
    """Read a decoded certificate and confirm it is in scope.

    Args:
        document (object): The decoded JSON.

    Returns:
        Certificate: The certificate.

    Raises:
        MalformedError: If the document is not shaped like a certificate.
        OutOfScopeError: If it is one this verifier does not take.

    """
    root = _mapping(document, "the certificate")
    identity = _mapping(_get(root, "identity"), "the identity")
    _check_scope(identity)
    graph = _get(identity, "graph")
    if isinstance(graph, dict) and graph.get(SYMMETRIES):
        msg = (
            "the graph declares symmetries, so the certificate is reduced; "
            "lift it to an unreduced certificate first"
        )
        raise OutOfScopeError(msg)
    agents = _get(identity, "agents")
    if not _is_int(agents):
        msg = "the agent count is not an integer"
        raise MalformedError(msg)
    if agents < MIN_AGENTS:
        msg = f"{agents} agents is below the minimum of {MIN_AGENTS}"
        raise OutOfScopeError(msg)
    return Certificate(
        graph=graph,
        agents=agents,
        bound=_fraction(_get(root, "certified_value"), "the certified value"),
        multipliers=_multipliers(_get(root, "multipliers")),
    )


def _check_scope(identity: dict[str, object]) -> None:
    formulation = _get(identity, "formulation")
    if formulation != _FORMULATION:
        msg = f"the formulation {formulation!r} is not {_FORMULATION!r}"
        raise OutOfScopeError(msg)
    result = _get(identity, "result")
    if result != _UNCONDITIONAL:
        msg = (
            f"a {result!r} result is not a bound; only unconditional results are taken"
        )
        raise OutOfScopeError(msg)
    support = _get(identity, "support")
    if support != _FULL_SUPPORT:
        msg = f"the support regime {support!r} is not {_FULL_SUPPORT!r}"
        raise OutOfScopeError(msg)
    subdivision = _get(identity, "subdivision")
    if not _is_int(subdivision):
        msg = "the subdivision factor is not an integer"
        raise MalformedError(msg)
    if subdivision != 1:
        msg = (
            f"subdivision factor {subdivision} is not 1; flatten the certificate "
            "to an explicit graph first"
        )
        raise OutOfScopeError(msg)


def _multipliers(value: object) -> dict[str, Fraction]:
    mapping = _mapping(value, "the multipliers")
    parsed = {name: _fraction(v, f"multiplier {name!r}") for name, v in mapping.items()}
    return {name: v for name, v in parsed.items() if v != 0}


def _mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"{what} is not a JSON object"
        raise MalformedError(msg)
    return value


def _get(mapping: dict[str, object], key: str) -> object:
    if key not in mapping:
        msg = f"there is no {key!r} key"
        raise MalformedError(msg)
    return mapping[key]


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _fraction(value: object, what: str) -> Fraction:
    # Only strings and integers: a JSON float is already inexact.
    if not isinstance(value, str | int) or isinstance(value, bool):
        msg = f"{what} is not an exact rational written as a string"
        raise MalformedError(msg)
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        msg = f"{what} is not a rational: {value!r}"
        raise MalformedError(msg) from error
