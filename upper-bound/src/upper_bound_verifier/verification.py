"""Complete S16 directory verification, with no partial acceptance mode."""

from dataclasses import dataclass
from pathlib import Path

from flint import fmpq

from .approximation import check_checked_approximation_root
from .comparison import ComparisonStreams
from .failures import Failure, FailureKind, VerificationError
from .lottery import check_lottery_admissibility
from .reader import BundleReader
from .simplex import Verified
from .sp import check_checked_sp_root


@dataclass(frozen=True)
class Accepted:
    """Complete acceptance returned by verify_directory, never a cell result.

    Constructing this record yourself does not verify a certificate.
    """

    certified_value: fmpq


def verify_directory(directory: str | Path) -> Accepted | Failure:
    """Verify all five files, or return a structured failure without a bound.

    Global attribution is completely parsed and checked before any residual.
    Comparison roots are checked one at a time for that actual lottery.
    A genuine counterexample may return early; acceptance requires both real
    EOF checks, all required roots, and every SP and approximation residual.
    """
    try:
        reader = BundleReader(directory)
        manifest = reader.manifest
        lottery = check_lottery_admissibility(
            manifest.graph,
            manifest.agents,
            manifest.selectors,
            reader.attribution,
            reader.vertices,
        )
        streams = ComparisonStreams(lottery)
        for root in streams.iter_sp_roots(reader.iter_sp_roots()):
            result = check_checked_sp_root(lottery, root)
            if isinstance(result, Failure):
                return result
            if not isinstance(result, Verified):
                raise TypeError("Unexpected SP check result")
        for root in streams.iter_approximation_roots(reader.iter_approximation_roots()):
            result = check_checked_approximation_root(
                lottery, root, manifest.certified_value
            )
            if isinstance(result, Failure):
                return result
            if not isinstance(result, Verified):
                raise TypeError("Unexpected approximation check result")
        # Each iterator must run past its final yield: both the reader's
        # trailing-record check and the independent checked sequence must end.
        if not reader.streams_exhausted or not streams.streams_exhausted:
            return Failure(
                FailureKind.INCOMPLETE,
                "streams_incomplete",
                "Both reader and checked comparison streams must reach EOF",
            )
        return Accepted(manifest.certified_value)
    except VerificationError as error:
        return error.failure
    except MemoryError, RecursionError:
        return Failure(
            FailureKind.INCOMPLETE,
            "resource_exhausted",
            "Verification exhausted a required resource",
        )
    except KeyboardInterrupt:
        return Failure(
            FailureKind.INCOMPLETE,
            "interrupted",
            "Verification was interrupted",
        )
    except Exception:  # noqa: BLE001 -- S03 requires fail-closed internal refusal.
        return Failure(
            FailureKind.REFUSED,
            "internal_error",
            "Unexpected failure during verification",
        )
