"""The two ways a document can be refused before any check can judge it.

Invariant: a certificate that raises neither was readable and in scope. Both
errors mean a producer error, never an infeasible certificate, which is why
the command gives them their own exit code.
"""


class MalformedError(ValueError):
    """The document is not shaped like a certificate, or a graph in one."""


class OutOfScopeError(ValueError):
    """The certificate is well formed but this verifier does not take it."""
