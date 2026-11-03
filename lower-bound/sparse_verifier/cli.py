"""The command: the judge's contract over `verify`.

Invariant: exit 0 prints the exact bound as one line on standard output and
nothing else; exit 1 (rejected) and exit 2 (unreadable, malformed or out of
scope) print the failing check and reason on standard error. There are no
flags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sparse_verifier.verify import CERTIFICATE, verify

VERIFIED = 0
REJECTED = 1
REFUSED = 2


def main(argv: list[str] | None = None) -> int:
    """Verify one certificate file.

    Args:
        argv (list[str] | None): The certificate path, or None for `sys.argv`.

    Returns:
        int: The exit code.

    """
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        return _fail(REFUSED, "usage", "python -m sparse_verifier <certificate>")
    try:
        document = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return _fail(REFUSED, CERTIFICATE, f"cannot read the file: {error}")
    except ValueError as error:
        return _fail(REFUSED, CERTIFICATE, f"not valid JSON: {error}")
    verdict = verify(document)
    if verdict.accepted:
        sys.stdout.write(f"{verdict.bound}\n")
        return VERIFIED
    reason = verdict.reason
    if verdict.failures > 1:
        reason += f" ({verdict.failures} failures of this check in all)"
    return _fail(
        REFUSED if verdict.refused else REJECTED, verdict.failing or "", reason
    )


def _fail(code: int, check: str, reason: str) -> int:
    sys.stderr.write(f"{check}: {reason}\n")
    return code
