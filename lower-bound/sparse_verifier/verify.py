"""The verification entry point: a certificate document in, a verdict out.

Invariant: an accepted `Verdict` carries the exact bound the certificate
establishes, and every other verdict names the check that stopped it. Checks
run in a fixed order, each with its own name: the document parses and is in
scope (`CERTIFICATE`, `SCOPE`, both refusals), the graph is valid (`GRAPH`),
then the dual checks of `sparse_verifier.dual`: every named row exists
(`ROWS`), signs (`SIGN`), columns (`COLUMN`), and the dual objective is the
claimed bound (`OBJECTIVE`). A verdict is refused when no check could judge the
document, and rejected when a check judged it and failed it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sparse_verifier.certificate import read_certificate
from sparse_verifier.dual import check_dual
from sparse_verifier.errors import MalformedError, OutOfScopeError
from sparse_verifier.graph import GraphInvalidError, read_graph

if TYPE_CHECKING:
    from fractions import Fraction

CERTIFICATE = "certificate"
SCOPE = "scope"
GRAPH = "graph"
ACCEPTED_REASON = "every check passes exactly"


@dataclass(frozen=True)
class Verdict:
    """What a verification concluded.

    Attributes:
        accepted (bool): Whether the certificate is verified.
        bound (Fraction | None): The exact bound, when accepted.
        failing (str | None): The check that stopped it, when not accepted.
        reason (str): Why.
        refused (bool): Whether the document could not be judged at all, as
            opposed to judged and failed.
        failures (int): How many failures the failing check found; the reason
            describes the first.

    """

    accepted: bool
    bound: Fraction | None
    failing: str | None
    reason: str
    refused: bool = False
    failures: int = 0


def verify(document: object) -> Verdict:
    """Check a decoded certificate document.

    Args:
        document (object): The decoded JSON of a certificate.

    Returns:
        Verdict: Accepted with the exact bound, or the failing check and reason.

    """
    try:
        certificate = read_certificate(document)
        graph = read_graph(certificate.graph)
    except MalformedError as error:
        return _refuse(CERTIFICATE, error)
    except OutOfScopeError as error:
        return _refuse(SCOPE, error)
    except GraphInvalidError as error:
        return _reject(GRAPH, str(error))

    failure = check_dual(
        graph, certificate.agents, certificate.multipliers, certificate.bound
    )
    if failure is not None:
        return _reject(failure.check, failure.reason, failure.count)
    return Verdict(
        accepted=True,
        bound=certificate.bound,
        failing=None,
        reason=ACCEPTED_REASON,
    )


def _refuse(check: str, reason: object) -> Verdict:
    return Verdict(
        accepted=False, bound=None, failing=check, reason=str(reason), refused=True
    )


def _reject(check: str, reason: str, failures: int = 1) -> Verdict:
    return Verdict(
        accepted=False, bound=None, failing=check, reason=reason, failures=failures
    )
