"""Shared failure data; these records never represent acceptance."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class FailureKind(StrEnum):
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    INVALID_CERTIFICATE = "invalid_certificate"
    COUNTEREXAMPLE = "counterexample"


@dataclass(frozen=True)
class Failure:
    """A stable reason and optional JSON-compatible diagnostic context.

    Callers supply normalized witness strings and treat context as read-only.
    A counterexample may only be issued after the relevant admissibility checks.
    The record itself does not check a mathematical witness.
    """

    kind: FailureKind
    code: str
    message: str
    location: Mapping[str, object] | None = None
    witness: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the SCHEMA diagnostic shape, omitting unavailable context."""
        result: dict[str, object] = {
            "kind": self.kind.value,
            "code": self.code,
            "message": self.message,
        }
        if self.location is not None:
            result["location"] = dict(self.location)
        if self.witness is not None:
            result["witness"] = dict(self.witness)
        return result


class VerificationError(ValueError):
    """A rejected input with its structured failure available to API callers."""

    def __init__(self, failure: Failure) -> None:
        self.failure = failure
        super().__init__(f"{failure.code}: {failure.message}")
