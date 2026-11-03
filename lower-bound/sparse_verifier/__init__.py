"""The sparse verifier: an independent check of explicit graph certificates.

It establishes one thing: a certificate it accepts is a rational dual solution,
feasible for the unreduced anonymous program over the explicit graph the
certificate embeds, whose exact value is the claimed bound. It imports nothing
but the standard library and itself, so no builder can pass a bug into the
check. The model hash is tolerated and never read (ADR 0002).

The public seam is `verify`, from a certificate document to a `Verdict`; the
command is `python -m sparse_verifier <certificate>`.
"""

from sparse_verifier.verify import Verdict, verify

__all__ = ["Verdict", "verify"]
