"""Ordinary complete-verification CLI; failures emit JSON and no bound."""

import json
import sys
from collections.abc import Sequence

from .exact import format_rational
from .failures import Failure, FailureKind
from .verification import Accepted, verify_directory


def _failure_exit(failure: Failure) -> int:
    try:
        print(
            json.dumps(failure.to_dict(), sort_keys=True), file=sys.stderr, flush=True
        )
    except Exception, KeyboardInterrupt:  # noqa: BLE001 -- Unwritable diagnostics cannot accept.
        return 2
    return (
        1
        if failure.kind in {FailureKind.INVALID_CERTIFICATE, FailureKind.COUNTEREXAMPLE}
        else 2
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Adapt complete verification; unsupported options are usage failures."""
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        if len(arguments) != 1 or arguments[0].startswith("-"):
            return _failure_exit(
                Failure(
                    FailureKind.REFUSED,
                    "usage",
                    "Usage: python -m upper_bound_verifier CERTIFICATE_DIRECTORY",
                )
            )
        result = verify_directory(arguments[0])
        if isinstance(result, Accepted):
            output = format_rational(result.certified_value) + "\n"
            if sys.stdout.write(output) != len(output):
                raise OSError("Incomplete bound output")
            sys.stdout.flush()
            return 0
        return _failure_exit(result)
    except MemoryError, RecursionError:
        return _failure_exit(
            Failure(
                FailureKind.INCOMPLETE, "resource_exhausted", "CLI resource failure"
            )
        )
    except KeyboardInterrupt:
        return _failure_exit(
            Failure(FailureKind.INCOMPLETE, "interrupted", "CLI was interrupted")
        )
    except Exception:  # noqa: BLE001 -- The process boundary must never accept errors.
        return _failure_exit(
            Failure(FailureKind.REFUSED, "internal_error", "Unexpected CLI failure")
        )


if __name__ == "__main__":
    sys.exit(main())
